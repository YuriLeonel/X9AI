use tray_icon::menu::{Menu, MenuEvent, MenuItem};
use tray_icon::{Icon, TrayIcon, TrayIconBuilder};
use windows_sys::Win32::Foundation::HWND;
use windows_sys::Win32::UI::Shell::{
    Shell_NotifyIconW, NIF_INFO, NIIF_INFO, NIM_ADD, NIM_DELETE, NOTIFYICONDATAW,
};

use crate::core::notify::TITLE;

use super::{EventSender, UiEvent};

const MENU_STOP: &str = "parar-gravacao";
const MENU_QUIT: &str = "sair";

/// Persistent system-tray icon with a "Sair" item always present and a
/// "Parar gravação" item enabled only while recording.
pub struct Tray {
    icon: TrayIcon,
    stop_item: MenuItem,
}

impl Tray {
    pub fn build(sender: EventSender) -> Result<Self, String> {
        let stop_item = MenuItem::with_id(MENU_STOP, "Parar gravação", false, None);
        let quit_item = MenuItem::with_id(MENU_QUIT, "Sair", true, None);

        let menu = Menu::new();
        menu.append(&stop_item)
            .map_err(|e| format!("menu append: {e}"))?;
        menu.append(&quit_item)
            .map_err(|e| format!("menu append: {e}"))?;

        MenuEvent::set_event_handler(Some(Box::new(move |event: MenuEvent| {
            let id = event.id().0.clone();
            match id.as_str() {
                MENU_STOP => sender.send(UiEvent::MenuStopRecording),
                MENU_QUIT => sender.send(UiEvent::Quit),
                _ => {}
            }
        })));

        let icon = Icon::from_rgba(tray_icon_rgba(), 16, 16).map_err(|e| format!("icon: {e}"))?;

        let icon = TrayIconBuilder::new()
            .with_tooltip(TITLE)
            .with_icon(icon)
            .with_menu(Box::new(menu))
            .build()
            .map_err(|e| format!("tray icon: {e}"))?;

        Ok(Self { icon, stop_item })
    }

    pub fn set_tooltip(&self, text: &str) -> Result<(), String> {
        self.icon
            .set_tooltip(Some(text))
            .map_err(|e| format!("tooltip: {e}"))
    }

    /// Best-effort "Parar gravação" availability (muda has no hide in v1).
    pub fn set_recording(&self, recording: bool) {
        self.stop_item.set_enabled(recording);
    }
}

/// Classic `Shell_NotifyIcon` balloon anchored on the app message-only window.
///
/// Windows 11 suppresses classic balloons by default (notification-center
/// redirect), so this is a best-effort success/error surface (CLI-17/18).
pub fn show_balloon(hwnd: HWND, body: &str) {
    let mut nid: NOTIFYICONDATAW = unsafe { std::mem::zeroed() };
    nid.cbSize = std::mem::size_of::<NOTIFYICONDATAW>() as u32;
    nid.hWnd = hwnd;
    nid.uID = 1;
    nid.uFlags = NIF_INFO;
    nid.dwInfoFlags = NIIF_INFO;
    nid.Anonymous.uTimeout = 3000;
    push_wide(&mut nid.szInfoTitle, TITLE);
    push_wide(&mut nid.szInfo, body);
    unsafe {
        Shell_NotifyIconW(NIM_ADD, &nid);
        Shell_NotifyIconW(NIM_DELETE, &nid);
    }
}

fn push_wide(dst: &mut [u16], s: &str) {
    let mut chars = s.encode_utf16();
    for slot in dst.iter_mut() {
        *slot = chars.next().unwrap_or(0);
    }
}

/// Flat 16×16 RGBA icon (X9AI blue).
fn tray_icon_rgba() -> Vec<u8> {
    let pixel = [0x00, 0x78, 0xD7, 0xFF];
    pixel.iter().copied().cycle().take(16 * 16 * 4).collect()
}
