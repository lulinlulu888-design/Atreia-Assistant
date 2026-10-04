// SPDX-License-Identifier: GPL-3.0-only
use atreia_combat_backend::{Backend, Input, bundled_dot_skills};
use std::io::{self, BufRead, Read, Write};

fn run() -> Result<(), String> {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 3 || args[1] != "--client" {
        return Err("Usage: atreia-combat-backend --client steam|purple\nInput: NDJSON {flow,timestamp_ms,payload_hex}; offline/reassembled payloads only. Current game compatibility is unverified.".into());
    }
    let mut backend = Backend::new(&args[2], bundled_dot_skills())?;
    let mut reader = io::stdin().lock();
    let mut output = io::stdout().lock();
    loop {
        let mut line = Vec::new();
        // Bounded input: do not let read_line allocate for an unbounded record.
        let length = reader
            .by_ref()
            .take(150_001)
            .read_until(b'\n', &mut line)
            .map_err(|e| e.to_string())?;
        if length == 0 {
            break;
        }
        if length > 150_000 {
            return Err("input record exceeds limit".into());
        }
        let input: Input =
            serde_json::from_slice(&line).map_err(|e| format!("invalid input: {e}"))?;
        let snapshot = backend.feed(input)?;
        serde_json::to_writer(&mut output, &snapshot).map_err(|e| e.to_string())?;
        writeln!(&mut output).map_err(|e| e.to_string())?;
        output.flush().map_err(|e| e.to_string())?;
    }
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("Atreia backend: {error}");
        std::process::exit(1);
    }
}
