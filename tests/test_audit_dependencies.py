import unittest
from audit_dependencies import inventory, UPSTREAM_REVISION


class InventoryTests(unittest.TestCase):
    def test_pinned_repository_license_is_explicit_not_assumed_from_name(self):
        package = {"name": "a2tools-dps-meter", "version": "2.0.48", "license": None,
                   "source": "git+https://github.com/taengu/A2Tools-DPS-Meter.git?rev="
                             + UPSTREAM_REVISION + "#" + UPSTREAM_REVISION}
        record, = inventory({"packages": [package]})
        self.assertEqual(record["license_evidence"], "pinned_upstream_repository_license")
        package["source"] = "git+https://example.com/other.git#" + UPSTREAM_REVISION
        record, = inventory({"packages": [package]})
        self.assertEqual(record["license_evidence"], "missing")
        package["source"] = "git+https://github.com/taengu/A2Tools-DPS-Meter.git-other#" + UPSTREAM_REVISION
        record, = inventory({"packages": [package]})
        self.assertEqual(record["license_evidence"], "missing")

    def test_output_does_not_expose_local_manifest_paths(self):
        record, = inventory({"packages": [{"name": "example", "version": "1", "license": "MIT",
            "manifest_path": "C:/private/work/manifest.toml", "source": None}]})
        self.assertNotIn("manifest_path", record)
        self.assertEqual(record["source_kind"], "local")
        self.assertEqual(record["license_expression"], "MIT")
