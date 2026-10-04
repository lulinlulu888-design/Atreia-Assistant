import os
import unittest
import tkinter as tk
from app import AssistantApp


@unittest.skipUnless(os.name == "nt" or os.environ.get("DISPLAY"), "GUI requires a display")
class AppTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = AssistantApp(self.root)

    def tearDown(self):
        self.app.close()

    def test_chinese_view_renders_damage_skills_and_healing(self):
        snapshot = {"status": "combat_detected", "compatibility": "unverified",
            "targets": [{"target_id": 120, "players": [{"actor_id": 100, "name": None,
                "damage": 50, "dps": 25, "contribution": 1,
                "skills": [{"skill_id": 20, "damage": 50, "dot": True,
                            "hits": 2, "critical_hits": 1}]}]}],
            "healing": [{"actor_id": 100, "skill_id": 20, "hot": True, "healing": 30, "ticks": 1}]}
        self.app.render(snapshot, {"payload_bytes": 12})
        row, = self.app.damage.get_children()
        self.assertEqual(tuple(str(v) for v in self.app.damage.item(row, "values")),
                         ("120", "#100", "50", "25.0", "100.0%", "50.0%"))
        self.app.damage.selection_set(row)
        self.app.select_player()
        self.assertEqual(len(self.app.skills.get_children()), 1)
        self.assertEqual(len(self.app.healing.get_children()), 1)
        self.assertEqual(self.app.client_box["values"], ("Steam / Global", "PURPLE"))

    def test_unknown_or_empty_snapshot_does_not_show_fake_damage(self):
        self.app.render({"status": "no_combat_detected", "targets": [], "healing": []}, {})
        self.assertFalse(self.app.damage.get_children())
        self.assertFalse(self.app.healing.get_children())
        self.assertIn("兼容性未验证", self.app.compatibility["text"])
        self.assertEqual(str(self.app.export_button["state"]), "disabled")

    def test_live_capture_requires_user_consent_by_default(self):
        self.assertFalse(self.app.consent.get())
        self.assertIsNone(self.app.npcap)
        self.assertFalse(self.app.running)

    def test_completion_keeps_final_gap_diagnostics(self):
        self.app.events.put(("done", {"closed_gaps": 2, "pending_bytes": 4}))
        self.app.poll()
        self.assertEqual(self.app.last_diagnostics["closed_gaps"], 2)
        self.assertEqual(self.app.report_state, "finished")
