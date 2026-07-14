import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QScrollArea, QSizePolicy, QTabWidget
from PIL import Image

import screen_layout_config
import group_config
from tools import gui_editor
from tools.gui_editor import GuiEditorApp, GuiEditorDataService


class GuiEditorDataServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = GuiEditorDataService()

    def test_build_resource_tree_rows_contains_cards_folder(self):
        rows = self.service.build_resource_tree_rows()
        self.assertTrue(any(row["id"] == "cards" and row["kind"] == "folder" for row in rows))
        self.assertTrue(any(row["id"] == "cards.card_back" and row["kind"] == "resource" for row in rows))
        self.assertTrue(any(row["id"] == "cards" and row["text"].startswith("[DIR] ") for row in rows))
        self.assertTrue(any(row["id"] == "cards.card_back" and row["text"].startswith("[PNG] ") for row in rows))

    def test_build_gui_explorer_nodes_contains_screen_frames_and_groups(self):
        nodes = self.service.build_gui_explorer_nodes()
        node_ids = {node.node_id for node in nodes}
        self.assertIn("screen:table_screen", node_ids)
        self.assertIn("frame:game_table", node_ids)
        self.assertIn("group:table_group", node_ids)
        self.assertTrue(any(node.node_id == "screen:table_screen" and node.label.startswith("[SCREEN] ") for node in nodes))
        self.assertTrue(any(node.node_id == "frame:game_table" and node.label.startswith("[FRAME] ") for node in nodes))
        self.assertTrue(any(node.node_id == "group:table_group" and node.label.startswith("[GROUP] ") for node in nodes))

    def test_group_node_is_attached_to_placement_frame(self):
        nodes = self.service.build_gui_explorer_nodes()
        table_group = next(node for node in nodes if node.node_id == "group:table_group")
        self.assertEqual(table_group.parent_id, "frame:game_table")

    def test_add_png_to_manifest_creates_resource_entry_for_assets_file(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "test_card.png"
            Image.new("RGBA", (126, 189), (255, 0, 0, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            resource_key, entry = service.add_png_to_manifest(str(png_path))

            self.assertEqual(resource_key, "cards.test_card")
            self.assertEqual(
                entry,
                {
                    "path": "cards/test_card.png",
                    "frame_width": 126,
                    "frame_height": 189,
                },
            )
            manifest = service.load_resource_manifest()
            self.assertIn("cards.test_card", manifest["resources"])

    def test_add_png_to_manifest_rejects_file_outside_assets(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            assets_dir.mkdir()
            external_png_path = Path(temp_dir) / "external.png"
            Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(external_png_path)

            service = GuiEditorDataService(project_dir=temp_dir)

            with self.assertRaisesRegex(ValueError, "inside assets/"):
                service.add_png_to_manifest(str(external_png_path))

    def test_create_manifest_folder_persists_logical_folder_without_png(self):
        with TemporaryDirectory() as temp_dir:
            service = GuiEditorDataService(project_dir=temp_dir)
            folder_id, folders = service.create_manifest_folder("ui.tokens")
            self.assertEqual(folder_id, "ui.tokens")
            self.assertIn("ui", folders)
            self.assertIn("ui.tokens", folders)
            manifest = service.load_resource_manifest()
            self.assertEqual(manifest["folders"], ["ui", "ui.tokens"])

    def test_rename_manifest_folder_updates_child_resource_keys(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "badge.png"
            Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            service.add_png_to_manifest(str(png_path), manifest_path="ui.icons.badge.png")
            service.create_manifest_folder("ui.icons")

            renamed = service.rename_manifest_folder("ui.icons", "sprites")

            manifest = service.load_resource_manifest()
            self.assertEqual(renamed, "ui.sprites")
            self.assertIn("ui.sprites.badge", manifest["resources"])
            self.assertNotIn("ui.icons.badge", manifest["resources"])

    def test_move_manifest_nodes_moves_resource_to_target_folder(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            source_dir = assets_dir / "cards"
            source_dir.mkdir(parents=True)
            png_path = source_dir / "badge.png"
            Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            service.add_png_to_manifest(str(png_path), manifest_path="cards.badge.png")
            service.create_manifest_folder("ui.tokens")

            target = service.move_manifest_nodes(["cards.badge"], "ui.tokens")

            manifest = service.load_resource_manifest()
            self.assertEqual(target, "ui.tokens")
            self.assertIn("ui.tokens.badge", manifest["resources"])
            self.assertNotIn("cards.badge", manifest["resources"])

    def test_rename_manifest_resource_updates_resource_key(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "badge.png"
            Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            service.add_png_to_manifest(str(png_path), manifest_path="ui.badge.png")

            renamed = service.rename_manifest_resource("ui.badge", "token")

            manifest = service.load_resource_manifest()
            self.assertEqual(renamed, "ui.token")
            self.assertIn("ui.token", manifest["resources"])
            self.assertNotIn("ui.badge", manifest["resources"])

    def test_remove_manifest_folder_deletes_folder_branch_and_resources_only_in_manifest(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "badge.png"
            Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            service.add_png_to_manifest(str(png_path), manifest_path="ui.icons.badge.png")
            service.create_manifest_folder("ui.icons")

            removed = service.remove_manifest_folder("ui")

            manifest = service.load_resource_manifest()
            self.assertEqual(removed, "ui")
            self.assertEqual(manifest["folders"], [])
            self.assertEqual(manifest["resources"], {})
            self.assertTrue(png_path.exists())


class GuiEditorThemeTests(unittest.TestCase):
    def test_available_themes_returns_non_empty_tuple(self):
        self.assertTrue(GuiEditorApp.available_themes())

    def test_available_themes_returns_only_requested_options(self):
        self.assertEqual(GuiEditorApp.available_themes(), ("cyborg", "darkly"))

    def test_branch_assets_exist(self):
        asset_urls = GuiEditorApp._branch_asset_urls()
        for asset_path in asset_urls.values():
            self.assertTrue(Path(asset_path).exists(), asset_path)

    def test_preview_screen_parser_accepts_table_screen(self):
        parser = gui_editor.build_parser()
        args = parser.parse_args(["preview-screen", "table_screen"])
        self.assertEqual(args.command, "preview-screen")
        self.assertEqual(args.screen_id, "table_screen")

    def test_table_screen_gui_preview_state_contains_full_ui_state(self):
        fixture = gui_editor.build_table_screen_gui_preview_state()
        self.assertEqual(
            fixture["bot_hand_counts"],
            {
                "left_player_hand": 6,
                "right_player_hand": 6,
                "top_player_hand": 6,
            },
        )
        self.assertEqual(
            fixture["bottom_player_cards"],
            (
                "cards.6_of_clubs",
                "cards.7_of_diamonds",
                "cards.8_of_hearts",
                "cards.9_of_spades",
                "cards.10_of_clubs",
                "cards.j_of_diamonds",
            ),
        )
        self.assertEqual(
            fixture["table_slots"]["cards_slot_frame"],
            ("cards.6_of_clubs", "cards.6_of_diamonds"),
        )


class GuiEditorUiContainerInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = GuiEditorApp()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def test_create_uses_scroll_instead_of_vertical_compression(self):
        create_views = self.window.left_panel.findChildren(QScrollArea)
        self.assertEqual(len(create_views), 1)
        self.assertTrue(create_views[0].widgetResizable())

    def test_create_panels_use_content_driven_vertical_size_policy(self):
        create_panels = [
            self.window.create_screen_button.parentWidget(),
            self.window.create_frame_button.parentWidget(),
            self.window.create_group_button.parentWidget(),
        ]
        for panel in create_panels:
            self.assertEqual(panel.property("panel"), True)
            self.assertEqual(panel.sizePolicy().verticalPolicy(), QSizePolicy.Maximum)
            self.assertEqual(panel.maximumHeight(), 16777215)

    def test_right_tabs_keep_stable_width_when_switching(self):
        right_tabs = self.window.right_tabs
        initial_width = right_tabs.width()
        right_tabs.setCurrentIndex(1)
        self.app.processEvents()
        gui_width = right_tabs.width()
        right_tabs.setCurrentIndex(0)
        self.app.processEvents()
        rm_width = right_tabs.width()
        self.assertEqual(initial_width, gui_width)
        self.assertEqual(initial_width, rm_width)

    def test_window_uses_compact_default_size_contract(self):
        self.assertEqual(self.window.width(), GuiEditorApp.MIN_WIDTH)
        self.assertEqual(self.window.height(), GuiEditorApp.MIN_HEIGHT)
        self.assertEqual(self.window.explorer_panel.width(), self.window.right_tabs.width())


class GuiEditorUiMetricInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = GuiEditorApp()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def test_create_form_inputs_share_consistent_height_metrics(self):
        full_width_inputs = [
            self.window.create_screen_id_input,
            self.window.create_root_frame_id_input,
            self.window.create_width_input,
            self.window.create_height_input,
            self.window.create_frame_screen_id_input,
            self.window.create_frame_id_input,
            self.window.create_frame_parent_id_input,
            self.window.create_group_screen_id_input,
            self.window.create_group_id_input,
            self.window.create_group_frame_id_input,
        ]
        compact_inputs = [
            self.window.create_frame_x_input,
            self.window.create_frame_y_input,
            self.window.create_frame_width_input,
            self.window.create_frame_height_input,
            self.window.create_group_x_input,
            self.window.create_group_y_input,
        ]
        full_heights = {widget.height() for widget in full_width_inputs}
        compact_heights = {widget.height() for widget in compact_inputs}
        self.assertEqual(len(full_heights), 1)
        self.assertEqual(len(compact_heights), 1)
        self.assertEqual(full_heights, compact_heights)

    def test_compact_numeric_inputs_share_same_maximum_width(self):
        compact_inputs = [
            self.window.create_frame_x_input,
            self.window.create_frame_y_input,
            self.window.create_frame_width_input,
            self.window.create_frame_height_input,
            self.window.create_group_x_input,
            self.window.create_group_y_input,
        ]
        self.assertEqual({widget.maximumWidth() for widget in compact_inputs}, {96})

    def test_identity_inputs_are_wider_than_compact_geometry_inputs(self):
        identity_inputs = [
            self.window.create_screen_id_input,
            self.window.create_root_frame_id_input,
            self.window.create_frame_screen_id_input,
            self.window.create_frame_id_input,
            self.window.create_frame_parent_id_input,
            self.window.create_group_screen_id_input,
            self.window.create_group_id_input,
            self.window.create_group_frame_id_input,
        ]
        compact_inputs = [
            self.window.create_frame_x_input,
            self.window.create_frame_y_input,
            self.window.create_frame_width_input,
            self.window.create_frame_height_input,
            self.window.create_group_x_input,
            self.window.create_group_y_input,
        ]
        self.assertGreater(min(widget.width() for widget in identity_inputs), max(widget.width() for widget in compact_inputs))

    def test_create_buttons_share_same_height(self):
        button_heights = {
            self.window.create_screen_button.height(),
            self.window.create_frame_button.height(),
            self.window.create_group_button.height(),
        }
        self.assertEqual(len(button_heights), 1)

    def test_create_status_labels_use_muted_role(self):
        status_labels = [
            self.window.create_status_label,
            self.window.create_frame_status_label,
            self.window.create_group_status_label,
        ]
        self.assertEqual({label.property("role") for label in status_labels}, {"muted"})


class GuiEditorUiCompositionInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = GuiEditorApp()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def test_action_and_status_rows_do_not_overlap_in_group_section(self):
        group_panel = self.window.create_group_button.parentWidget()
        button_geometry = self.window.create_group_button.geometry()
        status_geometry = self.window.create_group_status_label.geometry()
        self.assertFalse(button_geometry.intersects(status_geometry))
        self.assertLess(button_geometry.bottom(), status_geometry.top())
        self.assertLessEqual(status_geometry.bottom(), group_panel.contentsRect().bottom())

    def test_create_sections_follow_shared_vertical_composition_order(self):
        sections = [
            (
                self.window.create_screen_button.parentWidget(),
                [self.window.create_screen_id_input, self.window.create_root_frame_id_input],
                [self.window.create_width_input, self.window.create_height_input],
                self.window.create_screen_button,
                self.window.create_status_label,
            ),
            (
                self.window.create_frame_button.parentWidget(),
                [
                    self.window.create_frame_screen_id_input,
                    self.window.create_frame_id_input,
                    self.window.create_frame_parent_id_input,
                ],
                [
                    self.window.create_frame_x_input,
                    self.window.create_frame_y_input,
                    self.window.create_frame_width_input,
                    self.window.create_frame_height_input,
                ],
                self.window.create_frame_button,
                self.window.create_frame_status_label,
            ),
            (
                self.window.create_group_button.parentWidget(),
                [
                    self.window.create_group_screen_id_input,
                    self.window.create_group_id_input,
                    self.window.create_group_frame_id_input,
                ],
                [self.window.create_group_x_input, self.window.create_group_y_input],
                self.window.create_group_button,
                self.window.create_group_status_label,
            ),
        ]
        for panel, identity_widgets, geometry_widgets, button, status_label in sections:
            self.assertLess(max(widget.geometry().bottom() for widget in identity_widgets), min(widget.geometry().top() for widget in geometry_widgets))
            self.assertLess(max(widget.geometry().bottom() for widget in geometry_widgets), button.geometry().top())
            self.assertLess(button.geometry().bottom(), status_label.geometry().top())
            self.assertLessEqual(status_label.geometry().bottom(), panel.contentsRect().bottom())

    def test_geometry_rows_are_two_column_compact_grids(self):
        self.assertEqual(self.window.create_frame_x_input.geometry().top(), self.window.create_frame_y_input.geometry().top())
        self.assertEqual(self.window.create_frame_width_input.geometry().top(), self.window.create_frame_height_input.geometry().top())
        self.assertEqual(self.window.create_group_x_input.geometry().top(), self.window.create_group_y_input.geometry().top())
        self.assertLess(self.window.create_frame_x_input.geometry().right(), self.window.create_frame_y_input.geometry().left())
        self.assertLess(self.window.create_group_x_input.geometry().right(), self.window.create_group_y_input.geometry().left())


class GuiEditorUiStructureInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = GuiEditorApp()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def test_main_tabs_match_expected_information_architecture(self):
        tab_widgets = self.window.findChildren(QTabWidget)
        self.assertEqual(len(tab_widgets), 1)
        tab_titles = [
            [tabs.tabText(index) for index in range(tabs.count())]
            for tabs in tab_widgets
        ]
        self.assertIn(["RM Manifest Explorer", "GUI Explorer"], tab_titles)


class GuiEditorCreateContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_gui_screen_context_can_start_action_runner_isolated_screen(self):
        window = GuiEditorApp()

        with mock.patch("tools.gui_editor.subprocess.Popen") as popen:
            started = window.run_gui_screen("screen:table_screen")

        self.assertEqual(started, "table_screen")
        popen.assert_called_once()
        command = popen.call_args.args[0]
        self.assertEqual(command[-2:], ["preview-screen", "table_screen"])
        window.close()

    def test_gui_screen_context_can_start_gui_editor_preview_for_editor_screen(self):
        window = GuiEditorApp()

        with mock.patch("tools.gui_editor.subprocess.Popen") as popen:
            started = window.run_gui_screen("screen:test_screen")

        self.assertEqual(started, "test_screen")
        popen.assert_called_once()
        command = popen.call_args.args[0]
        self.assertEqual(command[-2:], ["preview-screen", "test_screen"])
        window.close()

    def test_gui_frame_context_populates_create_forms(self):
        window = GuiEditorApp()
        frame_item = window._select_gui_node("frame:game_table", expand_parents=True)

        window.load_gui_node_into_create(frame_item)

        self.assertEqual(window.create_screen_id_input.text(), "table_screen")
        self.assertEqual(window.create_frame_id_input.text(), "game_table")
        self.assertEqual(window.create_frame_parent_id_input.text(), "")
        self.assertEqual(window.create_frame_x_input.text(), "0")
        self.assertEqual(window.create_frame_y_input.text(), "0")
        self.assertEqual(window.create_frame_width_input.text(), "1280")
        self.assertEqual(window.create_frame_height_input.text(), "720")
        self.assertEqual(window.create_group_frame_id_input.text(), "game_table")
        window.close()

    def test_gui_nested_frame_context_populates_geometry_from_manifest(self):
        window = GuiEditorApp()
        frame_item = window._select_gui_node("frame:play_area_frame", expand_parents=True)

        window.load_gui_node_into_create(frame_item)

        self.assertEqual(window.create_screen_id_input.text(), "table_screen")
        self.assertEqual(window.create_frame_id_input.text(), "play_area_frame")
        self.assertEqual(window.create_frame_parent_id_input.text(), "game_table")
        self.assertEqual(window.create_frame_x_input.text(), "20")
        self.assertEqual(window.create_frame_y_input.text(), "20")
        self.assertEqual(window.create_frame_width_input.text(), "1240")
        self.assertEqual(window.create_frame_height_input.text(), "680")
        self.assertEqual(window.create_group_frame_id_input.text(), "play_area_frame")
        window.close()

    def test_gui_frame_context_clears_stale_group_screen_id(self):
        window = GuiEditorApp()
        frame_item = window._select_gui_node("frame:play_area_frame", expand_parents=True)
        window.create_group_screen_id_input.setText("logo")

        window.load_gui_node_into_create(frame_item)

        self.assertEqual(window.create_group_screen_id_input.text(), "table_screen")
        self.assertEqual(window.create_group_frame_id_input.text(), "play_area_frame")
        window.close()

    def test_gui_group_context_populates_group_fields(self):
        window = GuiEditorApp()
        group_item = window._select_gui_node("group:table_group", expand_parents=True)

        window.load_gui_node_into_create(group_item)

        self.assertEqual(window.create_group_screen_id_input.text(), "table_screen")
        self.assertEqual(window.create_group_id_input.text(), "table_group")
        self.assertEqual(window.create_group_frame_id_input.text(), "game_table")
        self.assertEqual(window.create_group_x_input.text(), "0")
        self.assertEqual(window.create_group_y_input.text(), "0")
        window.close()

    def test_gui_screen_context_populates_screen_size_fields(self):
        window = GuiEditorApp()
        screen_item = window._select_gui_node("screen:table_screen", expand_parents=True)

        window.load_gui_node_into_create(screen_item)

        self.assertEqual(window.create_screen_id_input.text(), "table_screen")
        self.assertEqual(window.create_root_frame_id_input.text(), "game_table")
        self.assertEqual(window.create_width_input.text(), "1280")
        self.assertEqual(window.create_height_input.text(), "720")
        window.close()

    def test_create_group_from_screen_context_shows_warning_and_marks_missing_frame(self):
        window = GuiEditorApp()
        screen_item = window._select_gui_node("screen:table_screen", expand_parents=True)
        window.gui_tree.setCurrentItem(screen_item)
        window.create_group_screen_id_input.setText("table_screen")
        window.create_group_id_input.setText("new_group")
        window.create_group_frame_id_input.setText("")

        with mock.patch("tools.gui_editor.QMessageBox.warning") as warning_box:
            result = window.create_group_from_form()

        self.assertIsNone(result)
        warning_box.assert_called_once()
        self.assertIn("#d9534f", window.create_group_frame_id_input.styleSheet())
        window.close()

    def test_save_existing_group_from_screen_context_allows_filled_frame_id(self):
        with TemporaryDirectory() as temp_dir:
            temp_layout_path = Path(temp_dir) / "screen_layout.json"
            temp_group_path = Path(temp_dir) / "group_config.json"
            with (
                mock.patch.object(screen_layout_config, "SCREEN_LAYOUT_PATH", str(temp_layout_path)),
                mock.patch.object(group_config, "GROUP_CONFIG_FILE", str(temp_group_path)),
            ):
                payload = screen_layout_config.upsert_screen("test_screen", "test_root_frame", (320, 320))
                payload = screen_layout_config.upsert_group_placement("test_group", "test_screen", "test_root_frame", position=(0, 0), payload=payload)
                screen_layout_config.save_screen_layout(payload)
                group_config.GROUP_CONFIG = {
                    "groups": {
                        "test_group": {
                            "role": "",
                            "tags": [],
                            "rect": [0, 0, 0, 0],
                            "hit_rect": [0, 0, 0, 0],
                            "scale_factor": 1.0,
                            "hide_rect": True,
                            "manifest_targets": {},
                            "layers": [],
                        }
                    }
                }
                group_config.save_group_config(group_config.GROUP_CONFIG)
                group_config.reload_group_config()

                window = GuiEditorApp()
                screen_item = window._select_gui_node("screen:test_screen", expand_parents=True)
                window.gui_tree.setCurrentItem(screen_item)
                window.create_group_screen_id_input.setText("test_screen")
                window.create_group_id_input.setText("test_group")
                window.create_group_frame_id_input.setText("test_root_frame")
                window.create_group_x_input.setText("0")
                window.create_group_y_input.setText("0")
                window.group_graphic_resource_rows[0]["entry"].setText("main_screen.table")

                with mock.patch("tools.gui_editor.QMessageBox.warning") as warning_box:
                    result = window.create_group_from_form()

                self.assertIsNotNone(result)
                warning_box.assert_not_called()
                groups_payload = group_config.load_group_config()
                self.assertEqual(
                    groups_payload["groups"]["test_group"]["layers"][0]["resource_key"],
                    "main_screen.table",
                )
                window.close()


class GuiEditorCreateScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_create_screen_form_persists_test_screen_with_root_frame(self):
        with TemporaryDirectory() as temp_dir:
            temp_layout_path = Path(temp_dir) / "screen_layout.json"
            with mock.patch.object(screen_layout_config, "SCREEN_LAYOUT_PATH", str(temp_layout_path)):
                window = GuiEditorApp()
                window.create_screen_id_input.setText("test_screen")
                window.create_root_frame_id_input.setText("test_root_frame")
                window.create_width_input.setText("1280")
                window.create_height_input.setText("720")

                window.create_screen_button.click()

                payload = screen_layout_config.load_screen_layout()
                screen_payload = payload["screens"]["test_screen"]
                self.assertEqual(screen_payload["root_frame_id"], "test_root_frame")
                self.assertEqual(screen_payload["size"], [1280, 720])
                self.assertEqual(
                    screen_payload["frames"]["test_root_frame"]["rect"],
                    [0, 0, 1280, 720],
                )
                node_ids = {node.node_id for node in window.service.build_gui_explorer_nodes()}
                self.assertIn("screen:test_screen", node_ids)
                self.assertIn("frame:test_root_frame", node_ids)
                self.assertEqual(window.gui_tree.currentItem().data(0, Qt.UserRole), "screen:test_screen")
                self.assertEqual(window.create_status_label.text(), "Created screen: test_screen")
                window.close()

    def test_create_frame_form_persists_child_frame_inside_test_screen(self):
        with TemporaryDirectory() as temp_dir:
            temp_layout_path = Path(temp_dir) / "screen_layout.json"
            with mock.patch.object(screen_layout_config, "SCREEN_LAYOUT_PATH", str(temp_layout_path)):
                payload = screen_layout_config.upsert_screen("test_screen", "test_root_frame", (1280, 720))
                screen_layout_config.save_screen_layout(payload)

                window = GuiEditorApp()
                window.create_frame_screen_id_input.setText("test_screen")
                window.create_frame_id_input.setText("left_panel")
                window.create_frame_parent_id_input.setText("test_root_frame")
                window.create_frame_x_input.setText("100")
                window.create_frame_y_input.setText("80")
                window.create_frame_width_input.setText("320")
                window.create_frame_height_input.setText("240")

                window.create_frame_button.click()

                payload = screen_layout_config.load_screen_layout()
                frame_payload = payload["screens"]["test_screen"]["frames"]["left_panel"]
                self.assertEqual(frame_payload["parent_frame_id"], "test_root_frame")
                self.assertEqual(frame_payload["rect"], [100, 80, 320, 240])
                nodes = window.service.build_gui_explorer_nodes()
                node_ids = {node.node_id for node in nodes}
                left_panel_node = next(node for node in nodes if node.node_id == "frame:left_panel")
                self.assertIn("frame:left_panel", node_ids)
                self.assertEqual(left_panel_node.parent_id, "frame:test_root_frame")
                self.assertEqual(window.gui_tree.currentItem().data(0, Qt.UserRole), "frame:left_panel")
                self.assertEqual(window.create_frame_status_label.text(), "Created frame: left_panel")
                window.close()

    def test_create_group_form_persists_group_and_placement(self):
        with TemporaryDirectory() as temp_dir:
            temp_layout_path = Path(temp_dir) / "screen_layout.json"
            temp_group_path = Path(temp_dir) / "group_config.json"
            with (
                mock.patch.object(screen_layout_config, "SCREEN_LAYOUT_PATH", str(temp_layout_path)),
                mock.patch.object(group_config, "GROUP_CONFIG_FILE", str(temp_group_path)),
            ):
                payload = screen_layout_config.upsert_screen("test_screen", "test_root_frame", (1280, 720))
                payload = screen_layout_config.upsert_frame("test_screen", "left_panel", "test_root_frame", (100, 80, 320, 240), payload=payload)
                screen_layout_config.save_screen_layout(payload)
                group_config.GROUP_CONFIG = {"groups": {}}
                group_config.save_group_config(group_config.GROUP_CONFIG)
                group_config.reload_group_config()

                window = GuiEditorApp()
                window.create_group_screen_id_input.setText("test_screen")
                window.create_group_id_input.setText("status_group")
                window.create_group_frame_id_input.setText("left_panel")
                window.create_group_x_input.setText("12")
                window.create_group_y_input.setText("34")

                window.create_group_button.click()

                groups_payload = group_config.load_group_config()
                self.assertIn("status_group", groups_payload["groups"])
                layout_payload = screen_layout_config.load_screen_layout()
                self.assertEqual(
                    layout_payload["screens"]["test_screen"]["groups"]["status_group"],
                    {"frame_id": "left_panel", "position": [12, 34]},
                )
                nodes = window.service.build_gui_explorer_nodes()
                group_node = next(node for node in nodes if node.node_id == "group:status_group")
                self.assertEqual(group_node.parent_id, "frame:left_panel")
                self.assertEqual(window.gui_tree.currentItem().data(0, Qt.UserRole), "group:status_group")
                self.assertEqual(window.create_group_status_label.text(), "Created group: status_group")
                window.close()

    def test_create_group_form_persists_graphic_and_text_layers(self):
        with TemporaryDirectory() as temp_dir:
            temp_layout_path = Path(temp_dir) / "screen_layout.json"
            temp_group_path = Path(temp_dir) / "group_config.json"
            with (
                mock.patch.object(screen_layout_config, "SCREEN_LAYOUT_PATH", str(temp_layout_path)),
                mock.patch.object(group_config, "GROUP_CONFIG_FILE", str(temp_group_path)),
            ):
                payload = screen_layout_config.upsert_screen("test_screen", "test_root_frame", (1280, 720))
                payload = screen_layout_config.upsert_frame("test_screen", "left_panel", "test_root_frame", (100, 80, 320, 240), payload=payload)
                screen_layout_config.save_screen_layout(payload)
                group_config.GROUP_CONFIG = {"groups": {}}
                group_config.save_group_config(group_config.GROUP_CONFIG)
                group_config.reload_group_config()

                window = GuiEditorApp()
                window.create_group_screen_id_input.setText("test_screen")
                window.create_group_id_input.setText("status_group")
                window.create_group_frame_id_input.setText("left_panel")
                window.create_group_x_input.setText("12")
                window.create_group_y_input.setText("34")
                window.group_graphic_resource_rows[0]["entry"].setText("main_screen.table")
                window.group_text_value_input.setText("Status")
                window.group_text_font_input.setText("Arial")
                window.group_text_size_input.setText("200,56")
                window.group_text_color_input.setText("255,255,255")

                window.create_group_button.click()

                groups_payload = group_config.load_group_config()
                layers = groups_payload["groups"]["status_group"]["layers"]
                self.assertEqual(layers[0]["resource_key"], "main_screen.table")
                self.assertEqual(layers[1]["text"], "Status")
                self.assertEqual(layers[1]["size"], [200, 56])
                self.assertEqual(layers[1]["style"]["font_name"], "Arial")
                self.assertEqual(layers[1]["style"]["color"], [255, 255, 255])

                group_item = window._select_gui_node("group:status_group", expand_parents=True)
                window.load_gui_node_into_create(group_item)
                self.assertEqual(window.group_graphic_resource_rows[0]["entry"].text(), "main_screen.table")
                self.assertEqual(window.group_text_value_input.text(), "Status")
                self.assertEqual(window.group_text_font_input.text(), "Arial")
                self.assertEqual(window.group_text_size_input.text(), "200,56")
                self.assertEqual(window.group_text_color_input.text(), "255,255,255")
                window.close()

    def test_attach_png_from_rm_and_save_group_persists_graphic_layer(self):
        with TemporaryDirectory() as temp_dir:
            temp_layout_path = Path(temp_dir) / "screen_layout.json"
            temp_group_path = Path(temp_dir) / "group_config.json"
            with (
                mock.patch.object(screen_layout_config, "SCREEN_LAYOUT_PATH", str(temp_layout_path)),
                mock.patch.object(group_config, "GROUP_CONFIG_FILE", str(temp_group_path)),
            ):
                payload = screen_layout_config.upsert_screen("test_screen", "test_root_frame", (320, 320))
                payload = screen_layout_config.upsert_group_placement("test_group", "test_screen", "test_root_frame", position=(0, 0), payload=payload)
                screen_layout_config.save_screen_layout(payload)
                group_config.GROUP_CONFIG = {
                    "groups": {
                        "test_group": {
                            "role": "",
                            "tags": [],
                            "rect": [0, 0, 0, 0],
                            "hit_rect": [0, 0, 0, 0],
                            "scale_factor": 1.0,
                            "hide_rect": True,
                            "manifest_targets": {},
                            "layers": [],
                        }
                    }
                }
                group_config.save_group_config(group_config.GROUP_CONFIG)
                group_config.reload_group_config()

                window = GuiEditorApp()
                group_item = window._select_gui_node("group:test_group", expand_parents=True)
                window.load_gui_node_into_create(group_item)
                resource_item = window._select_rm_node("main_screen.table", expand_parents=True)
                window.rm_tree.setCurrentItem(resource_item)

                window.group_graphic_resource_rows[0]["add_button"].click()
                window.create_group_button.click()

                groups_payload = group_config.load_group_config()
                layers = groups_payload["groups"]["test_group"]["layers"]
                self.assertEqual(window.group_graphic_resource_rows[0]["entry"].text(), "main_screen.table")
                self.assertEqual(layers[0]["resource_key"], "main_screen.table")
                self.assertEqual(window.group_graphic_status_label.text(), "Saved 1 graphic layer(s)")
                window.close()

    def test_create_group_form_preserves_existing_layers_when_layer_inputs_are_empty(self):
        with TemporaryDirectory() as temp_dir:
            temp_layout_path = Path(temp_dir) / "screen_layout.json"
            temp_group_path = Path(temp_dir) / "group_config.json"
            with (
                mock.patch.object(screen_layout_config, "SCREEN_LAYOUT_PATH", str(temp_layout_path)),
                mock.patch.object(group_config, "GROUP_CONFIG_FILE", str(temp_group_path)),
            ):
                payload = screen_layout_config.upsert_screen("test_screen", "test_root_frame", (1280, 720))
                payload = screen_layout_config.upsert_frame("test_screen", "left_panel", "test_root_frame", (100, 80, 320, 240), payload=payload)
                payload = screen_layout_config.upsert_group_placement("status_group", "test_screen", "left_panel", position=(12, 34), payload=payload)
                screen_layout_config.save_screen_layout(payload)
                group_config.GROUP_CONFIG = {
                    "groups": {
                        "status_group": {
                            "role": "",
                            "tags": [],
                            "rect": [0, 0, 0, 0],
                            "hit_rect": [0, 0, 0, 0],
                            "scale_factor": 1.0,
                            "hide_rect": True,
                            "manifest_targets": {},
                            "layers": [
                                {
                                    "name": "graphic_layer_1",
                                    "type": "image",
                                    "resource_key": "main_screen.table",
                                    "position": [0, 0],
                                },
                                {
                                    "name": "text_layer",
                                    "type": "text",
                                    "text": "Status",
                                    "position": [0, 0],
                                    "size": [200, 56],
                                    "style": {"font_name": "Arial", "color": [255, 255, 255]},
                                },
                            ],
                        }
                    }
                }
                group_config.save_group_config(group_config.GROUP_CONFIG)
                group_config.reload_group_config()

                window = GuiEditorApp()
                group_item = window._select_gui_node("group:status_group", expand_parents=True)
                window.load_gui_node_into_create(group_item)
                window.create_group_x_input.setText("20")
                window.create_group_y_input.setText("40")

                window.create_group_button.click()

                groups_payload = group_config.load_group_config()
                layers = groups_payload["groups"]["status_group"]["layers"]
                self.assertEqual(len(layers), 2)
                self.assertEqual(layers[0]["resource_key"], "main_screen.table")
                self.assertEqual(layers[1]["text"], "Status")
                layout_payload = screen_layout_config.load_screen_layout()
                self.assertEqual(
                    layout_payload["screens"]["test_screen"]["groups"]["status_group"],
                    {"frame_id": "left_panel", "position": [20, 40]},
                )
                self.assertEqual(window.group_graphic_status_label.text(), "Saved 1 graphic layer(s)")
                self.assertEqual(window.group_text_status_label.text(), "Saved text layer")
                window.close()

    def test_save_screen_blocks_geometry_change_when_nested_nodes_exist(self):
        with TemporaryDirectory() as temp_dir:
            temp_layout_path = Path(temp_dir) / "screen_layout.json"
            with mock.patch.object(screen_layout_config, "SCREEN_LAYOUT_PATH", str(temp_layout_path)):
                payload = screen_layout_config.upsert_screen("test_screen", "test_root_frame", (1280, 720))
                payload = screen_layout_config.upsert_frame("test_screen", "left_panel", "test_root_frame", (10, 10, 320, 200), payload=payload)
                payload = screen_layout_config.upsert_group_placement("status_group", "test_screen", "left_panel", position=(5, 5), payload=payload)
                screen_layout_config.save_screen_layout(payload)

                window = GuiEditorApp()
                window.create_screen_id_input.setText("test_screen")
                window.create_root_frame_id_input.setText("test_root_frame")
                window.create_width_input.setText("1400")
                window.create_height_input.setText("800")

                with mock.patch("tools.gui_editor.QMessageBox.warning") as warning_box:
                    result = window.create_screen_from_form()

                self.assertIsNone(result)
                warning_box.assert_called_once()
                self.assertEqual(window.right_tabs.currentIndex(), 1)
                self.assertIn("frame:left_panel", window.gui_problem_node_ids)
                self.assertIn("group:status_group", window.gui_problem_node_ids)
                self.assertTrue(window._select_gui_node("frame:left_panel").parent().isExpanded())
                self.assertEqual(window.create_status_label.text(), "Screen geometry save blocked by nested GUI objects")
                window.close()

    def test_save_frame_blocks_geometry_change_when_nested_nodes_exist(self):
        with TemporaryDirectory() as temp_dir:
            temp_layout_path = Path(temp_dir) / "screen_layout.json"
            with mock.patch.object(screen_layout_config, "SCREEN_LAYOUT_PATH", str(temp_layout_path)):
                payload = screen_layout_config.upsert_screen("test_screen", "test_root_frame", (1280, 720))
                payload = screen_layout_config.upsert_frame("test_screen", "parent_frame", "test_root_frame", (10, 10, 320, 200), payload=payload)
                payload = screen_layout_config.upsert_frame("test_screen", "child_frame", "parent_frame", (5, 5, 100, 50), payload=payload)
                screen_layout_config.save_screen_layout(payload)

                window = GuiEditorApp()
                window.create_frame_screen_id_input.setText("test_screen")
                window.create_frame_id_input.setText("parent_frame")
                window.create_frame_parent_id_input.setText("test_root_frame")
                window.create_frame_x_input.setText("20")
                window.create_frame_y_input.setText("20")
                window.create_frame_width_input.setText("400")
                window.create_frame_height_input.setText("300")

                with mock.patch("tools.gui_editor.QMessageBox.warning") as warning_box:
                    result = window.create_frame_from_form()

                self.assertIsNone(result)
                warning_box.assert_called_once()
                self.assertIn("frame:child_frame", window.gui_problem_node_ids)
                self.assertEqual(window.create_frame_status_label.text(), "Frame geometry save blocked by nested GUI objects")
                window.close()

    def test_delete_gui_group_removes_group_from_layout_and_group_config(self):
        with TemporaryDirectory() as temp_dir:
            temp_layout_path = Path(temp_dir) / "screen_layout.json"
            temp_group_path = Path(temp_dir) / "group_config.json"
            with (
                mock.patch.object(screen_layout_config, "SCREEN_LAYOUT_PATH", str(temp_layout_path)),
                mock.patch.object(group_config, "GROUP_CONFIG_FILE", str(temp_group_path)),
            ):
                payload = screen_layout_config.upsert_screen("test_screen", "test_root_frame", (1280, 720))
                payload = screen_layout_config.upsert_frame("test_screen", "left_panel", "test_root_frame", (100, 80, 320, 240), payload=payload)
                payload = screen_layout_config.upsert_group_placement("status_group", "test_screen", "left_panel", position=(12, 34), payload=payload)
                screen_layout_config.save_screen_layout(payload)
                group_config.GROUP_CONFIG = {"groups": {}}
                group_config.ensure_group("status_group")
                group_config.save_group_config(group_config.GROUP_CONFIG)
                group_config.reload_group_config()

                window = GuiEditorApp()

                with mock.patch("tools.gui_editor.QMessageBox.question", return_value=QMessageBox.Yes):
                    deleted = window.delete_gui_group("group:status_group")

                layout_payload = screen_layout_config.load_screen_layout()
                groups_payload = group_config.load_group_config()
                self.assertEqual(deleted, "status_group")
                self.assertNotIn("status_group", layout_payload["screens"]["test_screen"]["groups"])
                self.assertNotIn("status_group", groups_payload["groups"])
                self.assertEqual(window.create_group_status_label.text(), "Deleted group: status_group")
                window.close()

    def test_delete_gui_frame_cascades_to_child_frames_and_groups(self):
        with TemporaryDirectory() as temp_dir:
            temp_layout_path = Path(temp_dir) / "screen_layout.json"
            temp_group_path = Path(temp_dir) / "group_config.json"
            with (
                mock.patch.object(screen_layout_config, "SCREEN_LAYOUT_PATH", str(temp_layout_path)),
                mock.patch.object(group_config, "GROUP_CONFIG_FILE", str(temp_group_path)),
            ):
                payload = screen_layout_config.upsert_screen("test_screen", "test_root_frame", (1280, 720))
                payload = screen_layout_config.upsert_frame("test_screen", "parent_frame", "test_root_frame", (100, 80, 320, 240), payload=payload)
                payload = screen_layout_config.upsert_frame("test_screen", "child_frame", "parent_frame", (10, 10, 100, 50), payload=payload)
                payload = screen_layout_config.upsert_group_placement("parent_group", "test_screen", "parent_frame", position=(1, 2), payload=payload)
                payload = screen_layout_config.upsert_group_placement("child_group", "test_screen", "child_frame", position=(3, 4), payload=payload)
                screen_layout_config.save_screen_layout(payload)
                group_config.GROUP_CONFIG = {"groups": {}}
                group_config.ensure_group("parent_group")
                group_config.ensure_group("child_group")
                group_config.save_group_config(group_config.GROUP_CONFIG)
                group_config.reload_group_config()

                window = GuiEditorApp()

                with mock.patch("tools.gui_editor.QMessageBox.question", return_value=QMessageBox.Yes):
                    deleted = window.delete_gui_node("frame:parent_frame")

                layout_payload = screen_layout_config.load_screen_layout()
                groups_payload = group_config.load_group_config()
                self.assertEqual(deleted, "parent_frame")
                self.assertNotIn("parent_frame", layout_payload["screens"]["test_screen"]["frames"])
                self.assertNotIn("child_frame", layout_payload["screens"]["test_screen"]["frames"])
                self.assertNotIn("parent_group", layout_payload["screens"]["test_screen"]["groups"])
                self.assertNotIn("child_group", layout_payload["screens"]["test_screen"]["groups"])
                self.assertNotIn("parent_group", groups_payload["groups"])
                self.assertNotIn("child_group", groups_payload["groups"])
                self.assertEqual(window.create_frame_status_label.text(), "Deleted frame: parent_frame")
                window.close()

    def test_delete_gui_group_preserves_expanded_tree_state(self):
        with TemporaryDirectory() as temp_dir:
            temp_layout_path = Path(temp_dir) / "screen_layout.json"
            temp_group_path = Path(temp_dir) / "group_config.json"
            with (
                mock.patch.object(screen_layout_config, "SCREEN_LAYOUT_PATH", str(temp_layout_path)),
                mock.patch.object(group_config, "GROUP_CONFIG_FILE", str(temp_group_path)),
            ):
                payload = screen_layout_config.upsert_screen("test_screen", "test_root_frame", (1280, 720))
                payload = screen_layout_config.upsert_frame("test_screen", "left_panel", "test_root_frame", (100, 80, 320, 240), payload=payload)
                payload = screen_layout_config.upsert_group_placement("first_group", "test_screen", "left_panel", position=(12, 34), payload=payload)
                payload = screen_layout_config.upsert_group_placement("second_group", "test_screen", "left_panel", position=(56, 78), payload=payload)
                screen_layout_config.save_screen_layout(payload)
                group_config.GROUP_CONFIG = {"groups": {}}
                group_config.ensure_group("first_group")
                group_config.ensure_group("second_group")
                group_config.save_group_config(group_config.GROUP_CONFIG)
                group_config.reload_group_config()

                window = GuiEditorApp()
                screen_item = window._select_gui_node("screen:test_screen")
                frame_item = window._select_gui_node("frame:left_panel", expand_parents=True)
                screen_item.setExpanded(True)
                frame_item.setExpanded(True)

                with mock.patch("tools.gui_editor.QMessageBox.question", return_value=QMessageBox.Yes):
                    deleted = window.delete_gui_node("group:first_group")

                remaining_screen_item = window._select_gui_node("screen:test_screen")
                remaining_frame_item = window._select_gui_node("frame:left_panel", expand_parents=True)
                self.assertEqual(deleted, "first_group")
                self.assertTrue(remaining_screen_item.isExpanded())
                self.assertTrue(remaining_frame_item.isExpanded())
                window.close()

    def test_delete_gui_screen_cascades_to_screen_frames_and_groups(self):
        with TemporaryDirectory() as temp_dir:
            temp_layout_path = Path(temp_dir) / "screen_layout.json"
            temp_group_path = Path(temp_dir) / "group_config.json"
            with (
                mock.patch.object(screen_layout_config, "SCREEN_LAYOUT_PATH", str(temp_layout_path)),
                mock.patch.object(group_config, "GROUP_CONFIG_FILE", str(temp_group_path)),
            ):
                payload = screen_layout_config.upsert_screen("test_screen", "test_root_frame", (1280, 720))
                payload = screen_layout_config.upsert_frame("test_screen", "left_panel", "test_root_frame", (100, 80, 320, 240), payload=payload)
                payload = screen_layout_config.upsert_group_placement("status_group", "test_screen", "left_panel", position=(12, 34), payload=payload)
                screen_layout_config.save_screen_layout(payload)
                group_config.GROUP_CONFIG = {"groups": {}}
                group_config.ensure_group("status_group")
                group_config.save_group_config(group_config.GROUP_CONFIG)
                group_config.reload_group_config()

                window = GuiEditorApp()

                with mock.patch("tools.gui_editor.QMessageBox.question", return_value=QMessageBox.Yes):
                    deleted = window.delete_gui_node("screen:test_screen")

                layout_payload = screen_layout_config.load_screen_layout()
                groups_payload = group_config.load_group_config()
                self.assertEqual(deleted, "test_screen")
                self.assertNotIn("test_screen", layout_payload["screens"])
                self.assertNotIn("status_group", groups_payload["groups"])
                self.assertEqual(window.create_status_label.text(), "Deleted screen: test_screen")
                window.close()


class GuiEditorRmManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_add_png_button_updates_manifest_without_manifest_path_prompt(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "dialog_card.png"
            Image.new("RGBA", (90, 140), (0, 255, 0, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            settings_path = Path(temp_dir) / "gui_editor_settings.json"
            with mock.patch.object(gui_editor, "GUI_EDITOR_SETTINGS_PATH", str(settings_path)):
                window = GuiEditorApp(service=service)
                with (
                    mock.patch("tools.gui_editor.QFileDialog.getOpenFileName", return_value=(str(png_path), "PNG Files (*.png)")) as file_dialog,
                    mock.patch("tools.gui_editor.QMessageBox.question", return_value=16384) as folder_dialog,
                ):
                    result = window.add_png_from_dialog()

                manifest = service.load_resource_manifest()
                self.assertEqual(result, "cards.dialog_card")
                self.assertIn("cards.dialog_card", manifest["resources"])
                self.assertEqual(window.rm_status_label.text(), "Added PNG: cards.dialog_card")
                file_dialog.assert_called_once()
                folder_dialog.assert_called_once()
                window.close()

    def test_add_png_reveals_and_selects_added_resource_in_tree(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "reveal_me.png"
            Image.new("RGBA", (32, 48), (0, 255, 0, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            settings_path = Path(temp_dir) / "gui_editor_settings.json"
            with mock.patch.object(gui_editor, "GUI_EDITOR_SETTINGS_PATH", str(settings_path)):
                window = GuiEditorApp(service=service)
                with (
                    mock.patch("tools.gui_editor.QFileDialog.getOpenFileName", return_value=(str(png_path), "PNG Files (*.png)")),
                    mock.patch("tools.gui_editor.QMessageBox.question", return_value=65536),
                ):
                    window.add_png_from_dialog()

                current_item = window.rm_tree.currentItem()
                self.assertIsNotNone(current_item)
                self.assertEqual(current_item.data(0, Qt.UserRole), "cards.reveal_me")
                self.assertEqual(current_item.text(1), "resource")
                self.assertTrue(current_item.parent().isExpanded())
                window.close()

    def test_add_png_can_save_default_folder_preference(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "default_dir.png"
            Image.new("RGBA", (32, 48), (0, 255, 0, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            settings_path = Path(temp_dir) / "gui_editor_settings.json"
            with mock.patch.object(gui_editor, "GUI_EDITOR_SETTINGS_PATH", str(settings_path)):
                window = GuiEditorApp(service=service)
                with (
                    mock.patch("tools.gui_editor.QFileDialog.getOpenFileName", return_value=(str(png_path), "PNG Files (*.png)")),
                    mock.patch("tools.gui_editor.QMessageBox.question", return_value=QMessageBox.Yes),
                ):
                    window.add_png_from_dialog()

                self.assertEqual(service.get_default_add_png_dir(), str(cards_dir.resolve()))
                window.close()

    def test_add_png_refusal_to_save_default_folder_does_not_cancel_manifest_update(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "no_default.png"
            Image.new("RGBA", (32, 48), (0, 255, 0, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            settings_path = Path(temp_dir) / "gui_editor_settings.json"
            with mock.patch.object(gui_editor, "GUI_EDITOR_SETTINGS_PATH", str(settings_path)):
                window = GuiEditorApp(service=service)
                with (
                    mock.patch("tools.gui_editor.QFileDialog.getOpenFileName", return_value=(str(png_path), "PNG Files (*.png)")),
                    mock.patch("tools.gui_editor.QMessageBox.question", return_value=QMessageBox.No),
                ):
                    result = window.add_png_from_dialog()

                manifest = service.load_resource_manifest()
                self.assertEqual(result, "cards.no_default")
                self.assertIn("cards.no_default", manifest["resources"])
                self.assertIsNone(service.get_default_add_png_dir())
                window.close()

    def test_del_png_removes_selected_resource_entry_from_manifest(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "delete_me.png"
            Image.new("RGBA", (64, 96), (0, 0, 255, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            service.add_png_to_manifest(str(png_path))
            window = GuiEditorApp(service=service)

            leaf_item = None
            for index in range(window.rm_tree.topLevelItemCount()):
                root_item = window.rm_tree.topLevelItem(index)
                if root_item.data(0, Qt.UserRole) == "cards":
                    for child_index in range(root_item.childCount()):
                        child_item = root_item.child(child_index)
                        if child_item.data(0, Qt.UserRole) == "cards.delete_me":
                            leaf_item = child_item
                            break
            self.assertIsNotNone(leaf_item)

            window.rm_tree.setCurrentItem(leaf_item)
            self.app.processEvents()

            result = window.delete_selected_png()

            manifest = service.load_resource_manifest()
            self.assertEqual(result, "cards.delete_me")
            self.assertNotIn("cards.delete_me", manifest["resources"])
            self.assertEqual(window.rm_status_label.text(), "Deleted PNG: cards.delete_me")
            window.close()

    def test_del_png_rejects_folder_selection(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "folder_case.png"
            Image.new("RGBA", (64, 96), (0, 0, 255, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            service.add_png_to_manifest(str(png_path))
            window = GuiEditorApp(service=service)

            folder_item = None
            for index in range(window.rm_tree.topLevelItemCount()):
                root_item = window.rm_tree.topLevelItem(index)
                if root_item.data(0, Qt.UserRole) == "cards":
                    folder_item = root_item
                    break
            self.assertIsNotNone(folder_item)

            window.rm_tree.setCurrentItem(folder_item)
            self.app.processEvents()

            result = window.delete_selected_png()

            self.assertIsNone(result)
            self.assertEqual(window.rm_status_label.text(), "Select a PNG leaf entry first")
            window.close()

    def test_rm_tree_is_collapsed_by_default_and_type_column_has_gap(self):
        window = GuiEditorApp()
        self.assertGreater(window.rm_tree.topLevelItemCount(), 0)
        for index in range(window.rm_tree.topLevelItemCount()):
            self.assertFalse(window.rm_tree.topLevelItem(index).isExpanded())
        self.assertGreater(window.rm_tree.columnWidth(0), window.rm_tree.header().sectionSizeHint(0))
        window.close()

    def test_create_folder_from_dialog_persists_folder_and_selects_it(self):
        with TemporaryDirectory() as temp_dir:
            service = GuiEditorDataService(project_dir=temp_dir)
            window = GuiEditorApp(service=service)
            with mock.patch("tools.gui_editor.QInputDialog.getText", return_value=("icons", True)):
                created = window.create_folder_from_dialog()

            manifest = service.load_resource_manifest()
            self.assertEqual(created, "icons")
            self.assertIn("icons", manifest["folders"])
            self.assertEqual(window.rm_tree.currentItem().data(0, Qt.UserRole), "icons")
            window.close()

    def test_rm_preview_panel_replaces_old_action_buttons(self):
        window = GuiEditorApp()
        self.assertIsNotNone(window.rm_preview_label)
        self.assertEqual(window.rm_preview_label.text(), "No PNG selected")
        self.assertIsNotNone(window.rm_preview_hint_label)
        self.assertIsNone(getattr(window, "rm_add_button", None))
        self.assertIsNone(getattr(window, "rm_del_button", None))
        window.close()

    def test_rename_folder_from_dialog_updates_manifest_branch(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "badge.png"
            Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            service.add_png_to_manifest(str(png_path), manifest_path="ui.icons.badge.png")
            service.create_manifest_folder("ui.icons")
            window = GuiEditorApp(service=service)
            window._select_rm_node("ui.icons", expand_parents=True)

            with mock.patch("tools.gui_editor.QInputDialog.getText", return_value=("sprites", True)):
                renamed = window.rename_folder_from_dialog()

            manifest = service.load_resource_manifest()
            self.assertEqual(renamed, "ui.sprites")
            self.assertIn("ui.sprites.badge", manifest["resources"])
            self.assertEqual(window.rm_tree.currentItem().data(0, Qt.UserRole), "ui.sprites")
            window.close()

    def test_rename_resource_from_dialog_updates_manifest_entry(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "badge.png"
            Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            service.add_png_to_manifest(str(png_path), manifest_path="ui.badge.png")
            window = GuiEditorApp(service=service)
            window._select_rm_node("ui.badge", expand_parents=True)

            with mock.patch("tools.gui_editor.QInputDialog.getText", return_value=("token", True)):
                renamed = window.rename_resource_from_dialog()

            manifest = service.load_resource_manifest()
            self.assertEqual(renamed, "ui.token")
            self.assertIn("ui.token", manifest["resources"])
            self.assertEqual(window.rm_tree.currentItem().data(0, Qt.UserRole), "ui.token")
            window.close()

    def test_move_selected_rm_nodes_to_folder_moves_multi_selection(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            first_png = cards_dir / "one.png"
            second_png = cards_dir / "two.png"
            Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(first_png)
            Image.new("RGBA", (32, 32), (0, 255, 0, 255)).save(second_png)

            service = GuiEditorDataService(project_dir=temp_dir)
            service.add_png_to_manifest(str(first_png), manifest_path="cards.one.png")
            service.add_png_to_manifest(str(second_png), manifest_path="cards.two.png")
            service.create_manifest_folder("ui.tokens")
            window = GuiEditorApp(service=service)

            first_item = window._select_rm_node("cards.one")
            second_item = window._select_rm_node("cards.two")
            first_item.setSelected(True)
            second_item.setSelected(True)

            moved = window.move_selected_rm_nodes_to_folder("ui.tokens")

            manifest = service.load_resource_manifest()
            self.assertEqual(moved, "ui.tokens")
            self.assertIn("ui.tokens.one", manifest["resources"])
            self.assertIn("ui.tokens.two", manifest["resources"])
            window.close()

    def test_delete_folder_from_rm_removes_folder_branch_but_keeps_local_png(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "badge.png"
            Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            service.add_png_to_manifest(str(png_path), manifest_path="ui.icons.badge.png")
            service.create_manifest_folder("ui.icons")
            window = GuiEditorApp(service=service)
            window._select_rm_node("ui", expand_parents=True)

            removed = window.delete_folder_from_rm()

            manifest = service.load_resource_manifest()
            self.assertEqual(removed, "ui")
            self.assertEqual(manifest["folders"], [])
            self.assertEqual(manifest["resources"], {})
            self.assertTrue(png_path.exists())
            self.assertEqual(window.rm_status_label.text(), "Deleted folder: ui")
            window.close()

    def test_delete_rm_node_removes_resource_after_confirmation(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "badge.png"
            Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            service.add_png_to_manifest(str(png_path), manifest_path="ui.badge.png")
            window = GuiEditorApp(service=service)
            window._select_rm_node("ui.badge", expand_parents=True)

            with mock.patch("tools.gui_editor.QMessageBox.question", return_value=QMessageBox.Yes):
                removed = window.delete_rm_node()

            manifest = service.load_resource_manifest()
            self.assertEqual(removed, "ui.badge")
            self.assertEqual(manifest["resources"], {})
            self.assertTrue(png_path.exists())
            self.assertEqual(window.rm_status_label.text(), "Deleted PNG: ui.badge")
            window.close()

    def test_delete_rm_node_cancels_without_changes_when_confirmation_declined(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "badge.png"
            Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            service.add_png_to_manifest(str(png_path), manifest_path="ui.badge.png")
            window = GuiEditorApp(service=service)
            window._select_rm_node("ui.badge", expand_parents=True)

            with mock.patch("tools.gui_editor.QMessageBox.question", return_value=QMessageBox.No):
                removed = window.delete_rm_node()

            manifest = service.load_resource_manifest()
            self.assertIsNone(removed)
            self.assertIn("ui.badge", manifest["resources"])
            self.assertEqual(window.rm_status_label.text(), "Delete cancelled")
            window.close()

    def test_rm_preview_updates_for_selected_png(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "preview.png"
            Image.new("RGBA", (32, 48), (255, 0, 0, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            service.add_png_to_manifest(str(png_path))
            window = GuiEditorApp(service=service)

            leaf_item = window._select_rm_node("cards.preview", expand_parents=True)
            window.rm_tree.setCurrentItem(leaf_item)
            self.app.processEvents()

            self.assertEqual(window.rm_preview_label.text(), "")
            self.assertFalse(window.rm_preview_label.pixmap().isNull())
            self.assertEqual(window.rm_preview_hint_label.text(), "cards/preview.png")
            window.close()

    def test_rm_preview_uses_real_asset_path_for_logical_rm_folder(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            cards_dir = assets_dir / "cards"
            cards_dir.mkdir(parents=True)
            png_path = cards_dir / "shield.png"
            Image.new("RGBA", (32, 48), (255, 0, 0, 255)).save(png_path)

            service = GuiEditorDataService(project_dir=temp_dir)
            service.add_png_to_manifest(str(png_path), manifest_path="test/shield.png")
            window = GuiEditorApp(service=service)

            leaf_item = window._select_rm_node("test.shield", expand_parents=True)
            window.rm_tree.setCurrentItem(leaf_item)
            self.app.processEvents()

            self.assertEqual(window.rm_preview_label.text(), "")
            self.assertFalse(window.rm_preview_label.pixmap().isNull())
            self.assertEqual(window.rm_preview_hint_label.text(), "cards/shield.png")
            window.close()


if __name__ == "__main__":
    unittest.main()
