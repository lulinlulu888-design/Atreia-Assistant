use std::collections::HashMap;

/// Resolves the ultimate owner of a summon chain by walking parent links.
pub fn resolve(actor_id: i32, summon_data: &HashMap<i32, i32>) -> i32 {
    if actor_id <= 0 {
        return actor_id;
    }
    let mut resolved = actor_id;
    let mut visited = std::collections::HashSet::new();
    let mut hops = 0;
    while hops < 16 && visited.insert(resolved) {
        match summon_data.get(&resolved) {
            Some(&parent) if parent > 0 => {
                resolved = parent;
                hops += 1;
            }
            _ => break,
        }
    }
    resolved
}
