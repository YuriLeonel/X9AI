use crate::core::retry::{ClipError, ClipboardSink};

/// Real clipboard sink backed by `arboard`; driven by the core retry policy.
pub struct ArboardClipboard {
    clipboard: arboard::Clipboard,
}

impl ArboardClipboard {
    pub fn new() -> Result<Self, String> {
        let clipboard = arboard::Clipboard::new().map_err(|e| format!("clipboard init: {e}"))?;
        Ok(Self { clipboard })
    }
}

impl ClipboardSink for ArboardClipboard {
    fn set(&mut self, text: &str) -> Result<(), ClipError> {
        self.clipboard.set_text(text).map_err(|e| e.to_string())
    }
}
