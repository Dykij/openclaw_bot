//! High-performance JSON-RPC 2.0 parser for MCP protocol.
//!
//! Exposed to Python via PyO3 for zero-copy parsing of incoming
//! JSON-RPC messages. Validates structure, extracts method/params,
//! and returns typed results without Python dict/json overhead.

use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde::{Deserialize, Serialize};

/// A parsed JSON-RPC 2.0 request.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcRequest {
    pub jsonrpc: String,
    pub method: String,
    pub params: Option<serde_json::Value>,
    pub id: Option<serde_json::Value>,
}

/// A parsed JSON-RPC 2.0 response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcResponse {
    pub jsonrpc: String,
    pub result: Option<serde_json::Value>,
    pub error: Option<JsonRpcError>,
    pub id: Option<serde_json::Value>,
}

/// JSON-RPC error object.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcError {
    pub code: i64,
    pub message: String,
    pub data: Option<serde_json::Value>,
}

/// Validation result returned to Python.
#[pyclass]
#[derive(Debug, Clone)]
pub struct ParseResult {
    #[pyo3(get)]
    pub valid: bool,
    #[pyo3(get)]
    pub method: String,
    #[pyo3(get)]
    pub params_json: String,
    #[pyo3(get)]
    pub id_value: String,
    #[pyo3(get)]
    pub error: String,
    #[pyo3(get)]
    pub is_batch: bool,
    #[pyo3(get)]
    pub batch_size: usize,
}

#[pymethods]
impl ParseResult {
    fn __repr__(&self) -> String {
        format!(
            "ParseResult(valid={}, method='{}', batch={})",
            self.valid, self.method, self.is_batch
        )
    }
}

/// Parse a single JSON-RPC 2.0 message (request or notification).
///
/// Returns a ParseResult with extracted fields, or an error description.
fn parse_single(raw: &str) -> ParseResult {
    let value: serde_json::Value = match serde_json::from_str(raw) {
        Ok(v) => v,
        Err(e) => {
            return ParseResult {
                valid: false,
                method: String::new(),
                params_json: String::new(),
                id_value: String::new(),
                error: format!("JSON parse error: {}", e),
                is_batch: false,
                batch_size: 0,
            };
        }
    };

    let obj = match value.as_object() {
        Some(o) => o,
        None => {
            return ParseResult {
                valid: false,
                method: String::new(),
                params_json: String::new(),
                id_value: String::new(),
                error: "Expected JSON object".into(),
                is_batch: false,
                batch_size: 0,
            };
        }
    };

    // Validate jsonrpc version
    match obj.get("jsonrpc").and_then(|v| v.as_str()) {
        Some("2.0") => {}
        _ => {
            return ParseResult {
                valid: false,
                method: String::new(),
                params_json: String::new(),
                id_value: String::new(),
                error: "Missing or invalid 'jsonrpc' field (must be \"2.0\")".into(),
                is_batch: false,
                batch_size: 0,
            };
        }
    }

    let method = obj
        .get("method")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();

    if method.is_empty() {
        return ParseResult {
            valid: false,
            method,
            params_json: String::new(),
            id_value: String::new(),
            error: "Missing 'method' field".into(),
            is_batch: false,
            batch_size: 0,
        };
    }

    let params_json = obj
        .get("params")
        .map(|v| v.to_string())
        .unwrap_or_default();

    let id_value = obj
        .get("id")
        .map(|v| v.to_string())
        .unwrap_or_default();

    ParseResult {
        valid: true,
        method,
        params_json,
        id_value,
        error: String::new(),
        is_batch: false,
        batch_size: 1,
    }
}

/// Parse a JSON-RPC 2.0 message — supports both single and batch requests.
///
/// For a batch (JSON array), returns a ParseResult with is_batch=True
/// and batch_size set. Individual messages can be parsed with parse_jsonrpc().
#[pyfunction]
pub fn parse_jsonrpc(raw: &str) -> ParseResult {
    let trimmed = raw.trim();

    // Batch detection
    if trimmed.starts_with('[') {
        match serde_json::from_str::<Vec<serde_json::Value>>(trimmed) {
            Ok(arr) => {
                if arr.is_empty() {
                    return ParseResult {
                        valid: false,
                        method: String::new(),
                        params_json: String::new(),
                        id_value: String::new(),
                        error: "Empty batch".into(),
                        is_batch: true,
                        batch_size: 0,
                    };
                }
                // Parse first message for method
                let first = parse_single(&arr[0].to_string());
                ParseResult {
                    valid: first.valid,
                    method: first.method,
                    params_json: first.params_json,
                    id_value: first.id_value,
                    error: first.error,
                    is_batch: true,
                    batch_size: arr.len(),
                }
            }
            Err(e) => ParseResult {
                valid: false,
                method: String::new(),
                params_json: String::new(),
                id_value: String::new(),
                error: format!("Batch parse error: {}", e),
                is_batch: true,
                batch_size: 0,
            },
        }
    } else {
        parse_single(trimmed)
    }
}

/// Build a JSON-RPC 2.0 response string (success).
#[pyfunction]
pub fn build_response(id_value: &str, result_json: &str) -> PyResult<String> {
    let id: serde_json::Value = serde_json::from_str(id_value)
        .unwrap_or(serde_json::Value::Null);
    let result: serde_json::Value = serde_json::from_str(result_json)
        .unwrap_or(serde_json::Value::Null);

    let resp = serde_json::json!({
        "jsonrpc": "2.0",
        "result": result,
        "id": id,
    });

    Ok(resp.to_string())
}

/// Build a JSON-RPC 2.0 error response string.
#[pyfunction]
pub fn build_error_response(id_value: &str, code: i64, message: &str) -> PyResult<String> {
    let id: serde_json::Value = serde_json::from_str(id_value)
        .unwrap_or(serde_json::Value::Null);

    let resp = serde_json::json!({
        "jsonrpc": "2.0",
        "error": {
            "code": code,
            "message": message,
        },
        "id": id,
    });

    Ok(resp.to_string())
}

/// PyO3 module registration — exposes Rust functions to Python.
#[pymodule]
fn openclaw_rust_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<ParseResult>()?;
    m.add_function(wrap_pyfunction!(parse_jsonrpc, m)?)?;
    m.add_function(wrap_pyfunction!(build_response, m)?)?;
    m.add_function(wrap_pyfunction!(build_error_response, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_valid_request() {
        let raw = r#"{"jsonrpc":"2.0","method":"tools/call","params":{"name":"read_file"},"id":1}"#;
        let result = parse_jsonrpc(raw);
        assert!(result.valid);
        assert_eq!(result.method, "tools/call");
        assert!(!result.is_batch);
    }

    #[test]
    fn test_parse_invalid_json() {
        let result = parse_jsonrpc("{invalid");
        assert!(!result.valid);
        assert!(result.error.contains("parse error"));
    }

    #[test]
    fn test_parse_batch() {
        let raw = r#"[{"jsonrpc":"2.0","method":"a","id":1},{"jsonrpc":"2.0","method":"b","id":2}]"#;
        let result = parse_jsonrpc(raw);
        assert!(result.valid);
        assert!(result.is_batch);
        assert_eq!(result.batch_size, 2);
    }

    #[test]
    fn test_build_response() {
        let resp = build_response("1", r#""ok""#).unwrap();
        assert!(resp.contains("\"result\":\"ok\""));
    }

    #[test]
    fn test_build_error() {
        let resp = build_error_response("1", -32600, "Invalid Request").unwrap();
        assert!(resp.contains("-32600"));
    }
}
