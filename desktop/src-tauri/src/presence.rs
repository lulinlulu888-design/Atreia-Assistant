//! Discord activity: "Playing AION2 — Naicha · Cleric · Lv 29 — Kaisinel (Elyos) · Europe".
//!
//! Opt-in (`dpsMeter.discordActivity`), and shown only while AION2 is open.
//! It talks to the Discord app on this computer over its local IPC socket, so
//! it needs no a2tools.app account and sends nothing anywhere else: Discord
//! already knows who its own user is.
//!
//! Everything shown is what the game has told the meter about the local
//! player (see `DataStorage::local_profile`): class and level from the self
//! record, the server from it or from loot. A field nobody has stated yet is
//! left out rather than guessed.

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};

use discord_rich_presence::activity::{Activity, Assets, Timestamps};
use discord_rich_presence::{DiscordIpc, DiscordIpcClient};
use tauri::Manager;

use crate::app::AppState;
use crate::combat::data_storage::{DataStorage, LocalProfile};
use crate::entity::job_class::JobClass;
use crate::platform::window_detector;

/// The Discord application whose name ("AION2") the activity shows under, and
/// whose art assets hold the class icons (keys as `class_key` returns them).
const DISCORD_APPLICATION_ID: &str = "1556021373401432214";

pub const SETTING_KEY: &str = "dpsMeter.discordActivity";

const TICK: Duration = Duration::from_secs(10);
/// Discord not running: try again this often, not every tick.
const RECONNECT_EVERY: Duration = Duration::from_secs(30);
/// A boss counts as being fought while it took damage this recently.
const FIGHTING_WITHIN_MS: i64 = 20_000;

/// Server names in every language the game ships, and region names.
static SERVERS: std::sync::LazyLock<ServerTable> = std::sync::LazyLock::new(|| {
    serde_json::from_str(include_str!("../../src/data/servers.json")).unwrap_or_default()
});

#[derive(Default, serde::Deserialize)]
struct ServerTable {
    servers: HashMap<String, HashMap<String, String>>,
    regions: HashMap<String, HashMap<String, String>>,
}

/// What the activity says. Compared between ticks so Discord is only told
/// when something changed.
#[derive(Debug, Clone, PartialEq)]
struct Shown {
    details: String,
    /// Class and level alone, for the class image's hover text.
    class_line: String,
    state: String,
    class_key: Option<&'static str>,
    class_name: Option<String>,
}

/// Whether a Discord application is configured into this build at all.
pub fn available() -> bool {
    !DISCORD_APPLICATION_ID.is_empty()
}

pub fn spawn(app: tauri::AppHandle) {
    if !available() {
        return;
    }
    std::thread::Builder::new()
        .name("discord-activity".into())
        .spawn(move || run(app))
        .ok();
}

fn run(app: tauri::AppHandle) {
    let mut client: Option<DiscordIpcClient> = None;
    let mut shown: Option<Shown> = None;
    let mut game_since: Option<i64> = None;
    let mut last_attempt: Option<Instant> = None;
    loop {
        std::thread::sleep(TICK);
        let Some(state) = app.try_state::<AppState>() else { continue };
        let enabled = state.settings.get(SETTING_KEY).as_deref() == Some("true");
        let playing = window_detector::find_aion2_window();
        if !playing {
            game_since = None;
        }
        if !enabled || !playing {
            if let Some(mut c) = client.take() {
                let _ = c.clear_activity();
                let _ = c.close();
                tracing::info!("Discord activity cleared");
            }
            shown = None;
            continue;
        }
        let since = *game_since.get_or_insert_with(crate::clock::now_ms);

        let lang = state.settings.get("dpsMeter.language").unwrap_or_else(|| "en".into());
        let text = Texts::load(state.i18n_data_dir.as_ref(), &lang);
        let next = describe(&state.data_storage, &state, &text, &lang);
        if shown.as_ref() == Some(&next) && client.is_some() {
            continue;
        }

        if client.is_none() {
            if last_attempt.is_some_and(|t| t.elapsed() < RECONNECT_EVERY) {
                continue;
            }
            last_attempt = Some(Instant::now());
            let mut c = DiscordIpcClient::new(DISCORD_APPLICATION_ID);
            match c.connect() {
                Ok(()) => {
                    tracing::info!("Discord activity: connected to Discord");
                    client = Some(c);
                }
                Err(e) => {
                    tracing::debug!("Discord activity: Discord not reachable ({e})");
                    continue;
                }
            }
        }
        let Some(c) = client.as_mut() else { continue };
        let mut assets = Assets::new().small_image("a2tools").small_text("A2Tools DPS Meter");
        // The image's hover text is the class with its level ("Cleric · Lv
        // 30"): the line beside it adds the name.
        if let Some(key) = next.class_key {
            assets = assets.large_image(key).large_text(next.class_line.as_str());
        }
        let mut activity = Activity::new()
            .details(next.details.as_str())
            .assets(assets)
            .timestamps(Timestamps::new().start(since));
        if !next.state.is_empty() {
            activity = activity.state(next.state.as_str());
        }
        match c.set_activity(activity) {
            Ok(()) => shown = Some(next),
            Err(e) => {
                // Discord closed or restarted: connect again on a later tick.
                tracing::info!("Discord activity: lost Discord ({e}); will reconnect");
                client = None;
                shown = None;
            }
        }
    }
}

/// The class's art-asset key in the Discord application.
fn class_key(class: JobClass) -> &'static str {
    match class {
        JobClass::Gladiator => "gladiator",
        JobClass::Templar => "templar",
        JobClass::Ranger => "ranger",
        JobClass::Assassin => "assassin",
        JobClass::Sorcerer => "sorcerer",
        JobClass::Cleric => "cleric",
        // The asset is named for the class as the game calls it.
        JobClass::Elementalist => "spiritmaster",
        JobClass::Chanter => "chanter",
        JobClass::Fighter => "brawler",
    }
}

fn describe(storage: &Arc<DataStorage>, state: &AppState, text: &Texts, lang: &str) -> Shown {
    let profile = storage.local_profile();
    let class_name = profile.class.map(|c| text.class(c));
    let mut details: Vec<String> = Vec::new();
    if let Some(name) = &class_name {
        details.push(name.clone());
    }
    if let Some(level) = profile.level {
        details.push(text.get("level", "Lv {level}").replace("{level}", &level.to_string()));
    }
    let class_line = if details.is_empty() { text.get("inGame", "In game") } else { details.join(" · ") };
    // The character's name leads: "Naicha · Cleric · Lv 30".
    let details = match profile.name.as_deref().map(str::trim).filter(|n| !n.is_empty()) {
        Some(name) => format!("{name} · {class_line}"),
        None => class_line.clone(),
    };

    let state_line = fighting(storage, state)
        .map(|boss| text.get("fighting", "Fighting {boss}").replace("{boss}", &boss))
        .or_else(|| in_dungeon(storage.current_dungeon_id(), state.i18n_data_dir.as_ref(), text, lang))
        .unwrap_or_else(|| where_from(&profile, text, lang));

    Shown {
        details,
        class_line,
        state: state_line,
        class_key: profile.class.map(class_key),
        class_name,
    }
}

/// The boss being fought right now, by name, if any.
fn fighting(storage: &Arc<DataStorage>, state: &AppState) -> Option<String> {
    let target = storage.current_target();
    if target == 0 {
        return None;
    }
    let code = *storage.get_mob_data().get(&target)?;
    if !state.npc_lookup.is_boss(code) || state.npc_lookup.is_training_dummy(code) {
        return None;
    }
    let last_hit = storage.get_combat_snapshot_light().get(&target)?.last_damage_time;
    if crate::clock::now_ms() - last_hit > FIGHTING_WITHIN_MS {
        return None;
    }
    let name = state.npc_lookup.get_npc_name(code);
    (!name.is_empty()).then_some(name)
}

/// "Urugugu Canyon · Conquest (Normal)", for the instance the party roster
/// says you are in. Its last digit is the difficulty; dungeons with nine ids
/// number levels instead, and are named without one.
fn in_dungeon(dungeon_id: i32, dir: Option<&PathBuf>, text: &Texts, lang: &str) -> Option<String> {
    if dungeon_id <= 0 {
        return None;
    }
    let read = |l: &str| -> Option<serde_json::Value> {
        let path = dir?.join("dungeons").join(format!("{l}.json"));
        serde_json::from_str(&std::fs::read_to_string(path).ok()?).ok()
    };
    let table = read(lang).or_else(|| read("en"))?;
    let table = table.as_object()?;
    let name = table.get(&dungeon_id.to_string())?.get("name")?.as_str()?.to_string();
    let group = dungeon_id - dungeon_id % 10;
    let ids_in_group = table
        .keys()
        .filter_map(|k| k.parse::<i32>().ok())
        .filter(|id| id - id % 10 == group)
        .count();
    let tier = if ids_in_group >= 9 {
        None
    } else {
        match dungeon_id % 10 {
            1 => Some(text.get("tierExpedition", "Expedition")),
            2 => Some(text.get("tierConquestNormal", "Conquest (Normal)")),
            3 => Some(text.get("tierConquestHard", "Conquest (Hard)")),
            _ => None,
        }
    };
    Some(match tier {
        Some(t) => format!("{name} · {t}"),
        None => name,
    })
}

/// "Kaisinel (Elyos) · Europe".
fn where_from(profile: &LocalProfile, text: &Texts, lang: &str) -> String {
    let sid = profile.server_id;
    if !(1000..3000).contains(&sid) {
        return String::new();
    }
    let table_lang = match lang {
        "zh-Hans" | "zh-Hant" => "zh-Hant",
        other => other,
    };
    let server = SERVERS
        .servers
        .get(&sid.to_string())
        .and_then(|names| names.get(table_lang).or_else(|| names.get("en")))
        .cloned();
    let faction = if sid / 1000 == 1 { text.get("elyos", "Elyos") } else { text.get("asmodian", "Asmodian") };
    let region = match sid / 100 % 10 {
        // Korea and Taiwan share these numbers; the meter's language and the
        // computer's time zone tell them apart, as for uploaded logs.
        0 => {
            let korean = lang == "ko" || chrono::Local::now().offset().local_minus_utc() == 9 * 3600;
            Some(if korean { text.get("korea", "Korea") } else { text.get("taiwan", "Taiwan") })
        }
        d => {
            let code = match d {
                1 => "NAE",
                2 => "NAW",
                3 => "EU",
                4 => "LA",
                5 => "AS",
                _ => "",
            };
            SERVERS
                .regions
                .get(table_lang)
                .and_then(|r| r.get(code))
                .or_else(|| SERVERS.regions.get("en").and_then(|r| r.get(code)))
                .cloned()
        }
    };
    let mut out = match server {
        Some(s) => format!("{s} ({faction})"),
        None => faction,
    };
    if let Some(r) = region {
        out = format!("{out} · {r}");
    }
    out
}

/// The `presence` and `classes` sections of the meter's own UI strings.
struct Texts {
    presence: HashMap<String, String>,
    classes: HashMap<String, String>,
}

impl Texts {
    fn load(dir: Option<&PathBuf>, lang: &str) -> Self {
        let read = |l: &str| -> Option<serde_json::Value> {
            let path = dir?.join("ui").join(format!("{l}.json"));
            serde_json::from_str(&std::fs::read_to_string(path).ok()?).ok()
        };
        let doc = read(lang).or_else(|| read("en")).unwrap_or_default();
        let section = |name: &str| -> HashMap<String, String> {
            doc.get(name)
                .and_then(|v| v.as_object())
                .map(|o| o.iter().filter_map(|(k, v)| Some((k.clone(), v.as_str()?.to_string()))).collect())
                .unwrap_or_default()
        };
        Self { presence: section("presence"), classes: section("classes") }
    }

    fn get(&self, key: &str, fallback: &str) -> String {
        self.presence.get(key).cloned().unwrap_or_else(|| fallback.to_string())
    }

    fn class(&self, class: JobClass) -> String {
        let key = match class {
            JobClass::Fighter => "FIGHTER".to_string(),
            JobClass::Elementalist => "ELEMENTALIST".to_string(),
            other => class_key(other).to_uppercase(),
        };
        self.classes.get(&key).cloned().unwrap_or_else(|| format!("{class:?}"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn texts() -> Texts {
        Texts { presence: HashMap::new(), classes: HashMap::new() }
    }

    #[test]
    fn a_global_server_reads_as_name_faction_and_region() {
        let p = LocalProfile { server_id: 1304, ..Default::default() };
        assert_eq!(where_from(&p, &texts(), "en"), "Kaisinel (Elyos) · Europe");
        let p = LocalProfile { server_id: 2304, ..Default::default() };
        assert_eq!(where_from(&p, &texts(), "en"), "Lumiel (Asmodian) · Europe");
        assert_eq!(where_from(&LocalProfile::default(), &texts(), "en"), "");
    }

    #[test]
    fn a_dungeon_is_named_with_its_difficulty() {
        let dir = PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/../src/data/i18n"));
        assert_eq!(in_dungeon(600012, Some(&dir), &texts(), "en").as_deref(), Some("Urugugu Canyon · Conquest (Normal)"));
        assert_eq!(in_dungeon(600091, Some(&dir), &texts(), "en").as_deref(), Some("Ferocious Horn Den · Expedition"));
        assert_eq!(in_dungeon(0, Some(&dir), &texts(), "en"), None);
    }

    #[test]
    fn the_server_name_follows_the_language() {
        let p = LocalProfile { server_id: 1304, ..Default::default() };
        assert!(where_from(&p, &texts(), "ko").starts_with("카이시넬"));
    }
}
