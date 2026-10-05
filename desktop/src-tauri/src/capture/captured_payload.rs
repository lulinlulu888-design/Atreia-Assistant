/// Raw TCP payload captured from pcap.
#[derive(Debug, Clone)]
pub struct CapturedPayload {
    pub src_port: u16,
    pub dst_port: u16,
    pub data: Vec<u8>,
    pub device_name: Option<String>,
    pub captured_at_ms: i64,
    pub src_ip: Option<String>,
    pub dst_ip: Option<String>,
    pub tcp_seq: u32,
    pub tcp_ack: u32,
}
