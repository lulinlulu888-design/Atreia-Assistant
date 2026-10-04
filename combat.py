"""Normalized combat-event aggregation; not a game packet decoder."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    event_id: str
    timestamp_ms: int
    actor_id: str
    target_id: str
    skill_id: str
    kind: str
    amount: int
    critical: bool = False

    def __post_init__(self):
        for field in (self.event_id, self.actor_id, self.target_id, self.skill_id):
            if not isinstance(field, str) or not field.strip():
                raise ValueError("Event identities must be nonempty strings")
        if self.kind not in ("damage", "heal"):
            raise ValueError("Unsupported event kind")
        if type(self.amount) is not int or self.amount < 0:
            raise ValueError("Amount must be a nonnegative integer")
        if type(self.timestamp_ms) is not int or self.timestamp_ms < 0:
            raise ValueError("Timestamp must be nonnegative integer milliseconds")
        if type(self.critical) is not bool:
            raise ValueError("critical must be boolean")


class Encounter:
    def __init__(self, start_ms):
        if type(start_ms) is not int or start_ms < 0:
            raise ValueError("Invalid encounter start")
        self.start_ms = start_ms
        self._events = {}

    def add(self, event):
        if not isinstance(event, Event):
            raise TypeError("Expected normalized Event")
        if event.timestamp_ms < self.start_ms:
            raise ValueError("Event precedes encounter")
        previous = self._events.get(event.event_id)
        if previous is not None:
            if previous != event:
                raise ValueError("Conflicting duplicate event ID")
            return False
        self._events[event.event_id] = event
        return True

    def snapshot(self, end_ms, target_id=None):
        if type(end_ms) is not int or end_ms < self.start_ms:
            raise ValueError("Invalid encounter end")
        if any(e.timestamp_ms > end_ms for e in self._events.values()):
            raise ValueError("Encounter end precedes recorded event")
        duration = (end_ms - self.start_ms) / 1000
        players = {}
        for event in self._events.values():
            if target_id is not None and event.target_id != target_id:
                continue
            player = players.setdefault(event.actor_id, self._empty())
            skill = player["skills"].setdefault(event.skill_id, self._empty())
            for bucket in (player, skill):
                bucket[event.kind] += event.amount
                if event.kind == "damage":
                    bucket["hits"] += 1
                    bucket["critical_hits"] += int(event.critical)
        total = sum(p["damage"] for p in players.values())
        for player in players.values():
            for bucket in (player, *player["skills"].values()):
                bucket["dps"] = bucket["damage"] / duration if duration else 0.0
                bucket["hps"] = bucket["heal"] / duration if duration else 0.0
                bucket["crit_rate"] = bucket["critical_hits"] / bucket["hits"] if bucket["hits"] else 0.0
            player["contribution"] = player["damage"] / total if total else 0.0
        return {"duration_seconds": duration, "total_damage": total, "players": players}

    @staticmethod
    def _empty():
        return {"damage": 0, "heal": 0, "hits": 0, "critical_hits": 0, "skills": {}}
