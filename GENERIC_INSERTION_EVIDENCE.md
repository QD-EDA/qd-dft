# Generic scan insertion: supported scope and evidence

`qd_scan_insert.py` creates a separate generic Yosys netlist containing one scan
mux per flop and a single deterministic chain. This is the first implementation
slice, not a technology scan-cell mapper or production DFT flow. It leaves the
original design and the existing structural checker unchanged.

## Contract

Input is one flattened Yosys JSON module consisting entirely of scalar
`$_DFF_PN0_` cells: positive-edge, asynchronous active-low reset, reset value zero.
Every cell must share the named scalar top-level clock/reset input nets. Cell
ports/directions and integer net connections are validated. Empty banks, other
cells, hierarchy, inouts, constant connections, undriven data/output nets,
multiple state drivers, opaque/protected cells and generated-name collisions
are rejected. Existing attributes and original functional connections are retained.
No cell is silently excluded. This intentionally bounded contract does not accept
arbitrary blocks or silently approximate unsupported cell behavior.

The transformation inserts `$_MUX_` with A=functional D, B=previous chain Q,
S=qd_scan_en and Y=new D. The first B is qd_scan_in; qd_scan_out aliases the last Q.
Chain order is lexicographic original cell name, recorded in manifest.json; it
is stable for an identical input netlist, not across synthesis renaming.
Normal mode is scan enable zero; shift is one. Reset must remain high for useful
shift/capture; assertion still asynchronously clears all state. Scan enable must
be stable around clock edges. Timing and electrical enforcement remain unknown.

```sh
python3 qd_scan_insert.py original.json --top TOP --clock clk_i --reset rst_ni --output-dir new-scan-output
```

The output directory must not exist. It contains scan.json and manifest.json
with input/output SHA256, chain order, source attributes, original D nets, control
assumptions and state/mux counts. Creation exits 0; unsupported input or output
errors exit 2. A successful transformation explicitly records qualification UNKNOWN
and fault_coverage null. It does not automatically run equivalence or qualify a
chain. A write failure can leave a partial new directory: retain it as failure
evidence and use a different new directory for retry. Existing files are never
overwritten. Input JSON stays immutable.

The current `qd_dft.py check` policy expects declared combined scan cells; it does
not recognize a mux-plus-flop pair as one scan cell. Do not use its legacy ready
status to qualify this output. The insertion manifest and the independent checks
below are the evidence for this generic representation.

## Named pilot and independent checks

Caliptra RTL v2.1.2 `49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e`, unchanged
`src/caliptra_prim_generic/rtl/caliptra_prim_generic_flop.sv`, Width=4,
ResetValue=0, is synthesized to four generic flops. This is an actual public
primitive configured for a four-bit pilot, not an owner-approved chip scan plan.
Application RTL/DV is never edited. The derived output contains four original
flops and four muxes. Their semantics are the native Yosys generic cell semantics;
no invented technology scan-cell model is substituted.

```sh
python3 -m unittest discover -s tests -v
/usr/bin/python3 -m unittest discover -s tests -v
python3 run_caliptra_scan_pilot.py /path/to/clean/caliptra-rtl /tmp/new-qd-scan-evidence
```

The pilot requires simple paths without spaces/metacharacters and a new evidence
directory. Each tool invocation has a 120-second timeout. The runner records exact
commands, generated Yosys scripts, statuses, elapsed seconds, tool version logs,
input hashes, emitted netlists, manifest and separate raw stdout/stderr logs.
Header hashes are an explicit inventory, not proven include closure.

- **Normal mode:** Yosys equiv_make/equiv_simple proves all four original output
  bits against the emitted design with scan enable tied low. Extra scan ports are
  removed only from the proof view. async2sync supplies the discrete clock/reset
  model. No unproven equivalence cell is accepted. A derived functional-mux fault
  must leave an unproven output and fail equiv_status -assert.
- **Shift/capture:** Icarus independently simulates exported Verilog alongside the
  unchanged original RTL. The scoreboard tests all 16 four-bit capture values and
  shifts each pattern through the chain, checking every cycle and serial output.
  It also checks X propagation, asynchronous reset during shifting, and post-reset
  normal operation. Chain-to-q_o ordering is verified before the fixed scoreboard
  is used. A broken link in a separate derived fault netlist must fail simulation.
- **Python:** 21 tests pass, including five new insertion tests covering immutability,
  deterministic order, functional/scan wiring, unsupported state/control cases,
  malformed metadata, generated-name collisions, and refusal to overwrite outputs.
  All 16 previous checker tests still pass.

Versions: Python 3.14.7 and Apple Python 3.9.6; Yosys 0.68+80
`621d943ac-dirty`; Icarus/vvp 13.0 stable. The installed dirty Yosys build is
not an immutable release toolchain. The original smoke CI exercises Python. A separate pinned Linux lane now runs
the Caliptra/Yosys/Icarus pilot; see PINNED_CI_EVIDENCE.md for versions and limits.

Local artifacts live in `../evidence/dft-generic-insertion/`, not a published
release bundle. Initial synthesis failed because the upstream assertion header
required the libs/rtl include directory; that diagnostic was retained and the
actual include path added. No header or assertion implementation was replaced.
The selected primitive contains no assertion invocations; this is not evidence
for application assertion coverage.

## Qualification still unknown

The proof concerns functional output equivalence under the discrete normal-mode
model, not scan timing, reset recovery/removal, metastability, physical placement,
ATPG correctness or fault coverage. No Liberty mapping, scan-cell area/timing,
lockup insertion, compression, clock-domain mixing, retention, security test-mode
policy or real chip test protocol is qualified. Technology libraries, design-owner
architecture approval, downstream synthesis/STA validation, broader primitive
support and fault simulation remain required. There is no raw/eligible fault
population yet, so every fault coverage denominator remains unavailable.

A fresh local clone of `590c87c` repeated the complete pilot and all 21 Python
tests under both interpreters. Emitted scan.json and manifest.json were
byte-identical to the prior run. This is workspace independence on the same host,
not an independently rebuilt toolchain. One local run measured 0.0296 seconds for
insertion, 0.0150 seconds for equivalence and 0.0051 seconds for positive simulation;
peak RSS was not measured by the runner. This four-bit case establishes no
large-block throughput or physical-design performance target.
