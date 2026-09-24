#!/usr/bin/env python3
"""Reproduce the four-bit generic insertion pilot; preserve every tool log."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time


def main():
    if len(sys.argv)!=3:
        print('usage: run_caliptra_scan_pilot.py CALIPTRA_ROOT NEW_EVIDENCE_DIR',file=sys.stderr)
        return 2
    root,out=[Path(p).resolve() for p in sys.argv[1:]]
    repo=Path(__file__).resolve().parent
    records=[]
    try:
        # Simple paths only: Yosys script tokenization is not shell quoting.
        if any(not re.fullmatch(r'[A-Za-z0-9_./:+-]+',str(p)) for p in (root,out,repo)):
            raise ValueError('pilot requires simple paths without spaces or metacharacters')
        if subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()!='49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e':
            raise ValueError('wrong Caliptra revision')
        if subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True):
            raise ValueError('Caliptra checkout must be clean')
        out.mkdir()
        def run(name,args,fail=False):
            start=time.monotonic()
            r=subprocess.run(args,cwd=repo,capture_output=True,text=True,timeout=120)
            (out/(name+'.stdout')).write_text(r.stdout)
            (out/(name+'.stderr')).write_text(r.stderr)
            records.append(dict(name=name,argv=args,exit_status=r.returncode,seconds=time.monotonic()-start))
            if bool(r.returncode)!=fail: raise ValueError(name+': unexpected tool status')
            return r.stdout+r.stderr
        def yosys(name,script,fail=False):
            path=out/(name+'.ys');path.write_text(script+'\n')
            return run(name,['yosys','-Q','-s',str(path)],fail)
        for tool in ('yosys','iverilog','vvp'):
            run(tool+'-version',[tool,'-V'])
        rtl=root/'src/caliptra_prim_generic/rtl/caliptra_prim_generic_flop.sv'
        includes=[root/'src/caliptra_prim/rtl',root/'src/libs/rtl']
        inc=' '.join('-I'+str(p) for p in includes)
        original=out/'original.json';scan=out/'inserted/scan.json'
        yosys('synthesis',f'read_verilog -sv {inc} {rtl}; chparam -set Width 4 caliptra_prim_generic_flop; hierarchy -top caliptra_prim_generic_flop; proc; opt; techmap; opt; write_json {original}')
        run('insert',[sys.executable,str(repo/'qd_scan_insert.py'),str(original),'--top','caliptra_prim_generic_flop',
            '--clock','clk_i','--reset','rst_ni','--output-dir',str(out/'inserted')])
        manifest_path=out/'inserted/manifest.json'
        run('audit',[sys.executable,str(repo/'qd_scan_audit.py'),str(original),str(scan),str(manifest_path),'--json'])
        manifest=json.loads(manifest_path.read_text())
        mod=json.loads(original.read_text())['modules']['caliptra_prim_generic_flop']
        if [row['scan_out'] for row in manifest['chain']]!=mod['ports']['q_o']['bits']:
            raise ValueError('pilot scoreboard expects chain order q_o[0] through q_o[3]')
        proof=f'''read_json {original}
rename caliptra_prim_generic_flop gold
read_json {scan}
rename caliptra_prim_generic_flop gate
cd gate
connect -set qd_scan_en 1'b0
delete -port qd_scan_en qd_scan_in qd_scan_out
cd ..
equiv_make gold gate equiv
hierarchy -top equiv
async2sync
equiv_simple
equiv_status -assert'''
        if 'Equivalence successfully proven!' not in yosys('equivalence',proof):
            raise ValueError('equivalence completion missing')
        broken_function=json.loads(scan.read_text())
        broken_function['modules']['caliptra_prim_generic_flop']['cells']['qd_scan_mux_0']['connections']['A']=['0']
        broken_path=out/'broken-function.json';broken_path.write_text(json.dumps(broken_function))
        failure=yosys('reject-functional-fault',proof.replace(str(scan),str(broken_path)),fail=True)
        if 'unproven' not in failure:
            raise ValueError('functional fault did not fail equivalence as expected')
        # Mutate only a derived scan link, never the golden source or normal transform.
        faulty=json.loads(scan.read_text())
        faulty['modules']['caliptra_prim_generic_flop']['cells']['qd_scan_mux_1']['connections']['B']=['0']
        fault=out/'fault.json';fault.write_text(json.dumps(faulty))
        fault_manifest=dict(manifest)
        fault_manifest['output_sha256']=hashlib.sha256(fault.read_bytes()).hexdigest()
        fault_manifest_path=out/'fault-manifest.json'
        fault_manifest_path.write_text(json.dumps(fault_manifest))
        failure=run('reject-scan-audit-fault',[sys.executable,str(repo/'qd_scan_audit.py'),
                    str(original),str(fault),str(fault_manifest_path)],fail=True)
        if 'scan netlist differs' not in failure:
            raise ValueError('scan audit did not reject broken link')
        for name,netlist in [('positive',scan),('fault',fault)]:
            exported=out/(name+'.v')
            yosys('export-'+name,f'read_json {netlist}; rename caliptra_prim_generic_flop scanned; write_verilog {exported}')
            executable=out/(name+'.vvp')
            run('compile-'+name,['iverilog','-g2012','-s','scan_bank_tb','-o',str(executable)]+
                ['-I'+str(p) for p in includes]+[str(rtl),str(exported),str(repo/'fixtures/scan_bank_tb.sv')])
            log=run('simulate-'+name,['vvp',str(executable)],fail=name=='fault')
            if ('PASS: 16 capture/shift patterns' if name=='positive' else 'scan state mismatch') not in log:
                raise ValueError(name+': missing simulation outcome')
        inputs=[rtl,repo/'qd_scan_insert.py',repo/'qd_scan_audit.py',repo/'fixtures/scan_bank_tb.sv']
        inputs += list(includes[0].glob('caliptra_prim_assert*'))+[includes[1]/'caliptra_sva.svh']
        (out/'inputs.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},indent=2))
        if subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True):
            raise ValueError('application checkout changed')
        print('PASS: scoped normal-mode equivalence and scan replay; qualification UNKNOWN')
        return 0
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        print(str(error),file=sys.stderr);return 1
    finally:
        # Do not write into a pre-existing directory rejected by mkdir.
        if records: (out/'commands.json').write_text(json.dumps(records,indent=2)+'\n')


if __name__=='__main__':
    raise SystemExit(main())
