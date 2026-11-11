#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::time::Duration;
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    net::TcpListener,
    time::timeout,
};
use url::Url;

#[derive(Deserialize)]
struct Discovery {
    issuer: String,
    authorization_endpoint: String,
    token_endpoint: String,
}
#[derive(Deserialize)]
struct Tokens {
    access_token: String,
    token_type: String,
}

fn https_url(value: &str) -> Result<Url, String> {
    let url = Url::parse(value).map_err(|_| "Invalid identity-provider address")?;
    if url.scheme() != "https"
        || url.host_str().is_none()
        || !url.username().is_empty()
        || url.password().is_some()
    {
        return Err("Identity endpoints must use HTTPS without embedded credentials".into());
    }
    Ok(url)
}

fn callback_code(target: &str, expected_state: &str) -> Result<String, String> {
    let parsed =
        Url::parse(&format!("http://127.0.0.1{}", target)).map_err(|_| "Invalid callback")?;
    if parsed.path() != "/callback" {
        return Err("Unexpected callback path".into());
    }
    let values: Vec<_> = parsed.query_pairs().collect();
    let states: Vec<_> = values.iter().filter(|(k, _)| k == "state").collect();
    if states.len() != 1 || states[0].1 != expected_state {
        return Err("Sign-in state mismatch".into());
    }
    if values.iter().any(|(k, _)| k == "error") {
        return Err("Identity provider declined sign-in".into());
    }
    let codes: Vec<_> = values.iter().filter(|(k, _)| k == "code").collect();
    if codes.len() != 1 || codes[0].1.is_empty() {
        return Err("Missing authorization code".into());
    }
    Ok(codes[0].1.to_string())
}

#[tauri::command]
async fn oidc_sign_in(issuer: String, client_id: String) -> Result<String, String> {
    // Public native client: no client secret, no persistent token storage.
    // A configured provider must permit a dynamic loopback redirect port.
    https_url(&issuer)?;
    if client_id.is_empty() || client_id.len() > 512 {
        return Err("Invalid public client ID".into());
    }
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(15))
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .map_err(|_| "Cannot initialize secure sign-in")?;
    let discovery: Discovery = client
        .get(format!(
            "{}/.well-known/openid-configuration",
            issuer.trim_end_matches('/')
        ))
        .send()
        .await
        .map_err(|_| "Cannot contact identity provider")?
        .error_for_status()
        .map_err(|_| "Identity discovery failed")?
        .json()
        .await
        .map_err(|_| "Invalid identity discovery response")?;
    if discovery.issuer.trim_end_matches('/') != issuer.trim_end_matches('/') {
        return Err("Identity issuer mismatch".into());
    }
    let mut authorization = https_url(&discovery.authorization_endpoint)?;
    https_url(&discovery.token_endpoint)?;
    let listener = TcpListener::bind("127.0.0.1:0")
        .await
        .map_err(|_| "Cannot open local sign-in callback")?;
    let redirect = format!(
        "http://127.0.0.1:{}/callback",
        listener
            .local_addr()
            .map_err(|_| "Cannot read callback port")?
            .port()
    );
    let verifier = URL_SAFE_NO_PAD.encode(rand::random::<[u8; 32]>());
    let challenge = URL_SAFE_NO_PAD.encode(Sha256::digest(verifier.as_bytes()));
    let state = URL_SAFE_NO_PAD.encode(rand::random::<[u8; 32]>());
    authorization.query_pairs_mut().extend_pairs([
        ("client_id", client_id.as_str()),
        ("response_type", "code"),
        ("redirect_uri", redirect.as_str()),
        ("scope", "openid profile email"),
        ("state", state.as_str()),
        ("code_challenge", challenge.as_str()),
        ("code_challenge_method", "S256"),
    ]);
    open::that(authorization.as_str()).map_err(|_| "Cannot open the system browser")?;
    let code = timeout(Duration::from_secs(180), async {
        loop {
            let (mut stream, _) = listener.accept().await.map_err(|_| "Sign-in callback failed")?;
            let mut buffer=vec![0u8;8192];
            let size=timeout(Duration::from_secs(5), stream.read(&mut buffer)).await.map_err(|_| "Callback timed out")?
                .map_err(|_| "Callback read failed")?;
            let line=std::str::from_utf8(&buffer[..size]).map_err(|_| "Invalid callback encoding")?.lines().next().unwrap_or("");
            let parts:Vec<_>=line.split_whitespace().collect();
            if parts.len()!=3 || parts[0]!="GET" { continue; }
            let result=callback_code(parts[1], &state);
            let (status,body)=if result.is_ok() {("200 OK","Sign-in received. You can return to ConstructPM AI.")} else {("400 Bad Request","Invalid sign-in callback. Return to the application and try again.")};
            let response=format!("HTTP/1.1 {}\r\nContent-Type: text/plain; charset=utf-8\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: {}\r\n\r\n{}",status,body.len(),body);
            let _=stream.write_all(response.as_bytes()).await;
            // Ignore favicon requests or unrelated local connections until timeout.
            if parts[1].starts_with("/callback?") { return result; }
        }
    }).await.map_err(|_| "Sign-in timed out; try again")??;
    let token: Tokens = client
        .post(discovery.token_endpoint)
        .form(&[
            ("grant_type", "authorization_code"),
            ("client_id", client_id.as_str()),
            ("code", code.as_str()),
            ("redirect_uri", redirect.as_str()),
            ("code_verifier", verifier.as_str()),
        ])
        .send()
        .await
        .map_err(|_| "Token exchange failed")?
        .error_for_status()
        .map_err(|_| "Identity provider rejected token exchange")?
        .json()
        .await
        .map_err(|_| "Invalid token response")?;
    if !token.token_type.eq_ignore_ascii_case("bearer") || token.access_token.is_empty() {
        return Err("Unsupported identity token response".into());
    }
    // API independently verifies signature, issuer, audience, expiry and verified email.
    Ok(token.access_token)
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![oidc_sign_in])
        .run(tauri::generate_context!())
        .expect("ConstructPM desktop could not start");
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_bad_callback_state() {
        assert!(callback_code("/callback?code=a&state=wrong", "expected").is_err());
    }
    #[test]
    fn parses_one_valid_callback() {
        assert_eq!(
            callback_code("/callback?code=abc&state=ok", "ok").unwrap(),
            "abc"
        );
    }
    #[test]
    fn rejects_duplicate_codes() {
        assert!(callback_code("/callback?code=a&code=b&state=ok", "ok").is_err());
    }
    #[test]
    fn requires_https() {
        assert!(https_url("http://identity.example").is_err());
    }
}
