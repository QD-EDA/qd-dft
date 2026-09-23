#!/usr/bin/env python3
"""Insert a generic mux scan chain into a supported resettable flop bank."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from qd_dft import InputError, validate_strict


def insert(netlist, top, clock, reset):
    validate_strict(netlist, top, {})
    if set(netlist['modules']) != {top}:
        raise InputError('insertion requires exactly one flattened module')
    mod = netlist['modules'][top]
    if not isinstance(mod.get('attributes', {}), dict):
        raise InputError('module attributes must be an object')
    if any(k in mod.get('attributes', {}) for k in ('blackbox', 'whitebox')):
        raise InputError('opaque module attributes are unsupported')
    if mod.get('memories') or mod.get('processes'):
        raise InputError('memories/processes are unsupported')
    ports, cells = mod.get('ports', {}), mod.get('cells', {})
    controls = []
    for name in (clock, reset):
        port = ports.get(name, {})
        bits = port.get('bits', [])
        if port.get('direction') != 'input' or len(bits) != 1 or type(bits[0]) is not int:
            raise InputError(f'{name}: expected scalar input control')
        controls.append(bits[0])
    if controls[0] == controls[1]:
        raise InputError('clock and reset must be distinct nets')
    if not cells:
        raise InputError('no eligible state cells')
    input_bits = {bit for p in ports.values() if p['direction']=='input' for bit in p['bits']}
    if any(p['direction']=='inout' for p in ports.values()):
        raise InputError('inout ports are unsupported')
    qbits = set()
    for name, cell in cells.items():
        con = cell.get('connections', {})
        if any(k in cell.get('attributes', {}) for k in ('blackbox', 'whitebox', 'dont_touch')):
            raise InputError(f'{name}: opaque/protected cells are unsupported')
        if (cell['type'] != '$_DFF_PN0_' or cell.get('parameters', {}) != {} or
                set(con) != {'C','R','D','Q'} or
                cell.get('port_directions') != {'C':'input','R':'input','D':'input','Q':'output'} or
                any(len(v)!=1 or type(v[0]) is not int for v in con.values())):
            raise InputError(f'{name}: requires scalar $_DFF_PN0_ net connections')
        if con['C'] != controls[:1] or con['R'] != controls[1:]:
            raise InputError(f'{name}: clock/reset differ from declared controls')
        if con['Q'][0] in input_bits | qbits:
            raise InputError(f'{name}: multiply driven state output')
        qbits.add(con['Q'][0])
    for name, cell in cells.items():
        if cell['connections']['D'][0] not in input_bits | qbits:
            raise InputError(f'{name}: undriven data input')
    names = mod.get('netnames', {})
    if not isinstance(names, dict):
        raise InputError('netnames must be an object')
    bits = set(input_bits) | qbits
    for item in list(ports.values()) + list(names.values()):
        if (not isinstance(item, dict) or not isinstance(item.get('bits'), list) or
                any(type(b) is not int or b < 0 for b in item['bits'])):
            raise InputError('insertion requires integer net bits in ports/netnames')
        bits.update(item['bits'])
    if any(b not in input_bits | qbits for p in ports.values() if p['direction']=='output' for b in p['bits']):
        raise InputError('undriven output port')
    new_names = ('qd_scan_en', 'qd_scan_in', 'qd_scan_out')
    mux_names = [f'qd_scan_mux_{i}' for i in range(len(cells))]
    if any(n in ports or n in names or n in cells for n in new_names + tuple(mux_names)):
        raise InputError('generated scan name already exists')
    result = copy.deepcopy(netlist)
    target = result['modules'][top]
    enable, serial = max(bits)+1, max(bits)+2
    target['ports']['qd_scan_en'] = {'direction':'input','bits':[enable]}
    target['ports']['qd_scan_in'] = {'direction':'input','bits':[serial]}
    chain = []
    for i, name in enumerate(sorted(cells)):
        cell = target['cells'][name]
        original_d, q = cell['connections']['D'][0], cell['connections']['Q'][0]
        mux_bit = enable+2+i
        target['cells'][mux_names[i]] = {
            'type':'$_MUX_', 'parameters':{}, 'attributes':{},
            'port_directions':{'A':'input','B':'input','S':'input','Y':'output'},
            'connections':{'A':[original_d],'B':[serial],'S':[enable],'Y':[mux_bit]}}
        cell['connections']['D'] = [mux_bit]
        chain.append({'cell':name,'mux':mux_names[i],'functional_d':original_d,
                      'scan_in':serial,'scan_out':q,'source':cell.get('attributes',{}).get('src')})
        serial = q
    target['ports']['qd_scan_out'] = {'direction':'output','bits':[serial]}
    manifest = {'schema_version':1,'top':top,'clock':clock,'reset':reset,
                'clock_edge':'posedge','reset_active_level':0,'reset_value':0,
                'scan_enable_active_level':1,'chain':chain,'inserted_muxes':len(chain),
                'state_cells':len(chain),'excluded_state_cells':0,'fault_coverage':None,
                'qualification':'UNKNOWN: generic insertion; equivalence and test evidence required',
                'test_assumptions':['hold reset high while shifting/capturing',
                                    'hold scan enable stable around clock edges']}
    return result, manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('netlist',type=Path)
    parser.add_argument('--top',required=True)
    parser.add_argument('--clock',required=True)
    parser.add_argument('--reset',required=True)
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args()
    try:
        raw=args.netlist.read_bytes()
        transformed,manifest=insert(json.loads(raw),args.top,args.clock,args.reset)
        encoded=json.dumps(transformed,sort_keys=True,indent=2)+'\n'
        manifest.update(input_sha256=hashlib.sha256(raw).hexdigest(),
                        output_sha256=hashlib.sha256(encoded.encode()).hexdigest())
        args.output_dir.mkdir() # Never overwrite source files or prior evidence.
        (args.output_dir/'scan.json').write_text(encoded)
        (args.output_dir/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    except (OSError, ValueError) as error:
        parser.exit(2, f'qd-scan-insert: {error}\n')
    print('Generated generic scan netlist and manifest; qualification UNKNOWN')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
