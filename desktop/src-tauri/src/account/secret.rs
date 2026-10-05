//! Keeping the account token off disk in the clear.
//!
//! The token the Device Authorization Grant returns is a bearer credential for
//! this account: anything holding it can read the profile and sync documents
//! until it is revoked. `settings.json` is plain JSON that users open to change
//! their hotkey, so it is the wrong home for it.
//!
//! Windows has DPAPI for exactly this. `CryptProtectData` encrypts with a key
//! derived from the logged-in user, so the file is readable by this user on this
//! machine and nobody else — no key for us to ship, lose, or have extracted from
//! the binary.
//!
//! **What it does not protect against, plainly:** malware already running as
//! this user can call `CryptUnprotectData` exactly as we do. DPAPI stops another
//! account on the machine and stops a copied file being useful elsewhere. It is
//! not a defence against a compromised session, which is why the token is
//! revocable from the website and why it holds narrow scopes.

use std::path::{Path, PathBuf};

/// Where the encrypted token lives, beside the other per-user state.
pub fn token_path(app_data_dir: &Path) -> PathBuf {
    app_data_dir.join("credentials.dat")
}

/// An extra input to the encryption, so a `credentials.dat` lifted from another
/// application's folder cannot be decrypted by ours even under the same user.
const ENTROPY: &[u8] = b"a2tools.account.v1";

/// The OS's per-user secret store (DPAPI on Windows, the desktop keyring on
/// Linux). Where an OS has none,
/// `platform::secret` refuses rather than degrading quietly: storing a token in
/// the clear would be worse than not storing one.
use crate::platform::secret as imp;
use crate::platform::UnsealError;

/// Encrypt and write the token. Returns false if it could not be stored, in
/// which case the caller must treat the account as not connected rather than
/// keeping a token only in memory and appearing connected until restart.
pub fn save(app_data_dir: &Path, token: &str) -> Result<(), String> {
    let sealed = imp::protect(token.as_bytes(), ENTROPY).map_err(|why| {
        tracing::error!("Could not encrypt the account token ({why}); refusing to store it");
        why
    })?;
    let path = token_path(app_data_dir);
    let previous = std::fs::read(&path).ok();
    match std::fs::write(&path, &sealed) {
        Ok(()) => {
            // Where the OS keeps the secret itself (a Linux keyring), the old
            // one would otherwise stay there after the file stops naming it.
            if let Some(previous) = previous {
                imp::forget(&previous);
            }
            Ok(())
        }
        Err(e) => {
            tracing::error!("Could not write the account token: {e}");
            Err(format!("the token file could not be written ({e})"))
        }
    }
}

/// What `load_stored` found.
#[derive(Debug, Clone, PartialEq)]
pub enum Stored {
    Token(String),
    /// No token on this machine.
    Missing,
    /// A token is stored, but the keyring did not hand it over now: not
    /// running yet, locked, unlock dismissed, or the item not visible. The
    /// file is kept for the next try.
    Locked,
}

/// Read the token back, or `None` if there is not a usable one now.
pub fn load(app_data_dir: &Path) -> Option<String> {
    match load_stored(app_data_dir) {
        Stored::Token(token) => Some(token),
        Stored::Missing | Stored::Locked => None,
    }
}

/// Read the token back, and say why when there is none.
///
/// A file that can never decrypt is deleted rather than retried forever: it
/// means the Windows profile changed or the file was copied from elsewhere.
pub fn load_stored(app_data_dir: &Path) -> Stored {
    let path = token_path(app_data_dir);
    let Ok(sealed) = std::fs::read(&path) else { return Stored::Missing };
    match imp::unprotect(&sealed, ENTROPY) {
        Ok(bytes) => match String::from_utf8(bytes) {
            Ok(token) if !token.is_empty() => Stored::Token(token),
            _ => discard(&path),
        },
        Err(UnsealError::Unavailable) => {
            tracing::info!("The keyring did not hand over the account token; keeping it");
            Stored::Locked
        }
        Err(UnsealError::Invalid) => discard(&path),
    }
}

fn discard(path: &Path) -> Stored {
    tracing::warn!("{} could not be decrypted for this user; removing it", path.display());
    let _ = std::fs::remove_file(path);
    Stored::Missing
}

/// Forget the token. Used on sign-out and whenever the server says it is dead.
pub fn clear(app_data_dir: &Path) {
    let path = token_path(app_data_dir);
    if let Ok(sealed) = std::fs::read(&path) {
        imp::forget(&sealed);
    }
    if path.exists() {
        if let Err(e) = std::fs::remove_file(&path) {
            tracing::warn!("Could not remove {}: {e}", path.display());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Nothing to test where the OS keeps no secrets: every save refuses. CI
    // sets A2_REQUIRE_KEYRING where it has started one, so a keyring that
    // failed to come up fails the tests instead of skipping them.
    fn skip() -> bool {
        let available = crate::platform::secret::available();
        if !available && std::env::var_os("A2_REQUIRE_KEYRING").is_some() {
            panic!("A2_REQUIRE_KEYRING is set but no secret store is available");
        }
        !available
    }

    fn temp(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("a2tools-secret-{name}"));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn a_token_round_trips() {
        if skip() {
            return;
        }
        let dir = temp("roundtrip");
        assert!(save(&dir, "tok_abc123").is_ok());
        assert_eq!(load(&dir).as_deref(), Some("tok_abc123"));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn the_file_on_disk_does_not_contain_the_token() {
        if skip() {
            return;
        }
        // The whole point: `settings.json` is readable, this must not be.
        let dir = temp("opaque");
        assert!(save(&dir, "tok_supersecret").is_ok());
        let raw = std::fs::read(token_path(&dir)).unwrap();
        assert!(
            !raw.windows(15).any(|w| w == b"tok_supersecret"),
            "the token is sitting in the file in the clear"
        );
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn clearing_removes_it() {
        if skip() {
            return;
        }
        let dir = temp("clear");
        assert!(save(&dir, "tok_x").is_ok());
        clear(&dir);
        assert!(load(&dir).is_none());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn a_corrupt_file_is_discarded_rather_than_retried() {
        if skip() {
            return;
        }
        let dir = temp("corrupt");
        std::fs::write(token_path(&dir), b"not dpapi output").unwrap();
        assert!(load(&dir).is_none());
        assert!(
            !token_path(&dir).exists(),
            "an undecryptable file should be removed, not left to fail forever"
        );
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn no_token_is_not_an_error() {
        if skip() {
            return;
        }
        let dir = temp("empty");
        assert!(load(&dir).is_none());
        let _ = std::fs::remove_dir_all(&dir);
    }
}
