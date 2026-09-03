use std::sync::mpsc::Receiver;

use windows_sys::Win32::Foundation::{HWND, LPARAM, LRESULT, WPARAM};
use windows_sys::Win32::System::LibraryLoader::GetModuleHandleW;
use windows_sys::Win32::UI::WindowsAndMessaging::{
    CreateWindowExW, DefWindowProcW, DispatchMessageW, GetMessageW, PostQuitMessage,
    RegisterClassW, TranslateMessage, HWND_MESSAGE, MSG, WNDCLASSW,
};

use super::UiEvent;

const CLASS_NAME: &str = "X9AITrayWindow";

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

unsafe extern "system" fn wnd_proc(
    hwnd: HWND,
    msg: u32,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    DefWindowProcW(hwnd, msg, wparam, lparam)
}

/// A message-only window plus the thread pump the tray and hotkey event
/// delivery rely on (both require WM dispatch on their owning thread).
pub struct MessageWindow {
    hwnd: HWND,
}

impl MessageWindow {
    pub fn new() -> Result<Self, String> {
        let instance = unsafe { GetModuleHandleW(std::ptr::null()) };
        if instance.is_null() {
            return Err("GetModuleHandleW failed".into());
        }
        let class_name = wide(CLASS_NAME);

        let wnd_class = WNDCLASSW {
            style: 0,
            lpfnWndProc: Some(wnd_proc),
            cbClsExtra: 0,
            cbWndExtra: 0,
            hInstance: instance,
            hIcon: std::ptr::null_mut(),
            hCursor: std::ptr::null_mut(),
            hbrBackground: std::ptr::null_mut(),
            lpszMenuName: std::ptr::null(),
            lpszClassName: class_name.as_ptr(),
        };
        if unsafe { RegisterClassW(&wnd_class) } == 0 {
            return Err(format!("RegisterClassW failed for {CLASS_NAME}"));
        }

        let hwnd = unsafe {
            CreateWindowExW(
                0,
                class_name.as_ptr(),
                std::ptr::null(),
                0,
                0,
                0,
                0,
                0,
                HWND_MESSAGE,
                std::ptr::null_mut(),
                instance,
                std::ptr::null(),
            )
        };
        if hwnd.is_null() {
            return Err("CreateWindowExW( HWND_MESSAGE ) failed".into());
        }
        Ok(Self { hwnd })
    }

    pub fn hwnd(&self) -> HWND {
        self.hwnd
    }

    /// Runs the message pump on the owning thread. Dispatches window messages
    /// (tray-icon and global-hotkey delivery happen here) and drains the app
    /// event channel in between. Returns `Ok(())` on quit.
    pub fn pump(
        &self,
        rx: &Receiver<UiEvent>,
        mut handle: impl FnMut(UiEvent),
    ) -> Result<(), String> {
        let mut msg: MSG = unsafe { std::mem::zeroed() };
        loop {
            let result = unsafe { GetMessageW(&mut msg, std::ptr::null_mut(), 0, 0) };
            if result == 0 {
                return Ok(()); // WM_QUIT
            }
            if result == -1 {
                return Err("GetMessageW failed".into());
            }
            unsafe {
                TranslateMessage(&msg);
                DispatchMessageW(&msg);
            }

            while let Ok(event) = rx.try_recv() {
                if matches!(event, UiEvent::Quit) {
                    unsafe {
                        PostQuitMessage(0);
                    }
                    return Ok(());
                }
                handle(event);
            }
        }
    }
}
