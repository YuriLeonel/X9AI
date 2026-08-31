/// Number of clipboard write attempts before giving up (CLI-15).
pub const CLIPBOARD_ATTEMPTS: usize = 3;
/// Delay between clipboard attempts in milliseconds (CLI-15).
pub const CLIPBOARD_DELAY_MS: u64 = 50;

pub type ClipError = String;

/// Abstraction over the OS clipboard so the retry policy is testable.
pub trait ClipboardSink {
    fn set(&mut self, text: &str) -> Result<(), ClipError>;
}

/// Abstraction over thread sleeping so retry delays are testable without
/// actually waiting.
pub trait Sleeper {
    fn sleep(&self, ms: u64);
}

/// Writes `text`, retrying up to `attempts` times with `delay_ms` between
/// attempts. Returns the last error only when every attempt fails (CLI-16).
pub fn write_with_retry(
    sink: &mut dyn ClipboardSink,
    text: &str,
    sleeper: &dyn Sleeper,
    attempts: usize,
    delay_ms: u64,
) -> Result<(), ClipError> {
    let mut last_error: Option<ClipError> = None;
    for attempt in 0..attempts {
        match sink.set(text) {
            Ok(()) => return Ok(()),
            Err(e) => {
                last_error = Some(e);
                if attempt + 1 < attempts {
                    sleeper.sleep(delay_ms);
                }
            }
        }
    }
    Err(last_error.unwrap_or_else(|| "clipboard write failed".to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Debug, Default)]
    struct FailingSink {
        calls: std::cell::RefCell<usize>,
        fail_until: usize,
    }

    impl FailingSink {
        fn failing_times(n: usize) -> Self {
            Self {
                fail_until: n,
                ..Self::default()
            }
        }

        fn always_fail() -> Self {
            Self {
                fail_until: usize::MAX,
                ..Self::default()
            }
        }
    }

    impl ClipboardSink for FailingSink {
        fn set(&mut self, text: &str) -> Result<(), ClipError> {
            *self.calls.borrow_mut() += 1;
            let calls = *self.calls.borrow();
            if calls <= self.fail_until {
                Err(format!("sink failure #{calls}"))
            } else {
                let _ = text.len();
                Ok(())
            }
        }
    }

    #[derive(Debug, Default)]
    struct RecordingSleeper {
        calls: std::cell::RefCell<Vec<u64>>,
    }

    impl Sleeper for RecordingSleeper {
        fn sleep(&self, ms: u64) {
            self.calls.borrow_mut().push(ms);
        }
    }

    fn attempts_of(sink: &FailingSink) -> usize {
        *sink.calls.borrow()
    }

    #[test]
    fn success_on_first_attempt_stops_retrying() {
        let mut sink = FailingSink::default(); // never fails
        let sleeper = RecordingSleeper::default();
        let result = write_with_retry(&mut sink, "texto", &sleeper, 3, 50);
        assert!(result.is_ok());
        assert_eq!(attempts_of(&sink), 1);
        assert!(sleeper.calls.borrow().is_empty());
    }

    #[test]
    fn success_on_second_attempt() {
        let mut sink = FailingSink::failing_times(1);
        let sleeper = RecordingSleeper::default();
        let result = write_with_retry(&mut sink, "texto", &sleeper, 3, 50);
        assert!(result.is_ok());
        assert_eq!(attempts_of(&sink), 2);
        assert_eq!(*sleeper.calls.borrow(), vec![50]);
    }

    #[test]
    fn success_on_third_attempt() {
        let mut sink = FailingSink::failing_times(2);
        let sleeper = RecordingSleeper::default();
        let result = write_with_retry(&mut sink, "texto", &sleeper, 3, 50);
        assert!(result.is_ok());
        assert_eq!(attempts_of(&sink), 3);
        assert_eq!(*sleeper.calls.borrow(), vec![50, 50]);
    }

    #[test]
    fn all_attempts_fail_returns_error() {
        let mut sink = FailingSink::always_fail();
        let sleeper = RecordingSleeper::default();
        let result = write_with_retry(&mut sink, "texto", &sleeper, 3, 50);
        assert!(result.is_err());
        assert_eq!(attempts_of(&sink), 3);
        assert_eq!(*sleeper.calls.borrow(), vec![50, 50]);
    }

    #[test]
    fn sleeps_happen_only_between_attempts() {
        let mut sink = FailingSink::failing_times(2);
        let sleeper = RecordingSleeper::default();
        write_with_retry(&mut sink, "texto", &sleeper, 3, 50).unwrap();
        assert_eq!(sleeper.calls.borrow().len(), 2);
        assert!(sleeper.calls.borrow().iter().all(|&d| d == 50));
    }

    #[test]
    fn defaults_are_3_attempts_and_50ms() {
        assert_eq!(CLIPBOARD_ATTEMPTS, 3);
        assert_eq!(CLIPBOARD_DELAY_MS, 50);
    }

    #[test]
    fn written_text_reaches_sink_exactly() {
        let mut recorded_texts = Vec::new();
        let mut sink = WriteCaptureSink::new(&mut recorded_texts);
        write_with_retry(
            &mut sink,
            "texto limpo",
            &RecordingSleeper::default(),
            3,
            50,
        )
        .unwrap();
        assert_eq!(recorded_texts, vec!["texto limpo"]);
    }

    struct WriteCaptureSink<'a> {
        texts: &'a mut Vec<String>,
    }

    impl<'a> WriteCaptureSink<'a> {
        fn new(texts: &'a mut Vec<String>) -> Self {
            Self { texts }
        }
    }

    impl ClipboardSink for WriteCaptureSink<'_> {
        fn set(&mut self, text: &str) -> Result<(), ClipError> {
            self.texts.push(text.to_string());
            Ok(())
        }
    }
}
