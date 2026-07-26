pub mod batch;
pub mod constants;
pub mod error;
pub mod grouping;
pub mod io;
pub mod ops;
pub mod output;
pub mod pipeline;
pub mod planar;
pub mod settings;

pub use batch::{
    process_scan_group, process_scan_parallel, BatchProcessReport, FailedGroup, ProcessedGroup,
};
pub use error::{Result, TexprocError};
pub use grouping::{
    parse_base_name, scan_inputs, Diagnostic, ScanEntry, ScanGroup, ScanResult, Severity,
    SuffixTable,
};
pub use io::{decode_image, probe_header, write_tiff_lzw, HeaderInfo};
pub use output::{
    process_and_write_stage2, process_stage2, write_stage2_outputs, DiffFormat, OutputImage,
    OutputResolution, OutputTextures, Stage2Report, Stage2Step, TextureSettings,
    TextureTypeSettings,
};
pub use pipeline::{
    process_stage1, ArmOrder, IntermediateSettings, IntermediateTextures, SourceImage,
    SourceTextures, Stage1Diagnostic, Stage1Report, Stage1Step, TextureGroup,
};
pub use planar::PlanarImage;
pub use settings::{
    default_settings_path, load_texture_settings, save_texture_settings,
    texture_settings_from_value, texture_settings_to_value,
};
