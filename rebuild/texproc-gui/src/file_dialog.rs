use std::path::{Path, PathBuf};

/// Parse the buffer that `GetOpenFileNameW` fills when
/// `OFN_ALLOWMULTISELECT | OFN_EXPLORER` is set.
///
/// The buffer is a sequence of NUL-separated UTF-16 strings ending in a double
/// NUL. When a single file is picked the buffer holds one full path; when
/// multiple files are picked the first segment is the directory and every
/// following segment is a file name relative to it.
///
/// Kept as a pure function over `&[u16]` so it can be unit-tested without a UI.
pub(crate) fn parse_multi_select(buffer: &[u16]) -> Vec<PathBuf> {
    let mut segments: Vec<String> = Vec::new();
    let mut start = 0usize;
    for (index, &code_unit) in buffer.iter().enumerate() {
        if code_unit == 0 {
            if index == start {
                break; // empty segment => end of list
            }
            segments.push(String::from_utf16_lossy(&buffer[start..index]));
            start = index + 1;
        }
    }
    match segments.len() {
        0 => Vec::new(),
        1 => vec![PathBuf::from(&segments[0])],
        _ => {
            let directory = Path::new(&segments[0]);
            segments[1..]
                .iter()
                .map(|name| directory.join(name))
                .collect()
        }
    }
}

#[cfg(windows)]
mod win {
    use super::parse_multi_select;
    use std::{
        ffi::{c_void, OsString},
        mem,
        os::windows::ffi::OsStringExt,
        path::{Path, PathBuf},
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

    #[repr(C)]
    struct BrowseInfoW {
        owner: *mut c_void,
        root: *const c_void,
        display_name: *mut u16,
        title: *const u16,
        flags: u32,
        callback: *mut c_void,
        lparam: isize,
        image: i32,
    }

    #[link(name = "Comdlg32")]
    extern "system" {
        fn GetOpenFileNameW(open_file_name: *mut OpenFileNameW) -> i32;
        fn GetSaveFileNameW(open_file_name: *mut OpenFileNameW) -> i32;
        fn CommDlgExtendedError() -> u32;
    }

    #[link(name = "Shell32")]
    extern "system" {
        fn SHBrowseForFolderW(browse_info: *mut BrowseInfoW) -> *mut c_void;
        fn SHGetPathFromIDListW(id_list: *const c_void, path: *mut u16) -> i32;
    }

    #[link(name = "Ole32")]
    extern "system" {
        fn CoTaskMemFree(pointer: *mut c_void);
    }

    const OFN_OVERWRITEPROMPT: u32 = 0x0000_0002;
    const OFN_NOCHANGEDIR: u32 = 0x0000_0008;
    const OFN_PATHMUSTEXIST: u32 = 0x0000_0800;
    const OFN_FILEMUSTEXIST: u32 = 0x0000_1000;
    const OFN_ALLOWMULTISELECT: u32 = 0x0000_0200;
    const OFN_EXPLORER: u32 = 0x0008_0000;

    const BIF_RETURNONLYFSDIRS: u32 = 0x0000_0001;
    const BIF_EDITBOX: u32 = 0x0000_0010;
    const BIF_NEWDIALOGSTYLE: u32 = 0x0000_0040;

    const MAX_PATH: usize = 260;

    #[derive(Clone, Copy)]
    pub(super) enum Mode {
        OpenSingle,
        OpenMulti,
        Save,
    }

    fn wide(value: &str) -> Vec<u16> {
        value.encode_utf16().chain(Some(0)).collect()
    }

    fn initial_directory(initial: &str) -> Option<Vec<u16>> {
        let trimmed = initial.trim();
        if trimmed.is_empty() {
            return None;
        }
        let path = Path::new(trimmed);
        let directory = if path.is_dir() {
            Some(path.to_path_buf())
        } else {
            path.parent()
                .filter(|value| value.is_dir())
                .map(Path::to_path_buf)
        };
        directory.map(|value| wide(&value.to_string_lossy()))
    }

    /// Drive the common-item dialog. Returns `Ok(None)` on user cancel.
    pub(super) fn run_dialog(
        title: &str,
        filter: &str,
        initial: &str,
        default_name: &str,
        mode: Mode,
    ) -> Result<Option<Vec<PathBuf>>, String> {
        let filter_wide = wide(filter);
        let title_wide = wide(title);
        let initial_directory = initial_directory(initial);
        let initial_pointer = initial_directory
            .as_ref()
            .map_or(ptr::null(), |value| value.as_ptr());

        let buffer_len = if matches!(mode, Mode::OpenMulti) {
            32_768
        } else {
            4_096
        };
        let mut file = vec![0_u16; buffer_len];
        for (slot, value) in file.iter_mut().zip(wide(default_name)) {
            *slot = value;
        }

        let mut flags = OFN_NOCHANGEDIR | OFN_PATHMUSTEXIST | OFN_EXPLORER;
        match mode {
            Mode::OpenSingle => flags |= OFN_FILEMUSTEXIST,
            Mode::OpenMulti => flags |= OFN_FILEMUSTEXIST | OFN_ALLOWMULTISELECT,
            Mode::Save => flags |= OFN_OVERWRITEPROMPT,
        }

        let mut dialog = OpenFileNameW {
            struct_size: mem::size_of::<OpenFileNameW>() as u32,
            owner: ptr::null_mut(),
            instance: ptr::null_mut(),
            filter: filter_wide.as_ptr(),
            custom_filter: ptr::null_mut(),
            max_custom_filter: 0,
            filter_index: 1,
            file: file.as_mut_ptr(),
            max_file: file.len() as u32,
            file_title: ptr::null_mut(),
            max_file_title: 0,
            initial_directory: initial_pointer,
            title: title_wide.as_ptr(),
            flags,
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

        // SAFETY: every pointer in `dialog` references storage that stays alive
        // for the duration of the modal call, the struct matches the Win32
        // OPENFILENAMEW layout, and the output buffer length is passed via
        // `max_file`.
        let ok = unsafe {
            if matches!(mode, Mode::Save) {
                GetSaveFileNameW(&mut dialog)
            } else {
                GetOpenFileNameW(&mut dialog)
            }
        };
        if ok == 0 {
            // SAFETY: takes no arguments; reports this thread's last dialog result.
            let error = unsafe { CommDlgExtendedError() };
            return if error == 0 {
                Ok(None)
            } else {
                Err(format!(
                    "Windows file dialog failed with error 0x{error:04X}"
                ))
            };
        }

        if matches!(mode, Mode::OpenMulti) {
            Ok(Some(parse_multi_select(&file)))
        } else {
            let length = file
                .iter()
                .position(|value| *value == 0)
                .unwrap_or(file.len());
            Ok(Some(vec![PathBuf::from(OsString::from_wide(
                &file[..length],
            ))]))
        }
    }

    pub(super) fn browse_folder(title: &str) -> Result<Option<PathBuf>, String> {
        let title_wide = wide(title);
        let mut display = vec![0_u16; MAX_PATH];
        let mut info = BrowseInfoW {
            owner: ptr::null_mut(),
            root: ptr::null(),
            display_name: display.as_mut_ptr(),
            title: title_wide.as_ptr(),
            flags: BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE | BIF_EDITBOX,
            callback: ptr::null_mut(),
            lparam: 0,
            image: 0,
        };

        // SAFETY: `info` matches BROWSEINFOW and the display buffer lives for
        // the call. COM is already initialised on the UI thread by winit's
        // OleInitialize (drag-and-drop is active), which the new-style dialog
        // requires.
        let id_list = unsafe { SHBrowseForFolderW(&mut info) };
        if id_list.is_null() {
            return Ok(None); // cancelled
        }
        let mut path = vec![0_u16; MAX_PATH];
        // SAFETY: `id_list` is a valid absolute PIDL from the shell; the buffer
        // holds MAX_PATH wide chars.
        let resolved = unsafe { SHGetPathFromIDListW(id_list, path.as_mut_ptr()) };
        // SAFETY: the PIDL was allocated by the shell and is freed exactly once.
        unsafe { CoTaskMemFree(id_list) };
        if resolved == 0 {
            return Err("The selected item is not a file-system folder.".to_owned());
        }
        let length = path
            .iter()
            .position(|value| *value == 0)
            .unwrap_or(path.len());
        Ok(Some(PathBuf::from(OsString::from_wide(&path[..length]))))
    }
}

#[cfg(windows)]
const RC_FILTER: &str = "CryEngine Resource Compiler (rc.exe)\0rc.exe\0Executable files (*.exe)\0*.exe\0All files (*.*)\0*.*\0";

#[cfg(windows)]
pub fn choose_files_multi(title: &str, filter: &str) -> Result<Vec<PathBuf>, String> {
    Ok(win::run_dialog(title, filter, "", "", win::Mode::OpenMulti)?.unwrap_or_default())
}

#[cfg(windows)]
pub fn choose_folder(title: &str, _initial: &str) -> Result<Option<PathBuf>, String> {
    // ponytail: SHBrowseForFolderW has no simple initial-dir argument without a
    // callback; the extra plumbing is not worth it for a folder picker.
    win::browse_folder(title)
}

#[cfg(windows)]
pub fn choose_file_open(
    title: &str,
    filter: &str,
    initial: &str,
) -> Result<Option<PathBuf>, String> {
    Ok(
        win::run_dialog(title, filter, initial, "", win::Mode::OpenSingle)?
            .and_then(|paths| paths.into_iter().next()),
    )
}

#[cfg(windows)]
pub fn choose_file_save(
    title: &str,
    filter: &str,
    default_name: &str,
) -> Result<Option<PathBuf>, String> {
    Ok(
        win::run_dialog(title, filter, "", default_name, win::Mode::Save)?
            .and_then(|paths| paths.into_iter().next()),
    )
}

#[cfg(windows)]
pub fn choose_rc_executable(initial_path: &str) -> Result<Option<PathBuf>, String> {
    choose_file_open(
        "Select CryEngine Resource Compiler",
        RC_FILTER,
        initial_path,
    )
}

#[cfg(not(windows))]
pub fn choose_files_multi(_title: &str, _filter: &str) -> Result<Vec<PathBuf>, String> {
    Ok(Vec::new())
}

#[cfg(not(windows))]
pub fn choose_folder(_title: &str, _initial: &str) -> Result<Option<PathBuf>, String> {
    Ok(None)
}

#[cfg(not(windows))]
pub fn choose_file_open(
    _title: &str,
    _filter: &str,
    _initial: &str,
) -> Result<Option<PathBuf>, String> {
    Ok(None)
}

#[cfg(not(windows))]
pub fn choose_file_save(
    _title: &str,
    _filter: &str,
    _default_name: &str,
) -> Result<Option<PathBuf>, String> {
    Ok(None)
}

#[cfg(not(windows))]
pub fn choose_rc_executable(_initial_path: &str) -> Result<Option<PathBuf>, String> {
    Ok(None)
}

#[cfg(test)]
mod tests {
    use super::parse_multi_select;
    use std::path::PathBuf;

    fn buffer(value: &str) -> Vec<u16> {
        // `value` uses `|` as the NUL separator so tests stay readable.
        value
            .split('|')
            .flat_map(|segment| segment.encode_utf16().chain(std::iter::once(0)))
            .collect()
    }

    #[test]
    fn single_selection_returns_full_path() {
        let parsed = parse_multi_select(&buffer(r"C:\textures\rock_diff.png|"));
        assert_eq!(parsed, vec![PathBuf::from(r"C:\textures\rock_diff.png")]);
    }

    #[test]
    fn multiple_selection_joins_directory_with_names() {
        let parsed = parse_multi_select(&buffer(r"C:\textures|rock_diff.png|rock_ddna.tif|"));
        assert_eq!(
            parsed,
            vec![
                PathBuf::from(r"C:\textures\rock_diff.png"),
                PathBuf::from(r"C:\textures\rock_ddna.tif"),
            ]
        );
    }

    #[test]
    fn empty_buffer_returns_nothing() {
        assert!(parse_multi_select(&[0, 0, 0]).is_empty());
        assert!(parse_multi_select(&[]).is_empty());
    }

    #[test]
    fn trailing_garbage_after_double_null_is_ignored() {
        // GetOpenFileNameW leaves the tail of the 32 KiB buffer untouched.
        let mut raw = buffer(r"C:\a|b.png|");
        raw.extend([0_u16; 16]);
        assert_eq!(parse_multi_select(&raw), vec![PathBuf::from(r"C:\a\b.png")]);
    }
}
