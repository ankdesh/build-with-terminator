import unittest

from scripts.setup_dc import CONFIG, _enabled_targets, load_config, preflight_target


class DCSetupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(CONFIG)

    def test_all_targets_are_configured(self):
        self.assertEqual(["freepdk45", "sky130", "asap7"], _enabled_targets(self.config, "all"))

    def test_preflight_generates_tcl_without_dc(self):
        result = preflight_target(self.config, "freepdk45")
        self.assertTrue(result["checks"]["rtl_files_exist"])
        self.assertTrue(result["checks"]["liberty_files_exist"])
        self.assertTrue(result["checks"]["tcl_generated"])
        self.assertIn(result["status"], {"preflight_only", "ready_to_run"})
        with open(result["artifacts"]["dc_tcl"], encoding="utf-8") as f:
            tcl = f.read()
        self.assertIn("compile_ultra", tcl)
        self.assertIn("report_qor", tcl)
        self.assertIn("write -format verilog", tcl)


if __name__ == "__main__":
    unittest.main()
