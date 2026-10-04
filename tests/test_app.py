import os
import copy
import unittest
import tkinter as tk
from unittest.mock import patch, Mock
from app import AssistantApp
from connections import GameConnection, DiscoveryReport
from connection_scope import ConnectionScope


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

    def test_npcap_guide_only_opens_official_page(self):
        with patch("app.webbrowser.open", return_value=True) as browser, patch("app.Npcap") as driver:
            self.app.open_npcap_guide()
        browser.assert_called_once_with("https://npcap.com/#download")
        driver.assert_not_called()
        self.assertIn("管理员提示需自行确认", self.app.status.get())
        self.assertFalse(self.app.running)
        self.assertFalse(self.app.consent.get())

    def test_failed_driver_refresh_discards_stale_interface_and_consent(self):
        self.app.npcap = Mock()
        self.app.devices = [("old", "old")]
        self.app.consent.set(True)
        with patch("app.Npcap", side_effect=RuntimeError("missing")), patch("app.messagebox.showerror"):
            self.app.refresh_devices()
        self.assertIsNone(self.app.npcap)
        self.assertFalse(self.app.devices)
        self.assertFalse(self.app.device_box["values"])
        self.assertFalse(self.app.consent.get())
        self.assertFalse(self.app.running)

    def test_driver_refresh_never_selects_interface_or_starts_capture(self):
        with patch("app.Npcap") as factory:
            factory.return_value.devices.return_value = [("fixture", "Synthetic")]
            self.app.refresh_devices()
            factory.return_value.packets.assert_not_called()
        self.assertEqual(self.app.device_box.current(), -1)
        self.assertIn("Npcap 可加载", self.app.status.get())
        self.assertFalse(self.app.running)

    def test_completion_keeps_final_gap_diagnostics(self):
        self.app.events.put(("done", {"closed_gaps": 2, "pending_bytes": 4}))
        self.app.poll()
        self.assertEqual(self.app.last_diagnostics["closed_gaps"], 2)
        self.assertEqual(self.app.report_state, "finished")

    def test_selected_player_survives_refresh_and_name_change(self):
        self.test_chinese_view_renders_damage_skills_and_healing()
        selected, = self.app.damage.selection()
        snapshot = copy.deepcopy(self.app.last_snapshot)
        player = snapshot["targets"][0]["players"][0]
        player["name"] = "测试角色"
        player["skills"][0]["damage"] = 75
        self.app.render(snapshot, {})
        self.assertEqual(self.app.damage.selection(), (selected,))
        skill, = self.app.skills.get_children()
        self.assertEqual(str(self.app.skills.item(skill, "values")[2]), "75")
        # Another target with the same actor must not inherit selection.
        snapshot["targets"][0]["target_id"] = 121
        self.app.render(snapshot, {})
        self.assertFalse(self.app.damage.selection())
        self.assertFalse(self.app.skills.get_children())

    def test_incomplete_transport_and_protocol_are_visible(self):
        self.app.render({"targets": [], "healing": [], "pending_bytes": 4,
                         "discarded_protocol_bytes": 3},
                        {"pending_bytes": 2, "partial_streams": 1})
        for phrase in ("中途开始", "未补齐缺口", "协议字节待解析", "丢弃了残帧"):
            self.assertIn(phrase, self.app.integrity.get())
        self.app.render({"targets": [], "healing": []}, {})
        self.assertEqual(self.app.integrity.get(), "")

    def test_discovered_connection_is_manual_and_does_not_start_capture(self):
        self.app.events.put(("connections", [GameConnection(100, "10.1.2.3", 7777, "unknown")]))
        self.app.poll()
        self.assertEqual(self.app.connection_box.current(), -1)
        self.assertEqual(self.app.server_ip.get(), "")
        self.app.connection_box.current(0)
        self.app.apply_connection()
        self.assertEqual(self.app.server_ip.get(), "10.1.2.3")
        self.assertEqual(self.app.port.get(), "7777")
        self.assertEqual(self.app.client.get(), "Steam / Global")
        self.assertFalse(self.app.running)
        self.assertFalse(self.app.consent.get())

    def test_discovery_diagnostics_do_not_offer_unsupported_capture(self):
        self.app.events.put(("discovery", DiscoveryReport([], 1, 1, 3)))
        self.app.poll()
        self.assertIn("读取受限", self.app.status.get())
        self.assertIn("本地回环", self.app.status.get())
        self.assertFalse(self.app.connection_box["values"])
        self.assertEqual(self.app.server_ip.get(), "")
        self.assertFalse(self.app.running)
        self.assertFalse(self.app.consent.get())

    def test_changed_game_connection_stops_before_opening_capture(self):
        scope = ConnectionScope("127.0.0.1", 50000, "127.0.0.1", 1111)
        candidate = GameConnection(100, "127.0.0.1", 1111, "path_restricted", scope)
        self.app.npcap = Mock()
        with patch("app.BackendBridge"), patch("app.find_game_discovery",
                return_value=DiscoveryReport([], 1, 1, 0)):
            self.app.work(None, "fixture", "steam", 1111, (r"\Device\NPF_Loopback", "127.0.0.1", candidate))
        self.app.npcap.packets.assert_not_called()
        self.app.poll()
        self.assertIn("连接已变化", self.app.status.get())
        self.assertIsNone(self.app.bridge)

    def test_reset_control_is_not_lost_during_fast_snapshot_refresh(self):
        previous = {"encounter_id": 1, "revision": 1, "status": "combat_detected", "targets": [], "healing": []}
        reset = {"encounter_id": 2, "revision": 2, "status": "no_combat_detected",
                 "targets": [], "healing": [], "previous_encounter": previous}
        self.app.notify(("reset", reset))
        for revision in range(3, 100):
            self.app.notify(("snapshot", {"encounter_id": 2, "revision": revision,
                             "targets": [], "healing": []}, {}))
        self.app.poll()
        self.assertEqual(len(self.app.history), 1)
        self.assertEqual(self.app.last_snapshot["revision"], 99)
        self.assertFalse(self.app.resetting)
        self.app.render(previous, {})
        self.assertEqual(self.app.last_snapshot["encounter_id"], 2)

    def test_history_is_bounded_and_exportable_after_clear(self):
        for encounter in range(25):
            self.app.notify(("reset", {"encounter_id": encounter + 2, "revision": encounter + 2,
                "status": "no_combat_detected", "targets": [], "healing": [],
                "previous_encounter": {"encounter_id": encounter + 1, "status": "combat_detected"}}))
        self.app.poll()
        self.assertEqual(len(self.app.history), 20)
        self.assertEqual(self.app.history[0]["encounter_id"], 6)
        self.assertEqual(str(self.app.export_button["state"]), "normal")
