pub mod app_loop;
pub mod clipboard;
pub mod hotkey;
pub mod recorder;
pub mod tray;
pub mod win_loop;

use std::sync::mpsc;

use windows_sys::Win32::Foundation::HWND;
use windows_sys::Win32::UI::WindowsAndMessaging::{PostMessageW, WM_NULL};

pub use crate::core::app::ProcessOutcome;

/// Input events driving the core `App`, produced by the tray, hotkey, recorder
/// and `/process` worker threads and consumed by the main loop.
#[derive(Debug)]
pub enum UiEvent {
    Quit,
    Hotkey,
    MenuStopRecording,
    RecordingDone(Result<Vec<u8>, String>),
    ProcessOutcome(ProcessOutcome),
}

/// A raw `HWND` that is `Send + Sync` so it can ride inside event-handler
/// closures required to satisfy `Send + Sync + 'static`.
#[derive(Clone)]
struct WakeHandle(HWND);

// SAFETY: the handle is only used to post a `WM_NULL` wake message from any
// thread; `PostMessageW` is thread-safe and the window outlives the handlers.
unsafe impl Send for WakeHandle {}
unsafe impl Sync for WakeHandle {}

/// Channel sender that also pokes the message loop with a `WM_NULL` so
/// `GetMessageW` wakes up and the main loop drains freshly queued events.
#[derive(Clone)]
pub struct EventSender {
    tx: mpsc::Sender<UiEvent>,
    wake: WakeHandle,
}

impl EventSender {
    pub fn new(tx: mpsc::Sender<UiEvent>, wake: HWND) -> Self {
        Self {
            tx,
            wake: WakeHandle(wake),
        }
    }

    pub fn send(&self, event: UiEvent) {
        let _ = self.tx.send(event);
        unsafe {
            PostMessageW(self.wake.0, WM_NULL, 0, 0);
        }
    }
}

pub fn run() -> Result<(), String> {
    app_loop::run()
}
