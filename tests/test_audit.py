import copy
import hashlib
import json
import unittest

from qd_scan_audit import audit, strict_loads
from qd_scan_insert import insert
from test_insertion import bank


def bundle(original):
    raw = json.dumps(original).encode()
    scan, manifest = insert(original, 'top', 'clk', 'rst')
    scan_raw = json.dumps(scan).encode()
    manifest.update(input_sha256=hashlib.sha256(raw).hexdigest(),
                    output_sha256=hashlib.sha256(scan_raw).hexdigest())
    return raw, scan_raw, manifest


class AuditTests(unittest.TestCase):
    def test_generated_two_flop_chain_is_unknown_not_fault_coverage(self):
        raw, scan, manifest = bundle(bank())
        result = audit(raw, scan, manifest)
        self.assertEqual(result['chain'], ['a', 'b'])
        self.assertEqual(result['status'], 'unknown')
        self.assertIsNone(result['fault_coverage'])

    def test_mutated_links_and_controls_fail_even_with_updated_output_hash(self):
        for pin in ('A', 'B', 'S', 'Y'):
            raw, scan_raw, manifest = bundle(bank())
            scan = json.loads(scan_raw)
            scan['modules']['top']['cells']['qd_scan_mux_1']['connections'][pin] = [999]
            changed = json.dumps(scan).encode()
            manifest['output_sha256'] = hashlib.sha256(changed).hexdigest()
            with self.subTest(pin=pin), self.assertRaisesRegex(ValueError, 'scan netlist differs'):
                audit(raw, changed, manifest)

    def test_manifest_and_input_provenance_mutations_fail(self):
        raw, scan, manifest = bundle(bank())
        changed = copy.deepcopy(manifest)
        changed['chain'][0]['scan_in'] = 999
        with self.assertRaisesRegex(ValueError, 'manifest differs'):
            audit(raw, scan, changed)
        with self.assertRaisesRegex(ValueError, 'input hash mismatch'):
            audit(raw + b' ', scan, manifest)

    def test_json_numeric_and_boolean_substitutions_fail(self):
        raw, scan_raw, manifest = bundle(bank())
        for changed_bit in (6.0,):
            scan = json.loads(scan_raw)
            scan['modules']['top']['cells']['a']['connections']['Q'] = [changed_bit]
            changed = json.dumps(scan).encode()
            altered = copy.deepcopy(manifest)
            altered['output_sha256'] = hashlib.sha256(changed).hexdigest()
            with self.subTest(bit=changed_bit), self.assertRaisesRegex(ValueError, 'scan netlist differs'):
                audit(raw, changed, altered)
        one_bit = bank()
        one_bit['modules']['top']['cells']['a']['connections']['Q'] = [1]
        one_bit['modules']['top']['ports']['q']['bits'][0] = 1
        raw, scan_raw, manifest = bundle(one_bit)
        scan = json.loads(scan_raw)
        scan['modules']['top']['cells']['a']['connections']['Q'] = [True]
        changed = json.dumps(scan).encode()
        manifest['output_sha256'] = hashlib.sha256(changed).hexdigest()
        with self.assertRaisesRegex(ValueError, 'scan netlist differs'):
            audit(raw, changed, manifest)
        raw, scan_raw, manifest = bundle(bank())
        for key, value in (('state_cells', 2.0), ('reset_active_level', False), ('schema_version', True)):
            altered = copy.deepcopy(manifest)
            altered[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit(raw, scan_raw, altered)

    def test_duplicate_json_keys_fail_closed(self):
        raw, scan_raw, manifest = bundle(bank())
        duplicate_scan = scan_raw.decode().replace('"modules":', '"modules": {}, "modules":', 1).encode()
        changed = copy.deepcopy(manifest)
        changed['output_sha256'] = hashlib.sha256(duplicate_scan).hexdigest()
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            audit(raw, duplicate_scan, changed)
        duplicate_original = raw.decode().replace('"modules":', '"modules": {}, "modules":', 1).encode()
        changed = copy.deepcopy(manifest)
        changed['input_sha256'] = hashlib.sha256(duplicate_original).hexdigest()
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            audit(duplicate_original, scan_raw, changed)
        duplicate_manifest = json.dumps(manifest).replace('"top":', '"top": "wrong", "top":', 1)
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            strict_loads(duplicate_manifest)

    def test_one_flop_boundary_and_extra_state_rejected(self):
        single = bank()
        del single['modules']['top']['cells']['b']
        single['modules']['top']['ports']['q']['bits'] = [6]
        raw, scan_raw, manifest = bundle(single)
        self.assertEqual(audit(raw, scan_raw, manifest)['chain'], ['a'])
        scan = json.loads(scan_raw)
        scan['modules']['top']['cells']['extra'] = copy.deepcopy(scan['modules']['top']['cells']['a'])
        changed = json.dumps(scan).encode()
        manifest['output_sha256'] = hashlib.sha256(changed).hexdigest()
        with self.assertRaisesRegex(ValueError, 'scan netlist differs'):
            audit(raw, changed, manifest)
        raw, scan_raw, manifest = bundle(single)
        del manifest['chain'][0]
        with self.assertRaisesRegex(ValueError, 'manifest differs'):
            audit(raw, scan_raw, manifest)
