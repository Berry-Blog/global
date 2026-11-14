import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "global-home-nodes"))
from relay_export import build_relay_export, read_runtime_export, write_relay_export


U1 = "11111111-1111-4111-8111-111111111111"
U2 = "22222222-2222-4222-8222-222222222222"
U3 = "33333333-3333-4333-8333-333333333333"
PUBLIC_KEY = "A" * 43


def sample_config():
    # Deliberately scramble client, route and outbound order: mapping must use
    # UUID -> email -> route -> outbound tag, never array positions.
    return {
        "inbounds": [{"protocol": "vless", "streamSettings": {"network": "tcp", "security": "reality", "realitySettings": {
            "serverNames": ["www.apple.com"], "shortIds": ["0123456789abcdef"], "privateKey": "never-export-this",
        }}, "settings": {"clients": [
            {"id": U2, "email": "pavlov@home", "flow": "xtls-rprx-vision"},
            {"id": U1, "email": "biglobe@home", "flow": "xtls-rprx-vision"},
            {"id": U3, "email": "starhub@home", "flow": "xtls-rprx-vision"},
        ]}}],
        "routing": {"rules": [
            {"type": "field", "user": ["starhub@home"], "outboundTag": "star-out"},
            {"type": "field", "user": ["biglobe@home"], "outboundTag": "big-out"},
            {"type": "field", "user": ["pavlov@home"], "outboundTag": "pav-out"},
        ]},
        "outbounds": [
            {"protocol": "socks", "tag": "pav-out", "settings": {"servers": [{"address": "10.88.0.1", "port": 5005, "users": [{"user": "private-user", "pass": "private-pass"}]}]}},
            {"protocol": "socks", "tag": "star-out", "settings": {"servers": [{"address": "10.88.0.1", "port": 5009}]}},
            {"protocol": "socks", "tag": "big-out", "settings": {"servers": [{"address": "10.88.0.1", "port": 5002}]}},
        ],
    }


def sample_state():
    return {"settings": {
        "public_host": "209.33.166.81", "external_port": 40045,
        "internal_port": 80, "sni": "www.apple.com", "public_key": PUBLIC_KEY,
        "short_id": "0123456789abcdef", "private_key": "never-export-this",
    }, "nodes": [
        {"key": "biglobe", "name": "日本 BIGLOBE", "uuid": U1, "server": "10.88.0.1", "port": 5002, "username": "private-user", "password": "private-pass"},
        {"key": "pavlov", "name": "美国 Pavlov", "uuid": U2, "server": "10.88.0.1", "port": 5005, "username": "private-user", "password": "private-pass"},
        {"key": "starhub", "name": "新加坡 StarHub", "uuid": U3, "server": "10.88.0.1", "port": 5009, "username": "private-user", "password": "private-pass"},
    ]}


def sample_audit():
    return [{"key": "biglobe", "ip": "61.193.51.9", "ok": True},
            {"key": "pavlov", "ip": "96.63.208.157", "ok": True},
            {"key": "starhub", "ip": "202.156.27.233", "ok": True}]


class RelayExportTests(unittest.TestCase):
    def test_global_export_matches_the_shared_dogma_fixture(self):
        fixture = Path(__file__).resolve().parent / "fixtures" / "global-home-dogma-relay-v1.json"
        expected = json.loads(fixture.read_text(encoding="utf-8"))
        actual = build_relay_export(sample_config(), sample_state(), sample_audit(), generated_at=expected["generated_at"])
        self.assertEqual(actual, expected)

    def test_maps_by_identity_and_exports_external_port_and_public_data(self):
        doc = build_relay_export(sample_config(), sample_state(), sample_audit(), generated_at="2026-11-14T00:00:00Z")
        self.assertEqual(doc["schema_version"], 1)
        self.assertEqual(doc["kind"], "global-home-dogma-relay")
        self.assertEqual(doc["profile"]["public_port"], 40045)
        self.assertNotIn("internal_port", doc["profile"])
        actual = {entry["id"]: entry for entry in doc["exits"]}
        self.assertEqual(len(actual), 3)
        self.assertEqual(actual["global-biglobe"]["uuid"], U1)
        self.assertEqual(actual["global-pavlov"]["outbound_tag"], "pav-out")
        self.assertEqual(actual["global-starhub"]["socks5"]["port"], 5009)
        self.assertEqual(actual["global-biglobe"]["expected_exit_ip"], "61.193.51.9")

    def test_missing_or_ambiguous_route_is_an_anomaly_and_not_an_exit(self):
        config = sample_config()
        config["routing"]["rules"] = [r for r in config["routing"]["rules"] if "pavlov@home" not in r["user"]]
        doc = build_relay_export(config, sample_state(), sample_audit(), generated_at="2026-11-14T00:00:00Z")
        self.assertNotIn("global-pavlov", {entry["id"] for entry in doc["exits"]})
        self.assertEqual(doc["anomalies"][0]["id"], "global-pavlov")
        self.assertFalse(doc["anomalies"][0]["route_valid"])

        config = sample_config()
        config["routing"]["rules"].append({"type": "field", "user": ["pavlov@home"], "outboundTag": "big-out"})
        doc = build_relay_export(config, sample_state(), sample_audit(), generated_at="2026-11-14T00:00:00Z")
        self.assertNotIn("global-pavlov", {entry["id"] for entry in doc["exits"]})
        self.assertTrue(any(a["id"] == "global-pavlov" for a in doc["anomalies"]))

    def test_same_uuid_must_belong_to_the_matching_email_metadata_row(self):
        config = sample_config()
        clients = config["inbounds"][0]["settings"]["clients"]
        clients[0]["id"], clients[1]["id"] = clients[1]["id"], clients[0]["id"]

        doc = build_relay_export(config, sample_state(), sample_audit(), generated_at="2026-11-14T00:00:00Z")

        exits = {entry["id"] for entry in doc["exits"]}
        self.assertNotIn("global-pavlov", exits)
        self.assertNotIn("global-biglobe", exits)
        self.assertEqual(sum(row["id"] == "unresolved-global-exit" for row in doc["anomalies"]), 2)

    def test_duplicate_xray_email_is_not_exported_as_a_unique_line(self):
        config = sample_config()
        clients = config["inbounds"][0]["settings"]["clients"]
        duplicate = dict(clients[0], id="44444444-4444-4444-8444-444444444444")
        clients.insert(0, duplicate)

        doc = build_relay_export(config, sample_state(), sample_audit(), generated_at="2026-11-14T00:00:00Z")

        self.assertNotIn("global-pavlov", {entry["id"] for entry in doc["exits"]})
        self.assertTrue(any(row["id"] == "unresolved-global-exit" for row in doc["anomalies"]))

    def test_state_mismatch_and_non_socks_outbound_are_rejected(self):
        config = sample_config()
        config["outbounds"][0]["protocol"] = "freedom"
        doc = build_relay_export(config, sample_state(), sample_audit(), generated_at="2026-11-14T00:00:00Z")
        self.assertNotIn("global-pavlov", {entry["id"] for entry in doc["exits"]})
        self.assertTrue(any(a["id"] == "global-pavlov" for a in doc["anomalies"]))

        config = sample_config()
        config["outbounds"][0]["settings"]["servers"][0]["port"] = 5009
        doc = build_relay_export(config, sample_state(), sample_audit(), generated_at="2026-11-14T00:00:00Z")
        self.assertNotIn("global-pavlov", {entry["id"] for entry in doc["exits"]})

    def test_runtime_reality_parameters_must_match_global_metadata(self):
        config = sample_config()
        config["inbounds"][0]["streamSettings"]["realitySettings"]["shortIds"] = ["ffffffffffffffff"]
        with self.assertRaises(ValueError):
            build_relay_export(config, sample_state(), sample_audit(), generated_at="2026-11-14T00:00:00Z")

        config = sample_config()
        config["inbounds"][0]["settings"]["clients"][0]["id"] = U1
        doc = build_relay_export(config, sample_state(), sample_audit(), generated_at="2026-11-14T00:00:00Z")
        self.assertTrue(doc["anomalies"])

    def test_export_never_contains_private_keys_or_socks_credentials(self):
        doc = build_relay_export(sample_config(), sample_state(), sample_audit(), generated_at="2026-11-14T00:00:00Z")
        encoded = json.dumps(doc)
        for secret in ("never-export-this", "private-user", "private-pass"):
            self.assertNotIn(secret, encoded)
        self.assertIn("public_key", doc["profile"])
        self.assertNotIn("private_key", doc["profile"])
        self.assertNotIn("dogma_client_uuid", encoded)

    def test_writer_uses_private_permissions_and_refuses_inactive_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "exports"
            path = write_relay_export(sample_config(), sample_state(), sample_audit(), root=root,
                                       generated_at="2026-11-14T00:00:00Z", service_active=True)
            self.assertEqual(path.name, "dogma-relay.json")
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            with self.assertRaisesRegex(RuntimeError, "未运行"):
                write_relay_export(sample_config(), sample_state(), sample_audit(), root=root,
                                   generated_at="2026-11-14T00:00:00Z", service_active=False)

    def test_runtime_generation_reads_audit_array_and_builds_export(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            generation = root / "generations" / "generation-1"
            generation.mkdir(parents=True)
            (generation / "config.json").write_text(json.dumps(sample_config()), encoding="utf-8")
            (generation / "state.private.json").write_text(json.dumps(sample_state()), encoding="utf-8")
            (generation / "upstream-audit.json").write_text(json.dumps(sample_audit()), encoding="utf-8")
            (root / "current").symlink_to(generation, target_is_directory=True)

            document = read_runtime_export(root)

            self.assertEqual(len(document["exits"]), 3)
            self.assertEqual({row["id"] for row in document["exits"]}, {"global-biglobe", "global-pavlov", "global-starhub"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
