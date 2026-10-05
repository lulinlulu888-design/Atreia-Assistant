//! Encrypting the account token for this user with DPAPI. See
//! `account::secret` for what that does and does not protect against.

use windows::Win32::Foundation::{HLOCAL, LocalFree};

use crate::platform::UnsealError;
use windows::Win32::Security::Cryptography::{
    CRYPT_INTEGER_BLOB, CryptProtectData, CryptUnprotectData,
};

/// This OS has a per-user secret store, so tokens can be kept.
pub fn available() -> bool {
    true
}

/// The protected blob is the whole secret here; deleting the file is enough.
pub fn forget(_sealed: &[u8]) {}

fn blob(bytes: &mut [u8]) -> CRYPT_INTEGER_BLOB {
    CRYPT_INTEGER_BLOB {
        cbData: bytes.len() as u32,
        pbData: bytes.as_mut_ptr(),
    }
}

/// Copy a blob out and hand its buffer back to the OS.
///
/// DPAPI allocates with `LocalAlloc`, so the caller frees with `LocalFree`.
/// Missing this leaks on every save and load.
unsafe fn take(out: &CRYPT_INTEGER_BLOB) -> Vec<u8> {
    let slice = unsafe { std::slice::from_raw_parts(out.pbData, out.cbData as usize) };
    let owned = slice.to_vec();
    let _ = unsafe { LocalFree(Some(HLOCAL(out.pbData as *mut _))) };
    owned
}

pub fn protect(plaintext: &[u8], entropy: &[u8]) -> Result<Vec<u8>, String> {
    let mut input = plaintext.to_vec();
    let mut extra = entropy.to_vec();
    let mut out = CRYPT_INTEGER_BLOB::default();
    unsafe {
        CryptProtectData(
            &blob(&mut input),
            None,
            Some(&blob(&mut extra)),
            None,
            None,
            0,
            &mut out,
        )
        .map_err(|e| format!("Windows could not encrypt it ({e})"))?;
        Ok(take(&out))
    }
}

pub fn unprotect(ciphertext: &[u8], entropy: &[u8]) -> Result<Vec<u8>, UnsealError> {
    let mut input = ciphertext.to_vec();
    let mut extra = entropy.to_vec();
    let mut out = CRYPT_INTEGER_BLOB::default();
    unsafe {
        CryptUnprotectData(
            &blob(&mut input),
            None,
            Some(&blob(&mut extra)),
            None,
            None,
            0,
            &mut out,
        )
        .map_err(|_| UnsealError::Invalid)?;
        Ok(take(&out))
    }
}
