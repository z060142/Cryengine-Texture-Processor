//! Thin Rust client for the rcbroker session (`rc_broker.exe` + `RcBrokerClient.dll`,
//! see E:\coding2\rcbroker). We spawn the broker as our own child process (a fresh
//! pipe name + token per session, `--parent <our pid>` ties its lifetime to ours via
//! its own Job Object), load its client DLL dynamically, and adapt our two RC call
//! sites (single CGF export, DDS batch) onto its C ABI. Any failure along the way
//! (DLL missing, spawn failed, handshake timed out, a specific request rejected)
//! yields `None`/no session — callers always fall back to a direct `rc.exe` spawn,
//! matching the broker's own "pure scheduling layer" contract.

#[cfg(windows)]
mod imp {
    use std::{
        ffi::{c_void, CString},
        os::windows::{ffi::OsStrExt, process::CommandExt},
        path::Path,
        process::{Child, Command, Stdio},
        ptr, thread,
        time::{Duration, Instant},
    };

    #[repr(C)]
    #[derive(Clone, Copy)]
    pub struct CryRcBrokerBatchResult {
        pub handled: i32,
        pub exit_code: i32,
        #[allow(dead_code)]
        pub batch_id: u64,
        #[allow(dead_code)]
        pub process_id: u32,
    }

    type LogCallback = extern "C" fn(*const i8, usize, *mut c_void);

    #[repr(C)]
    struct CryRcBrokerBatchRequestUtf8 {
        absolute_input: *const i8,
        absolute_target_root: *const i8,
        overwrite_filename: *const i8,
        rc_options: *const i8,
        estimated_bytes: u64,
        priority: u32,
        log_callback: Option<LogCallback>,
        user_data: *mut c_void,
    }

    type IsAvailableFn = unsafe extern "C" fn() -> i32;
    type ShutdownFn = unsafe extern "C" fn() -> i32;
    type CloseClientFn = unsafe extern "C" fn();
    type InvokeLegacyFn = unsafe extern "C" fn(
        *const i8,
        *const i8,
        *const i8,
        u32,
        Option<LogCallback>,
        *mut c_void,
        *mut i32,
    ) -> i32;
    type InvokeBatchFn = unsafe extern "C" fn(
        *const CryRcBrokerBatchRequestUtf8,
        usize,
        *mut CryRcBrokerBatchResult,
    ) -> i32;

    #[link(name = "kernel32")]
    extern "system" {
        fn LoadLibraryW(name: *const u16) -> *mut c_void;
        fn GetProcAddress(module: *mut c_void, name: *const u8) -> *mut c_void;
        fn FreeLibrary(module: *mut c_void) -> i32;
    }

    /// Resolve one exported symbol and transmute it to the exact `unsafe extern
    /// "C" fn` type declared above (a concrete-type `transmute` per call site,
    /// not a generic one, so the size check is real).
    macro_rules! resolve {
        ($library:expr, $name:literal, $ty:ty) => {{
            let raw = GetProcAddress($library, concat!($name, "\0").as_bytes().as_ptr());
            if raw.is_null() {
                None
            } else {
                Some(std::mem::transmute::<*mut c_void, $ty>(raw))
            }
        }};
    }

    fn wide(path: &Path) -> Vec<u16> {
        path.as_os_str().encode_wide().chain(Some(0)).collect()
    }

    fn path_to_cstring(path: &Path) -> Option<CString> {
        CString::new(path.to_string_lossy().into_owned()).ok()
    }

    /// Dependency-free local randomness: each fresh `RandomState` draws new keys
    /// from the OS entropy source, so hashing nothing with it still yields a
    /// pseudorandom 64-bit value. Good enough for a local-loopback pipe name and
    /// auth token; no cryptographic guarantee needed here.
    fn random_hex(byte_len: usize) -> String {
        use std::collections::hash_map::RandomState;
        use std::hash::{BuildHasher, Hasher};
        let mut out = String::with_capacity(byte_len * 2);
        while out.len() < byte_len * 2 {
            let value = RandomState::new().build_hasher().finish();
            out.push_str(&format!("{value:016x}"));
        }
        out.truncate(byte_len * 2);
        out
    }

    /// One DDS conversion request pre-built for the broker's batch RC contract
    /// (which, unlike the legacy single-file contract, requires an explicit
    /// target root and output filename — no implicit derivation from input).
    pub struct BrokerBatchItem {
        input: CString,
        target_root: CString,
        overwrite_filename: CString,
        options: CString,
        estimated_bytes: u64,
    }

    impl BrokerBatchItem {
        /// `tif` → `<tif-stem>.dds` in `output_root`, matching the direct-spawn
        /// path's `/refresh /userdialog=0` implicit RC output naming.
        pub fn rc_dds(tif: &Path, output_root: &Path) -> Option<Self> {
            let input = path_to_cstring(tif)?;
            let target_root = path_to_cstring(output_root)?;
            let dds = tif.with_extension("dds");
            let overwrite_filename = CString::new(dds.file_name()?.to_str()?).ok()?;
            let options = CString::new("/refresh /userdialog=0").ok()?;
            let estimated_bytes = std::fs::metadata(tif).map(|meta| meta.len()).unwrap_or(1).max(1);
            Some(Self {
                input,
                target_root,
                overwrite_filename,
                options,
                estimated_bytes,
            })
        }
    }

    /// A running `rc_broker.exe` we spawned, plus its loaded client DLL. Lives
    /// entirely on one worker thread (constructed and dropped there); the broker
    /// process is tied to our own via `--parent <pid>` so it cannot outlive us.
    pub struct BrokerSession {
        library: *mut c_void,
        child: Child,
        invoke_legacy: InvokeLegacyFn,
        invoke_batch: InvokeBatchFn,
        shutdown: ShutdownFn,
        close_client: CloseClientFn,
    }

    // SAFETY: `library`/the resolved function pointers are process-wide
    // addresses valid from any thread, and `Child` is already `Send`. A session
    // is created and used by exactly one worker thread for its whole lifetime,
    // so no concurrent access to its handles ever occurs.
    unsafe impl Send for BrokerSession {}

    impl BrokerSession {
        /// Spawns `broker_exe --pipe ... --token ... --engine-root ... --parent
        /// <our pid>`, loads `RcBrokerClient.dll` next to it, and waits (up to 5s)
        /// for the handshake. `rc_exe` is only used to derive `--engine-root`
        /// (`<engine-root>/Tools/rc/rc.exe`) and to sanity-check it exists.
        /// Returns `None` on any failure — the caller falls back to direct RC.
        pub fn start(broker_exe: &Path, rc_exe: &Path) -> Option<Self> {
            if !broker_exe.is_file() {
                return None;
            }
            let engine_root = rc_exe.parent()?.parent()?.parent()?;
            if !engine_root.is_absolute()
                || !engine_root.join("Tools").join("rc").join("rc.exe").is_file()
            {
                return None;
            }
            let dll_path = broker_exe.parent()?.join("RcBrokerClient.dll");
            if !dll_path.is_file() {
                return None;
            }

            // SAFETY: `wide(&dll_path)` is a valid NUL-terminated UTF-16 string
            // that outlives this call.
            let library = unsafe { LoadLibraryW(wide(&dll_path).as_ptr()) };
            if library.is_null() {
                return None;
            }

            // SAFETY: `library` is a just-loaded, valid module handle; each
            // `resolve!` call only reads a NUL-terminated `'static` byte string
            // and the resulting `GetProcAddress` pointer, if non-null, is a valid
            // function of the concrete type named at that call site.
            let loaded = unsafe {
                (|| {
                    Some((
                        resolve!(library, "CryRcBrokerInvokeLegacyUtf8", InvokeLegacyFn)?,
                        resolve!(library, "CryRcBrokerInvokeBatchUtf8", InvokeBatchFn)?,
                        resolve!(library, "CryRcBrokerIsAvailable", IsAvailableFn)?,
                        resolve!(library, "CryRcBrokerShutdownBroker", ShutdownFn)?,
                        resolve!(library, "CryRcBrokerCloseClient", CloseClientFn)?,
                    ))
                })()
            };
            let Some((invoke_legacy, invoke_batch, is_available, shutdown, close_client)) = loaded
            else {
                unsafe { FreeLibrary(library) };
                return None;
            };

            // A fresh pipe name + token per session; the client DLL reads these
            // from *our own* process environment (it connects in-process, not the
            // broker's), so they must be set here before any broker call.
            let pipe_name = format!("texproc-{}-{}", std::process::id(), random_hex(8));
            let token = random_hex(24);
            std::env::set_var("CRY_RC_BROKER_PIPE", &pipe_name);
            std::env::set_var("CRY_RC_BROKER_TOKEN", &token);

            let mut command = Command::new(broker_exe);
            command
                .arg("--pipe")
                .arg(&pipe_name)
                .arg("--token")
                .arg(&token)
                .arg("--engine-root")
                .arg(engine_root)
                .arg("--parent")
                .arg(std::process::id().to_string())
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .creation_flags(0x0800_0000);
            let mut child = match command.spawn() {
                Ok(child) => child,
                Err(_) => {
                    unsafe { FreeLibrary(library) };
                    return None;
                }
            };

            let deadline = Instant::now() + Duration::from_secs(5);
            let available = loop {
                // SAFETY: `is_available` takes no arguments and was resolved from
                // the still-loaded `library` above.
                if unsafe { is_available() } != 0 {
                    break true;
                }
                if child.try_wait().ok().flatten().is_some() {
                    break false; // the broker process exited before coming up
                }
                if Instant::now() >= deadline {
                    break false;
                }
                thread::sleep(Duration::from_millis(100));
            };
            if !available {
                let _ = child.kill();
                let _ = child.wait();
                unsafe { FreeLibrary(library) };
                return None;
            }

            Some(Self {
                library,
                child,
                invoke_legacy,
                invoke_batch,
                shutdown,
                close_client,
            })
        }

        /// Adapts the legacy single-file RC contract (matches our existing
        /// `rc.exe <input> <options...>`, cwd = `working_dir` call shape).
        /// `None` means the broker did not accept the request — the caller must
        /// fall back to a direct spawn.
        pub fn invoke_legacy_rc(
            &self,
            input: &Path,
            options: &str,
            working_dir: &Path,
            priority: u32,
        ) -> Option<i32> {
            let input_c = path_to_cstring(input)?;
            let options_c = CString::new(options).ok()?;
            let workdir_c = path_to_cstring(working_dir)?;
            let mut exit_code: i32 = 1;
            // SAFETY: all pointers are valid, NUL-terminated C strings kept alive
            // for the duration of this call; `&mut exit_code` is a valid out-param.
            let handled = unsafe {
                (self.invoke_legacy)(
                    input_c.as_ptr(),
                    options_c.as_ptr(),
                    workdir_c.as_ptr(),
                    priority,
                    None,
                    ptr::null_mut(),
                    &mut exit_code,
                )
            };
            (handled != 0).then_some(exit_code)
        }

        /// Batched RC contract: one result per input item, same order.
        /// `results[i].handled == 0` means that item needs the caller's direct-RC
        /// fallback. Returns `None` only if the call itself was rejected outright
        /// (e.g. bad argument count) — every item then needs the fallback.
        pub fn invoke_batch_rc(
            &self,
            items: &[&BrokerBatchItem],
        ) -> Option<Vec<CryRcBrokerBatchResult>> {
            if items.is_empty() {
                return Some(Vec::new());
            }
            let requests: Vec<CryRcBrokerBatchRequestUtf8> = items
                .iter()
                .map(|item| CryRcBrokerBatchRequestUtf8 {
                    absolute_input: item.input.as_ptr(),
                    absolute_target_root: item.target_root.as_ptr(),
                    overwrite_filename: item.overwrite_filename.as_ptr(),
                    rc_options: item.options.as_ptr(),
                    estimated_bytes: item.estimated_bytes,
                    priority: 1, // Background
                    log_callback: None,
                    user_data: ptr::null_mut(),
                })
                .collect();
            let mut results = vec![
                CryRcBrokerBatchResult {
                    handled: 0,
                    exit_code: 1,
                    batch_id: 0,
                    process_id: 0
                };
                requests.len()
            ];
            // SAFETY: `requests`/`results` are correctly sized `#[repr(C)]` arrays
            // matching the DLL's declared signature; every `CString` backing a
            // `requests[i]` pointer is owned by `items` and outlives this call.
            let ok = unsafe {
                (self.invoke_batch)(requests.as_ptr(), requests.len(), results.as_mut_ptr())
            };
            (ok != 0).then_some(results)
        }
    }

    impl Drop for BrokerSession {
        fn drop(&mut self) {
            // SAFETY: both functions take no arguments and were resolved from the
            // still-loaded `library`; nothing else touches this session's FFI
            // surface after `drop` starts.
            unsafe {
                (self.shutdown)();
                (self.close_client)();
            }
            // Belt-and-suspenders: the broker's own `--parent` watch plus its Job
            // Objects already clean up if we vanish, but on a normal drop we can
            // just wait for the graceful shutdown above to have stopped it.
            let _ = self.child.kill();
            let _ = self.child.wait();
            // SAFETY: `library` is a valid handle from the matching `LoadLibraryW`
            // call in `start`, and no function pointer resolved from it is used
            // after this.
            unsafe {
                FreeLibrary(self.library);
            }
        }
    }
}

#[cfg(windows)]
#[allow(unused_imports)] // CryRcBrokerBatchResult is part of the module's public API surface
pub use imp::{BrokerBatchItem, BrokerSession, CryRcBrokerBatchResult};

#[cfg(not(windows))]
mod stub {
    use std::path::Path;

    #[derive(Clone, Copy)]
    pub struct CryRcBrokerBatchResult {
        pub handled: i32,
        pub exit_code: i32,
    }

    pub struct BrokerBatchItem;

    impl BrokerBatchItem {
        pub fn rc_dds(_tif: &Path, _output_root: &Path) -> Option<Self> {
            None
        }
    }

    pub struct BrokerSession;

    impl BrokerSession {
        pub fn start(_broker_exe: &Path, _rc_exe: &Path) -> Option<Self> {
            None
        }

        pub fn invoke_legacy_rc(
            &self,
            _input: &Path,
            _options: &str,
            _working_dir: &Path,
            _priority: u32,
        ) -> Option<i32> {
            None
        }

        pub fn invoke_batch_rc(
            &self,
            _items: &[&BrokerBatchItem],
        ) -> Option<Vec<CryRcBrokerBatchResult>> {
            None
        }
    }
}

#[cfg(not(windows))]
pub use stub::{BrokerBatchItem, BrokerSession, CryRcBrokerBatchResult};
