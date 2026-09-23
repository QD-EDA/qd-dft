import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from qd_dft import InputError
from qd_scan_insert import insert


def bank():
    return {'modules':{'top':{'ports':{
        'clk':{'direction':'input','bits':[2]},'rst':{'direction':'input','bits':[3]},
        'd':{'direction':'input','bits':[4,5]},'q':{'direction':'output','bits':[6,7]}},
        'cells':{name:{'type':'$_DFF_PN0_','parameters':{},
            'port_directions':{'C':'input','R':'input','D':'input','Q':'output'},
            'connections':{'C':[2],'R':[3],'D':[d],'Q':[q]}}
            for name,d,q in [('b',5,7),('a',4,6)]},'netnames':{}}}}


class InsertionTests(unittest.TestCase):
    def test_chain_and_functional_pins_preserve_input(self):
        data=bank(); before=copy.deepcopy(data)
        result,m=insert(data,'top','clk','rst')
        self.assertEqual(data,before)
        self.assertEqual([r['cell'] for r in m['chain']],['a','b'])
        cells=result['modules']['top']['cells'];ports=result['modules']['top']['ports']
        self.assertEqual(cells['qd_scan_mux_0']['connections']['A'],[4])
        self.assertEqual(cells['qd_scan_mux_1']['connections']['B'],[6])
        self.assertEqual(ports['qd_scan_out']['bits'],[7])
        self.assertEqual(m['state_cells'],2)
        self.assertIsNone(m['fault_coverage'])
        data['modules']['top']['cells']=dict(reversed(list(data['modules']['top']['cells'].items())))
        self.assertEqual((result,m),insert(data,'top','clk','rst'))

    def test_unsupported_and_malformed_state_rejected(self):
        for change in ('type','clock','reset','wide','direction','driver','undriven'):
            data=bank();c=data['modules']['top']['cells']['a']
            if change=='type':c['type']='$_DFF_P_'
            if change=='clock':c['connections']['C']=[4]
            if change=='reset':c['connections']['R']=[4]
            if change=='wide':c['connections']['D']=[4,5]
            if change=='direction':c['port_directions']['D']='output'
            if change=='driver':c['connections']['Q']=[7]
            if change=='undriven':c['connections']['D']=[99]
            with self.subTest(change=change), self.assertRaises(InputError):insert(data,'top','clk','rst')

    def test_empty_hierarchy_collisions_and_control_alias_rejected(self):
        for change in ('empty','hierarchy','collision','alias'):
            data=bank();mod=data['modules']['top']
            if change=='empty':mod['cells']={}
            if change=='hierarchy':data['modules']['other']={}
            if change=='collision':mod['netnames']['qd_scan_en']={'bits':[90]}
            if change=='alias':mod['ports']['rst']['bits']=[2]
            with self.subTest(change=change), self.assertRaises(InputError):insert(data,'top','clk','rst')

    def test_protected_or_malformed_metadata_rejected(self):
        for change in ('protected','opaque','netnames','connections','output'):
            data=bank();mod=data['modules']['top']
            if change=='protected':mod['cells']['a']['attributes']={'dont_touch':1}
            if change=='opaque':mod['attributes']={'blackbox':'1'}
            if change=='netnames':mod['netnames']={'x':{'bits':None}}
            if change=='connections':del mod['cells']['a']['connections']
            if change=='output':mod['ports']['q']['bits']=[98,99]
            with self.subTest(change=change), self.assertRaises(InputError):insert(data,'top','clk','rst')

    def test_cli_never_overwrites_existing_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'original.json';source.write_text(json.dumps(bank()))
            args=[sys.executable,'qd_scan_insert.py',str(source),'--top','top','--clock','clk',
                  '--reset','rst','--output-dir',str(root/'out')]
            first=subprocess.run(args,capture_output=True,text=True)
            self.assertEqual(first.returncode,0,first.stderr)
            content=(root/'out/scan.json').read_bytes()
            self.assertEqual(subprocess.run(args,capture_output=True).returncode,2)
            self.assertEqual(content,(root/'out/scan.json').read_bytes())
            self.assertEqual(json.loads(source.read_text()),bank())
