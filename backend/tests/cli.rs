// SPDX-License-Identifier: GPL-3.0-only
use serde_json::Value;
use std::io::Write;
use std::process::{Command, Stdio};

fn run(client: &str, input: &str) -> std::process::Output {
    let mut child = Command::new(env!("CARGO_BIN_EXE_atreia-combat-backend"))
        .args(["--client", client])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(input.as_bytes())
        .unwrap();
    child.wait_with_output().unwrap()
}

#[test]
fn steam_and_purple_cli_parse_wire_records_without_network() {
    // Synthetic skill 20 is in the pinned upstream DoT allowlist.
    let input = concat!(
        "{\"flow\":\"test\",\"timestamp_ms\":1000,\"payload_hex\":\"0f053878026400d007000032\"}\n",
        "{\"flow\":\"test\",\"timestamp_ms\":2000,\"payload_hex\":\"0f0538780b6400d00700001e\"}\n"
    );
    for client in ["steam", "purple"] {
        let output = run(client, input);
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        let text = String::from_utf8(output.stdout).unwrap();
        let snapshots: Vec<Value> = text
            .lines()
            .map(|l| serde_json::from_str(l).unwrap())
            .collect();
        assert_eq!(snapshots.len(), 2);
        assert_eq!(snapshots[1]["client"], client);
        assert_eq!(snapshots[1]["targets"][0]["damage"], 50);
        assert_eq!(snapshots[1]["healing"][0]["healing"], 30);
        assert_eq!(snapshots[1]["compatibility"], "unverified");
    }
}

#[test]
fn cli_rejects_unknown_profiles_and_fields() {
    assert!(!run("unknown", "").status.success());
    let input =
        "{\"flow\":\"test\",\"timestamp_ms\":1000,\"payload_hex\":\"\",\"client\":\"purple\"}\n";
    let output = run("steam", input);
    assert!(!output.status.success());
    assert!(output.stdout.is_empty());
}

#[test]
fn cli_bounds_record_size() {
    let output = run("steam", &format!("{}\n", "x".repeat(150_001)));
    assert!(!output.status.success());
    assert!(String::from_utf8_lossy(&output.stderr).contains("limit"));
}
