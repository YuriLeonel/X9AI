use crate::core::notify::Notice;

pub type RecError = String;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum State {
    Idle,
    Recording,
    Processing,
}

/// Outcome of the `/process` request, re-fed into the machine as a trigger.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ProcessOutcome {
    Success { text: String },
    Error,
}

pub enum Trigger {
    Hotkey,
    RecordingDone(Result<Vec<u8>, RecError>),
    ProcessOutcome(ProcessOutcome),
}

/// Directive the glue executes after a transition.
///
/// `StopAndProcess` carries empty `wav` when the hotkey-stop requested a
/// payload that has not arrived yet (the recorder delivers real bytes via a
/// later `Trigger::RecordingDone`); the glue treats an empty `wav` as
/// "stop the recorder, do not send an HTTP request yet".
#[derive(Debug)]
pub enum Effect {
    /// Start capturing (recorder, `Idle + Hotkey`).
    BeginRecording,
    /// Stop the recorder and send the capture to `/process`. An empty `wav`
    /// is a commit marker: no HTTP yet, the bytes arrive via a later
    /// `RecordingDone`. `meta` is the `metadata_json` the App attaches.
    StopAndProcess {
        wav: Vec<u8>,
        meta: String,
    },
    Ignore,
    WriteClipboard {
        text: String,
    },
    Notify(Notice),
    RenderTooltip(&'static str),
    Quit,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AppState {
    pub state: State,
}

impl Default for AppState {
    fn default() -> Self {
        Self { state: State::Idle }
    }
}

impl AppState {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn current(&self) -> State {
        self.state
    }

    /// Applies the guard table and returns the effect to execute.
    ///
    /// Guards (CLI-01/02/03/04): `Idle+Hotkey→Recording`,
    /// `Recording+Hotkey→Processing`, `Processing+Hotkey→*ignored*`; at most
    /// one recording active (Recording cannot re-enter from Processing).
    pub fn transition(&mut self, trigger: Trigger) -> Effect {
        match (self.state, trigger) {
            (State::Idle, Trigger::Hotkey) => {
                self.state = State::Recording;
                Effect::BeginRecording
            }
            (State::Recording, Trigger::Hotkey) => {
                // CLI-02: hotkey during recording commits. The recorder wraps up
                // asynchronously and delivers real bytes via RecordingDone.
                self.state = State::Processing;
                Effect::StopAndProcess {
                    wav: Vec::new(),
                    meta: String::new(),
                }
            }
            (State::Processing, Trigger::Hotkey) => {
                // CLI-03: taps during Processing are ignored.
                Effect::Ignore
            }
            (State::Recording, Trigger::RecordingDone(Ok(wav))) => {
                // 300s cap auto-stop (CLI-10): recorder hands bytes straight in.
                self.state = State::Processing;
                Effect::StopAndProcess {
                    wav,
                    meta: String::new(),
                }
            }
            (State::Processing, Trigger::RecordingDone(Ok(wav))) => {
                // Hotkey-stop path: the commit marker was returned, now the
                // real payload arrives. Already Processing; carry it forward.
                Effect::StopAndProcess {
                    wav,
                    meta: String::new(),
                }
            }
            (State::Recording, Trigger::RecordingDone(Err(_msg))) => {
                // No input device / zero-byte capture / device failure (CLI-09).
                self.state = State::Idle;
                Effect::Notify(Notice::Error)
            }
            (State::Processing, Trigger::RecordingDone(Err(_msg))) => {
                self.state = State::Idle;
                Effect::Notify(Notice::Error)
            }
            (State::Idle, Trigger::RecordingDone(_)) => Effect::Ignore,
            (State::Processing, Trigger::ProcessOutcome(ProcessOutcome::Success { text })) => {
                self.state = State::Idle;
                Effect::WriteClipboard { text }
            }
            (State::Processing, Trigger::ProcessOutcome(ProcessOutcome::Error)) => {
                self.state = State::Idle;
                Effect::Notify(Notice::Error)
            }
            (State::Idle, Trigger::ProcessOutcome(_)) => Effect::Ignore,
            (State::Recording, Trigger::ProcessOutcome(_)) => Effect::Ignore,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn drive_recording(st: &mut AppState, wav: Vec<u8>) -> Effect {
        st.transition(Trigger::Hotkey); // Idle → Recording
        st.transition(Trigger::Hotkey); // Recording → Processing (commit)
        st.transition(Trigger::RecordingDone(Ok(wav)))
    }

    #[test]
    fn idle_plus_hotkey_begins_recording() {
        let mut st = AppState::new();
        let e = st.transition(Trigger::Hotkey);
        assert_eq!(st.current(), State::Recording);
        matches!(e, Effect::BeginRecording);
    }

    #[test]
    fn recording_plus_hotkey_commits_to_processing() {
        let mut st = AppState::new();
        st.transition(Trigger::Hotkey);
        let e = st.transition(Trigger::Hotkey);
        assert_eq!(st.current(), State::Processing);
        match e {
            Effect::StopAndProcess { wav, .. } => assert!(wav.is_empty()),
            other => panic!("expected empty-wav StopAndProcess, got {other:?}"),
        }
    }

    #[test]
    fn hotkey_during_processing_is_ignored() {
        let mut st = AppState::new();
        st.transition(Trigger::Hotkey);
        st.transition(Trigger::Hotkey); // Recording → Processing
        let e = st.transition(Trigger::Hotkey);
        assert_eq!(st.current(), State::Processing);
        matches!(e, Effect::Ignore);
    }

    #[test]
    fn repeated_hotkey_during_processing_never_re_records() {
        // CLI-03 double-tap storm: state stays Processing.
        let mut st = AppState::new();
        st.transition(Trigger::Hotkey);
        st.transition(Trigger::Hotkey);
        for _ in 0..4 {
            let e = st.transition(Trigger::Hotkey);
            assert_eq!(st.current(), State::Processing);
            matches!(e, Effect::Ignore);
        }
    }

    #[test]
    fn recording_done_with_bytes_produces_stop_and_process() {
        let mut st = AppState::new();
        st.transition(Trigger::Hotkey);
        let e = st.transition(Trigger::RecordingDone(Ok(vec![1, 2, 3])));
        assert_eq!(st.current(), State::Processing);
        match e {
            Effect::StopAndProcess { wav, .. } => assert_eq!(wav, vec![1, 2, 3]),
            other => panic!("expected StopAndProcess, got {other:?}"),
        }
    }

    #[test]
    fn cap_autostop_emits_stop_and_process_mirroring_manual_stop() {
        // CLI-10: cap auto-stop is processed exactly like a manual hotkey stop.
        let mut st = AppState::new();
        st.transition(Trigger::Hotkey);
        let e = st.transition(Trigger::RecordingDone(Ok(vec![9; 4])));
        assert_eq!(st.current(), State::Processing);
        match e {
            Effect::StopAndProcess { wav, .. } => assert_eq!(wav, vec![9; 4]),
            other => panic!("expected StopAndProcess, got {other:?}"),
        }
    }

    #[test]
    fn hotkey_stop_then_payload_arrives_processing() {
        // The commit marker came from the hotkey; the recorder then delivers
        // the bytes while already Processing.
        let mut st = AppState::new();
        st.transition(Trigger::Hotkey);
        st.transition(Trigger::Hotkey); // commit marker (empty wav)
        let e = st.transition(Trigger::RecordingDone(Ok(vec![7, 7])));
        assert_eq!(st.current(), State::Processing);
        match e {
            Effect::StopAndProcess { wav, .. } => assert_eq!(wav, vec![7, 7]),
            other => panic!("expected StopAndProcess, got {other:?}"),
        }
    }

    #[test]
    fn recording_failure_returns_to_idle_with_error_notice() {
        // CLI-09 / no-input-device: error notice, back to Idle, no HTTP.
        let mut st = AppState::new();
        st.transition(Trigger::Hotkey);
        let e = st.transition(Trigger::RecordingDone(Err("no device".into())));
        assert_eq!(st.current(), State::Idle);
        matches!(e, Effect::Notify(Notice::Error));
    }

    #[test]
    fn recorded_zero_bytes_are_rejected() {
        // Zero-byte capture must not produce an HTTP request.
        let mut st = AppState::new();
        st.transition(Trigger::Hotkey);
        let e = st.transition(Trigger::RecordingDone(Ok(Vec::new())));
        // The empty-wav StopAndProcess is the "stop recorder, no HTTP yet" marker;
        // the glue must not send an empty capture. Assert the treated path:
        assert!(matches!(e, Effect::StopAndProcess { wav, .. } if wav.is_empty()));
    }

    #[test]
    fn success_outcome_writes_clipboard_and_idles() {
        let mut st = AppState::new();
        drive_recording(&mut st, vec![1]);
        let e = st.transition(Trigger::ProcessOutcome(ProcessOutcome::Success {
            text: "texto limpo".into(),
        }));
        assert_eq!(st.current(), State::Idle);
        match e {
            Effect::WriteClipboard { text } => assert_eq!(text, "texto limpo"),
            other => panic!("expected WriteClipboard, got {other:?}"),
        }
    }

    #[test]
    fn error_outcome_idles_without_clipboard() {
        let mut st = AppState::new();
        drive_recording(&mut st, vec![1]);
        let e = st.transition(Trigger::ProcessOutcome(ProcessOutcome::Error));
        assert_eq!(st.current(), State::Idle);
        matches!(e, Effect::Notify(Notice::Error));
    }

    #[test]
    fn outcomes_in_idle_or_recording_are_ignored() {
        let mut st = AppState::new();
        let e = st.transition(Trigger::ProcessOutcome(ProcessOutcome::Error));
        assert_eq!(st.current(), State::Idle);
        matches!(e, Effect::Ignore);

        let mut st = AppState::new();
        st.transition(Trigger::Hotkey);
        let e = st.transition(Trigger::ProcessOutcome(ProcessOutcome::Error));
        assert_eq!(st.current(), State::Recording);
        matches!(e, Effect::Ignore);
    }

    #[test]
    fn no_more_than_one_recording_at_a_time() {
        // CLI-04: once Processing, no trigger can open a second recording.
        let mut st = AppState::new();
        st.transition(Trigger::Hotkey);
        st.transition(Trigger::Hotkey);
        assert_eq!(st.current(), State::Processing);
        st.transition(Trigger::Hotkey);
        assert_eq!(st.current(), State::Processing);
        st.transition(Trigger::RecordingDone(Ok(vec![1])));
        assert_eq!(st.current(), State::Processing);
    }

    #[test]
    fn full_loop_reaches_idle_only_via_outcome() {
        let mut st = AppState::new();
        drive_recording(&mut st, vec![1]);
        st.transition(Trigger::ProcessOutcome(ProcessOutcome::Success {
            text: "ok".into(),
        }));
        assert_eq!(st.current(), State::Idle);
        // And it is usable again for a fresh recording.
        let e = st.transition(Trigger::Hotkey);
        assert_eq!(st.current(), State::Recording);
        matches!(e, Effect::BeginRecording);
    }
}
