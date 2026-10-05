use std::ffi::{c_char, c_int, c_long, c_uint, CStr, CString};
use std::ptr;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use libloading::{Library, Symbol};
use tokio::sync::mpsc;
use tracing::{error, info, warn};

use super::captured_payload::CapturedPayload;

fn now_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as i64
}

// ===== Raw pcap FFI types =====

type PcapT = *mut std::ffi::c_void;
type PcapIfT = *mut PcapIf;

#[repr(C)]
struct PcapIf {
    next: *mut PcapIf,
    name: *const c_char,
    description: *const c_char,
    addresses: *mut PcapAddr,
    flags: c_uint,
}

#[repr(C)]
struct PcapAddr {
    next: *mut PcapAddr,
    addr: *mut SockAddr,
    netmask: *mut SockAddr,
    broadaddr: *mut SockAddr,
    dstaddr: *mut SockAddr,
}

#[repr(C)]
struct SockAddr {
    sa_family: u16,
    sa_data: [u8; 14],
}

/// `struct pcap_pkthdr`. The timestamp is a C `struct timeval`, two `long`s:
/// 32-bit on Windows, 64-bit on 64-bit Linux. Declaring them `i32` (as this
/// once did) reads `caplen` from the middle of the timestamp on Linux.
#[repr(C)]
struct PcapPkthdr {
    ts_sec: c_long,
    ts_usec: c_long,
    caplen: c_uint,
    len: c_uint,
}

const PCAP_IF_LOOPBACK: c_uint = 0x00000001;

// ===== Device info =====

#[derive(Clone)]
struct DeviceInfo {
    name: String,
    description: String,
    has_addresses: bool,
    is_loopback: bool,
}

impl DeviceInfo {
    fn label(&self) -> &str {
        if self.description.is_empty() {
            &self.name
        } else {
            &self.description
        }
    }

    fn is_virtual(&self) -> bool {
        let label = self.label().to_lowercase();
        self.is_loopback
            || self.name.to_lowercase().contains("loopback")
            || label.contains("loopback")
            || label.contains("tap-windows")
            || label.contains("tap")
            || label.contains("wintun")
            || label.contains("wireguard")
    }
}

// ===== Pcap library wrapper =====

struct PcapLib {
    _lib: Library,
    findalldevs: unsafe extern "C" fn(*mut PcapIfT, *mut c_char) -> c_int,
    freealldevs: unsafe extern "C" fn(PcapIfT),
    open_live: unsafe extern "C" fn(*const c_char, c_int, c_int, c_int, *mut c_char) -> PcapT,
    close: unsafe extern "C" fn(PcapT),
    next_ex: unsafe extern "C" fn(PcapT, *mut *mut PcapPkthdr, *mut *const u8) -> c_int,
    datalink: unsafe extern "C" fn(PcapT) -> c_int,
}

impl PcapLib {
    fn load() -> Result<Self, String> {
        #[cfg(target_os = "windows")]
        let lib = crate::platform::pcap::load_library()?;
        #[cfg(not(target_os = "windows"))]
        let lib = {
        // The first of the OS's names for the library that loads.
        let mut errors = Vec::new();
        let mut loaded = None;
        for name in crate::platform::pcap::LIBRARIES {
            // SAFETY: loading libpcap runs no initialisation we depend on not running.
            match unsafe { Library::new(name) } {
                Ok(lib) => {
                    loaded = Some(lib);
                    break;
                }
                Err(e) => errors.push(format!("{name}: {e}")),
            }
        }
        let lib = loaded.ok_or_else(|| {
            format!(
                "Failed to load {}. {}\nError: {}",
                crate::platform::pcap::LIBRARIES.join(" or "),
                crate::platform::pcap::MISSING_HELP,
                errors.join("; ")
            )
        })?;
        lib
        };

        unsafe {
            let findalldevs: Symbol<unsafe extern "C" fn(*mut PcapIfT, *mut c_char) -> c_int> =
                lib.get(b"pcap_findalldevs").map_err(|e| format!("pcap_findalldevs: {}", e))?;
            let freealldevs: Symbol<unsafe extern "C" fn(PcapIfT)> =
                lib.get(b"pcap_freealldevs").map_err(|e| format!("pcap_freealldevs: {}", e))?;
            let open_live: Symbol<
                unsafe extern "C" fn(*const c_char, c_int, c_int, c_int, *mut c_char) -> PcapT,
            > = lib.get(b"pcap_open_live").map_err(|e| format!("pcap_open_live: {}", e))?;
            let close: Symbol<unsafe extern "C" fn(PcapT)> =
                lib.get(b"pcap_close").map_err(|e| format!("pcap_close: {}", e))?;
            let next_ex: Symbol<
                unsafe extern "C" fn(PcapT, *mut *mut PcapPkthdr, *mut *const u8) -> c_int,
            > = lib.get(b"pcap_next_ex").map_err(|e| format!("pcap_next_ex: {}", e))?;
            let datalink: Symbol<unsafe extern "C" fn(PcapT) -> c_int> =
                lib.get(b"pcap_datalink").map_err(|e| format!("pcap_datalink: {}", e))?;

            Ok(Self {
                findalldevs: *findalldevs,
                freealldevs: *freealldevs,
                open_live: *open_live,
                close: *close,
                next_ex: *next_ex,
                datalink: *datalink,
                _lib: lib,
            })
        }
    }

    fn find_all_devs(&self) -> Result<Vec<DeviceInfo>, String> {
        let mut alldevs: PcapIfT = ptr::null_mut();
        let mut errbuf = [0u8; 256];

        let ret =
            unsafe { (self.findalldevs)(&mut alldevs, errbuf.as_mut_ptr() as *mut c_char) };

        if ret != 0 || alldevs.is_null() {
            let err = unsafe { CStr::from_ptr(errbuf.as_ptr() as *const c_char) }
                .to_string_lossy()
                .to_string();
            return Err(format!("pcap_findalldevs failed: {}", err));
        }

        let mut devices = Vec::new();
        let mut dev = alldevs;
        while !dev.is_null() {
            let d = unsafe { &*dev };
            let name = if d.name.is_null() {
                String::new()
            } else {
                unsafe { CStr::from_ptr(d.name) }
                    .to_string_lossy()
                    .to_string()
            };
            let description = if d.description.is_null() {
                String::new()
            } else {
                unsafe { CStr::from_ptr(d.description) }
                    .to_string_lossy()
                    .to_string()
            };
            let has_addresses = !d.addresses.is_null();
            let is_loopback = (d.flags & PCAP_IF_LOOPBACK) != 0;

            devices.push(DeviceInfo {
                name,
                description,
                has_addresses,
                is_loopback,
            });
            dev = d.next;
        }

        unsafe { (self.freealldevs)(alldevs) };
        Ok(devices)
    }

    fn open_live_handle(&self, name: &str) -> Result<PcapT, String> {
        let c_name = CString::new(name).map_err(|e| format!("Invalid device name: {}", e))?;
        let mut errbuf = [0u8; 256];

        let handle = unsafe {
            (self.open_live)(
                c_name.as_ptr(),
                65535,  // snaplen
                1,      // promiscuous
                100,    // timeout ms
                errbuf.as_mut_ptr() as *mut c_char,
            )
        };

        if handle.is_null() {
            let err = unsafe { CStr::from_ptr(errbuf.as_ptr() as *const c_char) }
                .to_string_lossy()
                .to_string();
            return Err(format!("pcap_open_live failed: {}", err));
        }

        Ok(handle)
    }
}

// Safety: PcapLib function pointers are thread-safe (each thread gets its own pcap handle)
unsafe impl Send for PcapLib {}
unsafe impl Sync for PcapLib {}

/// Manages pcap device handles and captures TCP traffic from network interfaces.
/// Loads the OS's pcap library at runtime (`platform::pcap::LIBRARIES`) — no SDK
/// needed at compile time.
pub struct PcapCapturer {
    running: Arc<AtomicBool>,
    sender: mpsc::Sender<CapturedPayload>,
}

impl PcapCapturer {
    pub fn new(sender: mpsc::Sender<CapturedPayload>) -> Self {
        Self {
            running: Arc::new(AtomicBool::new(false)),
            sender,
        }
    }

    pub fn start(&mut self) {
        if self.is_running() {
            return;
        }
        // A stopped session's workers must never be revived by a later start.
        self.running = Arc::new(AtomicBool::new(true));

        let pcap = match PcapLib::load() {
            Ok(p) => Arc::new(p),
            Err(e) => {
                error!("{}", e);
                self.running.store(false, Ordering::SeqCst);
                return;
            }
        };

        let devices = match pcap.find_all_devs() {
            Ok(d) => d,
            Err(e) => {
                error!("Failed to list devices: {}", e);
                self.running.store(false, Ordering::SeqCst);
                return;
            }
        };

        // Only capture on devices that have addresses, and that this OS does not
        // rule out (Linux's catch-all "any" would duplicate every packet).
        let devices: Vec<_> = devices
            .into_iter()
            .filter(|d| d.has_addresses && !crate::platform::pcap::skip_device(&d.name))
            .collect();

        if devices.is_empty() {
            error!("No capture devices found with addresses");
            self.running.store(false, Ordering::SeqCst);
            return;
        }

        info!("Found {} capture devices", devices.len());
        for (i, dev) in devices.iter().enumerate() {
            info!(
                "  [{}] {} (loopback={}, addresses={})",
                i,
                dev.label(),
                dev.is_loopback,
                dev.has_addresses
            );
        }

        let virtual_devices: Vec<_> = devices.iter().filter(|d| d.is_virtual()).cloned().collect();
        let physical_devices: Vec<_> = devices.iter().filter(|d| !d.is_virtual()).cloned().collect();

        // Start virtual/loopback devices first
        for device in &virtual_devices {
            start_capture_thread(
                device.clone(),
                pcap.clone(),
                self.sender.clone(),
                self.running.clone(),
            );
        }

        if virtual_devices.is_empty() {
            // No virtual devices — start physical immediately
            for device in &physical_devices {
                start_capture_thread(
                    device.clone(),
                    pcap.clone(),
                    self.sender.clone(),
                    self.running.clone(),
                );
            }
        } else {
            // Start physical after delay as fallback
            let running = self.running.clone();
            let sender = self.sender.clone();
            let pcap2 = pcap.clone();
            std::thread::spawn(move || {
                std::thread::sleep(std::time::Duration::from_millis(1500));
                if !running.load(Ordering::SeqCst) {
                    return;
                }
                for device in &physical_devices {
                    info!("Starting capture on physical device: {}", device.label());
                    start_capture_thread(
                        device.clone(),
                        pcap2.clone(),
                        sender.clone(),
                        running.clone(),
                    );
                }
            });
        }
    }

    pub fn stop(&self) {
        self.running.store(false, Ordering::SeqCst);
    }

    pub fn is_running(&self) -> bool {
        self.running.load(Ordering::SeqCst)
    }
}

/// List available capture device labels (for the settings UI dropdown).
pub fn list_device_labels() -> Result<Vec<String>, String> {
    let pcap = PcapLib::load().map_err(|e| e.to_string())?;
    let devices = pcap.find_all_devs().map_err(|e| e.to_string())?;
    Ok(devices
        .into_iter()
        .filter(|d| d.has_addresses && !crate::platform::pcap::skip_device(&d.name))
        .map(|d| d.label().to_string())
        .collect())
}

fn start_capture_thread(
    device: DeviceInfo,
    pcap: Arc<PcapLib>,
    sender: mpsc::Sender<CapturedPayload>,
    running: Arc<AtomicBool>,
) {
    let label = device.label().to_string();
    let dev_name = device.name.clone();

    std::thread::spawn(move || {
        if !running.load(Ordering::SeqCst) {
            return;
        }
        let handle = match pcap.open_live_handle(&dev_name) {
            Ok(h) => h,
            Err(e) => {
                warn!("Failed to open capture on {}: {}", label, e);
                return;
            }
        };

        let link_type = unsafe { (pcap.datalink)(handle) };
        info!("Capture active on {} (link type {})", label, link_type);

        while running.load(Ordering::SeqCst) {
            let mut header: *mut PcapPkthdr = ptr::null_mut();
            let mut data: *const u8 = ptr::null();

            let ret = unsafe { (pcap.next_ex)(handle, &mut header, &mut data) };
            if !running.load(Ordering::SeqCst) {
                break;
            }

            match ret {
                1 => {
                    let hdr = unsafe { &*header };
                    let len = hdr.caplen as usize;
                    // Use pcap hardware timestamp (seconds + microseconds since epoch)
                    let pcap_ts_ms = (hdr.ts_sec as i64) * 1000 + (hdr.ts_usec as i64) / 1000;
                    // Sanity check: if pcap timestamp looks bogus, fall back to wall clock
                    let ts = if pcap_ts_ms > 1_000_000_000_000 && pcap_ts_ms < 2_000_000_000_000 {
                        pcap_ts_ms
                    } else {
                        now_ms()
                    };
                    let frame = unsafe { std::slice::from_raw_parts(data, len) };
                    if let Some(mut payload) = parse_tcp_payload(frame, link_type, &label) {
                        payload.captured_at_ms = ts;
                        let _ = sender.try_send(payload);
                    }
                }
                0 => continue, // Timeout
                -2 => break,   // EOF (savefile)
                _ => {
                    warn!("Capture error on {} (ret={})", label, ret);
                    break;
                }
            }
        }

        unsafe { (pcap.close)(handle) };
        info!("Capture stopped on {}", label);
    });
}

/// Where IPv4 starts in a frame of pcap link type `link_type`, or `None` if this
/// frame is not IPv4 under that type. Link types are libpcap's (DLT_*/LINKTYPE_*),
/// the same on every OS.
fn link_header_len(link_type: c_int, frame: &[u8]) -> Option<usize> {
    let be16 = |at: usize| frame.get(at..at + 2).map(|b| u16::from_be_bytes([b[0], b[1]]));
    match link_type {
        // Ethernet, with up to two 802.1Q / 802.1ad VLAN tags (some NICs, e.g.
        // Realtek with "Priority & VLAN" on, tag every frame).
        1 => {
            let mut at = 12;
            for _ in 0..2 {
                match be16(at)? {
                    0x8100 | 0x88A8 => at += 4,
                    _ => break,
                }
            }
            (be16(at)? == 0x0800).then_some(at + 2)
        }
        // BSD loopback / Npcap loopback: 4-byte address family, AF_INET = 2.
        0 => (frame.get(..4)? == [2, 0, 0, 0]).then_some(4),
        // Raw IP (VPN and tunnel adapters, WireGuard).
        12 | 14 | 101 | 228 => Some(0),
        // Linux "cooked" capture v1: protocol at bytes 14-15, 16-byte header.
        113 => (be16(14)? == 0x0800).then_some(16),
        // Linux "cooked" capture v2: protocol at bytes 0-1, 20-byte header.
        276 => (be16(0)? == 0x0800).then_some(20),
        _ => None,
    }
}

/// The original guess at the link layer, from the frame alone. Kept as the
/// fallback so nothing that parsed before the link type was consulted can stop
/// parsing now.
fn guess_link_header_len(frame: &[u8]) -> Option<usize> {
    if frame.len() >= 14 {
        let ether_type = u16::from_be_bytes([frame[12], frame[13]]);
        if ether_type == 0x0800 {
            Some(14) // Standard Ethernet
        } else if frame[0] == 2 && frame[1] == 0 && frame[2] == 0 && frame[3] == 0 {
            Some(4) // NULL/Loopback: AF_INET (little-endian 2) = IPv4
        } else if (frame[0] >> 4) == 4 {
            Some(0) // Raw IPv4
        } else {
            None
        }
    } else if (frame[0] >> 4) == 4 {
        Some(0) // Raw IPv4 (short frame)
    } else {
        None
    }
}

/// Parse raw captured frame to extract TCP payload. The link type says where
/// IPv4 starts; when it does not fit, the frame-only guess gets a chance.
fn parse_tcp_payload(frame: &[u8], link_type: c_int, device_name: &str) -> Option<CapturedPayload> {
    if frame.len() < 4 {
        return None;
    }
    let ip_offset = link_header_len(link_type, frame)
        .filter(|&at| frame.get(at).is_some_and(|b| b >> 4 == 4))
        .or_else(|| guess_link_header_len(frame))?;

    if frame.len() < ip_offset + 20 {
        return None;
    }
    let ip_header = &frame[ip_offset..];
    if ip_header[0] >> 4 != 4 {
        return None;
    }
    let ip_header_len = ((ip_header[0] & 0x0F) as usize) * 4;
    if ip_header[9] != 6 {
        return None; // Not TCP
    }

    let src_ip = format!(
        "{}.{}.{}.{}",
        ip_header[12], ip_header[13], ip_header[14], ip_header[15]
    );
    let dst_ip = format!(
        "{}.{}.{}.{}",
        ip_header[16], ip_header[17], ip_header[18], ip_header[19]
    );

    let tcp_offset = ip_offset + ip_header_len;
    if frame.len() < tcp_offset + 20 {
        return None;
    }
    let tcp_header = &frame[tcp_offset..];
    let src_port = u16::from_be_bytes([tcp_header[0], tcp_header[1]]);
    let dst_port = u16::from_be_bytes([tcp_header[2], tcp_header[3]]);
    let tcp_seq = u32::from_be_bytes([tcp_header[4], tcp_header[5], tcp_header[6], tcp_header[7]]);
    let tcp_ack =
        u32::from_be_bytes([tcp_header[8], tcp_header[9], tcp_header[10], tcp_header[11]]);
    let tcp_header_len = ((tcp_header[12] >> 4) as usize) * 4;

    let payload_offset = tcp_offset + tcp_header_len;
    if payload_offset >= frame.len() {
        return None;
    }
    let payload = &frame[payload_offset..];
    if payload.is_empty() {
        return None;
    }

    Some(CapturedPayload {
        src_port,
        dst_port,
        data: payload.to_vec(),
        device_name: Some(device_name.to_string()),
        captured_at_ms: now_ms(),
        src_ip: Some(src_ip),
        dst_ip: Some(dst_ip),
        tcp_seq,
        tcp_ack,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// IPv4 + TCP from 10.0.0.2:51000 to 193.202.112.99:13328, payload "hi".
    fn ipv4_tcp() -> Vec<u8> {
        let mut ip = vec![0x45, 0, 0, 42, 0, 0, 0, 0, 64, 6, 0, 0, 10, 0, 0, 2, 193, 202, 112, 99];
        let tcp = [0xC7, 0x38, 0x34, 0x10, 0, 0, 0, 1, 0, 0, 0, 0, 0x50, 0x18, 0, 0, 0, 0, 0, 0];
        ip.extend_from_slice(&tcp);
        ip.extend_from_slice(b"hi");
        ip
    }

    fn check(link_type: c_int, header: &[u8]) {
        let frame = [header, &ipv4_tcp()].concat();
        let p = parse_tcp_payload(&frame, link_type, "dev").expect("parsed");
        assert_eq!((p.src_port, p.dst_port), (51000, 13328), "link type {link_type}");
        assert_eq!(p.dst_ip.as_deref(), Some("193.202.112.99"));
        assert_eq!(p.data, b"hi");
    }

    #[test]
    fn reads_every_link_layer_the_meter_meets() {
        let ether = [[0u8; 12].as_slice(), &[0x08, 0x00]].concat();
        check(1, &ether); // Ethernet / Wi-Fi
        let vlan = [[0u8; 12].as_slice(), &[0x81, 0x00, 0x00, 0x05, 0x08, 0x00]].concat();
        check(1, &vlan); // Ethernet with an 802.1Q tag
        check(0, &[2, 0, 0, 0]); // Npcap / BSD loopback
        check(12, &[]); // raw IP (VPN, WireGuard)
        check(101, &[]);
        let sll = [[0u8; 14].as_slice(), &[0x08, 0x00]].concat();
        check(113, &sll); // Linux cooked v1
        let sll2 = [[0x08u8, 0x00].as_slice(), &[0u8; 18]].concat();
        check(276, &sll2); // Linux cooked v2
    }

    #[test]
    fn an_unknown_or_mismatched_link_type_still_gets_the_old_guess() {
        // Ethernet framing reported as some other link type: guessed as before.
        let ether = [[0u8; 12].as_slice(), &[0x08, 0x00]].concat();
        check(999, &ether);
        // Raw IP on a device that claims Ethernet: the exact read fails, the
        // guess finds IPv4 at 0, as it always did.
        check(1, &[]);
    }

    #[test]
    fn non_ipv4_frames_are_ignored() {
        let arp = [[0u8; 12].as_slice(), &[0x08, 0x06], &[0u8; 28]].concat();
        assert!(parse_tcp_payload(&arp, 1, "dev").is_none());
    }
}
