#!/usr/bin/env python3
"""Audit a generic scan insertion against its immutable input and manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from qd_scan_insert import insert


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def strict_loads(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def audit(original_raw, scan_raw, manifest):
    if (not isinstance(manifest, dict) or
            type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1):
        raise ValueError('unsupported manifest schema')
    for name, raw in (('input', original_raw), ('output', scan_raw)):
        if manifest.get(name + '_sha256') != hashlib.sha256(raw).hexdigest():
            raise ValueError(name + ' hash mismatch')
    original = strict_loads(original_raw)
    scan = strict_loads(scan_raw)
    expected, expected_manifest = insert(original, manifest['top'], manifest['clock'], manifest['reset'])
    if canonical(scan) != canonical(expected):
        raise ValueError('scan netlist differs from the declared generic insertion')
    expected_manifest.update(input_sha256=manifest['input_sha256'],
                             output_sha256=manifest['output_sha256'])
    if canonical(manifest) != canonical(expected_manifest):
        raise ValueError('manifest differs from the audited chain and controls')
    return {'status':'unknown', 'top':manifest['top'],
            'state_cells':manifest['state_cells'], 'scan_cells':len(manifest['chain']),
            'chain':[row['cell'] for row in manifest['chain']],
            'fault_coverage':None,
            'unverified':['cell behavior, test-mode activation and clock/reset operation unverified']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('original', type=Path)
    ap.add_argument('scan', type=Path)
    ap.add_argument('manifest', type=Path)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()
    try:
        result = audit(args.original.read_bytes(), args.scan.read_bytes(),
                       strict_loads(args.manifest.read_bytes()))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'qd-scan-audit: {error}', file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"UNKNOWN: {result['top']} generic scan chain {result['scan_cells']}/{result['state_cells']} structurally consistent; fault_coverage=UNKNOWN")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
