# QD-DFT v0 scope

Build a conservative design-for-test structural audit for Yosys `write_json` netlists. It reports scan readiness and structural gaps; it does not insert scan, generate ATPG vectors, or replace commercial DFT signoff.

CLI: `qd-dft check netlist.json --top TOP --policy policy.json [--json]`. Policy declares test-mode, scan-in/out, scan-enable, and known scan-cell types/ports. Count supported state cells; trace declared scan chain connectivity and report unreachable, multiply-connected, cyclic, or unrecognized state cells. Report unknown/blackbox cells and clock/reset controls as UNKNOWN rather than declaring coverage. Report measured scan-connected/total only when the netlist supports it; never equate that ratio with stuck-at or transition fault coverage. Deterministic diagnostics and nonzero status on broken declared chains.

Tests: complete tiny chain, broken link, missing scan endpoint, unrecognized flop, empty netlist/no-state boundary. Include a tiny Yosys-generated fixture if feasible, alongside pure JSON fixtures. Add README with limits, Apache-2.0 license, and test command. Own only this repo; no commit/push/remote creation.
