import unittest

from scripts.run_synthesis import TARGETS, build_project


class SynthesisSetupTest(unittest.TestCase):
    def test_targets_are_available(self):
        self.assertEqual({"freepdk45", "sky130", "asap7"}, set(TARGETS))

    def test_flow_contains_only_yosys_synthesis(self):
        project = build_project("freepdk45", 10.0, jobname="unit")
        flow = project.get("option", "flow")
        self.assertEqual("yosys_logic_synthesis", flow)
        self.assertEqual([("synthesis", "0")], list(project.get_flow(flow).get_nodes()))


if __name__ == "__main__":
    unittest.main()

