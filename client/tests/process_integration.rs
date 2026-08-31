use std::collections::HashMap;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::mpsc;

use x9ai_client::core::audio::pcm_to_wav16;
use x9ai_client::core::http::{endpoint_from_env, ProcError, Processor, ReqwestProcessor};

/// A minimal one-shot HTTP server: accepts a single connection, reads the full
/// request (headers + Content-Length body), replies with a canned response.
struct StubServer {
    addr: std::net::SocketAddr,
    captured: mpsc::Receiver<Vec<u8>>,
    handle: std::thread::JoinHandle<()>,
}

impl StubServer {
    fn spawn(body: Vec<u8>) -> Self {
        Self::spawn_with_status(body, 200)
    }

    fn spawn_with_status(body: Vec<u8>, status: u16) -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").expect("bind stub listener");
        let addr = listener.local_addr().expect("stub addr");
        let (tx, rx) = mpsc::channel();
        let handle = std::thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("stub accept");
            let request = read_fully(&stream);
            tx.send(request).ok();
            write_response(&mut stream, &body, status);
        });
        Self {
            addr,
            captured: rx,
            handle,
        }
    }

    fn port(&self) -> u16 {
        self.addr.port()
    }

    fn request(&self) -> Vec<u8> {
        self.captured.recv().expect("stub captured request")
    }
}

fn read_fully(mut stream: &TcpStream) -> Vec<u8> {
    let mut buf = [0u8; 8192];
    let mut acc = Vec::new();
    loop {
        let n = stream.read(&mut buf).expect("stub read");
        if n == 0 {
            break;
        }
        acc.extend_from_slice(&buf[..n]);
        if let Some(pos) = index_of(&acc, b"\r\n\r\n") {
            let header_len = pos + 4;
            let head = String::from_utf8_lossy(&acc[..pos]);
            let content_length: usize = head
                .lines()
                .find_map(|line| {
                    let line = line.trim();
                    line.to_ascii_lowercase()
                        .strip_prefix("content-length:")
                        .map(str::trim_start)
                        .and_then(|v| v.parse().ok())
                })
                .unwrap_or(0);
            if acc.len() >= header_len + content_length {
                break;
            }
        }
    }
    acc
}

fn write_response(stream: &mut TcpStream, body: &[u8], status: u16) {
    let head = format!(
        "HTTP/1.1 {status} X\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        body.len()
    );
    stream.write_all(head.as_bytes()).expect("stub write head");
    stream.write_all(body).expect("stub write body");
}

fn index_of(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    haystack
        .windows(needle.len())
        .position(|window| window == needle)
}

fn split_on<'a>(mut haystack: &'a [u8], needle: &[u8]) -> Vec<&'a [u8]> {
    let mut parts = Vec::new();
    while let Some(pos) = index_of(haystack, needle) {
        parts.push(&haystack[..pos]);
        haystack = &haystack[pos + needle.len()..];
    }
    parts.push(haystack);
    parts
}

/// Splits a multipart request body into named fields (raw bytes).
fn multipart_fields(raw: &[u8]) -> HashMap<String, Vec<u8>> {
    let header_end = index_of(raw, b"\r\n\r\n").expect("request headers");
    let head = String::from_utf8_lossy(&raw[..header_end]);
    let boundary = head
        .split("boundary=")
        .nth(1)
        .expect("multipart boundary")
        .lines()
        .next()
        .unwrap()
        .split(';')
        .next()
        .unwrap()
        .trim()
        .to_string();

    let body = &raw[header_end + 4..];
    let delimiters = format!("--{boundary}");
    let delim = delimiters.as_bytes();

    let mut fields = HashMap::new();
    for raw_segment in split_on(body, delim) {
        let mut segment = raw_segment;
        if let Some(s) = segment.strip_prefix(b"\r\n") {
            segment = s;
        }
        if let Some(s) = segment.strip_suffix(b"\r\n") {
            segment = s;
        }
        if segment.is_empty() || segment.starts_with(b"--") {
            continue; // preamble or closing boundary
        }
        let Some(part_header_end) = index_of(segment, b"\r\n\r\n") else {
            continue;
        };
        let part_head = String::from_utf8_lossy(&segment[..part_header_end]);
        let name = part_head
            .split("name=\"")
            .nth(1)
            .and_then(|rest| rest.split('"').next())
            .expect("field name");
        let value = &segment[part_header_end + 4..];
        let value = value.strip_suffix(b"\r\n").unwrap_or(value).to_vec();
        fields.insert(name.to_string(), value);
    }
    fields
}

fn wav_fixture() -> Vec<u8> {
    pcm_to_wav16(&[0.25, -0.5, 1.0, -1.0, 0.0], 16_000)
}

#[test]
fn sends_multipart_with_audio_and_metadata() {
    let server = StubServer::spawn(
        br#"{"status":"success","text":"texto limpo","processing_time_ms":42}"#.to_vec(),
    );
    let wav = wav_fixture();
    let processor = ReqwestProcessor::new(format!("http://127.0.0.1:{}", server.port())).unwrap();

    let result = processor.process(
        wav.clone(),
        r#"{"language":"pt","client_timestamp":1752480000}"#,
    );

    assert_eq!(result.unwrap(), "texto limpo");

    let request = server.request();
    let head = String::from_utf8_lossy(&request[..index_of(&request, b"\r\n\r\n").unwrap()]);
    assert!(head.lines().next().unwrap().starts_with("POST /process "));

    let fields = multipart_fields(&request);
    assert_eq!(
        fields.keys().len(),
        2,
        "expected exactly audio_file + metadata: {fields:?}"
    );
    assert_eq!(fields.get("audio_file").unwrap(), &wav);
    let metadata: serde_json::Value =
        serde_json::from_slice(fields.get("metadata").unwrap()).expect("metadata is JSON");
    assert_eq!(metadata["language"], "pt");
    assert!(metadata["client_timestamp"].is_u64());
}

#[test]
fn connection_refused_is_transport_error() {
    let listener = TcpListener::bind("127.0.0.1:0").expect("probe port");
    let port = listener.local_addr().unwrap().port();
    drop(listener); // free the port so the connect is refused

    let processor =
        ReqwestProcessor::new(format!("http://127.0.0.1:{port}")).expect("processor builds");
    let result = processor.process(wav_fixture(), "{}");
    assert!(matches!(result, Err(ProcError::Transport(_))));
}

#[test]
fn error_status_body_is_remote_error() {
    let server = StubServer::spawn(r#"{"status":"error","message":"no speech"}"#.into());
    let processor = ReqwestProcessor::new(format!("http://127.0.0.1:{}", server.port())).unwrap();
    let result = processor.process(wav_fixture(), "{}");
    assert_eq!(result, Err(ProcError::RemoteError));
}

#[test]
fn non2xx_status_is_error() {
    let server = StubServer::spawn_with_status(b"internal error".to_vec(), 500);
    let processor = ReqwestProcessor::new(format!("http://127.0.0.1:{}", server.port())).unwrap();
    let result = processor.process(wav_fixture(), "{}");
    assert!(matches!(result, Err(ProcError::Non2xx(500))));
}

#[test]
fn malformed_body_is_error() {
    let server = StubServer::spawn(b"definitely not json".to_vec());
    let processor = ReqwestProcessor::new(format!("http://127.0.0.1:{}", server.port())).unwrap();
    let result = processor.process(wav_fixture(), "{}");
    assert!(matches!(result, Err(ProcError::Malformed { .. })));
}

#[test]
fn env_override_reaches_the_wire() {
    let server = StubServer::spawn(r#"{"status":"success","text":"ok"}"#.into());
    let base = endpoint_from_env(Some(&format!("http://127.0.0.1:{}", server.port())));
    let processor = ReqwestProcessor::new(base).unwrap();
    let result = processor.process(wav_fixture(), r#"{"language":"pt"}"#);
    assert_eq!(result.unwrap(), "ok");
    let request = server.request();
    let head = String::from_utf8_lossy(&request[..index_of(&request, b"\r\n\r\n").unwrap()]);
    assert!(head.lines().next().unwrap().starts_with("POST /process "));
}

#[test]
fn server_thread_finishes_cleanly() {
    let server = StubServer::spawn(
        r#"{"status":"success","text":"com texto","processing_time_ms":7}"#.into(),
    );
    let processor = ReqwestProcessor::new(format!("http://127.0.0.1:{}", server.port())).unwrap();
    let result = processor.process(wav_fixture(), "{}");
    assert_eq!(result.unwrap(), "com texto");
    assert!(server.handle.join().is_ok());
}
