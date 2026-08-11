use base64::{engine::general_purpose::STANDARD, Engine as _};
use minisign_verify::{PublicKey, Signature};
use serde_json::Value;
use std::{
    env,
    error::Error,
    fs::{self, File},
    io::Read,
    path::Path,
};

fn decoded_text(encoded: &str, label: &str) -> Result<String, Box<dyn Error>> {
    let bytes = STANDARD.decode(encoded.trim())?;
    String::from_utf8(bytes).map_err(|error| format!("invalid UTF-8 in {label}: {error}").into())
}

fn verify(
    config_path: &Path,
    artifact_path: &Path,
    signature_path: &Path,
) -> Result<(), Box<dyn Error>> {
    let config: Value = serde_json::from_slice(&fs::read(config_path)?)?;
    let encoded_public_key = config
        .pointer("/plugins/updater/pubkey")
        .and_then(Value::as_str)
        .ok_or("Tauri config has no updater public key")?;
    let public_key_text = decoded_text(encoded_public_key, "updater public key")?;
    let public_key = PublicKey::decode(&public_key_text)?;

    let encoded_signature = fs::read_to_string(signature_path)?;
    let signature_text = decoded_text(&encoded_signature, "updater signature")?;
    let signature = Signature::decode(&signature_text)?;
    let mut verifier = public_key.verify_stream(&signature)?;
    let mut artifact = File::open(artifact_path)?;
    let mut buffer = vec![0_u8; 1024 * 1024];
    loop {
        let read = artifact.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        verifier.update(&buffer[..read]);
    }
    verifier.finalize()?;
    Ok(())
}

fn main() -> Result<(), Box<dyn Error>> {
    let arguments = env::args().skip(1).collect::<Vec<_>>();
    if arguments.len() != 3 {
        return Err("usage: verify_updater_signature TAURI_CONFIG UPDATE_ARCHIVE SIGNATURE".into());
    }
    verify(
        Path::new(&arguments[0]),
        Path::new(&arguments[1]),
        Path::new(&arguments[2]),
    )?;
    println!("Verified updater artifact signature: {}", arguments[1]);
    Ok(())
}
