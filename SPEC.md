# Product scope

QD-DFT will both analyze testability and implement design-for-test by inserting the necessary design elements into RTL or netlists for an explicitly supported scope. Scan-cell mapping, chain stitching and test controls are implementation outputs, alongside fault simulation, ATPG integration and evidence. The original checker audits structure. An optional generic mux-scan insertion pilot now supports a tightly bounded flop-bank scope; technology mapping and production qualification remain unfinished.

The historical v0 specification below describes the existing prototype, not a limit on the intended product. The staged implementation and qualification contract is in ROADMAP.md.

# QD-DFT v0 scope

Build a conservative design-for-test structural audit for Yosys `write_json` netlists. It reports scan readiness and structural gaps; it does not insert scan, generate ATPG vectors, or replace commercial DFT signoff.

CLI: `qd-dft check netlist.json --top TOP --policy policy.json [--json]`. Policy declares test-mode, scan-in/out, scan-enable, and known scan-cell types/ports. Count supported state cells; trace declared scan chain connectivity and report unreachable, multiply-connected, cyclic, or unrecognized state cells. Report unknown/blackbox cells and clock/reset controls as UNKNOWN rather than declaring coverage. Report measured scan-connected/total only when the netlist supports it; never equate that ratio with stuck-at or transition fault coverage. Deterministic diagnostics and nonzero status on broken declared chains.

Tests: complete tiny chain, broken link, missing scan endpoint, unrecognized flop, empty netlist/no-state boundary. Include a tiny Yosys-generated fixture if feasible, alongside pure JSON fixtures. Add README with limits, Apache-2.0 license, and test command. Own only this repo; no commit/push/remote creation.

## Optional generic flop-bank insertion

Provide a separate opt-in transform for one flattened bank of scalar Yosys
$_DFF_PN0_ cells with a shared direct clock/reset. Insert native generic muxes and
one lexicographically ordered chain into a separate netlist, preserving the golden
input. Emit original D/chain/source mapping, hashes, control assumptions and explicit
UNKNOWN qualification. Reject unsupported semantics instead of excluding state.
Require normal-mode equivalence, independent shift/capture/reset simulation and
negative derived-netlist mutations in the pinned Caliptra pilot. Technology scan
mapping and fault coverage are not supplied by this slice.
