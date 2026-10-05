//! The supporter roster — who gets a golden name, resolved on the machine that
//! draws it.
//!
//! The requirement is that a supporter's name is gold on *everyone's* meter, not
//! just their own, live during a fight. The obvious implementation is to ask the
//! server "is this player a supporter?", and it is the wrong one: it would send
//! the server a list of who you are playing with, every fight, for a cosmetic.
//! That is exactly the kind of quiet data collection the rest of this design
//! exists to avoid.
//!
//! So the roster travels the other way. A small file on the CDN lists the
//! supporters; the meter fetches it periodically and matches locally. Nothing
//! about your party ever leaves the machine, and it works offline.
//!
//! **The entries are hashed, and that is anti-scraping rather than secrecy.**
//! The salt is in this file and this file is public, so anyone can test a name
//! they already have. What it stops is downloading the list and reading off who
//! has given money — you can check a guess, you cannot enumerate. Supporters
//! opted into being visibly gold in the first place; this only keeps the roster
//! from doubling as a donor list.
//!
//! ## Format (`patrons-v1.bin`)
//!
//! ```text
//! "A2PR" | u16 version | u8 key_kind | u8 salt_len | salt | u32 count | [u64 key]*
//! ```
//!
//! Keys are sorted so lookup is a binary search, and truncated to 8 bytes — a
//! collision needs 2^64, and the cost of one is that a stranger's name renders
//! gold.
//!
//! `key_kind` exists because the right key changes once accounts do. Today a
//! supporter is known by the character name they typed into a Ko-fi message, so
//! the roster is name-keyed. Once characters are verified the server will know
//! their roster id, which survives renames and does not collide across worlds,
//! and the file can move to `KeyKind::Dbid` without the meter needing to guess
//! which it is holding.

use std::collections::HashSet;

use sha2::{Digest, Sha256};

pub const MAGIC: &[u8; 4] = b"A2PR";
pub const VERSION: u16 = 1;

/// What the hashed keys were built from.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum KeyKind {
    /// Lowercased character name. What a hand-curated list can produce, because
    /// a name is what someone puts in a payment message.
    ///
    /// Names are not unique across worlds, so a supporter on one server makes
    /// the same name gold on another. Cosmetic, rare, and the price of being
    /// able to run this before accounts exist.
    Name,
    /// The roster id (`dbid`). Survives renames and is unique per world, but
    /// only knowable from a packet capture — so this is for after characters can
    /// be verified.
    Dbid,
}

impl KeyKind {
    fn from_byte(b: u8) -> Option<Self> {
        match b {
            0 => Some(KeyKind::Name),
            1 => Some(KeyKind::Dbid),
            _ => None,
        }
    }

    fn to_byte(self) -> u8 {
        match self {
            KeyKind::Name => 0,
            KeyKind::Dbid => 1,
        }
    }
}

/// A parsed roster, ready to answer "is this one of them?".
#[derive(Debug, Clone, Default)]
pub struct Roster {
    kind_is_dbid: bool,
    salt: Vec<u8>,
    keys: HashSet<u64>,
}

impl Roster {
    pub fn is_empty(&self) -> bool {
        self.keys.is_empty()
    }

    pub fn len(&self) -> usize {
        self.keys.len()
    }

    /// Normalise a character name the way the roster builder did.
    ///
    /// Lowercased and trimmed, nothing cleverer. Unicode case folding would be
    /// more correct for the CJK-adjacent scripts in play, but it has to match
    /// whatever generated the file byte for byte, and "lowercase and trim" is
    /// the rule that is easy to reimplement correctly on the other side.
    fn normalise(name: &str) -> String {
        name.trim().to_lowercase()
    }

    fn hash(&self, material: &[u8]) -> u64 {
        let mut hasher = Sha256::new();
        hasher.update(&self.salt);
        hasher.update(material);
        let digest = hasher.finalize();
        u64::from_le_bytes(digest[..8].try_into().unwrap_or_default())
    }

    /// Is this character a supporter?
    ///
    /// `dbid` is used when the roster is keyed on it and we have one; otherwise
    /// the name is. A name-keyed roster still works for players with no roster
    /// entry, which is most of the people you will ever see.
    pub fn contains(&self, name: &str, dbid: u64) -> bool {
        if self.keys.is_empty() {
            return false;
        }
        if self.kind_is_dbid {
            if dbid == 0 {
                return false;
            }
            return self.keys.contains(&self.hash(&dbid.to_le_bytes()));
        }
        if name.is_empty() {
            return false;
        }
        self.keys.contains(&self.hash(Self::normalise(name).as_bytes()))
    }

    /// Parse a roster file. Returns `None` for anything that is not one, so a
    /// truncated download or an HTML error page simply means nobody is gold
    /// rather than a crash.
    pub fn parse(data: &[u8]) -> Option<Self> {
        let mut o = 0usize;
        fn take<'a>(d: &'a [u8], o: &mut usize, n: usize) -> Option<&'a [u8]> {
            if *o + n > d.len() {
                return None;
            }
            let s = &d[*o..*o + n];
            *o += n;
            Some(s)
        }
        if take(data, &mut o, 4)? != MAGIC {
            return None;
        }
        let version = u16::from_le_bytes(take(data, &mut o, 2)?.try_into().ok()?);
        if version != VERSION {
            return None;
        }
        let kind = KeyKind::from_byte(take(data, &mut o, 1)?[0])?;
        let salt_len = take(data, &mut o, 1)?[0] as usize;
        let salt = take(data, &mut o, salt_len)?.to_vec();
        let count = u32::from_le_bytes(take(data, &mut o, 4)?.try_into().ok()?) as usize;

        // Guard against a corrupt length asking for a huge allocation.
        if count > 5_000_000 || o + count * 8 > data.len() {
            return None;
        }
        let mut keys = HashSet::with_capacity(count);
        for _ in 0..count {
            keys.insert(u64::from_le_bytes(take(data, &mut o, 8)?.try_into().ok()?));
        }
        Some(Roster {
            kind_is_dbid: kind == KeyKind::Dbid,
            salt,
            keys,
        })
    }
}

/// Stamp supporter status onto a saved fight, using the roster as it is *now*.
///
/// Saved records carry whatever was true when they were written, which is the
/// wrong answer twice over: a fight from before this feature existed has no flag
/// at all, and someone who became a supporter last week should light up on the
/// fights they were already in.
///
/// Party members are the limitation, and it is worth being plain about it.
/// `obscure_nickname` masks their names before the record hits disk, so a
/// name-keyed roster can only ever match the local player, whose name is stored
/// intact. Each actor's `dbid` is kept for exactly this reason: a dbid-keyed
/// roster resolves everyone, because a roster id survives being masked.
pub fn apply_to_record(record: &mut crate::entity::fight_record::FightRecord, roster: &Roster) {
    if roster.is_empty() {
        // Nothing published and no override: clear rather than leave a stale
        // flag from whenever the record was written.
        for actor in &mut record.actors {
            actor.is_supporter = false;
        }
        return;
    }
    for actor in &mut record.actors {
        actor.is_supporter = roster.contains(&actor.nickname, actor.dbid);
    }
}

/// Build a roster file. Used by whatever publishes `patrons-v1.bin`, and by the
/// tests that check the meter reads what the publisher wrote.
pub fn build(kind: KeyKind, salt: &[u8], entries: &[String]) -> Vec<u8> {
    let mut keys: Vec<u64> = entries
        .iter()
        .map(|e| {
            let material: Vec<u8> = match kind {
                KeyKind::Name => Roster::normalise(e).into_bytes(),
                KeyKind::Dbid => e.parse::<u64>().unwrap_or(0).to_le_bytes().to_vec(),
            };
            let mut hasher = Sha256::new();
            hasher.update(salt);
            hasher.update(&material);
            u64::from_le_bytes(hasher.finalize()[..8].try_into().unwrap_or_default())
        })
        .collect();
    keys.sort_unstable();
    keys.dedup();

    let mut out = Vec::with_capacity(16 + salt.len() + keys.len() * 8);
    out.extend_from_slice(MAGIC);
    out.extend_from_slice(&VERSION.to_le_bytes());
    out.push(kind.to_byte());
    out.push(salt.len().min(255) as u8);
    out.extend_from_slice(&salt[..salt.len().min(255)]);
    out.extend_from_slice(&(keys.len() as u32).to_le_bytes());
    for k in keys {
        out.extend_from_slice(&k.to_le_bytes());
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    const SALT: &[u8] = b"a2tools-supporters-v1";

    #[test]
    fn a_name_roster_round_trips() {
        let names = vec!["Misti".to_string(), "Grandine".to_string()];
        let roster = Roster::parse(&build(KeyKind::Name, SALT, &names)).expect("parses");
        assert_eq!(roster.len(), 2);
        assert!(roster.contains("Misti", 0));
        assert!(roster.contains("Grandine", 0));
        assert!(!roster.contains("SomeoneElse", 0));
    }

    #[test]
    fn name_matching_ignores_case_and_padding() {
        let roster =
            Roster::parse(&build(KeyKind::Name, SALT, &["Misti".to_string()])).expect("parses");
        assert!(roster.contains("misti", 0));
        assert!(roster.contains("MISTI", 0));
        assert!(roster.contains("  Misti  ", 0));
    }

    #[test]
    fn cjk_names_work() {
        let name = "九州依然在".to_string();
        let roster = Roster::parse(&build(KeyKind::Name, SALT, &[name.clone()])).expect("parses");
        assert!(roster.contains(&name, 0));
    }

    #[test]
    fn a_dbid_roster_ignores_names() {
        let roster = Roster::parse(&build(KeyKind::Dbid, SALT, &["285134151408007616".to_string()]))
            .expect("parses");
        assert!(roster.contains("anything", 285_134_151_408_007_616));
        assert!(!roster.contains("Misti", 0), "a dbid roster must not match on name");
        assert!(!roster.contains("", 1));
    }

    #[test]
    fn the_salt_changes_every_key() {
        let a = build(KeyKind::Name, b"salt-one", &["Misti".into()]);
        let b = build(KeyKind::Name, b"salt-two", &["Misti".into()]);
        assert_ne!(a, b, "the same name under a different salt must hash differently");
        // Each still matches under its own salt, which travels with the file.
        assert!(Roster::parse(&a).unwrap().contains("Misti", 0));
        assert!(Roster::parse(&b).unwrap().contains("Misti", 0));
    }

    #[test]
    fn duplicates_collapse() {
        let names = vec!["Misti".into(), "misti".into(), "MISTI".into()];
        let roster = Roster::parse(&build(KeyKind::Name, SALT, &names)).expect("parses");
        assert_eq!(roster.len(), 1);
    }

    fn record_with(actors: Vec<(&str, u64)>) -> crate::entity::fight_record::FightRecord {
        use crate::entity::details_context::{DetailsActorSummary, TargetDetailsResponse};
        crate::entity::fight_record::FightRecord {
            id: "auto_1_2".into(),
            boss_name: "Boss".into(),
            target_id: 1,
            start_time_ms: 0,
            duration_ms: 1000,
            total_damage: 1,
            jobs: vec![],
            job_ids: vec![],
            details: TargetDetailsResponse {
                target_id: 1,
                max_hp: 1,
                total_target_damage: 1,
                battle_time: 1000,
                start_time: 0,
                skills: vec![],
                ping_history: vec![],
                heal_skills: vec![],
            },
            actors: actors
                .into_iter()
                .map(|(name, dbid)| DetailsActorSummary {
                    actor_id: 1,
                    nickname: name.into(),
                    job: String::new(),
                    job_id: 0,
                    party_heal: 0,
                    regen: 0,
                    damage_received: 0,
                    hits_received: 0,
                    dbid,
                    server_id: 0,
                    // Deliberately wrong, so the tests show it being recomputed
                    // rather than carried through.
                    is_supporter: true,
                    level: 0,
                    gear_score: 0,
                    combat_power: 0,
                })
                .collect(),
            is_train: false,
            app_version: "2.0.22".into(),
            mob_code: 0,
            dungeon_id: 0,
            server_id: 0,
        }
    }

    #[test]
    fn opening_a_saved_fight_uses_the_roster_as_it_is_now() {
        // "Misti" is the local player, stored unmasked. "Gr****e" is a party
        // member, masked by obscure_nickname before the record was written.
        let mut record = record_with(vec![("Misti", 0), ("Gr****e", 0)]);
        let roster =
            Roster::parse(&build(KeyKind::Name, SALT, &["Misti".into()])).expect("roster");

        apply_to_record(&mut record, &roster);

        assert!(record.actors[0].is_supporter, "the local player should resolve");
        assert!(
            !record.actors[1].is_supporter,
            "a masked party name cannot match a name-keyed roster"
        );
    }

    #[test]
    fn a_dbid_roster_resolves_a_party_member_whose_name_was_masked() {
        // The reason dbid is stored on every actor: it survives masking.
        let mut record = record_with(vec![("Gr****e", 0x03f5_0000_0001_b9c0)]);
        let roster = Roster::parse(&build(
            KeyKind::Dbid,
            SALT,
            &["285134151408007616".into()],
        ))
        .expect("roster");
        assert_eq!(0x03f5_0000_0001_b9c0u64, 285_134_151_408_007_616);

        apply_to_record(&mut record, &roster);
        assert!(record.actors[0].is_supporter);
    }

    #[test]
    fn no_roster_clears_a_stale_flag() {
        // A record written while a roster was loaded must not keep claiming
        // someone is a supporter once there is no roster at all.
        let mut record = record_with(vec![("Misti", 7)]);
        apply_to_record(&mut record, &Roster::default());
        assert!(!record.actors[0].is_supporter);
    }

    #[test]
    fn nothing_that_is_not_a_roster_parses() {
        assert!(Roster::parse(b"").is_none());
        assert!(Roster::parse(b"<html>404 not found</html>").is_none());
        // A truncated download: header intact, entries missing.
        let full = build(KeyKind::Name, SALT, &["Misti".into(), "Grandine".into()]);
        assert!(Roster::parse(&full[..full.len() - 4]).is_none());
    }

    #[test]
    fn an_empty_roster_makes_nobody_gold() {
        let roster = Roster::parse(&build(KeyKind::Name, SALT, &[])).expect("parses");
        assert!(roster.is_empty());
        assert!(!roster.contains("Misti", 1));
        // And so does the default, which is what the meter holds before the
        // first fetch and after a failed one.
        assert!(!Roster::default().contains("Misti", 1));
    }

    #[test]
    fn ten_thousand_supporters_is_a_small_file() {
        let names: Vec<String> = (0..10_000).map(|i| format!("Player{i}")).collect();
        let bytes = build(KeyKind::Name, SALT, &names);
        assert!(
            bytes.len() < 100 * 1024,
            "roster for 10k supporters was {} bytes",
            bytes.len()
        );
        let roster = Roster::parse(&bytes).expect("parses");
        assert!(roster.contains("Player9999", 0));
    }
}
