//! Independently implemented hidden-cube protocol reader. No upstream Python
//! source is bundled. Reuses the existing bounded framing/LZ4 implementation.
use std::collections::HashMap;
use serde::Serialize;
use crate::capture::{framing, stream_processor::read_varint};

const CUBE_IDS: &[u32] = &[
    1000295, 1000548, 1000556, 1000568, 1000566, 1000567, 1100056, 1100094,
    1200018, 1200036, 1200037, 1200039, 1200040, 1200041, 1200667, 1200707,
    1201054, 1201055, 1300081, 1300082, 1300754, 1301199, 1301200, 1401335,
    1401336, 3682560,
];
#[derive(Clone, Copy, Debug, Serialize, PartialEq)]
pub struct Position { pub x: f32, pub y: f32, pub z: f32 }
impl Position {
    fn read(bytes: &[u8], at: usize) -> Option<Self> {
        let xyz = bytes.get(at..at.checked_add(12)?)?;
        let read = |i| f32::from_le_bytes(xyz[i..i+4].try_into().unwrap());
        let p = Self { x: read(0), y: read(4), z: read(8) };
        [p.x,p.y,p.z].iter().all(|v| v.is_finite() && v.abs() <= 10_000_000.).then_some(p)
    }
    #[cfg(test)]
    fn distance(self, other: Self) -> f32 {
        ((self.x-other.x).powi(2)+(self.y-other.y).powi(2)+(self.z-other.z).powi(2)).sqrt()/100.
    }
}
#[derive(Clone, Serialize)]
pub struct Cube { pub entity: i32, pub model: u32, pub position: Position }
#[derive(Clone, Serialize)]
pub struct Snapshot {
    pub self_identified: bool,
    pub player: Option<Position>, pub cubes: Vec<Cube>, pub frames: u64,
    pub position_age_ms: Option<i64>, pub discoveries: u64,
}
#[derive(Default)]
pub struct Radar {
    player_id: Option<i32>, player: Option<Position>, cubes: HashMap<i32,Cube>,
    frames: u64, discoveries: u64, position_at: Option<i64>,
}
impl Radar {
    pub fn snapshot(&self, now: i64) -> Snapshot {
        let mut cubes: Vec<_> = self.cubes.values().cloned().collect();
        cubes.sort_by_key(|c| c.entity);
        Snapshot { self_identified:self.player_id.is_some(), player: self.player, cubes, frames: self.frames, discoveries: self.discoveries,
            position_age_ms: self.position_at.map(|at| now.saturating_sub(at).max(0)) }
    }
    pub fn reset(&mut self) { *self = Self::default(); }
    pub fn consume(&mut self, bytes: &[u8], now: i64) -> usize {
        let parsed = framing::walk(bytes);
        self.frames(&parsed, bytes, now, 0);
        parsed.consumed
    }
    fn frames(&mut self, frames: &framing::Framing, bytes: &[u8], now: i64, depth: u8) {
        if depth > 4 { return; }
        for frame in &frames.frames {
            let body = frame.payload(bytes);
            if frame.kind == framing::FrameKind::Bundle {
                if let Some(plain) = framing::decompress_bundle(body) {
                    self.frames(&framing::walk_inner(&plain), &plain, now, depth+1);
                }
            } else { self.packet(body, now); }
        }
    }
    fn packet(&mut self, body: &[u8], now: i64) {
        if let Some(id) = crate::capture::stream_processor::embedded_self_identity(body) {
            if self.player_id != Some(id) { self.player=None; self.position_at=None; }
            self.player_id=Some(id);
        }
        let Some(op) = body.get(..2).map(|b| u16::from_le_bytes([b[0],b[1]])) else { return; };
        let p = &body[2..];
        let id = read_varint(p,0);
        let valid_id = id.length > 0 && id.value > 0;
        let n = id.length.max(0) as usize;
        self.frames = self.frames.saturating_add(1);
        match op {
            0x3634 | 0x3641 if valid_id => {
                let at = if op == 0x3634 { n+2 } else { n+5 };
                let Some(model) = p.get(at..at+4).map(|b| u32::from_le_bytes(b.try_into().unwrap())) else { return; };
                if !CUBE_IDS.contains(&model) { return; }
                let pos_at = if op == 0x3634 { n+6 } else { n+11 };
                let Some(position) = Position::read(p,pos_at) else { return; };
                if self.cubes.len() >= 512 && !self.cubes.contains_key(&id.value) { return; }
                if self.cubes.insert(id.value,Cube { entity:id.value, model,position }).is_none() {
                    self.discoveries = self.discoveries.saturating_add(1);
                }
            }
            0x3635 | 0x363a | 0x3642 if valid_id => { self.cubes.remove(&id.value); }
            // Only the self-spawn record identifies the player. Never guess
            // from another entity's first movement or a generic sync record.
            0x3633 | 0x8d00 if valid_id => {
                if self.player_id != Some(id.value) { self.player = None; self.position_at = None; }
                self.player_id = Some(id.value);
            }
            // As in the DPS parser, entity zero is the local world transition.
            // Other entities' position records must not erase our identity.
            0x3623 if id.length > 0 && id.value == 0 => {
                self.player = None; self.player_id = None; self.cubes.clear(); self.position_at=None;
            }
            0x561e => { self.player = None; self.cubes.clear(); self.position_at=None; }
            0x3710..=0x3750 | 0x382a | 0x382b | 0x382c | 0x3804 if valid_id && self.player_id == Some(id.value) => {
                if p.len() < n+12 { return; }
                let at=if (0x3710..=0x3750).contains(&op) { n+2 } else { p.len()-12 };
                if let Some(position) = Position::read(p,at) {
                    self.player=Some(position); self.position_at=Some(now);
                }
            }
            // Collection is confirmed by the entity despawn packets above.
            // A generic gathering notification is not proof which nearby cube
            // was collected, so it must not erase unrelated markers.
            _ => {}
        }
    }
}

/// Bounded, direction-specific TCP buffer. Duplicate adapter/retransmit bytes
/// are ignored; a sequence gap discards the partial frame rather than joining
/// unrelated bytes into an invented cube. Out-of-order gaps may miss a cube.
#[derive(Default)]
pub struct Flow { next: Option<u32>, bytes: Vec<u8> }
impl Flow {
    pub fn push(&mut self, seq:u32, bytes:&[u8], radar:&mut Radar, now:i64) {
        let end=seq.wrapping_add(bytes.len() as u32);
        let mut bytes=bytes;
        if let Some(next)=self.next {
            let delta=seq.wrapping_sub(next) as i32;
            if delta<0 {
                let skip=next.wrapping_sub(seq) as usize;
                if skip>=bytes.len() { return; }
                bytes=&bytes[skip..];
            } else if delta>0 { self.bytes.clear(); }
        }
        self.next=Some(end);
        if self.bytes.len()+bytes.len()>1024*1024 { self.bytes.clear(); return; }
        self.bytes.extend_from_slice(bytes);
        let consumed=radar.consume(&self.bytes,now);
        self.bytes.drain(..consumed);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn frame(op:u16,p:&[u8])->Vec<u8> {
        let mut b=vec![(p.len()+6) as u8]; b.extend(op.to_le_bytes()); b.extend(p); b
    }
    fn spawn(id:u8,model:u32)->Vec<u8> {
        let mut p=vec![id,0,0]; p.extend(model.to_le_bytes());
        for v in [100f32,200.,300.] {p.extend(v.to_le_bytes());} frame(0x3634,&p)
    }
    #[test] fn spawn_whitelist_dedup_and_despawn() {
        let mut r=Radar::default(); r.consume(&spawn(1,1000295),0); r.consume(&spawn(1,1000295),1);
        r.consume(&spawn(2,9999999),2); assert_eq!(r.cubes.len(),1); assert_eq!(r.discoveries,1);
        r.consume(&frame(0x3635,&[1]),3); assert!(r.cubes.is_empty());
    }
    #[test] fn movement_requires_self_and_finite_coords() {
        let mut r=Radar::default(); let mut p=vec![1]; for v in [100f32,200.,300.] {p.extend(v.to_le_bytes());}
        r.consume(&frame(0x382a,&p),1); assert!(r.player.is_none());
        r.consume(&frame(0x3633,&[1]),2); r.consume(&frame(0x382a,&p),3); assert_eq!(r.player.unwrap().x,100.);
        p[1..5].copy_from_slice(&f32::NAN.to_le_bytes()); r.consume(&frame(0x382a,&p),4); assert_eq!(r.position_at,Some(3));
    }
    #[test] fn fragmented_retransmitted_tcp_is_not_reparsed() {
        let mut r=Radar::default(); let mut f=Flow::default(); let b=spawn(1,1000295);
        f.push(100,&b[..5],&mut r,0); assert!(r.cubes.is_empty());
        f.push(105,&b[5..],&mut r,1); f.push(100,&b,&mut r,2);
        assert_eq!(r.cubes.len(),1); assert_eq!(r.frames,1);
    }
    #[test] fn zone_change_clears_positions_and_objects() {
        let mut r=Radar::default(); r.consume(&spawn(1,1000295),0);
        r.consume(&frame(0x3623,&[0]),1); assert!(r.cubes.is_empty()); assert!(r.player.is_none());
    }
    #[test] fn server_sync_identifies_self_without_choosing_first_moving_player() {
        let mut r=Radar::default();
        let mut position=vec![7];for v in [100f32,200.,300.] {position.extend(v.to_le_bytes());}
        r.consume(&frame(0x382a,&position),0);assert!(r.player.is_none());
        r.consume(&frame(0x8d00,&[7]),1);
        r.consume(&frame(0x382a,&position),2);
        assert_eq!(r.player.unwrap().x,100.);
        r.consume(&spawn(9,1000295),3);
        r.consume(&frame(0x3623,&[8]),4);
        r.consume(&frame(0x3623,&[]),5);
        assert_eq!(r.player_id,Some(7));assert!(r.player.is_some());assert_eq!(r.cubes.len(),1);
        r.consume(&frame(0x3623,&[0]),6);
        assert!(r.player_id.is_none());assert!(r.cubes.is_empty());
    }
    #[test] fn embedded_self_identity_reuses_dps_mask_validation() {
        let mut r=Radar::default();
        let identity=[0x33,0x36,7,0,0,0,0,1,3,b'A',b'b',b'c'];
        let mut container=vec![0xaa,0xbb];container.extend(identity);
        r.packet(&container,0);assert_eq!(r.player_id,Some(7));
        let mut bad=identity;bad[7]=0;
        assert!(crate::capture::stream_processor::embedded_self_identity(&bad).is_none());
        assert!(crate::capture::stream_processor::embedded_self_identity(&identity[..10]).is_none());
        let mut ambiguous=identity.to_vec();let mut second=identity;second[2]=8;
        ambiguous.extend(second);
        assert!(crate::capture::stream_processor::embedded_self_identity(&ambiguous).is_none());
    }
    #[test] fn malformed_input_is_bounded_and_safe() {
        let mut r=Radar::default(); for n in 0..100 { r.consume(&vec![255;n],0); }
        assert!(r.cubes.is_empty()); assert_eq!(Position{x:0.,y:0.,z:0.}.distance(Position{x:300.,y:400.,z:0.}),5.);
    }
    #[test] fn compressed_bundle_and_truncated_bundle() {
        let inner=spawn(1,1000295);
        let mut body=vec![255,255];body.extend((inner.len() as u32).to_le_bytes());body.extend(lz4_flex::compress(&inner));
        let mut packet=vec![(body.len()+4) as u8];packet.extend(body);
        let mut r=Radar::default();r.consume(&packet[..packet.len()-1],0);assert!(r.cubes.is_empty());
        r.consume(&packet,1);assert_eq!(r.cubes.len(),1);
    }
    #[test] fn overlapping_tcp_and_sequence_wrap_do_not_duplicate() {
        let b=spawn(1,1000295);let mut r=Radar::default();let mut f=Flow::default();
        let start=u32::MAX-8;f.push(start,&b[..10],&mut r,0);
        f.push(start.wrapping_add(6),&b[6..],&mut r,1);
        let remove=frame(0x363a,&[1]);f.push(start.wrapping_add(b.len() as u32),&remove,&mut r,2);
        assert!(r.cubes.is_empty());assert_eq!(r.frames,2);
    }
    #[test] fn other_player_movement_and_gathering_cannot_move_or_remove_our_marker() {
        let mut r=Radar::default();r.consume(&spawn(1,1000295),0);r.consume(&frame(0x3633,&[3]),0);
        let mut p=vec![4];for v in [100f32,200.,300.] {p.extend(v.to_le_bytes());}
        r.consume(&frame(0x382a,&p),1);r.consume(&frame(0x8d6d,&[4]),2);
        assert!(r.player.is_none());assert_eq!(r.cubes.len(),1);
    }
}
