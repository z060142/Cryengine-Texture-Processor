use std::path::PathBuf;

#[cfg(windows)]
pub fn choose_rc_executable(initial_path: &str) -> Result<Option<PathBuf>, String> {
    use std::{
        ffi::{c_void, OsString},
        mem,
        os::windows::ffi::OsStringExt,
        path::Path,
        ptr,
    };

    #[repr(C)]
    struct OpenFileNameW {
        struct_size: u32,
        owner: *mut c_void,
        instance: *mut c_void,
        filter: *const u16,
        custom_filter: *mut u16,
        max_custom_filter: u32,
        filter_index: u32,
        file: *mut u16,
        max_file: u32,
        file_title: *mut u16,
        max_file_title: u32,
        initial_directory: *const u16,
        title: *const u16,
        flags: u32,
        file_offset: u16,
        file_extension: u16,
        default_extension: *const u16,
        custom_data: isize,
        hook: *mut c_void,
        template_name: *const u16,
        reserved: *mut c_void,
        reserved_flags: u32,
        extended_flags: u32,
    }

    #[link(name = "Comdlg32")]
    extern "system" {
        fn GetOpenFileNameW(open_file_name: *mut OpenFileNameW) -> i32;
        fn CommDlgExtendedError() -> u32;
    }

    const OFN_NOCHANGEDIR: u32 = 0x0000_0008;
    const OFN_PATHMUSTEXIST: u32 = 0x0000_0800;
    const OFN_FILEMUSTEXIST: u32 = 0x0000_1000;
    const OFN_EXPLORER: u32 = 0x0008_0000;

    fn wide(value: &str) -> Vec<u16> {
        value.encode_utf16().chain(Some(0)).collect()
    }

    let filter = wide(
        "CryEngine Resource Compiler (rc.exe)\0rc.exe\0Executable files (*.exe)\0*.exe\0All files (*.*)\0*.*\0",
    );
    let title = wide("Select CryEngine Resource Compiler");
    let initial_directory = Path::new(initial_path.trim())
        .parent()
        .filter(|path| path.is_dir())
        .map(|path| wide(&path.to_string_lossy()));
    let initial_directory_pointer = initial_directory
        .as_ref()
        .map_or(ptr::null(), |value| value.as_ptr());
    let mut file = vec![0_u16; 32_768];
    let mut dialog = OpenFileNameW {
        struct_size: mem::size_of::<OpenFileNameW>() as u32,
        owner: ptr::null_mut(),
        instance: ptr::null_mut(),
        filter: filter.as_ptr(),
        custom_filter: ptr::null_mut(),
        max_custom_filter: 0,
        filter_index: 1,
        file: file.as_mut_ptr(),
        max_file: file.len() as u32,
        file_title: ptr::null_mut(),
        max_file_title: 0,
        initial_directory: initial_directory_pointer,
        title: title.as_ptr(),
        flags: OFN_NOCHANGEDIR | OFN_PATHMUSTEXIST | OFN_FILEMUSTEXIST | OFN_EXPLORER,
        file_offset: 0,
        file_extension: 0,
        default_extension: ptr::null(),
        custom_data: 0,
        hook: ptr::null_mut(),
        template_name: ptr::null(),
        reserved: ptr::null_mut(),
        reserved_flags: 0,
        extended_flags: 0,
    };

    // SAFETY: Every pointer in `dialog` references live storage for the duration of
    // the modal call, the structure follows the Win32 OPENFILENAMEW layout, and the
    // output buffer length is supplied through `max_file`.
    if unsafe { GetOpenFileNameW(&mut dialog) } == 0 {
        // SAFETY: CommDlgExtendedError takes no arguments and reports the most
        // recent common-dialog result on this thread.
        let error = unsafe { CommDlgExtendedError() };
        return if error == 0 {
            Ok(None)
        } else {
            Err(format!(
                "Windows file dialog failed with error 0x{error:04X}"
            ))
        };
    }
    let length = file
        .iter()
        .position(|value| *value == 0)
        .ok_or_else(|| "Windows file dialog returned an unterminated path".to_owned())?;
    Ok(Some(PathBuf::from(OsString::from_wide(&file[..length]))))
}

#[cfg(not(windows))]
pub fn choose_rc_executable(_initial_path: &str) -> Result<Option<PathBuf>, String> {
    Ok(None)
}
