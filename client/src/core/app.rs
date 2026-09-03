use std::time::{SystemTime, UNIX_EPOCH};

pub use crate::core::notify::Notice;
pub use crate::core::state::{Effect, ProcessOutcome, RecError, State};

use crate::core::audio::metadata_json;
use crate::core::state::{AppState, Trigger};

/// Tray tooltip per state (CLI-06/07).
pub const TOOLTIP_IDLE: &str = "X9AI";
pub const TOOLTIP_RECORDING: &str = "Recording…";
pub const TOOLTIP_PROCESSING: &str = "Processing…";

pub fn ui_tooltip(state: &State) -> &'static str {
    match state {
        State::Idle => TOOLTIP_IDLE,
        State::Recording => TOOLTIP_RECORDING,
        State::Processing => TOOLTIP_PROCESSING,
    }
}

fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// Drives the state machine and decorates machine effects with the capture
/// metadata. The glue feeds UiEvents here and executes the returned `Effect`.
pub struct App {
    machine: AppState,
    start_timestamp: u64,
}

impl Default for App {
    fn default() -> Self {
        Self::new()
    }
}

impl App {
    pub fn new() -> Self {
        Self {
            machine: AppState::new(),
            start_timestamp: 0,
        }
    }

    pub fn current(&self) -> State {
        self.machine.current()
    }

    /// Tooltip directive the glue applies after any state change.
    pub fn render(&self) -> Effect {
        Effect::RenderTooltip(ui_tooltip(&self.machine.current()))
    }

    /// The `Ctrl+Alt+Space` global hotkey fired.
    pub fn on_hotkey(&mut self) -> Effect {
        let effect = self.machine.transition(Trigger::Hotkey);
        self.decorate(effect)
    }

    /// The recorder finished: `Ok(wav)` = capture finalized, `Err` = device or
    /// zero-byte failure (CLI-09).
    pub fn on_recording_ready(&mut self, result: Result<Vec<u8>, RecError>) -> Effect {
        let trigger = match result {
            // CLI-09: zero bytes captured means failure — no HTTP request.
            Ok(wav) if wav.is_empty() => Trigger::RecordingDone(Err("zero-byte capture".into())),
            other => Trigger::RecordingDone(other),
        };
        let effect = self.machine.transition(trigger);
        self.decorate(effect)
    }

    /// The `/process` request finished.
    pub fn on_process_outcome(&mut self, outcome: ProcessOutcome) -> Effect {
        self.machine.transition(Trigger::ProcessOutcome(outcome))
    }

    /// Fills `StopAndProcess` with the metadata captured at record start.
    fn decorate(&mut self, effect: Effect) -> Effect {
        match effect {
            Effect::BeginRecording => {
                self.start_timestamp = current_timestamp();
                Effect::BeginRecording
            }
            Effect::StopAndProcess { wav, .. } => {
                let meta = metadata_json(self.start_timestamp);
                Effect::StopAndProcess { wav, meta }
            }
            other => other,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn drive_request(app: &mut App, wav: Vec<u8>) -> Effect {
        assert!(matches!(app.on_hotkey(), Effect::BeginRecording));
        assert!(matches!(app.on_hotkey(), Effect::StopAndProcess { .. }));
        app.on_recording_ready(Ok(wav))
    }

    #[test]
    fn ui_tooltip_idle() {
        assert_eq!(ui_tooltip(&State::Idle), "X9AI");
    }

    #[test]
    fn ui_tooltip_recording() {
        assert_eq!(ui_tooltip(&State::Recording), "Recording…");
    }

    #[test]
    fn ui_tooltip_processing() {
        assert_eq!(ui_tooltip(&State::Processing), "Processing…");
    }

    #[test]
    fn hotkey_in_idle_begins_recording() {
        let mut app = App::new();
        assert!(matches!(app.on_hotkey(), Effect::BeginRecording));
        assert_eq!(app.current(), State::Recording);
    }

    #[test]
    fn hotkey_in_recording_emits_stop_marker() {
        let mut app = App::new();
        app.on_hotkey();
        let effect = app.on_hotkey();
        match effect {
            Effect::StopAndProcess { wav, meta } => {
                assert!(wav.is_empty(), "commit marker must not carry http payload");
                let meta: serde_json::Value = serde_json::from_str(&meta).unwrap();
                assert_eq!(meta["language"], "pt");
                assert!(meta["client_timestamp"].is_u64());
            }
            other => panic!("expected StopAndProcess marker, got {other:?}"),
        }
        assert_eq!(app.current(), State::Processing);
    }

    #[test]
    fn hotkey_in_processing_is_ignored() {
        let mut app = App::new();
        drive_request(&mut app, vec![1, 2]);
        assert_eq!(app.current(), State::Processing);
        assert!(matches!(app.on_hotkey(), Effect::Ignore));
    }

    #[test]
    fn double_hotkey_never_opens_second_recording() {
        let mut app = App::new();
        app.on_hotkey();
        app.on_hotkey();
        assert_eq!(app.current(), State::Processing);
        app.on_hotkey();
        assert_eq!(app.current(), State::Processing);
    }

    #[test]
    fn zero_byte_capture_notifies_without_http() {
        let mut app = App::new();
        app.on_hotkey();
        app.on_hotkey();
        let effect = app.on_recording_ready(Ok(Vec::new()));
        assert!(
            matches!(effect, Effect::Notify(Notice::Error)),
            "zero bytes must produce an error notice, got {effect:?}"
        );
        assert_eq!(app.current(), State::Idle);
    }

    #[test]
    fn healthy_capture_produces_request_with_metadata() {
        let mut app = App::new();
        let wav = vec![1, 2, 3];
        let effect = drive_request(&mut app, wav.clone());
        match effect {
            Effect::StopAndProcess { wav: got, meta } => {
                assert_eq!(got, wav);
                let meta: serde_json::Value = serde_json::from_str(&meta).unwrap();
                assert_eq!(meta["language"], "pt");
                assert!(meta["client_timestamp"].is_u64());
            }
            other => panic!("expected StopAndProcess, got {other:?}"),
        }
    }

    #[test]
    fn recorder_error_notifies() {
        let mut app = App::new();
        app.on_hotkey();
        let effect = app.on_recording_ready(Err("no input device".into()));
        assert!(matches!(effect, Effect::Notify(Notice::Error)));
        assert_eq!(app.current(), State::Idle);
    }

    #[test]
    fn success_writes_clipboard() {
        let mut app = App::new();
        drive_request(&mut app, vec![1]);
        let effect = app.on_process_outcome(ProcessOutcome::Success {
            text: "texto limpo".into(),
        });
        match effect {
            Effect::WriteClipboard { text } => assert_eq!(text, "texto limpo"),
            other => panic!("expected WriteClipboard, got {other:?}"),
        }
        assert_eq!(app.current(), State::Idle);
    }

    #[test]
    fn success_resets_tooltip_to_idle() {
        let mut app = App::new();
        drive_request(&mut app, vec![1]);
        app.on_process_outcome(ProcessOutcome::Success { text: "ok".into() });
        assert!(matches!(app.render(), Effect::RenderTooltip("X9AI")));
    }

    #[test]
    fn failure_never_writes_clipboard() {
        let mut app = App::new();
        drive_request(&mut app, vec![1]);
        let effect = app.on_process_outcome(ProcessOutcome::Error);
        assert!(matches!(effect, Effect::Notify(Notice::Error)));
        assert_eq!(app.current(), State::Idle);
        assert!(matches!(app.render(), Effect::RenderTooltip("X9AI")));
    }

    #[test]
    fn tooltip_tracks_each_state() {
        let mut app = App::new();
        assert!(matches!(app.render(), Effect::RenderTooltip("X9AI")));
        app.on_hotkey();
        assert!(matches!(app.render(), Effect::RenderTooltip("Recording…")));
        app.on_hotkey();
        assert!(matches!(app.render(), Effect::RenderTooltip("Processing…")));
    }
}
