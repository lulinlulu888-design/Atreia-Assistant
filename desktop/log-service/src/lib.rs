//! The log service: turn an uploaded Evidence Slice into the fight it records.
//!
//! One route, `POST /derive`, reachable only through a service binding from the
//! a2tools.app Worker (this Worker has no public route; see wrangler.toml). The
//! site handles accounts, storage and access; this does the one thing the site
//! cannot: run the meter's own parser, compiled to wasm32, over the slice, so a
//! log shows what the packets say rather than what a client claimed.
//!
//! Stateless and deterministic: the same slice and the same build give the
//! same record, byte for byte. That is what lets a log be re-derived later, by
//! anyone with the slice and the published source.

use std::io::Read;

use a2tools_dps_meter_lib::rederive::{derive_fight, DeriveError};
use flate2::read::GzDecoder;
use worker::*;

/// The meter's own data tables, compiled in. Without the NPC table no target
/// counts as a boss and nothing is derived; without the DoT list ticks are
/// filed as direct hits. English, because the stored record is language
/// neutral apart from names, and the site translates by code.
const NPCS: &str = include_str!("../../src/data/i18n/npcs/en.json");
const SKILLS: &str = include_str!("../../src/data/i18n/skills/en.json");
const DOTS: &str = include_str!("../../src/data/dot_skill_ids.json");

/// Upper bounds, generous against real slices (a party boss fight gzips to
/// tens of KB) and tight against anything built to make this Worker work.
const MAX_GZIPPED: usize = 4 * 1024 * 1024;
const MAX_INFLATED: u64 = 24 * 1024 * 1024;

#[event(fetch)]
async fn fetch(mut req: Request, env: Env, _ctx: Context) -> Result<Response> {
    if req.method() != Method::Post || req.path() != "/derive" {
        return Response::error("not found", 404);
    }
    // Defence in depth: the binding is the real boundary, but a Worker that
    // does expensive work on request should not trust that nobody ever adds a
    // route to it by mistake.
    let key = env.secret("LOG_SERVICE_KEY").map(|s| s.to_string()).unwrap_or_default();
    let presented = req.headers().get("x-a2-service-key")?.unwrap_or_default();
    if key.is_empty() || !constant_time_eq(key.as_bytes(), presented.as_bytes()) {
        return Response::error("forbidden", 403);
    }

    let body = req.bytes().await?;
    if body.len() > MAX_GZIPPED {
        return error("too_large", "The slice is larger than any real fight.", 413);
    }
    let mut slice = Vec::new();
    if GzDecoder::new(&body[..]).take(MAX_INFLATED + 1).read_to_end(&mut slice).is_err() {
        return error("not_gzip", "The body must be a gzipped Evidence Slice.", 400);
    }
    if slice.len() as u64 > MAX_INFLATED {
        return error("too_large", "The slice inflates past any real fight.", 413);
    }

    match derive_fight(&slice, NPCS, SKILLS, DOTS) {
        Ok(fight) => Response::from_json(&fight),
        Err(DeriveError::NotASlice) => error("not_a_slice", "Not an Evidence Slice this build reads.", 422),
        Err(DeriveError::NothingDerived) => error("no_fight", "The slice contains no boss fight.", 422),
    }
}

fn error(code: &str, message: &str, status: u16) -> Result<Response> {
    Ok(Response::from_json(&serde_json::json!({ "error": code, "message": message }))?
        .with_status(status))
}

fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.iter().zip(b).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}
