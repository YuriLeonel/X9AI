#![cfg(not(test))]

#[cfg(target_os = "windows")]
fn main() -> Result<(), String> {
    x9ai_client::glue::run()
}

#[cfg(not(target_os = "windows"))]
fn main() {
    eprintln!("X9AI client is Windows-only. Run it on Windows.");
}
