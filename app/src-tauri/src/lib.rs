use serde::{Deserialize, Serialize};
use std::{
    env,
    fmt::Write as _,
    fs,
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

const DESKTOP_PROTOCOL: &str = "atpiano.desktop.v1";
const CONTRACT_SCHEMA: &str = "atpiano.contract.v1";
const MODEL_PACK_ID: &str = "atpiano-cpu-models-2026.07";
const DESKTOP_ORIGIN: &str = "tauri://localhost";
const MAX_READY_BYTES: usize = 64 * 1024;
const MAX_HANDSHAKE_BYTES: u64 = 1024 * 1024;
const STARTUP_TIMEOUT: Duration = Duration::from_secs(30);

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct DesktopRuntimeInfo {
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

fn runtime_root(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    #[cfg(debug_assertions)]
    if let Some(override_path) = env::var_os("ATPIANO_DESKTOP_RUNTIME_ROOT") {
        return Ok(PathBuf::from(override_path));
    }
    app.path()
        .resource_dir()
        .map(|directory| directory.join("desktop-runtime"))
        .map_err(|error| format!("could not locate desktop resources: {error}"))
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

fn validate_ready(ready: &ReadyRecord) -> Result<(), String> {
    if ready.schema_version != "atpiano.desktop-ready.v1"
        || ready.protocol_version != DESKTOP_PROTOCOL
        || ready.contract_schema_version != CONTRACT_SCHEMA
        || ready.host != "127.0.0.1"
        || ready.platform != "macos"
        || ready.architecture != "arm64"
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

fn fetch_handshake(port: u16, credential: &str) -> Result<HandshakeRecord, String> {
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
         Origin: {DESKTOP_ORIGIN}\r\n\
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
        || handshake.score_available
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
            if !expected_shutdown.load(Ordering::SeqCst) {
                let detail = last_stderr(&stderr_lines, &credential);
                let message = if detail.is_empty() {
                    format!("The local engine stopped unexpectedly ({exit_status}).")
                } else {
                    format!("The local engine stopped unexpectedly ({exit_status}): {detail}")
                };
                if let Ok(mut state) = status.write() {
                    *state = RuntimeStatus::Failed(message.clone());
                }
                let _ = app.emit("desktop-runtime-failed", message);
            }
            return;
        }
        thread::sleep(Duration::from_millis(250));
    });
}

fn start_sidecar(
    app: &tauri::AppHandle,
    status: Arc<RwLock<RuntimeStatus>>,
) -> Result<(DesktopProcess, DesktopRuntimeInfo), String> {
    #[cfg(not(all(target_os = "macos", target_arch = "aarch64")))]
    return Err("Phase 5 desktop builds require macOS arm64".to_string());

    #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
    {
        let runtime = runtime_root(app)?;
        let python = runtime.join("bin/python3");
        let model_pack = runtime.join("model-pack/model-pack.json");
        let replay_manifest = runtime.join("fixture/input.json");
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
        let path = format!(
            "{}:{}",
            runtime.join("bin").display(),
            env::var("PATH").unwrap_or_default()
        );
        let mut command = Command::new(&python);
        command
            .arg("-I")
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
            .env("ATPIANO_DESKTOP_TOKEN", &credential)
            .env("ATPIANO_EXECUTION_BACKEND", "cpu")
            .env("CUDA_VISIBLE_DEVICES", "")
            .env("PYTHONDONTWRITEBYTECODE", "1")
            .env("PYTHONNOUSERSITE", "1")
            .env("PATH", path)
            .env_remove("PYTHONHOME")
            .env_remove("PYTHONPATH")
            .env_remove("VIRTUAL_ENV")
            .env_remove("ATPIANO_BASIC_PITCH_MODEL")
            .env_remove("ATPIANO_TRANSKUN_CHECKPOINT")
            .env_remove("ATPIANO_TRANSKUN_CONFIG")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
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
        if let Err(error) = validate_ready(&ready) {
            DesktopProcess {
                child,
                expected_shutdown: Arc::new(AtomicBool::new(true)),
            }
            .shutdown();
            return Err(error);
        }
        let handshake = match fetch_handshake(ready.port, &credential) {
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
}

#[tauri::command]
fn desktop_runtime(state: tauri::State<'_, DesktopState>) -> Result<DesktopRuntimeInfo, String> {
    match state
        .status
        .read()
        .map_err(|_| "desktop runtime state is unavailable".to_string())?
        .clone()
    {
        RuntimeStatus::Ready(info) => Ok(*info),
        RuntimeStatus::Failed(error) => Err(error),
        RuntimeStatus::Initializing => Err("The local engine is still starting.".to_string()),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let application = tauri::Builder::default()
        .setup(|app| {
            let status = Arc::new(RwLock::new(RuntimeStatus::Initializing));
            let result = start_sidecar(app.handle(), Arc::clone(&status));
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
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![desktop_runtime])
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

    #[test]
    fn validates_bounded_ready_record() {
        let document = br#"{"schema_version":"atpiano.desktop-ready.v1","protocol_version":"atpiano.desktop.v1","contract_schema_version":"atpiano.contract.v1","sidecar_version":"0.1.0","host":"127.0.0.1","port":49152,"platform":"macos","architecture":"arm64","execution_backend":"cpu","model_pack_id":"atpiano-cpu-models-2026.07","model_pack_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}"#;
        let mut with_newline = document.to_vec();
        with_newline.push(b'\n');
        let mut reader = BufReader::new(&with_newline[..]);
        let ready = read_ready(&mut reader).expect("ready record");
        validate_ready(&ready).expect("compatible record");
        assert_eq!(ready.port, 49152);
    }

    #[test]
    fn token_is_lowercase_hex_without_separators() {
        let credential = token().expect("token");
        assert_eq!(credential.len(), 64);
        assert!(is_lower_hex_64(&credential));
    }
}
