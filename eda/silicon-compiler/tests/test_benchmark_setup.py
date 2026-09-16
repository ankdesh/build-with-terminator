import unittest

from scripts.run_benchmarks import (
    CONFIG,
    benchmark_names,
    benchmark_rtl,
    compare_results,
    load_config,
    preflight_dc,
)


class BenchmarkSetupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(CONFIG)

    def test_arithmetic_benchmarks_are_configured(self):
        names = benchmark_names(self.config, "all")
        self.assertIn("bar", names)
        self.assertEqual(10, len(names))

    def test_barrel_shifter_rtl_is_subproject_file(self):
        rtl = benchmark_rtl(self.config, "bar")
        self.assertTrue(rtl.exists())
        self.assertIn("third_party/lsils-benchmarks", str(rtl))

    def test_dc_preflight_generates_barrel_shifter_tcl(self):
        result = preflight_dc(self.config, "bar", "freepdk45")
        self.assertEqual("preflight_only", result["status"])
        self.assertTrue(result["checks"]["rtl_files_exist"])
        self.assertTrue(result["checks"]["liberty_files_exist"])
        self.assertTrue(result["checks"]["tcl_generated"])
        with open(result["artifacts"]["dc_tcl"], encoding="utf-8") as f:
            tcl = f.read()
        self.assertIn("create_clock -name virtual_clock", tcl)
        self.assertIn("compile_ultra", tcl)

    def test_comparison_generation(self):
        rows = compare_results(self.config)
        self.assertTrue(any(row["benchmark"] == "bar" for row in rows))


if __name__ == "__main__":
    unittest.main()
