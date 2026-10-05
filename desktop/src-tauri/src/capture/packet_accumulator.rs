/// Growable byte buffer for TCP stream reassembly.
/// Appends incoming chunks and allows the parser to consume bytes from the front.
pub struct PacketAccumulator {
    buffer: Vec<u8>,
}

const MAX_BUFFER_SIZE: usize = 2 * 1024 * 1024;

impl PacketAccumulator {
    pub fn new() -> Self {
        Self {
            buffer: Vec::with_capacity(64 * 1024),
        }
    }

    pub fn append(&mut self, data: &[u8]) {
        if self.buffer.len() > MAX_BUFFER_SIZE {
            tracing::error!("PacketAccumulator buffer exceeded limit, resetting");
            self.buffer.clear();
        }
        self.buffer.extend_from_slice(data);
    }

    pub fn snapshot(&self) -> &[u8] {
        &self.buffer
    }

    pub fn discard_bytes(&mut self, length: usize) {
        if length >= self.buffer.len() {
            self.buffer.clear();
        } else {
            self.buffer.drain(..length);
        }
    }

    pub fn size(&self) -> usize {
        self.buffer.len()
    }
}
