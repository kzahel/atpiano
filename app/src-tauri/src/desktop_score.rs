use reqwest::{
    blocking::{Client, Response},
    redirect,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::HashSet,
    fs::{self, File, OpenOptions},
    io::{self, Read, Write},
    path::{Component, Path, PathBuf},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    time::{Duration, SystemTime, UNIX_EPOCH},
};
use tauri::{Emitter, Manager};
use zip::ZipArchive;

const CONTRACT_JSON: &str = include_str!("../../../desktop-score/acquisition.json");
const PROGRESS_EVENT: &str = "desktop-score-acquisition-progress";
const ACTIVE_INSTALLATION_FILE: &str = "score-runtime.json";
const ACKNOWLEDGEMENT_FILE: &str = "score-acknowledgement.json";
const SUPPORT_MANIFEST_FILE: &str = "support-manifest.json";
const RUNTIME_MANIFEST_FILE: &str = "runtime.json";

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct AcquisitionContract {
    schema_version: String,
    contract_id: String,
    notice_version: String,
    model_name: String,
    purpose: String,
    notice: String,
    acknowledgement: String,
    source: SourceAsset,
    checkpoint: CheckpointAsset,
    paper_url: String,
    allowed_https_hosts: Vec<String>,
    support_layer_id: String,
    supported_targets: Vec<SupportedTarget>,
    score_runtime_schema: String,
    score_pipeline_revision: u32,
    execution_backend: String,
    download_bytes: u64,
    installed_space_estimate_bytes: u64,
    minimum_free_bytes: u64,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct SourceAsset {
    repository_url: String,
    commit: String,
    archive_url: String,
    archive_sha256: String,
    archive_bytes: u64,
    archive_root: String,
    tree_sha256: String,
    maximum_entry_count: usize,
    maximum_expanded_bytes: u64,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct CheckpointAsset {
    release_url: String,
    download_url: String,
    sha256: String,
    bytes: u64,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct SupportedTarget {
    platform: String,
    architecture: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct SupportManifest {
    schema_version: String,
    support_layer_id: String,
    platform: String,
    architecture: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct InstallationRecord {
    schema_version: String,
    contract_id: String,
    notice_version: String,
    runtime_relative_path: String,
    platform: String,
    architecture: String,
    support_layer_id: String,
    source_archive_sha256: String,
    checkpoint_sha256: String,
    installed_bytes: u64,
    validated_at: u64,
}

#[derive(Debug, Serialize)]
struct AcknowledgementRecord<'a> {
    schema_version: &'static str,
    contract_id: &'a str,
    notice_version: &'a str,
    accepted_at: u64,
    application_version: &'a str,
    source_archive_sha256: &'a str,
    checkpoint_sha256: &'a str,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct ScoreRuntimeStatus {
    state: String,
    contract_id: String,
    notice_version: String,
    model_name: String,
    purpose: String,
    notice: String,
    acknowledgement: String,
    repository_url: String,
    checkpoint_release_url: String,
    paper_url: String,
    source_bytes: u64,
    checkpoint_bytes: u64,
    download_bytes: u64,
    installed_space_estimate_bytes: u64,
    minimum_free_bytes: u64,
    support_available: bool,
    installed_bytes: Option<u64>,
    error: Option<String>,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct AcquisitionProgress {
    phase: &'static str,
    completed_bytes: u64,
    total_bytes: u64,
}

#[derive(Clone, Default)]
pub(crate) struct ScoreAcquisitionState {
    running: Arc<AtomicBool>,
    cancelled: Arc<AtomicBool>,
}

struct OperationGuard {
    running: Arc<AtomicBool>,
}

impl Drop for OperationGuard {
    fn drop(&mut self) {
        self.running.store(false, Ordering::SeqCst);
    }
}

impl ScoreAcquisitionState {
    fn begin(&self) -> Result<OperationGuard, String> {
        self.running
            .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .map_err(|_| "A score model operation is already running.".to_string())?;
        self.cancelled.store(false, Ordering::SeqCst);
        Ok(OperationGuard {
            running: Arc::clone(&self.running),
        })
    }

    pub(crate) fn cancel(&self) -> bool {
        if !self.running.load(Ordering::SeqCst) {
            return false;
        }
        self.cancelled.store(true, Ordering::SeqCst);
        true
    }
}

fn contract() -> Result<AcquisitionContract, String> {
    let contract: AcquisitionContract = serde_json::from_str(CONTRACT_JSON)
        .map_err(|error| format!("score acquisition contract is invalid: {error}"))?;
    let allowed_hosts = contract
        .allowed_https_hosts
        .iter()
        .map(String::as_str)
        .collect::<HashSet<_>>();
    let urls = [
        &contract.source.repository_url,
        &contract.source.archive_url,
        &contract.checkpoint.release_url,
        &contract.checkpoint.download_url,
        &contract.paper_url,
    ];
    let urls_valid = urls.iter().all(|value| {
        reqwest::Url::parse(value).is_ok_and(|url| {
            url.scheme() == "https"
                && url.username().is_empty()
                && url.password().is_none()
                && url.port().is_none()
                && url.fragment().is_none()
                && url
                    .host_str()
                    .is_some_and(|host| allowed_hosts.contains(host))
        })
    });
    let targets = contract
        .supported_targets
        .iter()
        .map(|target| (target.platform.as_str(), target.architecture.as_str()))
        .collect::<HashSet<_>>();
    if contract.schema_version != "atpiano.score-acquisition.v1"
        || contract.score_runtime_schema != "atpiano.midi2score-runtime.v2"
        || contract.score_pipeline_revision != 4
        || contract.execution_backend != "cpu"
        || contract.download_bytes != contract.source.archive_bytes + contract.checkpoint.bytes
        || contract.minimum_free_bytes <= contract.installed_space_estimate_bytes
        || allowed_hosts.len() != contract.allowed_https_hosts.len()
        || !urls_valid
        || targets != HashSet::from([("macos", "arm64"), ("windows", "x86_64")])
        || contract.supported_targets.len() != 2
    {
        return Err("score acquisition contract is incompatible".to_string());
    }
    Ok(contract)
}

fn target_supported(contract: &AcquisitionContract, platform: &str, architecture: &str) -> bool {
    contract
        .supported_targets
        .iter()
        .any(|target| target.platform == platform && target.architecture == architecture)
}

fn support_root(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    #[cfg(debug_assertions)]
    if let Some(runtime) = std::env::var_os("ATPIANO_DESKTOP_RUNTIME_ROOT") {
        return Ok(PathBuf::from(runtime).join("score-support"));
    }
    app.path()
        .resource_dir()
        .map(|root| root.join("desktop-runtime/score-support"))
        .map_err(|error| format!("could not locate score support resources: {error}"))
}

fn support_manifest(
    app: &tauri::AppHandle,
    contract: &AcquisitionContract,
    platform: &str,
    architecture: &str,
) -> Result<(PathBuf, SupportManifest), String> {
    let root = support_root(app)?;
    let document = fs::read(root.join(SUPPORT_MANIFEST_FILE))
        .map_err(|_| "This build does not contain score model support.".to_string())?;
    let manifest: SupportManifest = serde_json::from_slice(&document)
        .map_err(|_| "The bundled score support manifest is invalid.".to_string())?;
    if manifest.schema_version != "atpiano.score-support.v1"
        || manifest.support_layer_id != contract.support_layer_id
        || manifest.platform != platform
        || manifest.architecture != architecture
    {
        return Err("The bundled score support does not match this application.".to_string());
    }
    let python = if platform == "windows" {
        root.join(".venv/Scripts/python.exe")
    } else {
        root.join(".venv/bin/python")
    };
    if !python.is_file() {
        return Err("The bundled score support Python runtime is missing.".to_string());
    }
    Ok((root, manifest))
}

fn config_paths(app: &tauri::AppHandle) -> Result<(PathBuf, PathBuf, PathBuf), String> {
    let config = app
        .path()
        .app_config_dir()
        .map_err(|error| format!("could not locate desktop config: {error}"))?;
    let data = app
        .path()
        .app_data_dir()
        .map_err(|error| format!("could not locate desktop data: {error}"))?;
    Ok((
        config.join(ACTIVE_INSTALLATION_FILE),
        config.join(ACKNOWLEDGEMENT_FILE),
        data.join("score-runtimes"),
    ))
}

fn read_installation(path: &Path) -> Result<InstallationRecord, String> {
    let document = fs::read(path).map_err(|_| "The score model is not installed.".to_string())?;
    serde_json::from_slice(&document)
        .map_err(|_| "The score model installation record is invalid.".to_string())
}

fn validate_installation(
    record: &InstallationRecord,
    runtime_parent: &Path,
    contract: &AcquisitionContract,
    platform: &str,
    architecture: &str,
) -> Result<PathBuf, String> {
    validate_installation_identity(record, contract, platform, architecture)?;
    let runtime = runtime_parent.join(&record.runtime_relative_path);
    let metadata = fs::symlink_metadata(&runtime)
        .map_err(|_| "The installed score model directory is missing.".to_string())?;
    if !metadata.is_dir() || metadata.file_type().is_symlink() {
        return Err("The installed score model directory is unsafe.".to_string());
    }
    let python = if platform == "windows" {
        runtime.join(".venv/Scripts/python.exe")
    } else {
        runtime.join(".venv/bin/python")
    };
    for path in [
        runtime.join("MIDI2ScoreTransformer"),
        runtime.join("MIDI2ScoreTF.ckpt"),
        runtime.join(RUNTIME_MANIFEST_FILE),
        python,
    ] {
        if !path.exists() {
            return Err("The installed score model is incomplete.".to_string());
        }
    }
    if runtime
        .join("MIDI2ScoreTF.ckpt")
        .metadata()
        .map_err(|_| "The score checkpoint is unavailable.".to_string())?
        .len()
        != contract.checkpoint.bytes
    {
        return Err("The installed score checkpoint has the wrong size.".to_string());
    }
    Ok(runtime)
}

fn validate_installation_identity(
    record: &InstallationRecord,
    contract: &AcquisitionContract,
    platform: &str,
    architecture: &str,
) -> Result<(), String> {
    if record.schema_version != "atpiano.score-runtime-installation.v1"
        || record.contract_id != contract.contract_id
        || record.notice_version != contract.notice_version
        || record.runtime_relative_path != contract.contract_id
        || record.platform != platform
        || record.architecture != architecture
        || record.support_layer_id != contract.support_layer_id
        || record.source_archive_sha256 != contract.source.archive_sha256
        || record.checkpoint_sha256 != contract.checkpoint.sha256
    {
        return Err("The installed score model is incompatible.".to_string());
    }
    Ok(())
}

pub(crate) fn active_runtime(
    app: &tauri::AppHandle,
    platform: &str,
    architecture: &str,
) -> Option<PathBuf> {
    let contract = contract().ok()?;
    let (active, _, runtime_parent) = config_paths(app).ok()?;
    let installation = read_installation(&active).ok()?;
    validate_installation(
        &installation,
        &runtime_parent,
        &contract,
        platform,
        architecture,
    )
    .ok()
}

pub(crate) fn status(
    app: &tauri::AppHandle,
    operation: &ScoreAcquisitionState,
    platform: &str,
    architecture: &str,
) -> Result<ScoreRuntimeStatus, String> {
    let contract = contract()?;
    if !target_supported(&contract, platform, architecture) {
        return Err("score acquisition is unsupported on this target".to_string());
    }
    let support_available = support_manifest(app, &contract, platform, architecture).is_ok();
    let (active, _, runtime_parent) = config_paths(app)?;
    let (state, installed_bytes, error) = if operation.running.load(Ordering::SeqCst) {
        ("installing", None, None)
    } else if !active.exists() {
        ("not-installed", None, None)
    } else {
        match read_installation(&active).and_then(|record| {
            let bytes = record.installed_bytes;
            validate_installation(&record, &runtime_parent, &contract, platform, architecture)?;
            Ok(bytes)
        }) {
            Ok(bytes) => ("available", Some(bytes), None),
            Err(error) => ("invalid", None, Some(error)),
        }
    };
    Ok(ScoreRuntimeStatus {
        state: state.to_string(),
        contract_id: contract.contract_id,
        notice_version: contract.notice_version,
        model_name: contract.model_name,
        purpose: contract.purpose,
        notice: contract.notice,
        acknowledgement: contract.acknowledgement,
        repository_url: contract.source.repository_url,
        checkpoint_release_url: contract.checkpoint.release_url,
        paper_url: contract.paper_url,
        source_bytes: contract.source.archive_bytes,
        checkpoint_bytes: contract.checkpoint.bytes,
        download_bytes: contract.download_bytes,
        installed_space_estimate_bytes: contract.installed_space_estimate_bytes,
        minimum_free_bytes: contract.minimum_free_bytes,
        support_available,
        installed_bytes,
        error,
    })
}

fn emit_progress(
    app: &tauri::AppHandle,
    phase: &'static str,
    completed_bytes: u64,
    total_bytes: u64,
) {
    let _ = app.emit(
        PROGRESS_EVENT,
        AcquisitionProgress {
            phase,
            completed_bytes,
            total_bytes,
        },
    );
}

fn download_client(allowed_hosts: &[String]) -> Result<Client, String> {
    let hosts = allowed_hosts.iter().cloned().collect::<HashSet<_>>();
    Client::builder()
        .connect_timeout(Duration::from_secs(15))
        .timeout(Duration::from_secs(15 * 60))
        .redirect(redirect::Policy::custom(move |attempt| {
            if attempt.previous().len() >= 5 {
                return attempt.error("too many score model redirects");
            }
            match attempt.url().host_str() {
                Some(host) if hosts.contains(host) => attempt.follow(),
                _ => attempt.stop(),
            }
        }))
        .user_agent(concat!("Atpiano/", env!("CARGO_PKG_VERSION")))
        .build()
        .map_err(|error| format!("could not prepare the score model download: {error}"))
}

fn checked_response(response: Response, expected_bytes: u64) -> Result<Response, String> {
    let response = response
        .error_for_status()
        .map_err(|error| format!("score model download was rejected: {error}"))?;
    if response.content_length() != Some(expected_bytes) {
        return Err("score model download size differs from its contract".to_string());
    }
    Ok(response)
}

struct DownloadSpec<'a> {
    url: &'a str,
    expected_sha256: &'a str,
    expected_bytes: u64,
    phase: &'static str,
    completed_before: u64,
    total_bytes: u64,
}

fn download_asset(
    app: &tauri::AppHandle,
    client: &Client,
    cancelled: &AtomicBool,
    destination: &Path,
    spec: DownloadSpec<'_>,
) -> Result<(), String> {
    let mut response = checked_response(
        client
            .get(spec.url)
            .send()
            .map_err(|error| format!("score model download failed: {error}"))?,
        spec.expected_bytes,
    )?;
    let mut output = OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(destination)
        .map_err(|error| format!("could not create a score model download: {error}"))?;
    let mut digest = Sha256::new();
    let mut downloaded = 0_u64;
    let mut block = [0_u8; 1024 * 1024];
    loop {
        if cancelled.load(Ordering::SeqCst) {
            return Err("Score model download was cancelled.".to_string());
        }
        let count = response
            .read(&mut block)
            .map_err(|error| format!("score model download failed: {error}"))?;
        if count == 0 {
            break;
        }
        downloaded = downloaded
            .checked_add(count as u64)
            .ok_or_else(|| "score model download exceeded its bound".to_string())?;
        if downloaded > spec.expected_bytes {
            return Err("score model download exceeded its bound".to_string());
        }
        digest.update(&block[..count]);
        output
            .write_all(&block[..count])
            .map_err(|error| format!("could not write the score model download: {error}"))?;
        emit_progress(
            app,
            spec.phase,
            spec.completed_before + downloaded,
            spec.total_bytes,
        );
    }
    if downloaded != spec.expected_bytes
        || format!("{:x}", digest.finalize()) != spec.expected_sha256
    {
        return Err("score model download checksum differs from its contract".to_string());
    }
    output
        .sync_all()
        .map_err(|error| format!("could not finish the score model download: {error}"))
}

fn safe_archive_relative(path: &Path, expected_root: &str) -> Option<PathBuf> {
    let mut components = path.components();
    match components.next()? {
        Component::Normal(root) if root == expected_root => {}
        _ => return None,
    }
    let mut relative = PathBuf::new();
    for component in components {
        match component {
            Component::Normal(value) => relative.push(value),
            _ => return None,
        }
    }
    Some(relative)
}

fn extract_source_archive(
    archive_path: &Path,
    destination: &Path,
    source: &SourceAsset,
) -> Result<(), String> {
    let file = File::open(archive_path)
        .map_err(|error| format!("could not read the score source archive: {error}"))?;
    let mut archive = ZipArchive::new(file)
        .map_err(|error| format!("score source archive is invalid: {error}"))?;
    if archive.len() > source.maximum_entry_count {
        return Err("score source archive contains too many entries".to_string());
    }
    fs::create_dir(destination)
        .map_err(|error| format!("could not create the score source directory: {error}"))?;
    let mut expanded = 0_u64;
    for index in 0..archive.len() {
        let mut entry = archive
            .by_index(index)
            .map_err(|error| format!("could not read the score source archive: {error}"))?;
        if entry
            .unix_mode()
            .is_some_and(|mode| mode & 0o170000 == 0o120000)
        {
            return Err("score source archive contains a symbolic link".to_string());
        }
        let enclosed = entry
            .enclosed_name()
            .ok_or_else(|| "score source archive contains an unsafe path".to_string())?;
        let relative = safe_archive_relative(&enclosed, &source.archive_root)
            .ok_or_else(|| "score source archive root changed".to_string())?;
        if relative.as_os_str().is_empty() {
            continue;
        }
        let output = destination.join(relative);
        if entry.is_dir() {
            fs::create_dir_all(&output)
                .map_err(|error| format!("could not extract score source: {error}"))?;
            continue;
        }
        if !entry.is_file() {
            return Err("score source archive contains an unsupported entry".to_string());
        }
        expanded = expanded
            .checked_add(entry.size())
            .ok_or_else(|| "score source archive exceeded its bound".to_string())?;
        if expanded > source.maximum_expanded_bytes {
            return Err("score source archive exceeded its bound".to_string());
        }
        let parent = output
            .parent()
            .ok_or_else(|| "score source archive path is invalid".to_string())?;
        fs::create_dir_all(parent)
            .map_err(|error| format!("could not extract score source: {error}"))?;
        let mut file = OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(&output)
            .map_err(|error| format!("could not extract score source: {error}"))?;
        io::copy(&mut entry, &mut file)
            .map_err(|error| format!("could not extract score source: {error}"))?;
    }
    Ok(())
}

fn copy_tree(source: &Path, destination: &Path) -> Result<u64, String> {
    let metadata = fs::symlink_metadata(source)
        .map_err(|error| format!("could not inspect bundled score support: {error}"))?;
    if !metadata.is_dir() || metadata.file_type().is_symlink() {
        return Err("bundled score support root is unsafe".to_string());
    }
    fs::create_dir(destination)
        .map_err(|error| format!("could not create the score runtime: {error}"))?;
    let mut bytes = 0_u64;
    for entry in fs::read_dir(source)
        .map_err(|error| format!("could not read bundled score support: {error}"))?
    {
        let entry =
            entry.map_err(|error| format!("could not read bundled score support: {error}"))?;
        let source_path = entry.path();
        let destination_path = destination.join(entry.file_name());
        let metadata = fs::symlink_metadata(&source_path)
            .map_err(|error| format!("could not inspect bundled score support: {error}"))?;
        if metadata.file_type().is_symlink() {
            return Err("bundled score support contains a symbolic link".to_string());
        }
        if metadata.is_dir() {
            bytes = bytes
                .checked_add(copy_tree(&source_path, &destination_path)?)
                .ok_or_else(|| "bundled score support exceeded its bound".to_string())?;
        } else if metadata.is_file() {
            bytes = bytes
                .checked_add(metadata.len())
                .ok_or_else(|| "bundled score support exceeded its bound".to_string())?;
            fs::copy(&source_path, &destination_path)
                .map_err(|error| format!("could not copy bundled score support: {error}"))?;
        } else {
            return Err("bundled score support contains an unsupported file".to_string());
        }
    }
    Ok(bytes)
}

fn directory_bytes(root: &Path) -> Result<u64, String> {
    let mut total = 0_u64;
    for entry in fs::read_dir(root)
        .map_err(|error| format!("could not inspect the score runtime: {error}"))?
    {
        let entry =
            entry.map_err(|error| format!("could not inspect the score runtime: {error}"))?;
        let metadata = fs::symlink_metadata(entry.path())
            .map_err(|error| format!("could not inspect the score runtime: {error}"))?;
        if metadata.file_type().is_symlink() {
            return Err("the score runtime contains a symbolic link".to_string());
        }
        total = total
            .checked_add(if metadata.is_dir() {
                directory_bytes(&entry.path())?
            } else if metadata.is_file() {
                metadata.len()
            } else {
                return Err("the score runtime contains an unsupported file".to_string());
            })
            .ok_or_else(|| "the score runtime size is invalid".to_string())?;
    }
    Ok(total)
}

fn tree_sha256(root: &Path) -> Result<String, String> {
    fn collect_files(
        root: &Path,
        directory: &Path,
        files: &mut Vec<PathBuf>,
    ) -> Result<(), String> {
        for entry in fs::read_dir(directory)
            .map_err(|error| format!("could not inspect score source: {error}"))?
        {
            let entry =
                entry.map_err(|error| format!("could not inspect score source: {error}"))?;
            let path = entry.path();
            let metadata = fs::symlink_metadata(&path)
                .map_err(|error| format!("could not inspect score source: {error}"))?;
            if metadata.file_type().is_symlink() {
                return Err("score source contains a symbolic link".to_string());
            }
            if metadata.is_dir() {
                collect_files(root, &path, files)?;
            } else if metadata.is_file() {
                files.push(
                    path.strip_prefix(root)
                        .map_err(|_| "score source path escaped its root".to_string())?
                        .to_path_buf(),
                );
            } else {
                return Err("score source contains an unsupported file".to_string());
            }
        }
        Ok(())
    }

    let mut files = Vec::new();
    collect_files(root, root, &mut files)?;
    files.sort_by_key(|path| {
        path.components()
            .map(|component| component.as_os_str().to_string_lossy().into_owned())
            .collect::<Vec<_>>()
            .join("/")
    });
    let mut tree = Sha256::new();
    for relative in files {
        let key = relative
            .components()
            .map(|component| component.as_os_str().to_string_lossy().into_owned())
            .collect::<Vec<_>>()
            .join("/");
        tree.update(key.as_bytes());
        tree.update(b"\0");
        let mut file = File::open(root.join(relative))
            .map_err(|error| format!("could not hash score source: {error}"))?;
        let mut digest = Sha256::new();
        let mut block = [0_u8; 1024 * 1024];
        loop {
            let count = file
                .read(&mut block)
                .map_err(|error| format!("could not hash score source: {error}"))?;
            if count == 0 {
                break;
            }
            digest.update(&block[..count]);
        }
        tree.update(digest.finalize());
    }
    Ok(format!("{:x}", tree.finalize()))
}

fn unix_time() -> Result<u64, String> {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .map_err(|_| "system time is unavailable".to_string())
}

fn write_json_atomic(path: &Path, value: &impl Serialize) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| "score runtime record has no parent".to_string())?;
    fs::create_dir_all(parent)
        .map_err(|error| format!("could not create score runtime config: {error}"))?;
    let temporary = parent.join(format!(
        ".{}.{}.tmp",
        path.file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("score-runtime"),
        uuid::Uuid::new_v4()
    ));
    let mut file = OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(&temporary)
        .map_err(|error| format!("could not create score runtime config: {error}"))?;
    serde_json::to_writer_pretty(&mut file, value)
        .map_err(|error| format!("could not encode score runtime config: {error}"))?;
    file.write_all(b"\n")
        .map_err(|error| format!("could not write score runtime config: {error}"))?;
    file.sync_all()
        .map_err(|error| format!("could not finish score runtime config: {error}"))?;
    fs::rename(&temporary, path)
        .map_err(|error| format!("could not publish score runtime config: {error}"))
}

pub(crate) fn acquire(
    app: &tauri::AppHandle,
    operation: ScoreAcquisitionState,
    platform: &str,
    architecture: &str,
    acknowledged: bool,
) -> Result<ScoreRuntimeStatus, String> {
    if !acknowledged {
        return Err("The research-use acknowledgement is required.".to_string());
    }
    let _guard = operation.begin()?;
    let contract = contract()?;
    if !target_supported(&contract, platform, architecture) {
        return Err("score acquisition is unsupported on this target".to_string());
    }
    let (support, _) = support_manifest(app, &contract, platform, architecture)?;
    let (active, acknowledgement, runtime_parent) = config_paths(app)?;
    fs::create_dir_all(&runtime_parent)
        .map_err(|error| format!("could not create score runtime storage: {error}"))?;
    let available = fs2::available_space(&runtime_parent)
        .map_err(|error| format!("could not inspect available score model space: {error}"))?;
    if available < contract.minimum_free_bytes {
        return Err("At least 2.5 GB of free space is required.".to_string());
    }
    if active.exists() {
        return Err("A score model installation already exists.".to_string());
    }
    let staging_parent = runtime_parent.join(".staging");
    fs::create_dir_all(&staging_parent)
        .map_err(|error| format!("could not create score model staging: {error}"))?;
    let staging = staging_parent.join(uuid::Uuid::new_v4().to_string());
    let final_runtime = runtime_parent.join(&contract.contract_id);
    fs::create_dir(&staging)
        .map_err(|error| format!("could not create score model staging: {error}"))?;
    let result = (|| {
        emit_progress(app, "preparing", 0, contract.download_bytes);
        copy_tree(&support, &staging)?;
        let client = download_client(&contract.allowed_https_hosts)?;
        let source_archive = staging.join("source.zip.download");
        download_asset(
            app,
            &client,
            &operation.cancelled,
            &source_archive,
            DownloadSpec {
                url: &contract.source.archive_url,
                expected_sha256: &contract.source.archive_sha256,
                expected_bytes: contract.source.archive_bytes,
                phase: "source",
                completed_before: 0,
                total_bytes: contract.download_bytes,
            },
        )?;
        emit_progress(
            app,
            "verifying-source",
            contract.source.archive_bytes,
            contract.download_bytes,
        );
        extract_source_archive(
            &source_archive,
            &staging.join("MIDI2ScoreTransformer"),
            &contract.source,
        )?;
        if tree_sha256(&staging.join("MIDI2ScoreTransformer"))? != contract.source.tree_sha256 {
            return Err("score source tree differs from its contract".to_string());
        }
        fs::remove_file(&source_archive)
            .map_err(|error| format!("could not clear score source staging: {error}"))?;
        let checkpoint = staging.join("MIDI2ScoreTF.ckpt");
        download_asset(
            app,
            &client,
            &operation.cancelled,
            &checkpoint,
            DownloadSpec {
                url: &contract.checkpoint.download_url,
                expected_sha256: &contract.checkpoint.sha256,
                expected_bytes: contract.checkpoint.bytes,
                phase: "checkpoint",
                completed_before: contract.source.archive_bytes,
                total_bytes: contract.download_bytes,
            },
        )?;
        emit_progress(
            app,
            "installing",
            contract.download_bytes,
            contract.download_bytes,
        );
        let runtime_manifest = serde_json::json!({
            "schema_version": contract.score_runtime_schema,
            "internal_use_only": false,
            "acquisition_contract_id": contract.contract_id,
            "support_layer_id": contract.support_layer_id,
            "repository": {
                "url": contract.source.repository_url,
                "commit": contract.source.commit,
                "archive_sha256": contract.source.archive_sha256,
                "tree_sha256": contract.source.tree_sha256,
            },
            "checkpoint": {
                "url": contract.checkpoint.download_url,
                "sha256": contract.checkpoint.sha256,
                "bytes": contract.checkpoint.bytes,
            },
            "execution": { "device": "cpu" },
        });
        write_json_atomic(&staging.join(RUNTIME_MANIFEST_FILE), &runtime_manifest)?;
        let installed_bytes = directory_bytes(&staging)?;
        if final_runtime.exists() {
            return Err("An inactive score model installation already exists.".to_string());
        }
        fs::rename(&staging, &final_runtime)
            .map_err(|error| format!("could not publish the score model: {error}"))?;
        let validated_at = unix_time()?;
        let installation = InstallationRecord {
            schema_version: "atpiano.score-runtime-installation.v1".to_string(),
            contract_id: contract.contract_id.clone(),
            notice_version: contract.notice_version.clone(),
            runtime_relative_path: contract.contract_id.clone(),
            platform: platform.to_string(),
            architecture: architecture.to_string(),
            support_layer_id: contract.support_layer_id.clone(),
            source_archive_sha256: contract.source.archive_sha256.clone(),
            checkpoint_sha256: contract.checkpoint.sha256.clone(),
            installed_bytes,
            validated_at,
        };
        let receipt = AcknowledgementRecord {
            schema_version: "atpiano.score-acknowledgement.v1",
            contract_id: &contract.contract_id,
            notice_version: &contract.notice_version,
            accepted_at: validated_at,
            application_version: env!("CARGO_PKG_VERSION"),
            source_archive_sha256: &contract.source.archive_sha256,
            checkpoint_sha256: &contract.checkpoint.sha256,
        };
        write_json_atomic(&acknowledgement, &receipt)?;
        write_json_atomic(&active, &installation)?;
        emit_progress(
            app,
            "complete",
            contract.download_bytes,
            contract.download_bytes,
        );
        Ok(())
    })();
    if result.is_err() && staging.exists() {
        let _ = fs::remove_dir_all(&staging);
    }
    if result.is_err() && !active.exists() && final_runtime.exists() {
        let _ = fs::remove_dir_all(&final_runtime);
    }
    result?;
    drop(_guard);
    status(app, &operation, platform, architecture)
}

pub(crate) fn remove(
    app: &tauri::AppHandle,
    operation: ScoreAcquisitionState,
    platform: &str,
    architecture: &str,
) -> Result<ScoreRuntimeStatus, String> {
    let guard = operation.begin()?;
    let contract = contract()?;
    let (active, acknowledgement, runtime_parent) = config_paths(app)?;
    let installation = read_installation(&active)?;
    validate_installation_identity(&installation, &contract, platform, architecture)?;
    let runtime = runtime_parent.join(&installation.runtime_relative_path);
    let metadata = fs::symlink_metadata(&runtime)
        .map_err(|_| "The installed score model directory is missing.".to_string())?;
    if !metadata.is_dir() || metadata.file_type().is_symlink() {
        return Err("The installed score model directory is unsafe.".to_string());
    }
    let removing = runtime_parent.join(format!(".removing-{}", uuid::Uuid::new_v4()));
    fs::rename(&runtime, &removing)
        .map_err(|error| format!("could not prepare score model removal: {error}"))?;
    if let Err(error) = fs::remove_file(&active) {
        let _ = fs::rename(&removing, &runtime);
        return Err(format!("could not deactivate the score model: {error}"));
    }
    match fs::remove_file(&acknowledgement) {
        Ok(()) => {}
        Err(error) if error.kind() == io::ErrorKind::NotFound => {}
        Err(error) => return Err(format!("could not remove score acknowledgement: {error}")),
    }
    fs::remove_dir_all(&removing)
        .map_err(|error| format!("could not finish score model removal: {error}"))?;
    drop(guard);
    status(app, &operation, platform, architecture)
}

#[cfg(test)]
mod tests {
    use super::*;
    use zip::{write::SimpleFileOptions, ZipWriter};

    #[test]
    fn embedded_contract_matches_release_targets_and_sizes() {
        let contract = contract().expect("embedded acquisition contract");
        assert!(target_supported(&contract, "macos", "arm64"));
        assert!(target_supported(&contract, "windows", "x86_64"));
        assert!(!target_supported(&contract, "windows", "arm64"));
        assert_eq!(contract.download_bytes, 390_016_983);
    }

    #[test]
    fn source_paths_are_bounded_to_the_exact_archive_root() {
        let root = "MIDI2ScoreTransformer-commit";
        assert_eq!(
            safe_archive_relative(Path::new("MIDI2ScoreTransformer-commit/src/model.py"), root),
            Some(PathBuf::from("src/model.py"))
        );
        for unsafe_path in ["other/file", "../escape", "/absolute"] {
            assert!(safe_archive_relative(Path::new(unsafe_path), root).is_none());
        }
    }

    #[test]
    fn source_extraction_rejects_path_escape() {
        let directory = tempfile::tempdir().expect("temporary directory");
        let archive_path = directory.path().join("source.zip");
        let file = File::create(&archive_path).expect("archive file");
        let mut archive = ZipWriter::new(file);
        archive
            .start_file("different-root/file.py", SimpleFileOptions::default())
            .expect("archive entry");
        archive
            .write_all(b"print('unsafe')\n")
            .expect("entry bytes");
        archive.finish().expect("finish archive");
        let source = SourceAsset {
            repository_url: String::new(),
            commit: String::new(),
            archive_url: String::new(),
            archive_sha256: String::new(),
            archive_bytes: 1,
            archive_root: "expected-root".to_string(),
            tree_sha256: String::new(),
            maximum_entry_count: 2,
            maximum_expanded_bytes: 1024,
        };

        let error =
            extract_source_archive(&archive_path, &directory.path().join("output"), &source)
                .expect_err("unsafe root");

        assert!(error.contains("root changed"));
    }
}
