use std::fmt;

pub type Result<T> = std::result::Result<T, TexprocError>;

#[derive(Debug)]
pub struct TexprocError {
    message: String,
}

impl TexprocError {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }
}

impl fmt::Display for TexprocError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(&self.message)
    }
}

impl std::error::Error for TexprocError {}

impl From<std::io::Error> for TexprocError {
    fn from(error: std::io::Error) -> Self {
        Self::new(format!("I/O error: {error}"))
    }
}

impl From<image::ImageError> for TexprocError {
    fn from(error: image::ImageError) -> Self {
        Self::new(format!("image decode error: {error}"))
    }
}

impl From<tiff::TiffError> for TexprocError {
    fn from(error: tiff::TiffError) -> Self {
        Self::new(format!("TIFF error: {error}"))
    }
}
