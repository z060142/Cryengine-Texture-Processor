pub mod constants;
pub mod error;
pub mod grouping;
pub mod io;
pub mod ops;
pub mod output;
pub mod pipeline;
pub mod planar;

pub use error::{Result, TexprocError};
pub use grouping::{
    scan_inputs, Diagnostic, ScanEntry, ScanGroup, ScanResult, Severity, SuffixTable,
};
pub use io::{decode_image, probe_header, write_tiff_lzw, HeaderInfo};
pub use output::{
    process_stage2, write_stage2_outputs, DiffFormat, OutputImage, OutputResolution,
    OutputTextures, Stage2Report, Stage2Step, TextureSettings, TextureTypeSettings,
};
pub use pipeline::{
    process_stage1, ArmOrder, IntermediateSettings, IntermediateTextures, SourceImage,
    SourceTextures, Stage1Diagnostic, Stage1Report, Stage1Step, TextureGroup,
};
pub use planar::PlanarImage;
