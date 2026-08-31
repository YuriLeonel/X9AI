use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::Duration;

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};

use crate::core::audio::MAX_RECORD_SECONDS;

use super::{EventSender, UiEvent};

const TARGET_RATE: u32 = 16_000;

/// Captures from the default input device until `stop` is raised or the
/// 300s cap is hit, returning mono f32 samples and the capture sample rate
/// (needed to write the true-rate WAV header). Zero bytes → `Err` (CLI-09).
pub fn record_until_stop(stop: Arc<AtomicBool>) -> Result<(Vec<f32>, u32), String> {
    let host = cpal::default_host();
    let device = host
        .default_input_device()
        .ok_or_else(|| "no default input device".to_string())?;

    let samples: Arc<Mutex<Vec<f32>>> = Arc::new(Mutex::new(Vec::new()));
    let fail: Arc<Mutex<Option<String>>> = Arc::new(Mutex::new(None));

    // Prefer 16 kHz mono; fall back to the device default (true-rate header).
    let primary = cpal::StreamConfig {
        channels: 1,
        sample_rate: cpal::SampleRate(TARGET_RATE),
        buffer_size: cpal::BufferSize::Default,
    };

    let result = device.build_input_stream_raw(
        &primary,
        cpal::SampleFormat::F32,
        data_callback(samples.clone(), stop.clone()),
        error_callback(fail.clone()),
        None,
    );
    let (stream, cap, rate) = match result {
        Ok(stream) => {
            let cap = TARGET_RATE as usize * MAX_RECORD_SECONDS as usize;
            (stream, cap, TARGET_RATE)
        }
        Err(_primary_err) => {
            let default = device
                .default_input_config()
                .map_err(|e| format!("no default input config: {e}"))?;
            let config = default.config();
            let rate = default.sample_rate().0;
            let cap = rate as usize * MAX_RECORD_SECONDS as usize;
            let stream = device
                .build_input_stream_raw(
                    &config,
                    default.sample_format(),
                    data_callback(samples.clone(), stop.clone()),
                    error_callback(fail.clone()),
                    None,
                )
                .map_err(|e| format!("failed to build input stream: {e}"))?;
            (stream, cap, rate)
        }
    };

    stream
        .play()
        .map_err(|e| format!("failed to start capture: {e}"))?;

    loop {
        if stop.load(Ordering::SeqCst) || samples.lock().unwrap().len() >= cap {
            break;
        }
        if let Some(message) = fail.lock().unwrap().clone() {
            return Err(message);
        }
        std::thread::sleep(Duration::from_millis(50));
    }

    drop(stream);
    let capture = std::mem::take(&mut *samples.lock().unwrap());
    if capture.is_empty() {
        return Err("zero-byte capture".to_string());
    }
    Ok((capture, rate))
}

/// Runs the capture on its own thread and reports back via the event channel.
pub fn spawn_record_thread(stop: Arc<AtomicBool>, sender: EventSender) -> JoinHandle<()> {
    std::thread::spawn(move || {
        let result = record_until_stop(stop)
            .map(|(samples, rate)| crate::core::audio::pcm_to_wav16(&samples, rate));
        sender.send(UiEvent::RecordingDone(result));
    })
}

fn data_callback(
    samples: Arc<Mutex<Vec<f32>>>,
    stop: Arc<AtomicBool>,
) -> impl FnMut(&cpal::Data, &cpal::InputCallbackInfo) {
    move |data: &cpal::Data, _info: &cpal::InputCallbackInfo| {
        if stop.load(Ordering::SeqCst) {
            return;
        }
        let mut buf = samples.lock().unwrap();
        match data.sample_format() {
            cpal::SampleFormat::F32 => buf.extend(data.as_slice::<f32>().unwrap().iter().copied()),
            cpal::SampleFormat::I16 => buf.extend(
                data.as_slice::<i16>()
                    .unwrap()
                    .iter()
                    .map(|&s| s as f32 / 32768.0),
            ),
            cpal::SampleFormat::U16 => buf.extend(
                data.as_slice::<u16>()
                    .unwrap()
                    .iter()
                    .map(|&s| (s as f32 / 32768.0) - 1.0),
            ),
            cpal::SampleFormat::F64 => {
                buf.extend(data.as_slice::<f64>().unwrap().iter().map(|&s| s as f32))
            }
            _ => {} // unsupported native format: skip those buffers
        }
    }
}

fn error_callback(fail: Arc<Mutex<Option<String>>>) -> impl FnMut(cpal::StreamError) {
    move |e: cpal::StreamError| {
        let mut slot = fail.lock().unwrap();
        if slot.is_none() {
            *slot = Some(e.to_string());
        }
    }
}
