/// Final user notice classification (Success/Error balloon).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Notice {
    Success,
    Error,
}

pub const TITLE: &str = "X9AI";
pub const SUCCESS_TEXT: &str = "Pronto para colar!";
pub const ERROR_TEXT: &str = "Falha no processamento. Verifique a conexão com o servidor.";

/// PT-BR message body for a notice (CLI-17/18).
pub fn notice_text(n: Notice) -> &'static str {
    match n {
        Notice::Success => SUCCESS_TEXT,
        Notice::Error => ERROR_TEXT,
    }
}

/// Abstraction over the OS notification (balloon) so the core can show
/// notices without touching Windows APIs.
pub trait Notifier {
    fn show(&self, title: &str, body: &str);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Debug, Default)]
    struct RecordingNotifier {
        calls: std::cell::RefCell<Vec<(String, String)>>,
    }

    impl Notifier for RecordingNotifier {
        fn show(&self, title: &str, body: &str) {
            self.calls
                .borrow_mut()
                .push((title.to_string(), body.to_string()));
        }
    }

    #[test]
    fn success_notice_text_is_exact() {
        assert_eq!(notice_text(Notice::Success), "Pronto para colar!");
    }

    #[test]
    fn error_notice_text_is_exact() {
        assert_eq!(
            notice_text(Notice::Error),
            "Falha no processamento. Verifique a conexão com o servidor."
        );
    }

    #[test]
    fn notice_text_returns_static() {
        let s: &'static str = notice_text(Notice::Success);
        assert_eq!(s, SUCCESS_TEXT);
        let e: &'static str = notice_text(Notice::Error);
        assert_eq!(e, ERROR_TEXT);
    }

    #[test]
    fn notifier_fired_with_title_and_body() {
        let n = RecordingNotifier::default();
        n.show(TITLE, notice_text(Notice::Error));
        let calls = n.calls.borrow();
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0], ("X9AI".to_string(), ERROR_TEXT.to_string()));
    }
}
