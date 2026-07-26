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

    #[link(name = "Comdlg32")]
    extern "system" {
        fn GetOpenFileNameW(open_file_name: *mut OpenFileNameW) -> i32;
        fn GetSaveFileNameW(open_file_name: *mut OpenFileNameW) -> i32;
        fn CommDlgExtendedError() -> u32;
    }

    // COM plumbing for the modern IFileOpenDialog folder picker.
    #[repr(C)]
    struct Guid {
        data1: u32,
        data2: u16,
        data3: u16,
        data4: [u8; 8],
    }

    #[link(name = "Ole32")]
    extern "system" {
        fn CoTaskMemFree(pointer: *mut c_void);
        fn CoInitializeEx(reserved: *mut c_void, co_init: u32) -> i32;
        fn CoUninitialize();
        fn CoCreateInstance(
            clsid: *const Guid,
            outer: *mut c_void,
            context: u32,
            iid: *const Guid,
            object: *mut *mut c_void,
        ) -> i32;
    }

    const OFN_OVERWRITEPROMPT: u32 = 0x0000_0002;
    const OFN_NOCHANGEDIR: u32 = 0x0000_0008;
    const OFN_PATHMUSTEXIST: u32 = 0x0000_0800;
    const OFN_FILEMUSTEXIST: u32 = 0x0000_1000;
    const OFN_ALLOWMULTISELECT: u32 = 0x0000_0200;
    const OFN_EXPLORER: u32 = 0x0008_0000;

    const COINIT_APARTMENTTHREADED: u32 = 0x2;
    const CLSCTX_INPROC_SERVER: u32 = 0x1;
    const FOS_PICKFOLDERS: u32 = 0x20;
    const FOS_FORCEFILESYSTEM: u32 = 0x40;
    const SIGDN_FILESYSPATH: u32 = 0x8005_8000;

    // HRESULTs we branch on (as signed i32; negative == failure).
    const S_OK: i32 = 0;
    const S_FALSE: i32 = 1;
    const RPC_E_CHANGED_MODE: i32 = 0x8001_0106_u32 as i32;
    const HRESULT_CANCELLED: i32 = 0x8007_04C7_u32 as i32; // HRESULT_FROM_WIN32(ERROR_CANCELLED)

    // CLSID_FileOpenDialog {DC1C5A9C-E88A-4dde-A5A1-60F82A20AEF7}
    const CLSID_FILE_OPEN_DIALOG: Guid = Guid {
        data1: 0xDC1C_5A9C,
        data2: 0xE88A,
        data3: 0x4DDE,
        data4: [0xA5, 0xA1, 0x60, 0xF8, 0x2A, 0x20, 0xAE, 0xF7],
    };
    // IID_IFileOpenDialog {D57C7288-D4AD-4768-BE02-9D969532D960}
    const IID_IFILE_OPEN_DIALOG: Guid = Guid {
        data1: 0xD57C_7288,
        data2: 0xD4AD,
        data3: 0x4768,
        data4: [0xBE, 0x02, 0x9D, 0x96, 0x95, 0x32, 0xD9, 0x60],
    };

    /// Vtable slots up to `GetResult`; slots we never call are opaque pointers.
    /// Layout order is IUnknown -> IModalWindow -> IFileDialog and must not move.
    #[repr(C)]
    struct IFileOpenDialogVtbl {
        query_interface: *const c_void,
        add_ref: *const c_void,
        release: unsafe extern "system" fn(*mut c_void) -> u32,
        show: unsafe extern "system" fn(*mut c_void, *mut c_void) -> i32,
        set_file_types: *const c_void,
        set_file_type_index: *const c_void,
        get_file_type_index: *const c_void,
        advise: *const c_void,
        unadvise: *const c_void,
        set_options: unsafe extern "system" fn(*mut c_void, u32) -> i32,
        get_options: unsafe extern "system" fn(*mut c_void, *mut u32) -> i32,
        set_default_folder: *const c_void,
        set_folder: *const c_void,
        get_folder: *const c_void,
        get_current_selection: *const c_void,
        set_file_name: *const c_void,
        get_file_name: *const c_void,
        set_title: unsafe extern "system" fn(*mut c_void, *const u16) -> i32,
        set_ok_button_label: *const c_void,
        set_file_name_label: *const c_void,
        get_result: unsafe extern "system" fn(*mut c_void, *mut *mut c_void) -> i32,
    }

    /// IShellItem vtable up to `GetDisplayName`.
    #[repr(C)]
    struct IShellItemVtbl {
        query_interface: *const c_void,
        add_ref: *const c_void,
        release: unsafe extern "system" fn(*mut c_void) -> u32,
        bind_to_handler: *const c_void,
        get_parent: *const c_void,
        get_display_name: unsafe extern "system" fn(*mut c_void, u32, *mut *mut u16) -> i32,
    }

    unsafe fn dialog_vtbl<'a>(this: *mut c_void) -> &'a IFileOpenDialogVtbl {
        &**(this as *const *const IFileOpenDialogVtbl)
    }

    unsafe fn shell_item_vtbl<'a>(this: *mut c_void) -> &'a IShellItemVtbl {
        &**(this as *const *const IShellItemVtbl)
    }

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

    /// Modern Explorer-style folder picker (IFileOpenDialog + FOS_PICKFOLDERS).
    pub(super) fn browse_folder(title: &str) -> Result<Option<PathBuf>, String> {
        let title_wide = wide(title);

        // SAFETY: CoInitializeEx is called per invocation on this thread; a
        // balanced CoUninitialize runs only when this call actually initialised
        // COM (S_OK/S_FALSE). RPC_E_CHANGED_MODE means COM is already usable in
        // another apartment model, so we proceed without owning the reference.
        let hr_init = unsafe { CoInitializeEx(ptr::null_mut(), COINIT_APARTMENTTHREADED) };
        let owns_com = match hr_init {
            S_OK | S_FALSE => true,
            RPC_E_CHANGED_MODE => false,
            _ => return Err(format!("CoInitializeEx failed: 0x{hr_init:08X}")),
        };

        // SAFETY: all COM calls below use the well-known FileOpenDialog vtable
        // layout; every interface pointer is released before returning.
        let result = unsafe { browse_folder_com(&title_wide) };

        if owns_com {
            // SAFETY: balances the successful CoInitializeEx above.
            unsafe { CoUninitialize() };
        }
        result
    }

    unsafe fn browse_folder_com(title_wide: &[u16]) -> Result<Option<PathBuf>, String> {
        let mut dialog: *mut c_void = ptr::null_mut();
        let hr = CoCreateInstance(
            &CLSID_FILE_OPEN_DIALOG,
            ptr::null_mut(),
            CLSCTX_INPROC_SERVER,
            &IID_IFILE_OPEN_DIALOG,
            &mut dialog,
        );
        if hr < 0 || dialog.is_null() {
            return Err(format!(
                "CoCreateInstance(FileOpenDialog) failed: 0x{hr:08X}"
            ));
        }
        let vtbl = dialog_vtbl(dialog);

        let mut options: u32 = 0;
        (vtbl.get_options)(dialog, &mut options);
        let hr = (vtbl.set_options)(dialog, options | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM);
        if hr < 0 {
            (vtbl.release)(dialog);
            return Err(format!("IFileDialog::SetOptions failed: 0x{hr:08X}"));
        }
        (vtbl.set_title)(dialog, title_wide.as_ptr());

        let hr = (vtbl.show)(dialog, ptr::null_mut());
        if hr < 0 {
            (vtbl.release)(dialog);
            return if hr == HRESULT_CANCELLED {
                Ok(None)
            } else {
                Err(format!("IFileDialog::Show failed: 0x{hr:08X}"))
            };
        }

        let mut item: *mut c_void = ptr::null_mut();
        let hr = (vtbl.get_result)(dialog, &mut item);
        if hr < 0 || item.is_null() {
            (vtbl.release)(dialog);
            return Err(format!("IFileDialog::GetResult failed: 0x{hr:08X}"));
        }

        let item_vtbl = shell_item_vtbl(item);
        let mut wide_path: *mut u16 = ptr::null_mut();
        let hr = (item_vtbl.get_display_name)(item, SIGDN_FILESYSPATH, &mut wide_path);
        let path = if hr >= 0 && !wide_path.is_null() {
            let length = (0..)
                .take_while(|&index| *wide_path.add(index) != 0)
                .count();
            let slice = std::slice::from_raw_parts(wide_path, length);
            let resolved = PathBuf::from(OsString::from_wide(slice));
            CoTaskMemFree(wide_path as *mut c_void);
            Some(resolved)
        } else {
            None
        };
        (item_vtbl.release)(item);
        (vtbl.release)(dialog);

        match path {
            Some(resolved) => Ok(Some(resolved)),
            None => Err("The selected item has no file-system path.".to_owned()),
        }
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
    // ponytail: the modern picker remembers its own last location, so wiring an
    // initial folder (SetFolder needs a built IShellItem) buys nothing here.
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
