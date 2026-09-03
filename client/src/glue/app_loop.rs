use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc, Arc};
use std::time::Duration;

use crate::core::app::{App, Effect, ProcessOutcome, State, TOOLTIP_RECORDING};
use crate::core::http::{endpoint_from_env, Processor, ReqwestProcessor};
use crate::core::notify::{notice_text, Notice};
use crate::core::retry::{write_with_retry, Sleeper, CLIPBOARD_ATTEMPTS, CLIPBOARD_DELAY_MS};
use crate::core::runner::spawn_processing;

use super::hotkey::{self, HotkeyManager};
use super::recorder;
use super::tray;
use super::win_loop::MessageWindow;
use super::{clipboard, EventSender, UiEvent};

struct StdSleeper;

impl Sleeper for StdSleeper {
    fn sleep(&self, ms: u64) {
        std::thread::sleep(Duration::from_millis(ms));
    }
}

/// Main-thread loop: owns the message pump, the tray, the hotkey registration,
/// the recorder thread, the clipboard, and the `reqwest` processor.
pub fn run() -> Result<(), String> {
    let (tx, rx) = mpsc::channel::<UiEvent>();

    let window = MessageWindow::new()?;
    let sender = EventSender::new(tx.clone(), window.hwnd());
    let endpoint = endpoint_from_env(std::env::var("X9AI_SERVER_URL").ok().as_deref());
    let processor = ReqwestProcessor::new(endpoint).map_err(|e| e.to_string())?;

    let tray = tray::Tray::build(sender.clone())?;
    hotkey::install_handler(sender.clone());
    let hotkeys = HotkeyManager::new()?;
    hotkeys.register()?;
    let _hotkeys = hotkeys; // keep the manager (and its message window) alive

    let hwnd = window.hwnd();
    let mut app = App::new();
    let mut stop: Option<Arc<AtomicBool>> = None;
    let mut clipboard = clipboard::ArboardClipboard::new()?;
    let sleeper = StdSleeper;

    window.pump(&rx, move |event| {
        let effect = match event {
            UiEvent::Quit => return,
            UiEvent::Hotkey => app.on_hotkey(),
            UiEvent::MenuStopRecording => {
                if matches!(app.current(), State::Recording) {
                    app.on_hotkey()
                } else {
                    Effect::Ignore
                }
            }
            UiEvent::RecordingDone(result) => app.on_recording_ready(result),
            UiEvent::ProcessOutcome(outcome) => app.on_process_outcome(outcome),
        };

        match effect {
            Effect::BeginRecording => {
                let flag = Arc::new(AtomicBool::new(false));
                stop = Some(flag.clone());
                let _ = recorder::spawn_record_thread(flag, sender.clone());
            }
            Effect::StopAndProcess { wav, meta } => {
                if wav.is_empty() {
                    // Commit marker: ask the running recorder to wrap up.
                    if let Some(flag) = &stop {
                        flag.store(true, Ordering::SeqCst);
                    }
                } else {
                    let worker_sender = sender.clone();
                    let worker_processor = processor.clone();
                    let _ = spawn_processing(move || {
                        let outcome = match worker_processor.process(wav, &meta) {
                            Ok(text) => ProcessOutcome::Success { text },
                            Err(_) => ProcessOutcome::Error,
                        };
                        worker_sender.send(UiEvent::ProcessOutcome(outcome));
                    });
                }
            }
            Effect::WriteClipboard { text } => {
                let verdict = match write_with_retry(
                    &mut clipboard,
                    &text,
                    &sleeper,
                    CLIPBOARD_ATTEMPTS,
                    CLIPBOARD_DELAY_MS,
                ) {
                    Ok(()) => Notice::Success,
                    Err(_) => Notice::Error,
                };
                tray::show_balloon(hwnd, notice_text(verdict));
            }
            Effect::Notify(notice) => {
                tray::show_balloon(hwnd, notice_text(notice));
            }
            Effect::RenderTooltip(_) | Effect::Ignore => {}
            Effect::Quit => sender.send(UiEvent::Quit),
        }

        if let Effect::RenderTooltip(label) = app.render() {
            let _ = tray.set_tooltip(label);
            tray.set_recording(label == TOOLTIP_RECORDING);
        }
    })
}
