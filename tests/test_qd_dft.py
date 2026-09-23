import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "tests/policy.json").read_text())


def netlist(chain=True, ports=True, unknown=False):
    p = {"test_mode":{"direction":"input","bits":[1]}, "scan_in":{"direction":"input","bits":[2]}, "scan_out":{"direction":"output","bits":[5]}}
    cells = {
        "u0":{"type":"SDFF","connections":{"SI":[2],"SO":[3],"SE":[1],"CK":[6],"RN":[7]}},
        "u1":{"type":"SDFF","connections":{"SI":[3 if chain else 8],"SO":[5],"SE":[1],"CK":[6],"RN":[7]}},
    }
    if not ports:
        p.pop("scan_out")
    if unknown:
        cells["mystery"] = {"type":"$unknown","connections":{}}
    return {"modules":{"top":{"ports":p,"cells":cells}}}


class CheckerTests(unittest.TestCase):
    def test_complete_chain(self):
        result = __import__("qd_dft").check(netlist(), "top", POLICY)
        self.assertEqual((result["status"], result["scan_connected"], result["fault_coverage"]), ("ready", 2, None))

    def test_broken_link_fails(self):
        result = __import__("qd_dft").check(netlist(chain=False), "top", POLICY)
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["scan_ratio"])
        self.assertTrue(any("unreachable scan cells" in d for d in result["diagnostics"]))

    def test_disconnected_cycle_is_reported(self):
        data = netlist()
        cells = data["modules"]["top"]["cells"]
        for name, si, so in (("x", 9, 10), ("y", 10, 9)):
            cells[name] = {"type":"SDFF","connections":{"SI":[si],"SO":[so],"SE":[1],"CK":[6],"RN":[7]}}
        result = __import__("qd_dft").check(data, "top", POLICY)
        self.assertTrue(any("cycle" in d for d in result["diagnostics"]))

    def test_missing_endpoint_fails(self):
        result = __import__("qd_dft").check(netlist(ports=False), "top", POLICY)
        self.assertEqual(result["status"], "error")
        self.assertTrue(any("missing declared scan-out" in d for d in result["diagnostics"]))

    def test_unrecognized_flop_is_unknown(self):
        data = netlist(unknown=True)
        data["modules"]["top"]["cells"]["flop"] = {"type":"DFF_X1","connections":{}}
        result = __import__("qd_dft").check(data, "top", POLICY)
        self.assertEqual(result["status"], "unknown")
        self.assertTrue(any("flop" in d for d in result["diagnostics"]))

    def test_recognized_unscanned_state_fails(self):
        data = netlist()
        data["modules"]["top"]["cells"]["plain"] = {"type": "DFF", "connections": {}}
        policy = dict(POLICY)
        policy["state_cells"] = dict(POLICY["state_cells"], DFF={"clock": "CK"})
        result = __import__("qd_dft").check(data, "top", policy)
        self.assertEqual(result["status"], "error")
        self.assertTrue(any("unscanned state cells: plain" in d for d in result["diagnostics"]))

    def test_empty_netlist_boundary(self):
        data = {"modules":{"top":{"ports":{"scan_in":{"direction":"input","bits":[2]},"scan_out":{"direction":"output","bits":[5]},"test_mode":{"direction":"input","bits":[1]}},"cells":{}}}}
        result = __import__("qd_dft").check(data, "top", POLICY)
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["scan_ratio"])

    def test_yosys_fixture(self):
        data = json.loads((ROOT / "tests/fixtures/tiny_chain.json").read_text())
        result = __import__("qd_dft").check(data, "top", POLICY)
        self.assertEqual((result["status"], result["state_cells"], result["scan_connected"]), ("ready", 2, 2))

    def test_cli(self):
        with tempfile.TemporaryDirectory() as td:
            n, p = pathlib.Path(td)/"n.json", pathlib.Path(td)/"p.json"
            n.write_text(json.dumps(netlist(chain=False)))
            p.write_text(json.dumps(POLICY))
            run = subprocess.run([sys.executable, str(ROOT/"qd_dft.py"), "check", str(n), "--top", "top", "--policy", str(p), "--json"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 1)
            self.assertEqual(json.loads(run.stdout)["status"], "error")


if __name__ == "__main__":
    unittest.main()
