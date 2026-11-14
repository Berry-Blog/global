import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock


PACKAGE = Path(__file__).resolve().parents[1] / "global-home-nodes"
sys.path.insert(0, str(PACKAGE))

import deploy


class GlobalHomeMenuTests(unittest.TestCase):
    def run_menu(self, answers):
        output = io.StringIO()
        with mock.patch("builtins.input", side_effect=answers), contextlib.redirect_stdout(output):
            deploy.relay_menu()
        return output.getvalue()

    def test_menu_provider_sync_reads_current_proxy_menu(self):
        with mock.patch.object(deploy, "deploy") as deploy_action:
            output = self.run_menu(["8", "0"])

        self.assertIn("供应商 proxy", output)
        args = deploy_action.call_args.args[0]
        self.assertEqual(args.action, "refresh")
        self.assertIsNone(args.import_json)

    def test_menu_json_refresh_uses_entered_authorized_file(self):
        with mock.patch.object(deploy, "deploy") as deploy_action:
            self.run_menu(["9", "/root/authorized-exits.json", "0"])

        args = deploy_action.call_args.args[0]
        self.assertEqual(args.action, "refresh")
        self.assertEqual(args.import_json, "/root/authorized-exits.json")

    def test_menu_blank_json_path_cancels(self):
        with mock.patch.object(deploy, "deploy") as deploy_action:
            output = self.run_menu(["9", "", "0"])

        deploy_action.assert_not_called()
        self.assertIn("已取消", output)

    def test_menu_routes_status_and_first_deploy(self):
        with mock.patch.object(deploy, "relay_status") as status_action:
            self.run_menu(["6", "0"])
        status_action.assert_called_once_with()

        with mock.patch.object(deploy, "deploy") as deploy_action:
            self.run_menu(["7", "0"])
        self.assertEqual(deploy_action.call_args.args[0].action, "deploy")

    def test_menu_routes_check_and_install_update_separately(self):
        with mock.patch.object(deploy, "update_manager") as update_action:
            self.run_menu(["10", "0"])
            self.run_menu(["11", "0"])

        self.assertEqual(update_action.call_args_list[0].kwargs, {"check_only": True})
        self.assertEqual(update_action.call_args_list[1].kwargs, {"check_only": False})

    def test_menu_uninstall_uses_existing_handler(self):
        with mock.patch.object(deploy, "uninstall") as uninstall_action:
            self.run_menu(["12", "0"])
        uninstall_action.assert_called_once_with()

    def test_menu_invalid_choice_does_not_dispatch(self):
        with mock.patch.object(deploy, "deploy") as deploy_action, mock.patch.object(
            deploy, "uninstall"
        ) as uninstall_action:
            output = self.run_menu(["99", "0"])

        deploy_action.assert_not_called()
        uninstall_action.assert_not_called()
        self.assertIn("无效选项", output)

    def test_menu_returns_without_operation(self):
        with mock.patch.object(deploy, "deploy") as deploy_action:
            self.run_menu(["0"])
        deploy_action.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)

