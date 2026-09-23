#!/usr/bin/env python3
"""Conservative structural scan-readiness checks for Yosys JSON."""
import argparse
import json
import sys


class InputError(ValueError):
    pass


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_strict(netlist, top, policy):
    """Validate the consumed JSON subset; declarations are not cell models."""
    def mapping(value, label):
        if not isinstance(value, dict):
            raise InputError(f"{label}: expected object")
        return value

    def bits(value, label):
        if not isinstance(value, list) or any(
            not (type(bit) is int and bit >= 0 or
                 isinstance(bit, str) and bit in ('0', '1', 'x', 'z')) for bit in value
        ):
            raise InputError(f"{label}: expected Yosys bit array")

    mapping(policy, 'policy')
    for group in ('state_cells', 'scan_cells'):
        for name, spec in mapping(policy.get(group, {}), group).items():
            mapping(spec, f'{group}.{name}')
            required = ('scan_in', 'scan_out') if group == 'scan_cells' else ()
            for key in set(required) | (set(spec) & {'clock', 'reset', 'scan_enable'}):
                if not isinstance(spec.get(key), str) or not spec[key]:
                    raise InputError(f'{group}.{name}.{key}: expected pin name')
    for key in ('test_mode', 'scan_in', 'scan_out'):
        if key in policy and (not isinstance(policy[key], str) or not policy[key]):
            raise InputError(f'{key}: expected port name')
    modules = mapping(mapping(netlist, 'netlist').get('modules', {}), 'modules')
    if top not in modules:
        raise InputError(f"top module {top!r} not found")
    mod = mapping(modules[top], top)
    for name, port in mapping(mod.get('ports', {}), 'ports').items():
        mapping(port, name)
        bits(port.get('bits', []), name)
        if port.get('direction') not in ('input', 'output', 'inout'):
            raise InputError(f'{name}: invalid port direction')
    for name, cell in mapping(mod.get('cells', {}), 'cells').items():
        mapping(cell, name)
        if not isinstance(cell.get('type'), str) or not cell['type']:
            raise InputError(f'{name}: expected cell type')
        mapping(cell.get('attributes', {}), f'{name}.attributes')
        for pin, value in mapping(cell.get('connections', {}), f'{name}.connections').items():
            bits(value, f'{name}.{pin}')


def check(netlist, top, policy, strict=False):
    if strict:
        validate_strict(netlist, top, policy)
    modules = netlist.get("modules", {})
    if top not in modules:
        raise InputError(f"top module {top!r} not found")
    mod = modules[top]
    ports, cells = mod.get("ports", {}), mod.get("cells", {})
    errors, notes = [], []
    state_specs, scan_specs = policy.get("state_cells", {}), policy.get("scan_cells", {})
    if strict:
        cells = dict(sorted(cells.items()))
    state = [(n, c) for n, c in cells.items() if c.get("type") in state_specs]
    scan = [(n, c, scan_specs[c.get("type")]) for n, c in cells.items() if c.get("type") in scan_specs]
    recognized = set(state_specs) | set(scan_specs)

    def endpoint(name, direction):
        p = ports.get(name)
        bits = p.get("bits", []) if p and p.get("direction") == direction else []
        return bits[0] if len(bits) == 1 and isinstance(bits[0], int) else None

    unknown = sorted(n for n, c in cells.items() if c.get("type") not in recognized or
                     c.get("attributes", {}).get("blackbox"))
    if unknown:
        notes.append("UNKNOWN cells: " + ", ".join(unknown))
    controls = sorted({pin for spec in list(state_specs.values()) + list(scan_specs.values()) if isinstance(spec, dict) for pin in (spec.get("clock"), spec.get("reset")) if pin})
    if controls:
        notes.append("UNKNOWN clock/reset behavior on declared pins: " + ", ".join(controls))
    mode = policy.get("test_mode")
    mode_bit = endpoint(mode, "input") if mode else None
    if mode:
        if mode_bit is None:
            errors.append(f"missing declared test-mode input {mode}")
        else:
            notes.append(f"test mode input {mode} present (activation not proven)")

    sin_name, sout_name = policy.get("scan_in", ""), policy.get("scan_out", "")
    sin, sout = endpoint(sin_name, "input"), endpoint(sout_name, "output")
    if sin is None:
        errors.append(f"missing declared scan-in input {sin_name}")
    if sout is None:
        errors.append(f"missing declared scan-out output {sout_name}")

    # Each scan-input net maps to its cell driver; duplicate entries flag fanout.
    drivers, outputs = {}, {}
    for name, cell, spec in scan:
        ib, ob = cell.get("connections", {}).get(spec["scan_in"], []), cell.get("connections", {}).get(spec["scan_out"], [])
        if len(ib) != 1 or len(ob) != 1 or not isinstance(ob[0], int):
            errors.append(f"{name}: invalid scan input/output connections")
            continue
        enable = spec.get("scan_enable")
        if enable:
            enable_bits = cell.get("connections", {}).get(enable, [])
            if len(enable_bits) != 1 or mode_bit is None or enable_bits[0] != mode_bit:
                errors.append(f"{name}: scan-enable {enable} is not connected to declared test-mode input {mode or '(missing)'}")
        drivers.setdefault(ib[0], []).append(name)
        outputs.setdefault(ob[0], []).append(name)
    edges = {}
    starts = []
    for name, cell, spec in scan:
        con = cell.get("connections", {})
        ib, ob = con.get(spec["scan_in"], []), con.get(spec["scan_out"], [])
        if len(ib) != 1 or len(ob) != 1 or not isinstance(ob[0], int):
            continue
        if ib[0] == sin:
            starts.append(name)
        pred = outputs.get(ib[0], [])
        if len(pred) > 1:
            errors.append(f"{name}: scan input has multiple cell drivers: {', '.join(sorted(pred))}")
        elif len(pred) == 1:
            edges[pred[0]] = name
        consumers = drivers.get(ob[0], [])
        if len(consumers) > 1:
            errors.append(f"{name}: scan output has multiple scan-cell consumers: {', '.join(sorted(consumers))}")
        if sout is None or ob[0] != sout:
            if not consumers:
                errors.append(f"{name}: scan output does not reach a scan input or {sout_name}")

    reached = []
    if scan and sin is not None and sout is not None:
        if len(starts) != 1:
            errors.append(f"declared scan-in reaches {len(starts)} scan cells; expected 1")
        if len(outputs.get(sout, [])) != 1:
            errors.append(f"declared scan-out is driven by {len(outputs.get(sout, []))} scan cells; expected 1")
        reached, seen = [], set()
        cur = starts[0] if len(starts) == 1 else None
        while cur is not None and cur not in seen:
            reached.append(cur)
            seen.add(cur)
            cur = edges.get(cur)
        if cur in seen:
            errors.append(f"scan chain cycle at {cur}")
        for start in sorted(n for n, _, _ in scan if n not in seen):
            path, node = set(), start
            while node in edges and node not in path and node not in seen:
                path.add(node)
                node = edges[node]
            if node in path:
                errors.append(f"scan chain cycle at {node}")
        if len(reached) != len(scan):
            errors.append("unreachable scan cells: " + ", ".join(sorted(n for n, _, _ in scan if n not in seen)))
        elif reached:
            last, cell = next((n, c) for n, c, _ in scan if n == reached[-1])
            outpin = scan_specs[cell["type"]]["scan_out"]
            if cell["connections"][outpin][0] != sout:
                errors.append(f"scan chain ends at {last}, not {sout_name}")

    state_names, scan_names = {n for n, _ in state}, {n for n, _, _ in scan}
    if state_names - scan_names:
        errors.append("unscanned state cells: " + ", ".join(sorted(state_names - scan_names)))
    count = len(state)
    connected = len(state_names & scan_names) if count and not errors else None
    result = {"top": top, "state_cells": count, "scan_cells": len(scan),
              "scan_connected": connected, "scan_ratio": connected / count if connected is not None else None,
              "fault_coverage": None,
              "status": "error" if errors else "unknown" if unknown or not count else "ready",
              "diagnostics": sorted(set(errors + notes))}
    if not count:
        result["diagnostics"].append("no recognized state cells; scan ratio unavailable")
        result["diagnostics"].sort()
    if strict:
        unverified = ['cell behavior, test-mode activation and clock/reset operation unverified']
        if unknown:
            unverified.append('unknown cell models: ' + ', '.join(unknown))
        if scan_names - state_names:
            unverified.append('scan cells missing from declared state inventory: ' +
                              ', '.join(sorted(scan_names - state_names)))
        if not count:
            unverified.append('state inventory denominator unavailable')
        result.update(legacy_status=result['status'], status='error' if errors else 'unknown',
                      unverified=unverified, scan_chain=reached,
                      cell_inventory=[{'cell': n, 'type': c['type'],
                                       'state_declared': n in state_names,
                                       'scan_declared': n in scan_names,
                                       'source': c.get('attributes', {}).get('src'),
                                       'connections': c.get('connections', {})}
                                      for n, c in cells.items()])
    return result


def main():
    ap = argparse.ArgumentParser(prog="qd-dft")
    sub = ap.add_subparsers(dest="command", required=True)
    ck = sub.add_parser("check")
    ck.add_argument("netlist")
    ck.add_argument("--top", required=True)
    ck.add_argument("--policy", required=True)
    ck.add_argument("--json", action="store_true")
    ck.add_argument("--strict", action="store_true", help="report unverified behavior; UNKNOWN exits 3")
    args = ap.parse_args()
    try:
        result = check(load(args.netlist), args.top, load(args.policy), strict=args.strict)
    except (OSError, json.JSONDecodeError, InputError) as e:
        print(f"qd-dft: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        ratio = "UNKNOWN" if result["scan_connected"] is None else f"{result['scan_connected']}/{result['state_cells']}"
        print(f"{result['status'].upper()}: {result['top']} state={result['state_cells']} scan={ratio} fault_coverage=UNKNOWN")
        for diagnostic in result["diagnostics"]:
            print(f"- {diagnostic}")
        for reason in result.get('unverified', []):
            print(f"- UNKNOWN: {reason}")
    return 1 if result["status"] == "error" else 3 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
