use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum SpecialDamage {
    Back,
    Critical,
    Parry,
    Perfect,
    Double,
    Frontal,
    Endure,
    Unknown4,
    PowerShard,
    Smite,
}
