use super::packet_accumulator::PacketAccumulator;
use super::stream_processor::StreamProcessor;

/// Reassembles TCP stream fragments and feeds complete data to the StreamProcessor.
pub struct StreamAssembler {
    accumulator: PacketAccumulator,
}

impl StreamAssembler {
    pub fn new() -> Self {
        Self {
            accumulator: PacketAccumulator::new(),
        }
    }

    /// Process a TCP chunk. Returns true if any packets were successfully parsed.
    pub fn process_chunk(&mut self, data: &[u8], processor: &mut StreamProcessor) -> bool {
        self.accumulator.append(data);
        let mut parsed_any = false;

        loop {
            if self.accumulator.size() == 0 {
                break;
            }

            let snapshot = self.accumulator.snapshot().to_vec();
            let consumed = processor.consume_stream(&snapshot);

            if consumed > 0 {
                self.accumulator.discard_bytes(consumed);
                parsed_any = true;
            } else {
                break;
            }
        }

        parsed_any
    }

    pub fn buffered_bytes(&self) -> usize {
        self.accumulator.size()
    }
}
