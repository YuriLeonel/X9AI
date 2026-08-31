/// Hard cap on a single recording before auto-stop (CLI-10).
pub const MAX_RECORD_SECONDS: u32 = 300;

pub const WAV_HEADER_SIZE: usize = 44;

fn sample_to_i16(sample: f32) -> i16 {
    let clamped = sample.clamp(-1.0, 1.0);
    (clamped * i16::MAX as f32) as i16
}

fn push_header(out: &mut Vec<u8>, sample_rate: u32, data_bytes: u32) {
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&(36 + data_bytes).to_le_bytes());
    out.extend_from_slice(b"WAVE");
    out.extend_from_slice(b"fmt ");
    out.extend_from_slice(&16u32.to_le_bytes()); // fmt chunk size
    out.extend_from_slice(&1u16.to_le_bytes()); // audio_format = PCM
    out.extend_from_slice(&1u16.to_le_bytes()); // channels = mono
    out.extend_from_slice(&sample_rate.to_le_bytes());
    out.extend_from_slice(&(sample_rate * 2).to_le_bytes()); // byte rate (16-bit mono)
    out.extend_from_slice(&2u16.to_le_bytes()); // block align
    out.extend_from_slice(&16u16.to_le_bytes()); // bits per sample
    out.extend_from_slice(b"data");
    out.extend_from_slice(&data_bytes.to_le_bytes());
}

/// Encodes mono f32 samples as a 16-bit PCM WAV (single interleaved channel).
pub fn pcm_to_wav16(mono: &[f32], sample_rate: u32) -> Vec<u8> {
    let data_bytes = (mono.len() * 2) as u32;
    let mut out = Vec::with_capacity(WAV_HEADER_SIZE + data_bytes as usize);
    push_header(&mut out, sample_rate, data_bytes);
    out.extend(mono.iter().flat_map(|&s| sample_to_i16(s).to_le_bytes()));
    out
}

/// Metadata sent with every `/process` request: PT-BR transcription,
/// client-side capture timestamp in epoch seconds.
pub fn metadata_json(timestamp: u64) -> String {
    format!(r#"{{"language":"pt","client_timestamp":{timestamp}}}"#)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wav_magic_and_fmt_chunk() {
        let wav = pcm_to_wav16(&[0.0; 8], 16_000);
        assert_eq!(&wav[0..4], b"RIFF");
        assert_eq!(&wav[8..12], b"WAVE");
        assert_eq!(&wav[12..16], b"fmt ");
    }

    #[test]
    fn wav_pcm16_mono_header_fields() {
        let wav = pcm_to_wav16(&[0.0; 8], 16_000);
        assert_eq!(u16::from_le_bytes([wav[20], wav[21]]), 1); // audio_format = PCM
        assert_eq!(u16::from_le_bytes([wav[22], wav[23]]), 1); // channels = mono
        assert_eq!(u32::from_le_bytes(wav[24..28].try_into().unwrap()), 16_000);
        assert_eq!(u16::from_le_bytes([wav[32], wav[33]]), 2); // block align = 2
        assert_eq!(u16::from_le_bytes([wav[34], wav[35]]), 16); // bits per sample
        assert_eq!(&wav[36..40], b"data");
    }

    #[test]
    fn wav_data_length_matches_sample_count() {
        let sample_rate = 16_000;
        let samples = 4_800_000usize; // 300 s at 16 kHz
        let wav = pcm_to_wav16(&[0.0; 4_800_000], sample_rate);
        assert_eq!(
            u32::from_le_bytes(wav[40..44].try_into().unwrap()) as usize,
            samples * 2
        );

        let wav = pcm_to_wav16(&[], sample_rate);
        assert_eq!(u32::from_le_bytes(wav[40..44].try_into().unwrap()), 0);
    }

    #[test]
    fn wav_data_bytes_are_le_i16_samples() {
        let wav = pcm_to_wav16(&[0.5, -0.5], 16_000);
        let samples = &wav[44..];
        assert_eq!(samples, &[0xFF, 0x3F, 0x01, 0xC0]); // 16383, -16383 little-endian
    }

    #[test]
    fn f32_out_of_range_clips_to_i16_limits() {
        let wav = pcm_to_wav16(&[2.0, -2.0], 8_000);
        assert_eq!(&wav[44..48], &[0xFF, 0x7F, 0x01, 0x80]);
    }

    #[test]
    fn empty_input_produces_valid_empty_wav() {
        let wav = pcm_to_wav16(&[], 16_000);
        assert_eq!(wav.len(), WAV_HEADER_SIZE);
        assert_eq!(u32::from_le_bytes(wav[40..44].try_into().unwrap()), 0);
    }

    #[test]
    fn metadata_json_pt_language_and_timestamp() {
        assert_eq!(
            metadata_json(1_752_480_000),
            r#"{"language":"pt","client_timestamp":1752480000}"#
        );
    }

    #[test]
    fn metadata_json_zero_timestamp() {
        assert_eq!(
            metadata_json(0),
            r#"{"language":"pt","client_timestamp":0}"#
        );
    }

    #[test]
    fn max_record_seconds_is_300() {
        assert_eq!(MAX_RECORD_SECONDS, 300);
    }
}
