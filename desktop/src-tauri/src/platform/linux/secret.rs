//! Keeping the account token in the desktop keyring (KWallet, GNOME Keyring,
//! KeePassXC…) through the Secret Service D-Bus API. See `account::secret` for
//! what this does and does not protect against; the keyring is unlocked with
//! the user's login, so it protects against the same things DPAPI does.
//!
//! DPAPI hands back ciphertext for the caller to write to a file. The keyring
//! holds the secret itself, so what goes in the file here is only a reference
//! to the keyring item (`REFERENCE` plus a per-save id), and `forget` deletes
//! the item when the token is cleared.

use std::collections::HashMap;

use secret_service::blocking::{Collection, SecretService};
use secret_service::EncryptionType;

use crate::platform::UnsealError;

const REFERENCE: &[u8] = b"secret-service:";
const APPLICATION: &str = "a2tools-dps-meter";

/// Whether a keyring answers on this desktop. Without one (no KWallet or
/// GNOME Keyring running) the token is not kept, rather than kept in the clear.
pub fn available() -> bool {
    connect().is_some()
}

fn connect<'a>() -> Option<SecretService<'a>> {
    // Dh: the secret crosses the bus encrypted, not as plain bytes.
    match SecretService::connect(EncryptionType::Dh) {
        Ok(ss) => Some(ss),
        Err(e) => {
            tracing::warn!("No desktop keyring (Secret Service) available: {e}");
            None
        }
    }
}

/// A collection to store into, unlocked, or why there is none. A keyring with
/// no collection yet (a fresh GNOME Keyring, some minimal desktops) gets a
/// default one, which shows the keyring's own "create keyring" prompt.
fn collection<'a>(ss: &'a SecretService<'a>) -> Result<Collection<'a>, String> {
    let collection = match ss.get_any_collection() {
        Ok(collection) => collection,
        Err(e) => {
            tracing::warn!("The keyring has no collection ({e}); asking to create one");
            ss.create_collection("Login", "default").map_err(|e| {
                tracing::warn!("Creating a keyring collection failed: {e}");
                "the keyring has no collection to store it in, and creating one failed or was cancelled"
                    .to_string()
            })?
        }
    };
    // `unlock` shows the keyring's password prompt; `ensure_unlocked` only
    // reports that the collection is locked.
    let locked = collection.is_locked().map_err(|e| {
        tracing::warn!("Could not ask the keyring whether it is locked: {e}");
        format!("the keyring did not answer ({e})")
    })?;
    if locked {
        collection.unlock().map_err(|e| {
            tracing::warn!("Unlocking the keyring failed: {e}");
            "the keyring stayed locked (the unlock was cancelled or failed)".to_string()
        })?;
    }
    Ok(collection)
}

fn attributes<'a>(entropy: &'a str, id: &'a str) -> HashMap<&'a str, &'a str> {
    HashMap::from([("application", APPLICATION), ("purpose", entropy), ("id", id)])
}

/// A fresh id for each save, so saves never overwrite each other's items.
/// It only has to be unique, not secret.
fn new_id() -> String {
    use std::sync::atomic::{AtomicU64, Ordering};
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or_default();
    format!("{nanos:x}-{:x}-{:x}", std::process::id(), COUNTER.fetch_add(1, Ordering::Relaxed))
}

fn parse_reference(sealed: &[u8]) -> Option<&str> {
    let id = std::str::from_utf8(sealed.strip_prefix(REFERENCE)?).ok()?;
    (!id.is_empty()).then_some(id)
}

pub fn protect(plaintext: &[u8], entropy: &[u8]) -> Result<Vec<u8>, String> {
    let entropy = std::str::from_utf8(entropy).map_err(|e| e.to_string())?;
    let ss = connect().ok_or(
        "no desktop keyring is running (GNOME Keyring, KWallet or KeePassXC with Secret Service on)",
    )?;
    let collection = collection(&ss)?;
    let id = new_id();
    if let Err(e) = collection.create_item(
        "A2Tools DPS Meter account",
        attributes(entropy, &id),
        plaintext,
        true,
        "text/plain",
    ) {
        tracing::error!("Could not store the account token in the keyring: {e}");
        return Err(format!("the keyring refused to store it ({e})"));
    }
    Ok([REFERENCE, id.as_bytes()].concat())
}

pub fn unprotect(sealed: &[u8], entropy: &[u8]) -> Result<Vec<u8>, UnsealError> {
    let id = parse_reference(sealed).ok_or(UnsealError::Invalid)?;
    let entropy = std::str::from_utf8(entropy).map_err(|_| UnsealError::Invalid)?;
    // Everything below can pass: the keyring may start later, a dismissed
    // unlock prompt may be accepted next time, and an item can be hidden in a
    // collection that is still locked.
    let ss = connect().ok_or(UnsealError::Unavailable)?;
    let found = ss
        .search_items(attributes(entropy, id))
        .map_err(|_| UnsealError::Unavailable)?;
    let item = match (found.unlocked.into_iter().next(), found.locked.into_iter().next()) {
        (Some(item), _) => item,
        (None, Some(item)) => {
            item.unlock().map_err(|_| UnsealError::Unavailable)?;
            item
        }
        (None, None) => return Err(UnsealError::Unavailable),
    };
    item.get_secret().map_err(|_| UnsealError::Unavailable)
}

pub fn forget(sealed: &[u8]) {
    let Some(id) = parse_reference(sealed) else { return };
    let Some(ss) = connect() else { return };
    // Every purpose: the reference alone identifies the item.
    let attrs = HashMap::from([("application", APPLICATION), ("id", id)]);
    let Ok(found) = ss.search_items(attrs) else { return };
    for item in found.unlocked.into_iter().chain(found.locked) {
        if let Err(e) = item.delete() {
            tracing::warn!("Could not remove the account token from the keyring: {e}");
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn references_are_recognised_and_nothing_else_is() {
        assert_eq!(parse_reference(b"secret-service:abc-1-0"), Some("abc-1-0"));
        assert_eq!(parse_reference(b"secret-service:"), None);
        assert_eq!(parse_reference(b"not dpapi output"), None);
        assert_ne!(new_id(), new_id());
    }

    #[test]
    fn a_reference_the_keyring_cannot_serve_is_not_invalid() {
        // No keyring, a locked one, or no such item: the reference stays.
        assert_eq!(
            unprotect(b"secret-service:no-such-item", b"a2tools.account.v1"),
            Err(UnsealError::Unavailable)
        );
        assert_eq!(unprotect(b"not a reference", b"a2tools.account.v1"), Err(UnsealError::Invalid));
    }
}
