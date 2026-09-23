# qd-dft

A small structural scan-readiness checker for Yosys `write_json` netlists. It does not insert scan or generate ATPG patterns.

```sh
python3 qd_dft.py check netlist.json --top top --policy policy.json
python3 qd_dft.py check netlist.json --top top --policy policy.json --json
python3 -m unittest discover -s tests -v
```

Policy maps top-level `test_mode`, `scan_in`, and `scan_out` port names, recognized state-cell types, and scan-cell types with their `scan_in` and `scan_out` pin names. For example, see [tests/policy.json](tests/policy.json). `clock`, `reset`, and `scan_enable` pin names may be declared; clock/reset semantics remain UNKNOWN.

The checker traces declared scan-cell output nets into scan-cell inputs, and reports missing endpoints, broken links, fanout, cycles, and unreachable scan cells. Unknown cell types and blackboxes are reported as UNKNOWN. An empty state inventory is also UNKNOWN. The reported scan-connected/state ratio is structural only; it is not stuck-at or transition fault coverage. This tool does not prove test-mode activation, clock controllability, reset behavior, cell semantics, or electrical integrity. Treat it as a quick audit, not DFT signoff.
