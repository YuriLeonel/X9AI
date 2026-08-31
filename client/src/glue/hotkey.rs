use global_hotkey::hotkey::{Code, HotKey, Modifiers};
use global_hotkey::{GlobalHotKeyEvent, GlobalHotKeyManager, HotKeyState};

use super::{EventSender, UiEvent};

/// Owns the global-hotkey registration. Must be created on the thread that
/// pumps messages, because `WM_HOTKEY` delivery requires delivery via that
/// pump.
pub struct HotkeyManager {
    manager: GlobalHotKeyManager,
}

impl HotkeyManager {
    pub fn new() -> Result<Self, String> {
        let manager = GlobalHotKeyManager::new().map_err(|e| format!("hotkey manager: {e}"))?;
        Ok(Self { manager })
    }

    /// Registers the fixed `Ctrl+Alt+Space` binding (no rebind UI in v1).
    pub fn register(&self) -> Result<(), String> {
        let hotkey = HotKey::new(Some(Modifiers::CONTROL | Modifiers::ALT), Code::Space);
        self.manager
            .register(hotkey)
            .map_err(|e| format!("failed to register Ctrl+Alt+Space: {e}"))
    }
}

/// Forwards hotkey presses into the app event channel. The handler receives
/// `WM_HOTKEY` while the pump dispatches on the owning thread.
pub fn install_handler(sender: EventSender) {
    GlobalHotKeyEvent::set_event_handler(Some(Box::new(move |event: GlobalHotKeyEvent| {
        if event.state() == HotKeyState::Pressed {
            sender.send(UiEvent::Hotkey);
        }
    })));
}
