import os
import copy
import gc
import unittest
import tkinter as tk
from tkinter import ttk
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
        self.app = None
        self.root = None
        # Collect destroyed Tk variables on their owning thread, before later
        # backend-worker tests can trigger Python's cyclic garbage collector.
        gc.collect()

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

    def test_basic_ui_hides_debug_controls_and_styles_all_widgets(self):
        self.assertFalse(self.app.advanced.winfo_manager())
        style = ttk.Style(self.root)
        self.assertEqual(style.lookup("TButton", "background"), "#24344c")
        self.assertEqual(style.lookup("Treeview.Heading", "background"), "#24344c")

    def test_overlay_is_hidden_by_default_and_hiding_does_not_stop_capture(self):
        overlay = self.app.overlay
        self.assertEqual(overlay.window.state(), "withdrawn")
        self.assertTrue(overlay.window.attributes("-topmost"))
        self.app.running = True
        self.app.show_overlay()
        overlay.toggle_lock()
        with patch.object(overlay.window, "geometry") as geometry:
            overlay.begin_drag(Mock(x_root=100, y_root=100))
            overlay.drag(Mock(x_root=200, y_root=200))
        geometry.assert_not_called()
        overlay.hide()
        self.assertTrue(self.app.running)
        self.assertFalse(self.app.consent.get())
        self.assertEqual(overlay.window.state(), "withdrawn")

    def test_overlay_keeps_targets_separate_and_healing_is_record_total(self):
        def player(actor, damage):
            return {"actor_id": actor, "name": None, "damage": damage, "dps": damage/2,
                    "contribution": 1, "skills": []}
        snapshot = {"targets": [{"target_id": 1, "players": [player(10, 20), player(11, 40)]},
                                {"target_id": 2, "players": [player(10, 500)]}],
                    "healing": [{"actor_id": 10, "skill_id": 2, "healing": 30, "ticks": 1, "hot": False},
                                {"actor_id": 10, "skill_id": 3, "healing": 50, "ticks": 2, "hot": True}]}
        self.app.render(snapshot, {})
        overlay = self.app.overlay
        self.assertEqual([row["total"] for row in overlay.ranking], [40, 20])
        overlay.target.current(1)
        overlay.render_rows()
        self.assertEqual(overlay.ranking[0]["dps"], 250)
        overlay.metric.set("治疗")
        overlay.refresh_targets()
        self.assertEqual(overlay.ranking[0]["total"], 80)
        self.assertNotIn("dps", overlay.ranking[0])
        self.assertIn("非有效治疗", overlay.target.get())
        overlay.show_details(0)
        tree, = overlay.details.winfo_children()
        self.assertEqual(len(tree.get_children()), 2)

    def test_overlay_retains_history_selection_without_changing_live_snapshot(self):
        past = {"targets": [{"target_id": 1, "players": [{"actor_id": 10,
                "damage": 90, "dps": 45, "skills": []}]}]}
        current = {"targets": [], "healing": []}
        overlay = self.app.overlay
        overlay.update(current, history=[past])
        overlay.source.current(1)
        overlay.refresh_targets()
        self.assertEqual(overlay.ranking[0]["total"], 90)
        overlay.update(current, history=[past])
        self.assertEqual(overlay.source.current(), 1)
        self.assertIs(overlay.snapshot, current)
        overlay.update(current, history=[])
        self.assertEqual(overlay.source.current(), 0)
        self.assertFalse(overlay.ranking)

    def test_localization_missing_components_and_declined_confirmation_do_not_write(self):
        self.app.localization_engine = Mock()
        self.app.localization_game = Mock(client="steam", root="isolated-fixture")
        with patch("app.messagebox.askyesno", return_value=False):
            self.app.run_localization("install")
        self.app.localization_engine.execute.assert_not_called()
        self.assertFalse(self.app.localization_writing)
        self.app.localization_game.client = "purple"
        self.app.client.set("PURPLE")
        with patch("app.messagebox.askyesno") as confirm:
            self.app.run_localization("install")
        confirm.assert_not_called()
        self.app.localization_engine.execute.assert_not_called()

    def test_localization_result_does_not_end_capture_or_claim_cancelled_success(self):
        self.app.running = True
        self.app.localization_busy = True
        self.app.localization_writing = True
        self.app.events.put(("localization_result", {"cancelled": True}, None))
        self.app.poll()
        self.assertTrue(self.app.running)
        self.assertFalse(self.app.localization_busy)
        self.assertFalse(self.app.localization_writing)
        self.assertIn("已取消", self.app.localization_status.get())

    def test_window_cannot_close_during_transaction(self):
        self.app.localization_writing = True
        with patch("app.messagebox.showinfo") as notice, patch.object(self.root, "destroy") as destroy:
            self.app.close()
        notice.assert_called_once()
        destroy.assert_not_called()
        self.app.localization_writing = False

    def test_compact_window_keeps_settings_out_of_statistics_layout(self):
        self.root.update_idletasks()
        scale = max(1.0, self.root.winfo_fpixels("1i") / 96)
        self.assertEqual(self.app.settings_window.state(), "withdrawn")
        self.assertEqual(self.app.advanced.master, self.app.settings_window)
        self.assertIn(f"{round(760 * scale)}x{round(570 * scale)}", self.root.geometry())
        self.assertLessEqual(self.root.winfo_reqwidth(), round(760 * scale))
        self.assertLessEqual(self.root.winfo_reqheight(), round(570 * scale))
        self.assertEqual(str(self.app.auto_start_button["state"]), "normal")
        self.assertFalse(self.app.consent.get())
        self.assertIn("检查环境", self.app.detect_button["text"])
        self.assertEqual(str(self.app.live_button["state"]), "disabled")
        self.app.toggle_advanced()
        self.assertEqual(self.app.advanced.winfo_manager(), "pack")
        self.app.toggle_advanced()
        self.assertFalse(self.app.advanced.winfo_manager())

    def test_guided_missing_driver_shows_next_step_without_modal_or_capture(self):
        with patch("app.WinDivertReader", side_effect=RuntimeError("missing")), \
                patch("app.messagebox.showerror") as modal, patch.object(self.app, "detect_connections") as detect:
            self.app.check_setup()
        modal.assert_not_called()
        detect.assert_not_called()
        self.assertIn("内置采集组件未就绪", self.app.status.get())
        self.assertFalse(self.app.consent.get())
        self.assertFalse(self.app.running)

    def test_guided_unique_loopback_selects_scope_but_never_consents_or_starts(self):
        scope = ConnectionScope("127.0.0.1", 50000, "127.0.0.1", 1111)
        candidate = GameConnection(100, "127.0.0.1", 1111, "path_restricted", scope)
        self.app.devices = [(r"\Device\NPF_Loopback", "Loopback")]
        self.app.device_box["values"] = ("Loopback",)
        self.app.guided_check = True
        self.app.events.put(("discovery", DiscoveryReport([candidate], 1, 1, 1)))
        self.app.poll()
        self.assertEqual(self.app.selected_connection, candidate)
        self.assertEqual(self.app.device_box.current(), 0)
        self.assertIn("环境已就绪", self.app.status.get())
        self.assertFalse(self.app.running)
        self.assertFalse(self.app.consent.get())

    def test_guided_multiple_connections_never_guess_combat_channel(self):
        candidates = [GameConnection(100, "10.0.0.2", port, "unknown") for port in (7777, 8888)]
        self.app.guided_check = True
        self.app.events.put(("discovery", DiscoveryReport(candidates, 1, 0, 0)))
        self.app.poll()
        self.assertIsNone(self.app.selected_connection)
        self.assertEqual(self.app.connection_box.current(), -1)
        self.assertIn("尚不能确定战斗通道", self.app.status.get())
        self.assertFalse(self.app.consent.get())

    def test_auto_capture_requires_human_confirmation_and_cancel_never_starts(self):
        scope = ConnectionScope("127.0.0.1", 50000, "127.0.0.1", 1111)
        report = DiscoveryReport([GameConnection(100, "127.0.0.1", 1111, "path_restricted", scope)], 1, 1, 1)
        self.app.devices = [(r"\Device\NPF_Loopback", "Loopback")]
        for consent in (False, True):
            self.app.consent.set(False)
            with patch.object(self.app, "backend_executable", return_value="fixture"), \
                    patch("app.messagebox.askyesno", return_value=consent) as question, \
                    patch.object(self.app, "start_replay") as start:
                self.app.confirm_auto_start(report)
            question.assert_called_once()
            self.assertEqual(self.app.consent.get(), consent)
            self.assertEqual(start.call_count, int(consent))

    def test_windivert_auto_entry_does_not_require_npcap_or_nic(self):
        with patch("app.WinDivertReader") as factory, patch.object(self.app, "is_admin", return_value=True), \
                patch.object(self.app, "detect_connections") as detect, patch("app.Npcap") as npcap:
            self.app.begin_auto()
        detect.assert_called_once()
        npcap.assert_not_called()
        factory.return_value.packets_for_scopes.assert_not_called()
        self.assertTrue(self.app.pending_auto_start)
        self.assertFalse(self.app.consent.get())

    def test_missing_admin_does_not_elevate_or_open_capture_automatically(self):
        with patch("app.WinDivertReader") as factory, patch.object(self.app, "is_admin", return_value=False), \
                patch.object(self.app, "detect_connections") as detect, patch.object(self.app, "relaunch_admin") as elevate:
            self.app.begin_auto()
        detect.assert_not_called()
        elevate.assert_not_called()
        factory.return_value.packets_for_scopes.assert_not_called()
        self.assertIn("管理员权限重开", self.app.status.get())

    def test_windivert_confirmation_discloses_driver_and_cancel_never_opens(self):
        self.app.windivert = Mock()
        scope = ConnectionScope("127.0.0.1", 50000, "127.0.0.1", 1111)
        report = DiscoveryReport([GameConnection(100, "127.0.0.1", 1111, "unknown", scope)], 1, 0, 1)
        with patch.object(self.app, "backend_executable", return_value="fixture"), \
                patch("app.messagebox.askyesno", return_value=False) as question, \
                patch.object(self.app, "start_replay") as start:
            self.app.confirm_auto_start(report)
        self.assertIn("WinDivert 驱动", question.call_args.args[1])
        start.assert_not_called()
        self.app.windivert.packets_for_scopes.assert_not_called()

    def test_changed_windivert_plan_never_opens_driver(self):
        from auto_capture import prepare_auto_capture
        self.app.windivert = Mock()
        scope = ConnectionScope("127.0.0.1", 50000, "127.0.0.1", 1111)
        report = DiscoveryReport([GameConnection(100, "127.0.0.1", 1111, "unknown", scope)], 1, 0, 1)
        plan = prepare_auto_capture(report, [], provider="windivert")
        with patch("app.BackendBridge"), patch("app.find_game_discovery", return_value=DiscoveryReport([], 1, 0, 0)):
            self.app.work(None, "fixture", "steam", 0, plan)
        self.app.windivert.packets_for_scopes.assert_not_called()
        self.app.poll()
        self.assertIn("连接已变化", self.app.status.get())

    def test_localization_discovery_is_read_only_and_does_not_finish_capture(self):
        from pathlib import Path
        from localization_paths import LocalizationInstallation
        record = LocalizationInstallation(Path("fixture-game"), "steam", True, False, False, False)
        self.app.running = True
        self.app.localization_busy = True
        self.app.events.put(("localization", "Steam / Global", [record], None))
        self.app.poll()
        self.assertEqual(self.app.localization_game, record)
        self.assertFalse(self.app.localization_busy)
        self.assertTrue(self.app.running)
        self.assertFalse(self.app.consent.get())
        self.assertIn("尚未检查", self.app.localization_status.get())

    def test_client_change_rejects_stale_localization_detection(self):
        self.app.client.set("PURPLE")
        self.app.events.put(("localization", "Steam / Global", [], None))
        self.app.poll()
        self.assertIsNone(self.app.localization_game)
        self.assertIn("客户端选择已变化", self.app.localization_status.get())

    def test_start_button_requires_ready_scope_interface_and_manual_consent(self):
        scope = ConnectionScope("127.0.0.1", 50000, "127.0.0.1", 1111)
        self.app.selected_connection = GameConnection(100, "127.0.0.1", 1111, "unknown", scope)
        self.app.server_ip.set("127.0.0.1")
        self.app.port.set("1111")
        self.app.npcap = Mock()
        self.app.devices = [(r"\Device\NPF_Loopback", "Loopback")]
        self.app.device_box["values"] = ("Loopback",)
        self.app.device_box.current(0)
        self.app.update_live_state()
        self.assertEqual(str(self.app.live_button["state"]), "disabled")
        self.app.consent.set(True)
        self.app.update_live_state()
        self.assertEqual(str(self.app.live_button["state"]), "normal")
        self.app.server_ip.set("127.0.0.2")
        self.app.update_live_state()
        self.assertEqual(str(self.app.live_button["state"]), "disabled")
        self.app.npcap.packets.assert_not_called()

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
