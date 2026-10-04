import unittest
from combat import Encounter, Event


def damage(id="1", time=1000, actor="cleric", target="boss", amount=100, critical=False):
    return Event(id, time, actor, target, "skill", "damage", amount, critical)


class CombatTests(unittest.TestCase):
    def test_damage_healing_and_skill_breakdown(self):
        fight = Encounter(0)
        fight.add(damage(critical=True))
        fight.add(damage("2", amount=300))
        fight.add(Event("3", 1500, "cleric", "ally", "heal", "heal", 200))
        player = fight.snapshot(2000)["players"]["cleric"]
        self.assertEqual((player["dps"], player["hps"], player["crit_rate"]), (200, 100, .5))
        self.assertEqual(player["skills"]["skill"]["damage"], 400)
        self.assertEqual(player["contribution"], 1)

    def test_duplicates_are_not_counted_and_conflicts_rejected(self):
        fight = Encounter(0)
        self.assertTrue(fight.add(damage()))
        self.assertFalse(fight.add(damage()))
        with self.assertRaises(ValueError):
            fight.add(damage(amount=101))
        self.assertEqual(fight.snapshot(2000)["total_damage"], 100)

    def test_target_filter_preserves_encounter_duration(self):
        fight = Encounter(0)
        fight.add(damage())
        fight.add(damage("2", actor="mage", target="add", amount=300))
        self.assertEqual(fight.snapshot(2000)["players"]["cleric"]["contribution"], .25)
        boss = fight.snapshot(2000, "boss")
        self.assertEqual(boss["players"]["cleric"]["dps"], 50)
        self.assertEqual(boss["players"]["cleric"]["contribution"], 1)
        self.assertNotIn("mage", boss["players"])

    def test_zero_duration_and_empty_fight(self):
        fight = Encounter(1000)
        self.assertEqual(fight.snapshot(1000)["players"], {})
        fight.add(damage())
        self.assertEqual(fight.snapshot(1000)["players"]["cleric"]["dps"], 0)

    def test_invalid_events_and_boundaries(self):
        for amount in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                damage(amount=amount)
        fight = Encounter(1000)
        with self.assertRaises(ValueError):
            fight.add(damage(time=999))
        fight.add(damage(time=2000))
        with self.assertRaises(ValueError):
            fight.snapshot(1999)

    def test_out_of_order_events_and_snapshot_isolation(self):
        fight = Encounter(0)
        fight.add(damage(time=2000))
        fight.add(damage("2", time=1000))
        first = fight.snapshot(3000)
        first["players"]["cleric"]["damage"] = 0
        self.assertEqual(fight.snapshot(3000)["total_damage"], 200)


if __name__ == "__main__":
    unittest.main()
