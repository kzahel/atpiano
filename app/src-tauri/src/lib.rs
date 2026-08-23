use serde::{Deserialize, Serialize};
use std::{
    env,
    ffi::OsStr,
    fmt::Write as _,
    fs::{self, File, OpenOptions},
    io::{self, BufRead, BufReader, Read, Write},
    net::{SocketAddr, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        mpsc, Arc, Mutex, RwLock,
    },
    thread,
    time::{Duration, Instant},
};
use tauri::{Emitter, Manager};
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_opener::OpenerExt;

mod desktop_score;

const DESKTOP_PROTOCOL: &str = "atpiano.desktop.v1";
const CONTRACT_SCHEMA: &str = "atpiano.contract.v1";
const MODEL_PACK_ID: &str = "atpiano-cpu-models-2026.07";
const UPDATE_ENDPOINT: &str =
    "https://updates.graehlarts.com/atpiano/tauri/{{target}}/{{arch}}/{{current_version}}";
const INSTALL_ID_FILE: &str = "cfu-id";
const MAX_READY_BYTES: usize = 64 * 1024;
const MAX_HANDSHAKE_BYTES: u64 = 1024 * 1024;
const MAX_ARTIFACT_HEADER_BYTES: usize = 64 * 1024;
const MAX_ARTIFACT_URL_BYTES: usize = 4 * 1024;
const STARTUP_TIMEOUT: Duration = Duration::from_secs(30);

#[derive(Clone, Copy, Debug, PartialEq)]
struct DesktopTarget {
    platform: &'static str,
    architecture: &'static str,
    python_relative: &'static str,
    package_type: &'static str,
    origin: &'static str,
}

const MACOS_ARM64_TARGET: DesktopTarget = DesktopTarget {
    platform: "macos",
    architecture: "arm64",
    python_relative: "bin/python3",
    package_type: "app",
    origin: "tauri://localhost",
};

const WINDOWS_X86_64_TARGET: DesktopTarget = DesktopTarget {
    platform: "windows",
    architecture: "x86_64",
    python_relative: "python.exe",
    package_type: "nsis",
    origin: "http://tauri.localhost",
};

fn desktop_target_for(os: &str, architecture: &str) -> Result<DesktopTarget, String> {
    match (os, architecture) {
        ("macos", "aarch64") => Ok(MACOS_ARM64_TARGET),
        ("windows", "x86_64") => Ok(WINDOWS_X86_64_TARGET),
        _ => Err("desktop builds require macOS arm64 or Windows x86_64".to_string()),
    }
}

fn current_desktop_target() -> Result<DesktopTarget, String> {
    desktop_target_for(env::consts::OS, env::consts::ARCH)
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
struct DesktopRuntimeInfo {
    app_version: String,
    base_url: String,
    bearer_token: String,
    web_socket_protocol: String,
    protocol_version: String,
    contract_schema_version: String,
    sidecar_version: String,
    platform: String,
    architecture: String,
    execution_backend: String,
    model_pack_id: String,
    model_pack_sha256: String,
    score_available: bool,
    installation_id: String,
    package_type: String,
    update_endpoint: String,
}

#[derive(Debug, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
struct DesktopArtifactExportResult {
    saved: bool,
    file_name: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct ReadyRecord {
    schema_version: String,
    protocol_version: String,
    contract_schema_version: String,
    sidecar_version: String,
    host: String,
    port: u16,
    platform: String,
    architecture: String,
    execution_backend: String,
    model_pack_id: String,
    model_pack_sha256: String,
}

#[derive(Debug, Deserialize)]
struct HandshakeRecord {
    schema_version: String,
    compatible: bool,
    protocol_version: String,
    contract_schema_version: String,
    sidecar_version: String,
    platform: String,
    architecture: String,
    execution_backend: String,
    model_pack: HandshakeModelPack,
    model_pack_sha256: String,
    storage_policy: String,
    score_available: bool,
}

#[derive(Debug, Deserialize)]
struct HandshakeModelPack {
    model_pack_id: String,
}

#[derive(Clone)]
enum RuntimeStatus {
    Initializing,
    Ready(Box<DesktopRuntimeInfo>),
    Failed(String),
}

struct DesktopProcess {
    child: Arc<Mutex<Child>>,
    expected_shutdown: Arc<AtomicBool>,
}

struct DesktopState {
    status: Arc<RwLock<RuntimeStatus>>,
    process: Mutex<Option<DesktopProcess>>,
}

impl DesktopState {
    fn shutdown(&self) {
        if let Ok(mut process) = self.process.lock() {
            if let Some(process) = process.take() {
                process.shutdown();
            }
        }
    }

    fn prepare_update_install(&self) -> Result<(), String> {
        if !matches!(
            &*self
                .status
                .read()
                .map_err(|_| "desktop runtime state is unavailable".to_string())?,
            RuntimeStatus::Ready(_)
        ) {
            return Err("The local engine is not ready for an update.".to_string());
        }
        let process = self
            .process
            .lock()
            .map_err(|_| "desktop process state is unavailable".to_string())?
            .take()
            .ok_or_else(|| "The local engine is already stopped.".to_string())?;
        process.shutdown();
        if let Ok(mut status) = self.status.write() {
            *status = RuntimeStatus::Initializing;
        }
        Ok(())
    }

    fn resume_after_update_failure(
        &self,
        app: &tauri::AppHandle,
        installation_id: &str,
    ) -> Result<(), String> {
        let mut slot = self
            .process
            .lock()
            .map_err(|_| "desktop process state is unavailable".to_string())?;
        if slot.is_some() {
            return Ok(());
        }
        if let Ok(mut status) = self.status.write() {
            *status = RuntimeStatus::Initializing;
        }
        match start_sidecar(app, Arc::clone(&self.status), installation_id) {
            Ok((process, info)) => {
                if let Ok(mut status) = self.status.write() {
                    *status = RuntimeStatus::Ready(Box::new(info));
                }
                *slot = Some(process);
                Ok(())
            }
            Err(error) => {
                if let Ok(mut status) = self.status.write() {
                    *status = RuntimeStatus::Failed(error.clone());
                }
                Err(error)
            }
        }
    }
}

impl Drop for DesktopState {
    fn drop(&mut self) {
        self.shutdown();
    }
}

impl DesktopProcess {
    fn shutdown(self) {
        self.expected_shutdown.store(true, Ordering::SeqCst);
        let deadline = Instant::now() + Duration::from_secs(3);
        if let Ok(mut child) = self.child.lock() {
            drop(child.stdin.take());
        }
        while Instant::now() < deadline {
            if let Ok(mut child) = self.child.lock() {
                match child.try_wait() {
                    Ok(Some(_)) => return,
                    Ok(None) => {}
                    Err(_) => break,
                }
            }
            thread::sleep(Duration::from_millis(50));
        }
        if let Ok(mut child) = self.child.lock() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

fn token() -> Result<String, String> {
    let mut bytes = [0_u8; 32];
    getrandom::fill(&mut bytes)
        .map_err(|error| format!("could not create desktop credentials: {error}"))?;
    let mut encoded = String::with_capacity(64);
    for byte in bytes {
        write!(&mut encoded, "{byte:02x}")
            .map_err(|_| "could not encode desktop credentials".to_string())?;
    }
    Ok(encoded)
}

fn read_valid_installation_id(path: &Path) -> Option<String> {
    let value = fs::read_to_string(path).ok()?;
    let value = value.trim();
    uuid::Uuid::parse_str(value).ok()?;
    Some(value.to_owned())
}

fn get_or_create_installation_id(config_dir: &Path) -> Result<String, String> {
    let path = config_dir.join(INSTALL_ID_FILE);
    if let Some(id) = read_valid_installation_id(&path) {
        return Ok(id);
    }
    fs::create_dir_all(config_dir)
        .map_err(|error| format!("could not create desktop config directory: {error}"))?;
    let id = uuid::Uuid::new_v4().to_string();
    let temporary = config_dir.join(format!("{INSTALL_ID_FILE}.tmp"));
    fs::write(&temporary, format!("{id}\n"))
        .map_err(|error| format!("could not write installation identity: {error}"))?;
    fs::rename(&temporary, &path)
        .map_err(|error| format!("could not publish installation identity: {error}"))?;
    Ok(id)
}

fn resource_dir_for_executable(executable: &Path, target: DesktopTarget) -> Option<PathBuf> {
    if target == MACOS_ARM64_TARGET {
        let macos = executable.parent()?;
        if macos.file_name()? != "MacOS" {
            return None;
        }
        let contents = macos.parent()?;
        if contents.file_name()? != "Contents" {
            return None;
        }
        return Some(contents.join("Resources"));
    }
    if target == WINDOWS_X86_64_TARGET {
        return executable.parent().map(Path::to_path_buf);
    }
    None
}

fn runtime_root(app: &tauri::AppHandle, target: DesktopTarget) -> Result<PathBuf, String> {
    #[cfg(debug_assertions)]
    if let Some(override_path) = env::var_os("ATPIANO_DESKTOP_RUNTIME_ROOT") {
        return Ok(PathBuf::from(override_path));
    }
    match app.path().resource_dir() {
        Ok(directory) => Ok(directory.join("desktop-runtime")),
        Err(error) => {
            let fallback = env::current_exe()
                .ok()
                .and_then(|executable| resource_dir_for_executable(&executable, target))
                .filter(|directory| directory.is_dir());
            fallback
                .map(|directory| directory.join("desktop-runtime"))
                .ok_or_else(|| format!("could not locate desktop resources: {error}"))
        }
    }
}

fn require_file(path: &Path, label: &str) -> Result<(), String> {
    if path.is_file() {
        Ok(())
    } else {
        Err(format!("desktop {label} is missing"))
    }
}

fn read_ready(reader: &mut BufReader<impl Read>) -> Result<ReadyRecord, String> {
    let mut bytes = Vec::new();
    reader
        .take((MAX_READY_BYTES + 1) as u64)
        .read_until(b'\n', &mut bytes)
        .map_err(|error| format!("could not read desktop startup record: {error}"))?;
    if bytes.len() > MAX_READY_BYTES || !bytes.ends_with(b"\n") {
        return Err("desktop startup record exceeded its bound".to_string());
    }
    serde_json::from_slice(&bytes)
        .map_err(|error| format!("desktop startup record is invalid: {error}"))
}

fn validate_ready(ready: &ReadyRecord, target: DesktopTarget) -> Result<(), String> {
    if ready.schema_version != "atpiano.desktop-ready.v1"
        || ready.protocol_version != DESKTOP_PROTOCOL
        || ready.contract_schema_version != CONTRACT_SCHEMA
        || ready.host != "127.0.0.1"
        || ready.platform != target.platform
        || ready.architecture != target.architecture
        || ready.execution_backend != "cpu"
        || ready.model_pack_id != MODEL_PACK_ID
        || !is_lower_hex_64(&ready.model_pack_sha256)
    {
        return Err("desktop startup record is incompatible".to_string());
    }
    Ok(())
}

fn is_lower_hex_64(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn valid_encoded_path_segment(value: &str) -> bool {
    if value.is_empty() {
        return false;
    }
    let bytes = value.as_bytes();
    let mut decoded = Vec::with_capacity(bytes.len());
    let mut index = 0;
    while index < bytes.len() {
        let byte = bytes[index];
        if byte == b'%' {
            if index + 2 >= bytes.len()
                || !bytes[index + 1].is_ascii_hexdigit()
                || !bytes[index + 2].is_ascii_hexdigit()
            {
                return false;
            }
            let high = (bytes[index + 1] as char).to_digit(16).unwrap_or(16);
            let low = (bytes[index + 2] as char).to_digit(16).unwrap_or(16);
            let decoded_byte = (high * 16 + low) as u8;
            if !(decoded_byte.is_ascii_alphanumeric()
                || matches!(decoded_byte, b'-' | b'.' | b'_' | b'~' | b':'))
            {
                return false;
            }
            decoded.push(decoded_byte);
            index += 3;
            continue;
        }
        if !(byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'.' | b'_' | b'~' | b':')) {
            return false;
        }
        decoded.push(byte);
        index += 1;
    }
    decoded != b"." && decoded != b".."
}

fn valid_artifact_url(value: &str) -> bool {
    if value.len() > MAX_ARTIFACT_URL_BYTES || !value.is_ascii() {
        return false;
    }
    let segments = value.split('/').collect::<Vec<_>>();
    segments.len() == 10
        && segments[0].is_empty()
        && segments[1] == "api"
        && segments[2] == "v1"
        && segments[3] == "workspaces"
        && valid_encoded_path_segment(segments[4])
        && segments[5] == "sessions"
        && valid_encoded_path_segment(segments[6])
        && segments[7] == "artifacts"
        && valid_encoded_path_segment(segments[8])
        && segments[9] == "content"
}

fn valid_suggested_name(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 255
        && value != "."
        && value != ".."
        && !value.contains('\0')
        && Path::new(value)
            .file_name()
            .is_some_and(|name| name == OsStr::new(value))
}

fn runtime_port(info: &DesktopRuntimeInfo) -> Result<u16, String> {
    info.base_url
        .strip_prefix("http://127.0.0.1:")
        .and_then(|value| value.parse::<u16>().ok())
        .filter(|port| *port > 0)
        .ok_or_else(|| "desktop artifact export has no valid loopback port".to_string())
}

fn read_artifact_header_line(
    reader: &mut impl BufRead,
    total: &mut usize,
) -> Result<Vec<u8>, String> {
    let remaining = MAX_ARTIFACT_HEADER_BYTES.saturating_sub(*total);
    let mut line = Vec::new();
    (&mut *reader)
        .take((remaining + 1) as u64)
        .read_until(b'\n', &mut line)
        .map_err(|error| format!("artifact export response failed: {error}"))?;
    *total += line.len();
    if *total > MAX_ARTIFACT_HEADER_BYTES || !line.ends_with(b"\n") {
        return Err("artifact export response headers exceeded their bound".to_string());
    }
    Ok(line)
}

fn read_artifact_response(reader: &mut impl BufRead) -> Result<u64, String> {
    let mut total = 0;
    let mut line = read_artifact_header_line(reader, &mut total)?;
    let status = std::str::from_utf8(&line)
        .map_err(|_| "artifact export response status is invalid".to_string())?;
    if status.split_whitespace().nth(1) != Some("200") {
        let code = status.split_whitespace().nth(1).unwrap_or("invalid");
        return Err(format!("artifact export was rejected with HTTP {code}"));
    }

    let mut content_length = None;
    loop {
        line = read_artifact_header_line(reader, &mut total)?;
        if line == b"\r\n" || line == b"\n" {
            break;
        }
        let header = std::str::from_utf8(&line)
            .map_err(|_| "artifact export response header is invalid".to_string())?;
        let (name, value) = header
            .trim_end_matches(['\r', '\n'])
            .split_once(':')
            .ok_or_else(|| "artifact export response header is malformed".to_string())?;
        if name.eq_ignore_ascii_case("transfer-encoding") {
            return Err("artifact export does not accept transfer encoding".to_string());
        }
        if name.eq_ignore_ascii_case("content-length") {
            let parsed = value
                .trim()
                .parse::<u64>()
                .map_err(|_| "artifact export content length is invalid".to_string())?;
            if content_length.replace(parsed).is_some() {
                return Err("artifact export content length is duplicated".to_string());
            }
        }
    }
    content_length.ok_or_else(|| "artifact export response has no content length".to_string())
}

fn temporary_export_file(destination: &Path) -> Result<(PathBuf, File), String> {
    if !destination.is_absolute() || destination.file_name().is_none() {
        return Err("artifact export destination is invalid".to_string());
    }
    let parent = destination
        .parent()
        .ok_or_else(|| "artifact export destination has no parent".to_string())?;
    let file_name = destination
        .file_name()
        .and_then(OsStr::to_str)
        .ok_or_else(|| "artifact export filename is invalid".to_string())?;
    for _ in 0..8 {
        let suffix = token()?;
        let temporary = parent.join(format!(".{file_name}.atpiano-{}.part", &suffix[..16]));
        match OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(&temporary)
        {
            Ok(file) => return Ok((temporary, file)),
            Err(error) if error.kind() == io::ErrorKind::AlreadyExists => continue,
            Err(error) => {
                return Err(format!(
                    "could not create the artifact export file: {error}"
                ))
            }
        }
    }
    Err("could not reserve an artifact export file".to_string())
}

fn download_artifact(
    port: u16,
    credential: &str,
    origin: &str,
    artifact_url: &str,
    destination: &Path,
) -> Result<(), String> {
    if !valid_artifact_url(artifact_url) {
        return Err("desktop artifact export target is invalid".to_string());
    }
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let mut stream = TcpStream::connect_timeout(&address, Duration::from_secs(5))
        .map_err(|error| format!("artifact export connection failed: {error}"))?;
    stream
        .set_read_timeout(Some(Duration::from_secs(60)))
        .map_err(|error| format!("could not bound artifact export: {error}"))?;
    stream
        .set_write_timeout(Some(Duration::from_secs(5)))
        .map_err(|error| format!("could not bound artifact export: {error}"))?;
    write!(
        stream,
        "GET {artifact_url} HTTP/1.0\r\n\
         Host: 127.0.0.1:{port}\r\n\
         Origin: {origin}\r\n\
         Authorization: Bearer {credential}\r\n\
         Connection: close\r\n\r\n"
    )
    .map_err(|error| format!("artifact export request failed: {error}"))?;

    let mut reader = BufReader::new(stream);
    let content_length = read_artifact_response(&mut reader)?;
    let (temporary, mut output) = temporary_export_file(destination)?;
    let result = (|| {
        let copied = io::copy(&mut reader.take(content_length), &mut output)
            .map_err(|error| format!("artifact export transfer failed: {error}"))?;
        if copied != content_length {
            return Err("artifact export ended before its declared length".to_string());
        }
        output
            .sync_all()
            .map_err(|error| format!("could not finish artifact export: {error}"))?;
        fs::rename(&temporary, destination)
            .map_err(|error| format!("could not publish artifact export: {error}"))
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temporary);
    }
    result
}

fn fetch_handshake(port: u16, credential: &str, origin: &str) -> Result<HandshakeRecord, String> {
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let mut stream = TcpStream::connect_timeout(&address, Duration::from_secs(5))
        .map_err(|error| format!("desktop handshake connection failed: {error}"))?;
    stream
        .set_read_timeout(Some(Duration::from_secs(5)))
        .map_err(|error| format!("could not bound desktop handshake: {error}"))?;
    stream
        .set_write_timeout(Some(Duration::from_secs(5)))
        .map_err(|error| format!("could not bound desktop handshake: {error}"))?;
    write!(
        stream,
        "GET /desktop/v1/handshake HTTP/1.0\r\n\
         Host: 127.0.0.1:{port}\r\n\
         Origin: {origin}\r\n\
         Authorization: Bearer {credential}\r\n\
         Connection: close\r\n\r\n"
    )
    .map_err(|error| format!("desktop handshake request failed: {error}"))?;
    let mut response = Vec::new();
    stream
        .take(MAX_HANDSHAKE_BYTES + 1)
        .read_to_end(&mut response)
        .map_err(|error| format!("desktop handshake response failed: {error}"))?;
    if response.len() as u64 > MAX_HANDSHAKE_BYTES {
        return Err("desktop handshake response exceeded its bound".to_string());
    }
    let header_end = response
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .ok_or_else(|| "desktop handshake response is malformed".to_string())?;
    let headers = &response[..header_end];
    if !headers.starts_with(b"HTTP/1.0 200") && !headers.starts_with(b"HTTP/1.1 200") {
        return Err("desktop handshake was rejected".to_string());
    }
    serde_json::from_slice(&response[header_end + 4..])
        .map_err(|error| format!("desktop handshake is invalid: {error}"))
}

fn validate_handshake(handshake: &HandshakeRecord, ready: &ReadyRecord) -> Result<(), String> {
    if handshake.schema_version != "atpiano.desktop-handshake.v1"
        || !handshake.compatible
        || handshake.protocol_version != DESKTOP_PROTOCOL
        || handshake.contract_schema_version != CONTRACT_SCHEMA
        || handshake.sidecar_version != ready.sidecar_version
        || handshake.platform != ready.platform
        || handshake.architecture != ready.architecture
        || handshake.execution_backend != "cpu"
        || handshake.model_pack.model_pack_id != MODEL_PACK_ID
        || handshake.model_pack_sha256 != ready.model_pack_sha256
        || handshake.storage_policy != "verified-mp3-default"
    {
        return Err("desktop handshake is incompatible".to_string());
    }
    Ok(())
}

fn last_stderr(lines: &Arc<Mutex<Vec<String>>>, credential: &str) -> String {
    let last = lines
        .lock()
        .ok()
        .and_then(|lines| lines.last().cloned())
        .unwrap_or_default();
    last.replace(credential, "[redacted]")
}

fn record_unexpected_exit(
    status: &RwLock<RuntimeStatus>,
    expected_shutdown: bool,
    exit_status: &str,
    detail: &str,
) -> Option<String> {
    if expected_shutdown {
        return None;
    }
    let message = if detail.is_empty() {
        format!("The local engine stopped unexpectedly ({exit_status}).")
    } else {
        format!("The local engine stopped unexpectedly ({exit_status}): {detail}")
    };
    if let Ok(mut state) = status.write() {
        if matches!(*state, RuntimeStatus::Failed(_)) {
            return None;
        }
        *state = RuntimeStatus::Failed(message.clone());
        return Some(message);
    }
    None
}

fn monitor_child(
    app: tauri::AppHandle,
    child: Arc<Mutex<Child>>,
    expected_shutdown: Arc<AtomicBool>,
    status: Arc<RwLock<RuntimeStatus>>,
    stderr_lines: Arc<Mutex<Vec<String>>>,
    credential: String,
) {
    thread::spawn(move || loop {
        let exit_status = child
            .lock()
            .ok()
            .and_then(|mut child| child.try_wait().ok())
            .flatten();
        if let Some(exit_status) = exit_status {
            let detail = last_stderr(&stderr_lines, &credential);
            if let Some(message) = record_unexpected_exit(
                &status,
                expected_shutdown.load(Ordering::SeqCst),
                &exit_status.to_string(),
                &detail,
            ) {
                let _ = app.emit("desktop-runtime-failed", message);
            }
            return;
        }
        thread::sleep(Duration::from_millis(250));
    });
}

fn configure_sidecar_environment(
    command: &mut Command,
    target: DesktopTarget,
    runtime: &Path,
    workspace: &Path,
    credential: &str,
) -> Result<(), String> {
    let cache_root = workspace.join(".runtime-cache");
    let mut path_entries = if target == WINDOWS_X86_64_TARGET {
        vec![
            runtime.to_path_buf(),
            runtime.join("Scripts"),
            runtime.join("bin"),
        ]
    } else {
        vec![runtime.join("bin")]
    };
    if let Some(existing) = env::var_os("PATH") {
        path_entries.extend(env::split_paths(&existing));
    }
    let path = env::join_paths(path_entries)
        .map_err(|error| format!("could not construct desktop runtime PATH: {error}"))?;
    command
        .env("ATPIANO_DESKTOP_TOKEN", credential)
        .env("ATPIANO_EXECUTION_BACKEND", "cpu")
        .env("CUDA_VISIBLE_DEVICES", "")
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .env("PYTHONNOUSERSITE", "1")
        .env("NUMBA_CACHE_DIR", cache_root.join("numba"))
        .env("MPLCONFIGDIR", cache_root.join("matplotlib"))
        .env("XDG_CACHE_HOME", &cache_root)
        .env("HF_HOME", cache_root.join("huggingface"))
        .env("PATH", path)
        .env_remove("PYTHONHOME")
        .env_remove("PYTHONPATH")
        .env_remove("VIRTUAL_ENV")
        .env_remove("ATPIANO_BASIC_PITCH_MODEL")
        .env_remove("ATPIANO_TRANSKUN_CHECKPOINT")
        .env_remove("ATPIANO_TRANSKUN_CONFIG");
    Ok(())
}

fn start_sidecar(
    app: &tauri::AppHandle,
    status: Arc<RwLock<RuntimeStatus>>,
    installation_id: &str,
) -> Result<(DesktopProcess, DesktopRuntimeInfo), String> {
    let target = current_desktop_target()?;
    let runtime = runtime_root(app, target)?;
    let python = runtime.join(target.python_relative);
    let model_pack = runtime.join("model-pack/model-pack.json");
    let replay_manifest = runtime.join("fixture/input.json");
    let score_runtime = desktop_score::active_runtime(app, target.platform, target.architecture);
    require_file(&python, "Python runtime")?;
    require_file(&model_pack, "model pack")?;
    require_file(&replay_manifest, "replay fixture")?;

    let workspace = app
        .path()
        .app_data_dir()
        .map_err(|error| format!("could not locate desktop data: {error}"))?
        .join("workspace");
    fs::create_dir_all(&workspace)
        .map_err(|error| format!("could not create desktop workspace: {error}"))?;

    let credential = token()?;
    let mut command = Command::new(&python);
    command
        .arg("-I")
        .arg("-B")
        .arg("-m")
        .arg("atpiano.desktop_sidecar")
        .arg("--workspace")
        .arg(&workspace)
        .arg("--replay-manifest")
        .arg(&replay_manifest)
        .arg("--model-pack")
        .arg(&model_pack)
        .arg("--expected-model-pack")
        .arg(MODEL_PACK_ID)
        .arg("--expected-protocol")
        .arg(DESKTOP_PROTOCOL)
        .arg("--expected-contract")
        .arg(CONTRACT_SCHEMA)
        .arg("--desktop-origin")
        .arg(target.origin)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    if let Some(score_runtime) = score_runtime {
        command.arg("--score-runtime").arg(score_runtime);
    }
    configure_sidecar_environment(&mut command, target, &runtime, &workspace, &credential)?;
    let mut child = command
        .spawn()
        .map_err(|error| format!("could not start the local engine: {error}"))?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "local engine stdout is unavailable".to_string())?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| "local engine stderr is unavailable".to_string())?;
    let child = Arc::new(Mutex::new(child));
    let stderr_lines = Arc::new(Mutex::new(Vec::new()));
    let stderr_target = Arc::clone(&stderr_lines);
    thread::spawn(move || {
        for line in BufReader::new(stderr).lines().map_while(Result::ok) {
            if let Ok(mut lines) = stderr_target.lock() {
                lines.push(line);
                if lines.len() > 16 {
                    lines.remove(0);
                }
            }
        }
    });

    let (sender, receiver) = mpsc::sync_channel(1);
    thread::spawn(move || {
        let mut reader = BufReader::new(stdout);
        let record = read_ready(&mut reader);
        let _ = sender.send(record);
        let _ = io::copy(&mut reader, &mut io::sink());
    });
    let ready = match receiver.recv_timeout(STARTUP_TIMEOUT) {
        Ok(Ok(ready)) => ready,
        Ok(Err(error)) => {
            let process = DesktopProcess {
                child,
                expected_shutdown: Arc::new(AtomicBool::new(true)),
            };
            process.shutdown();
            return Err(error);
        }
        Err(_) => {
            let process = DesktopProcess {
                child,
                expected_shutdown: Arc::new(AtomicBool::new(true)),
            };
            process.shutdown();
            return Err("local engine startup timed out".to_string());
        }
    };
    if let Err(error) = validate_ready(&ready, target) {
        DesktopProcess {
            child,
            expected_shutdown: Arc::new(AtomicBool::new(true)),
        }
        .shutdown();
        return Err(error);
    }
    let handshake = match fetch_handshake(ready.port, &credential, target.origin) {
        Ok(handshake) => handshake,
        Err(error) => {
            DesktopProcess {
                child,
                expected_shutdown: Arc::new(AtomicBool::new(true)),
            }
            .shutdown();
            return Err(error);
        }
    };
    if let Err(error) = validate_handshake(&handshake, &ready) {
        DesktopProcess {
            child,
            expected_shutdown: Arc::new(AtomicBool::new(true)),
        }
        .shutdown();
        return Err(error);
    }

    let info = DesktopRuntimeInfo {
        app_version: env!("CARGO_PKG_VERSION").to_string(),
        base_url: format!("http://127.0.0.1:{}", ready.port),
        bearer_token: credential.clone(),
        web_socket_protocol: format!("{DESKTOP_PROTOCOL}.{credential}"),
        protocol_version: ready.protocol_version,
        contract_schema_version: ready.contract_schema_version,
        sidecar_version: ready.sidecar_version,
        platform: ready.platform,
        architecture: ready.architecture,
        execution_backend: ready.execution_backend,
        model_pack_id: ready.model_pack_id,
        model_pack_sha256: ready.model_pack_sha256,
        score_available: handshake.score_available,
        installation_id: installation_id.to_string(),
        package_type: target.package_type.to_string(),
        update_endpoint: UPDATE_ENDPOINT.to_string(),
    };
    let expected_shutdown = Arc::new(AtomicBool::new(false));
    monitor_child(
        app.clone(),
        Arc::clone(&child),
        Arc::clone(&expected_shutdown),
        Arc::clone(&status),
        stderr_lines,
        credential,
    );
    Ok((
        DesktopProcess {
            child,
            expected_shutdown,
        },
        info,
    ))
}

fn current_runtime_info(status: &RwLock<RuntimeStatus>) -> Result<DesktopRuntimeInfo, String> {
    match status
        .read()
        .map_err(|_| "desktop runtime state is unavailable".to_string())?
        .clone()
    {
        RuntimeStatus::Ready(info) => Ok(*info),
        RuntimeStatus::Failed(error) => Err(error),
        RuntimeStatus::Initializing => Err("The local engine is still starting.".to_string()),
    }
}

#[tauri::command]
fn desktop_runtime(state: tauri::State<'_, DesktopState>) -> Result<DesktopRuntimeInfo, String> {
    current_runtime_info(&state.status)
}

#[tauri::command]
fn desktop_score_runtime_status(
    app: tauri::AppHandle,
    state: tauri::State<'_, desktop_score::ScoreAcquisitionState>,
) -> Result<desktop_score::ScoreRuntimeStatus, String> {
    let target = current_desktop_target()?;
    desktop_score::status(&app, &state, target.platform, target.architecture)
}

#[tauri::command(async)]
async fn desktop_score_acquire(
    app: tauri::AppHandle,
    state: tauri::State<'_, desktop_score::ScoreAcquisitionState>,
    acknowledged: bool,
) -> Result<desktop_score::ScoreRuntimeStatus, String> {
    let target = current_desktop_target()?;
    let operation = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        desktop_score::acquire(
            &app,
            operation,
            target.platform,
            target.architecture,
            acknowledged,
        )
    })
    .await
    .map_err(|error| format!("score model operation stopped unexpectedly: {error}"))?
}

#[tauri::command(async)]
async fn desktop_score_remove(
    app: tauri::AppHandle,
    state: tauri::State<'_, desktop_score::ScoreAcquisitionState>,
) -> Result<desktop_score::ScoreRuntimeStatus, String> {
    let target = current_desktop_target()?;
    let operation = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        desktop_score::remove(&app, operation, target.platform, target.architecture)
    })
    .await
    .map_err(|error| format!("score model operation stopped unexpectedly: {error}"))?
}

#[tauri::command]
fn desktop_score_cancel(state: tauri::State<'_, desktop_score::ScoreAcquisitionState>) -> bool {
    state.cancel()
}

#[tauri::command]
fn desktop_score_open_link(app: tauri::AppHandle, link_id: String) -> Result<(), String> {
    let url = desktop_score::link_url(&link_id)?;
    app.opener()
        .open_url(url, None::<&str>)
        .map_err(|error| format!("could not open the score model link: {error}"))
}

#[tauri::command(async)]
fn desktop_prepare_update_install(
    state: tauri::State<'_, DesktopState>,
    score_state: tauri::State<'_, desktop_score::ScoreAcquisitionState>,
) -> Result<(), String> {
    if score_state.is_running() {
        return Err("Wait for the research model operation to finish.".to_string());
    }
    state.prepare_update_install()
}

#[tauri::command(async)]
fn desktop_resume_after_update_failure(
    app: tauri::AppHandle,
    state: tauri::State<'_, DesktopState>,
) -> Result<(), String> {
    let info = current_runtime_info(&state.status).ok();
    let installation_id =
        info.as_ref()
            .map(|value| value.installation_id.clone())
            .or_else(|| {
                app.path().app_config_dir().ok().and_then(|directory| {
                    read_valid_installation_id(&directory.join(INSTALL_ID_FILE))
                })
            })
            .ok_or_else(|| "The installation identity is unavailable.".to_string())?;
    state.resume_after_update_failure(&app, &installation_id)
}

#[tauri::command(async)]
fn desktop_export_artifact(
    app: tauri::AppHandle,
    state: tauri::State<'_, DesktopState>,
    artifact_url: String,
    suggested_name: String,
) -> Result<DesktopArtifactExportResult, String> {
    if !valid_artifact_url(&artifact_url) || !valid_suggested_name(&suggested_name) {
        return Err("desktop artifact export request is invalid".to_string());
    }
    let info = current_runtime_info(&state.status)?;
    let target = current_desktop_target()?;
    let port = runtime_port(&info)?;
    let destination = app
        .dialog()
        .file()
        .set_title("Export Atpiano artifact")
        .set_file_name(&suggested_name)
        .blocking_save_file();
    let Some(destination) = destination else {
        return Ok(DesktopArtifactExportResult {
            saved: false,
            file_name: None,
        });
    };
    let destination = destination
        .into_path()
        .map_err(|_| "artifact export destination is not a local file".to_string())?;
    download_artifact(
        port,
        &info.bearer_token,
        target.origin,
        &artifact_url,
        &destination,
    )?;
    Ok(DesktopArtifactExportResult {
        saved: true,
        file_name: destination
            .file_name()
            .map(|value| value.to_string_lossy().into_owned()),
    })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let application = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            let config_dir = app
                .path()
                .app_config_dir()
                .map_err(|error| format!("could not locate desktop config: {error}"))?;
            let installation_id = get_or_create_installation_id(&config_dir)?;
            let updater = tauri_plugin_updater::Builder::new()
                .header("X-CFU-Id", &installation_id)?
                .build();
            app.handle().plugin(updater)?;
            let status = Arc::new(RwLock::new(RuntimeStatus::Initializing));
            let result = start_sidecar(app.handle(), Arc::clone(&status), &installation_id);
            let process = match result {
                Ok((process, info)) => {
                    if let Ok(mut current) = status.write() {
                        *current = RuntimeStatus::Ready(Box::new(info));
                    }
                    Some(process)
                }
                Err(error) => {
                    if let Ok(mut current) = status.write() {
                        *current = RuntimeStatus::Failed(error);
                    }
                    None
                }
            };
            app.manage(DesktopState {
                status,
                process: Mutex::new(process),
            });
            app.manage(desktop_score::ScoreAcquisitionState::default());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            desktop_runtime,
            desktop_score_runtime_status,
            desktop_score_acquire,
            desktop_score_cancel,
            desktop_score_remove,
            desktop_score_open_link,
            desktop_export_artifact,
            desktop_prepare_update_install,
            desktop_resume_after_update_failure
        ])
        .build(tauri::generate_context!())
        .expect("error while building Atpiano");

    application.run(|handle, event| {
        if matches!(
            event,
            tauri::RunEvent::Exit | tauri::RunEvent::ExitRequested { .. }
        ) {
            handle.state::<DesktopState>().shutdown();
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;

    fn artifact_server(
        response: Vec<u8>,
        expected_path: &'static str,
        expected_credential: String,
        expected_origin: &'static str,
    ) -> (u16, thread::JoinHandle<()>) {
        let listener = TcpListener::bind(("127.0.0.1", 0)).expect("test listener");
        let port = listener.local_addr().expect("listener address").port();
        let handle = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("artifact connection");
            let mut request = Vec::new();
            let mut byte = [0_u8; 1];
            while !request.ends_with(b"\r\n\r\n") {
                assert!(request.len() < MAX_ARTIFACT_HEADER_BYTES);
                stream.read_exact(&mut byte).expect("artifact request");
                request.push(byte[0]);
            }
            let request = String::from_utf8(request).expect("ASCII request");
            assert!(request.starts_with(&format!("GET {expected_path} HTTP/1.0\r\n")));
            assert!(request.contains(&format!(
                "\r\nAuthorization: Bearer {expected_credential}\r\n"
            )));
            assert!(request.contains(&format!("\r\nOrigin: {expected_origin}\r\n")));
            stream.write_all(&response).expect("artifact response");
        });
        (port, handle)
    }

    fn export_test_directory(label: &str) -> PathBuf {
        let path = env::temp_dir().join(format!(
            "atpiano-{label}-{}",
            &token().expect("test token")[..16]
        ));
        fs::create_dir(&path).expect("test directory");
        path
    }

    fn runtime_info_fixture() -> DesktopRuntimeInfo {
        DesktopRuntimeInfo {
            app_version: "0.1.0".to_string(),
            base_url: "http://127.0.0.1:49152".to_string(),
            bearer_token: "a".repeat(64),
            web_socket_protocol: format!("{DESKTOP_PROTOCOL}.{}", "a".repeat(64)),
            protocol_version: DESKTOP_PROTOCOL.to_string(),
            contract_schema_version: CONTRACT_SCHEMA.to_string(),
            sidecar_version: "0.1.0".to_string(),
            platform: "macos".to_string(),
            architecture: "arm64".to_string(),
            execution_backend: "cpu".to_string(),
            model_pack_id: MODEL_PACK_ID.to_string(),
            model_pack_sha256: "b".repeat(64),
            score_available: false,
            installation_id: "0198be8e-ebcf-7f2a-8dc0-7d54cbf49621".to_string(),
            package_type: "app".to_string(),
            update_endpoint: UPDATE_ENDPOINT.to_string(),
        }
    }

    #[test]
    fn installation_id_is_stable_and_valid() {
        let directory = tempfile::tempdir().expect("temporary directory");
        let first = get_or_create_installation_id(directory.path()).expect("create ID");
        let second = get_or_create_installation_id(directory.path()).expect("read ID");
        assert_eq!(first, second);
        assert!(uuid::Uuid::parse_str(&first).is_ok());
    }

    #[test]
    fn malformed_installation_id_is_replaced() {
        let directory = tempfile::tempdir().expect("temporary directory");
        fs::write(directory.path().join(INSTALL_ID_FILE), "invalid\n").expect("malformed ID");
        let replacement = get_or_create_installation_id(directory.path()).expect("replacement ID");
        assert!(uuid::Uuid::parse_str(&replacement).is_ok());
        assert_ne!(replacement, "invalid");
    }

    #[test]
    fn derives_packaged_resources_from_executable() {
        let executable = Path::new("/tmp/Atpiano.app/Contents/MacOS/atpiano-desktop");

        assert_eq!(
            resource_dir_for_executable(executable, MACOS_ARM64_TARGET),
            Some(PathBuf::from("/tmp/Atpiano.app/Contents/Resources"))
        );
        assert_eq!(
            resource_dir_for_executable(Path::new("/tmp/atpiano-desktop"), MACOS_ARM64_TARGET,),
            None
        );
        assert_eq!(
            resource_dir_for_executable(
                Path::new("/install/Atpiano/atpiano-desktop.exe"),
                WINDOWS_X86_64_TARGET,
            ),
            Some(PathBuf::from("/install/Atpiano"))
        );
    }

    #[test]
    fn accepts_only_declared_desktop_targets() {
        assert_eq!(
            desktop_target_for("macos", "aarch64").expect("macOS target"),
            MACOS_ARM64_TARGET
        );
        assert_eq!(
            desktop_target_for("windows", "x86_64").expect("Windows target"),
            WINDOWS_X86_64_TARGET
        );
        for (os, architecture) in [
            ("macos", "x86_64"),
            ("windows", "aarch64"),
            ("linux", "x86_64"),
        ] {
            assert!(desktop_target_for(os, architecture).is_err());
        }
    }

    #[test]
    fn redirects_runtime_caches_outside_the_bundle() {
        let mut command = Command::new("/bundle/runtime/bin/python3");
        let workspace = Path::new("/data/workspace");
        configure_sidecar_environment(
            &mut command,
            MACOS_ARM64_TARGET,
            Path::new("/bundle/runtime"),
            workspace,
            "credential",
        )
        .expect("desktop environment");
        let environment = command.get_envs().collect::<Vec<_>>();

        for (key, relative) in [
            ("NUMBA_CACHE_DIR", Some("numba")),
            ("MPLCONFIGDIR", Some("matplotlib")),
            ("XDG_CACHE_HOME", None),
            ("HF_HOME", Some("huggingface")),
        ] {
            let cache_root = workspace.join(".runtime-cache");
            let expected =
                relative.map_or_else(|| cache_root.clone(), |value| cache_root.join(value));
            assert!(
                environment.iter().any(|(name, value)| *name == key
                    && value.is_some_and(|value| value == expected.as_os_str())),
                "{key} did not equal {expected:?}: {environment:?}"
            );
        }
    }

    #[test]
    fn validates_bounded_ready_record() {
        let document = br#"{"schema_version":"atpiano.desktop-ready.v1","protocol_version":"atpiano.desktop.v1","contract_schema_version":"atpiano.contract.v1","sidecar_version":"0.1.0","host":"127.0.0.1","port":49152,"platform":"macos","architecture":"arm64","execution_backend":"cpu","model_pack_id":"atpiano-cpu-models-2026.07","model_pack_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}"#;
        let mut with_newline = document.to_vec();
        with_newline.push(b'\n');
        let mut reader = BufReader::new(&with_newline[..]);
        let ready = read_ready(&mut reader).expect("ready record");
        validate_ready(&ready, MACOS_ARM64_TARGET).expect("compatible record");
        assert_eq!(ready.port, 49152);
    }

    #[test]
    fn validates_windows_ready_record_only_for_windows_target() {
        let document = br#"{"schema_version":"atpiano.desktop-ready.v1","protocol_version":"atpiano.desktop.v1","contract_schema_version":"atpiano.contract.v1","sidecar_version":"0.1.0","host":"127.0.0.1","port":49152,"platform":"windows","architecture":"x86_64","execution_backend":"cpu","model_pack_id":"atpiano-cpu-models-2026.07","model_pack_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}"#;
        let mut with_newline = document.to_vec();
        with_newline.push(b'\n');
        let ready =
            read_ready(&mut BufReader::new(&with_newline[..])).expect("Windows ready record");

        validate_ready(&ready, WINDOWS_X86_64_TARGET).expect("Windows target");
        assert!(validate_ready(&ready, MACOS_ARM64_TARGET).is_err());
    }

    #[test]
    fn rejects_oversized_ready_record() {
        let oversized = vec![b'a'; MAX_READY_BYTES + 1];
        let mut reader = BufReader::new(&oversized[..]);

        let error = read_ready(&mut reader).expect_err("bounded record");

        assert!(error.contains("exceeded its bound"));
    }

    #[test]
    fn duplicate_bootstrap_reads_do_not_change_state() {
        let expected = runtime_info_fixture();
        let status = RwLock::new(RuntimeStatus::Ready(Box::new(expected.clone())));

        let first = current_runtime_info(&status).expect("first bootstrap");
        let second = current_runtime_info(&status).expect("second bootstrap");

        assert_eq!(first, expected);
        assert_eq!(second, expected);
    }

    #[test]
    fn unexpected_exit_records_one_bounded_failure() {
        let status = RwLock::new(RuntimeStatus::Ready(Box::new(runtime_info_fixture())));

        let message = record_unexpected_exit(&status, false, "status: 7", "engine failed")
            .expect("unexpected failure");

        assert_eq!(
            message,
            "The local engine stopped unexpectedly (status: 7): engine failed"
        );
        assert!(matches!(
            &*status.read().expect("runtime state"),
            RuntimeStatus::Failed(error) if error == &message
        ));
        assert!(record_unexpected_exit(&status, false, "status: 8", "another failure").is_none());
        assert!(record_unexpected_exit(&status, true, "status: 0", "").is_none());
    }

    #[test]
    fn cleanup_closes_stdin_and_reaps_child() {
        #[cfg(not(target_os = "windows"))]
        let mut command = {
            let mut command = Command::new("sh");
            command.args(["-c", "read line"]);
            command
        };
        #[cfg(target_os = "windows")]
        let mut command = {
            let mut command = Command::new("cmd.exe");
            command.args(["/d", "/s", "/c", "set /p line="]);
            command
        };
        let child = command
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .expect("helper child");
        assert!(child.stdin.is_some());
        let child = Arc::new(Mutex::new(child));
        let retained = Arc::clone(&child);
        let expected_shutdown = Arc::new(AtomicBool::new(false));
        let expected = Arc::clone(&expected_shutdown);

        DesktopProcess {
            child,
            expected_shutdown,
        }
        .shutdown();

        assert!(expected.load(Ordering::SeqCst));
        assert!(retained
            .lock()
            .expect("child state")
            .try_wait()
            .expect("child status")
            .is_some());
    }

    #[test]
    fn token_is_lowercase_hex_without_separators() {
        let credential = token().expect("token");
        assert_eq!(credential.len(), 64);
        assert!(is_lower_hex_64(&credential));
    }

    #[test]
    fn accepts_only_encoded_local_artifact_content_paths() {
        assert!(valid_artifact_url(
            "/api/v1/workspaces/local/sessions/session-1/artifacts/artifact%3Aabc/content"
        ));
        for invalid in [
            "https://example.com/file",
            "/api/v1/workspaces/local/sessions/session-1/artifacts/a/access",
            "/api/v1/workspaces/local/sessions/session-1/artifacts/a/content?x=1",
            "/api/v1/workspaces/local/sessions/session-1/artifacts/a\r\nX-Evil: yes/content",
            "/api/v1/workspaces/local/sessions/../artifacts/a/content",
        ] {
            assert!(!valid_artifact_url(invalid), "{invalid}");
        }
    }

    #[test]
    fn streams_authenticated_artifact_to_an_atomic_destination() {
        let path = "/api/v1/workspaces/local/sessions/session-1/artifacts/artifact%3Aabc/content";
        let credential = "c".repeat(64);
        let body = b"exact artifact bytes";
        let response = format!(
            "HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {}\r\n\r\n",
            body.len()
        )
        .into_bytes()
        .into_iter()
        .chain(body.iter().copied())
        .collect();
        let (port, server) = artifact_server(
            response,
            path,
            credential.clone(),
            MACOS_ARM64_TARGET.origin,
        );
        let directory = export_test_directory("artifact-export");
        let destination = directory.join("artifact.txt");
        fs::write(&destination, b"old bytes").expect("old destination");

        download_artifact(
            port,
            &credential,
            MACOS_ARM64_TARGET.origin,
            path,
            &destination,
        )
        .expect("artifact export");
        server.join().expect("artifact server");

        assert_eq!(fs::read(&destination).expect("saved artifact"), body);
        assert_eq!(
            fs::read_dir(&directory).expect("export directory").count(),
            1
        );
        fs::remove_dir_all(directory).expect("remove test directory");
    }

    #[test]
    fn truncated_artifact_keeps_the_existing_destination() {
        let path = "/api/v1/workspaces/local/sessions/session-1/artifacts/artifact%3Aabc/content";
        let credential = "d".repeat(64);
        let response = b"HTTP/1.0 200 OK\r\nContent-Length: 20\r\n\r\nshort".to_vec();
        let (port, server) = artifact_server(
            response,
            path,
            credential.clone(),
            WINDOWS_X86_64_TARGET.origin,
        );
        let directory = export_test_directory("truncated-export");
        let destination = directory.join("artifact.txt");
        fs::write(&destination, b"old bytes").expect("old destination");

        let error = download_artifact(
            port,
            &credential,
            WINDOWS_X86_64_TARGET.origin,
            path,
            &destination,
        )
        .expect_err("truncated");
        server.join().expect("artifact server");

        assert!(error.contains("declared length"));
        assert_eq!(
            fs::read(&destination).expect("unchanged destination"),
            b"old bytes"
        );
        assert_eq!(
            fs::read_dir(&directory).expect("export directory").count(),
            1
        );
        fs::remove_dir_all(directory).expect("remove test directory");
    }
}
