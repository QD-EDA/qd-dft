import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from qd_dft import check, InputError
from test_qd_dft import POLICY, ROOT, netlist


class StrictTests(unittest.TestCase):
    def test_complete_structure_does_not_prove_test_behavior(self):
        result = check(netlist(), 'top', POLICY, strict=True)
        self.assertEqual(result['legacy_status'], 'ready')
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['scan_chain'], ['u0', 'u1'])
        self.assertEqual(len(result['cell_inventory']), 2)
        self.assertEqual(result['scan_ratio'], 1)
        self.assertIsNone(result['fault_coverage'])
        self.assertIn('cell behavior, test-mode activation and clock/reset operation unverified',
                      result['unverified'])

    def test_unknown_and_scan_only_cells_remain_in_inventory(self):
        policy = copy.deepcopy(POLICY)
        policy['state_cells'] = {}
        result = check(netlist(unknown=True), 'top', policy, strict=True)
        self.assertEqual(len(result['cell_inventory']), 3)
        self.assertEqual(result['status'], 'unknown')
        self.assertIn('scan cells missing from declared state inventory: u0, u1', result['unverified'])
        self.assertIsNone(result['scan_ratio'])

    def test_partial_chain_and_empty_design_cannot_pass(self):
        result = check(netlist(chain=False), 'top', POLICY, strict=True)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['scan_chain'], ['u0'])
        data = netlist(); data['modules']['top']['cells'] = {}
        result = check(data, 'top', POLICY, strict=True)
        self.assertEqual((result['status'], result['scan_chain'], result['cell_inventory']),
                         ('unknown', [], []))

    def test_malformed_policy_and_connections_fail_as_input(self):
        for field in ('scan_in', 'scan_out'):
            policy = copy.deepcopy(POLICY); del policy['scan_cells']['SDFF'][field]
            with self.assertRaises(InputError): check(netlist(), 'top', policy, strict=True)
        for bits in (None, {}, [True], [None], ['bad']):
            data = netlist(); data['modules']['top']['cells']['u0']['connections']['SI'] = bits
            with self.assertRaises(InputError): check(data, 'top', POLICY, strict=True)
        for data in (None, {'modules': []}, {'modules': {'top': {'cells': []}}}):
            with self.assertRaises(InputError): check(data, 'top', POLICY, strict=True)

    def test_constants_and_ambiguous_structure_never_pass(self):
        for bit in ('0', '1', 'x', 'z'):
            data = netlist(); data['modules']['top']['cells']['u0']['connections']['SI'] = [bit]
            self.assertEqual(check(data, 'top', POLICY, strict=True)['status'], 'error')
        data = netlist()
        data['modules']['top']['cells']['u2'] = copy.deepcopy(data['modules']['top']['cells']['u1'])
        result = check(data, 'top', POLICY, strict=True)
        self.assertEqual(result['status'], 'error')
        self.assertIsNone(result['scan_ratio'])
        data['modules']['top']['cells'] = dict(reversed(list(data['modules']['top']['cells'].items())))
        self.assertEqual(result, check(data, 'top', POLICY, strict=True))

    def test_deterministic_inventory_and_port_evidence(self):
        data = netlist(); data['modules']['top']['cells']['u0']['attributes'] = {'src': 'design.sv:9'}
        result = check(data, 'top', POLICY, strict=True)
        data['modules']['top']['cells'] = dict(reversed(list(data['modules']['top']['cells'].items())))
        self.assertEqual(result, check(data, 'top', POLICY, strict=True))
        self.assertEqual(result['cell_inventory'][0]['source'], 'design.sv:9')
        self.assertEqual(result['cell_inventory'][0]['connections']['CK'], [6])

    def test_cli_strict_unknown_is_nonzero_but_legacy_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'n.json').write_text(json.dumps(netlist()))
            (root/'p.json').write_text(json.dumps(POLICY))
            args = [sys.executable, str(ROOT/'qd_dft.py'), 'check', str(root/'n.json'),
                    '--top', 'top', '--policy', str(root/'p.json'), '--json']
            for flags, expected in [([], 0), (['--strict'], 3)]:
                run = subprocess.run(args+flags, capture_output=True, text=True)
                self.assertEqual(run.returncode, expected, run.stderr)
                self.assertEqual(json.loads(run.stdout)['status'], 'unknown' if flags else 'ready')
