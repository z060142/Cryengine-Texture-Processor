use serde::Serialize;
use serde_json::Value;
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Diagnostic {
    pub severity: String,
    pub code: String,
    pub material: String,
    #[serde(flatten)]
    pub details: BTreeMap<String, Value>,
    pub message: String,
}

impl Diagnostic {
    pub fn new(
        severity: impl Into<String>,
        code: impl Into<String>,
        material: impl Into<String>,
        message: impl Into<String>,
    ) -> Self {
        Self {
            severity: severity.into(),
            code: code.into(),
            material: material.into(),
            details: BTreeMap::new(),
            message: message.into(),
        }
    }

    pub fn detail(mut self, key: impl Into<String>, value: impl Into<Value>) -> Self {
        self.details.insert(key.into(), value.into());
        self
    }
}
