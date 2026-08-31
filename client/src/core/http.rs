pub const DEFAULT_ENDPOINT: &str = "http://127.0.0.1:8000";
pub const ENDPOINT_ENV_VAR: &str = "X9AI_SERVER_URL";

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ProcError {
    /// HTTP status outside 2xx.
    Non2xx(u16),
    /// Body reported `"status":"error"`.
    RemoteError,
    /// Body did not decode to the success schema (bad JSON, missing `text`).
    Malformed { body: String },
    /// I/O, connect or timeout failure talking to the server.
    Transport(String),
}

impl std::fmt::Display for ProcError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ProcError::Non2xx(status) => write!(f, "server returned HTTP {status}"),
            ProcError::RemoteError => write!(f, "server reported a processing error"),
            ProcError::Malformed { body } => write!(f, "malformed response: {body}"),
            ProcError::Transport(msg) => write!(f, "request failed: {msg}"),
        }
    }
}

impl std::error::Error for ProcError {}

/// Base URL for `/process`. A non-blank `X9AI_SERVER_URL` wins; otherwise the
/// local default is used (CLI-12).
pub fn endpoint_from_env(env: Option<&str>) -> String {
    match env {
        Some(v) if !v.trim().is_empty() => v.trim().trim_end_matches('/').to_string(),
        _ => DEFAULT_ENDPOINT.to_string(),
    }
}

/// Parses a `/process` response body into the transcribed text (CLI-13/14).
///
/// Mirrors `server/x9ai/schemas.py`: success carries `{status, text,
/// processing_time_ms}`; anything else (error status, malformed body, missing
/// `text`) is an error.
pub fn parse_response(bytes: &[u8]) -> Result<String, ProcError> {
    let body = String::from_utf8_lossy(bytes).into_owned();
    let value: serde_json::Value =
        serde_json::from_str(&body).map_err(|_| ProcError::Malformed { body: body.clone() })?;

    match value.get("status").and_then(serde_json::Value::as_str) {
        Some("success") => value
            .get("text")
            .and_then(serde_json::Value::as_str)
            .map(str::to_string)
            .ok_or_else(|| ProcError::Malformed { body: body.clone() }),
        Some("error") => Err(ProcError::RemoteError),
        _ => Err(ProcError::Malformed { body: body.clone() }),
    }
}

/// Seam over the `/process` HTTP call so the core can swap implementations.
pub trait Processor {
    fn process(&self, wav: Vec<u8>, metadata: &str) -> Result<String, ProcError>;
}

const REQUEST_TIMEOUT: std::time::Duration = std::time::Duration::from_secs(60);

/// Default `/process` client: blocking multipart POST over `reqwest`.
#[derive(Clone)]
pub struct ReqwestProcessor {
    client: reqwest::blocking::Client,
    base_url: String,
}

impl ReqwestProcessor {
    pub fn new(base_url: String) -> Result<Self, ProcError> {
        let client = reqwest::blocking::Client::builder()
            .timeout(REQUEST_TIMEOUT)
            .build()
            .map_err(|e| ProcError::Transport(e.to_string()))?;
        Ok(Self { client, base_url })
    }
}

impl Processor for ReqwestProcessor {
    /// POSTs `wav` + `metadata` as multipart fields to `{base}/process`
    /// (CLI-11) and maps the outcome per the server contract (CLI-13/14).
    fn process(&self, wav: Vec<u8>, metadata: &str) -> Result<String, ProcError> {
        let form = reqwest::blocking::multipart::Form::new()
            .part("audio_file", reqwest::blocking::multipart::Part::bytes(wav))
            .text("metadata", metadata.to_string());

        let response = self
            .client
            .post(format!("{}/process", self.base_url))
            .multipart(form)
            .send()
            .map_err(|e| ProcError::Transport(e.to_string()))?;

        let status = response.status();
        let bytes = response
            .bytes()
            .map_err(|e| ProcError::Transport(e.to_string()))?;

        if !status.is_success() {
            return Err(ProcError::Non2xx(status.as_u16()));
        }
        parse_response(&bytes)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_endpoint_when_env_absent() {
        assert_eq!(endpoint_from_env(None), DEFAULT_ENDPOINT);
    }

    #[test]
    fn blank_env_yields_default() {
        assert_eq!(endpoint_from_env(Some("")), DEFAULT_ENDPOINT);
        assert_eq!(endpoint_from_env(Some("   ")), DEFAULT_ENDPOINT);
    }

    #[test]
    fn env_override_is_used() {
        assert_eq!(
            endpoint_from_env(Some("http://192.168.0.5:9000")),
            "http://192.168.0.5:9000"
        );
    }

    #[test]
    fn env_override_strips_trailing_slash_and_whitespace() {
        assert_eq!(
            endpoint_from_env(Some(" http://host:1234/ ")),
            "http://host:1234"
        );
    }

    #[test]
    fn success_body_returns_text() {
        let body = br#"{"status":"success","text":"texto limpo","processing_time_ms":42}"#;
        assert_eq!(parse_response(body).unwrap(), "texto limpo");
    }

    #[test]
    fn error_status_returns_remote_error() {
        let body = br#"{"status":"error","message":"no speech detected"}"#;
        assert_eq!(parse_response(body), Err(ProcError::RemoteError));
    }

    #[test]
    fn malformed_json_returns_malformed() {
        assert!(matches!(
            parse_response(b"not json"),
            Err(ProcError::Malformed { .. })
        ));
    }

    #[test]
    fn success_body_without_text_is_malformed() {
        let body = br#"{"status":"success","processing_time_ms":1}"#;
        assert!(matches!(
            parse_response(body),
            Err(ProcError::Malformed { .. })
        ));
    }
}
