# QD-DFT: testability analysis and design-for-test implementation

## Intended product (scope clarified 2026-09-23)

QD-DFT will both analyze testability and implement design-for-test by inserting the necessary design elements into RTL or netlists for an explicitly supported scope. Scan-cell mapping, chain stitching and test controls are implementation outputs, alongside fault simulation, ATPG integration and evidence. The current executable only audits structure; insertion is not implemented today.

## Current capability

Baseline `84ed4eba7a3ed12c071107fa392e4d77bcb80e2f`: nine tests;
CI runs `python3 -m unittest discover -s tests -v`. Declared scan connectivity
is checked against a cell policy in one Yosys module. Unknown cells stay visible,
but CLI status UNKNOWN currently exits zero; clock/reset notes can accompany
`ready`. Neither status nor scan ratio proves mode controllability or fault
coverage. `fault_coverage` remains null. Preserve that distinction and legacy CLI.

## Stages and interfaces

1. **Next useful slice:** validate cell/policy schemas and publish an explicit
   analyzed/unknown inventory with ordered chain artifacts. Add opt-in strict
   qualification status that blocks UNKNOWN and unproven controls without
   changing legacy exit behavior. Library maps must declare SI/SO/SE, clock edge,
   reset polarity and mode truth table; unknown semantics stay unproven.
2. **Pinned pilot:** Caliptra generic RTL and OpenTitan generic primitive/state
   inventory first; then obtain an owner-approved scan-mapped netlist, Liberty
   revision and test protocol for each named block. Public RTL does not by itself
   supply production scan insertion/mapping. Missing mapped collateral blocks
   scan qualification. A generated scan fixture may test the tool, not stand in
   for an actual design's implemented scan chain.
3. **DFT implementation:** on a supported single-clock block, map eligible flops
   to specified scan cells, insert required scan muxes/control ports, and stitch
   deterministic chains from a reviewed test architecture. Use established
   synthesis/insertion passes where suitable. Emit a separate transformed netlist,
   source/cell mapping, chain order, constraints and an insertion manifest. Prove
   normal-mode equivalence against the immutable original; independently simulate
   shift/capture and audit every inserted or excluded state element. Extend to
   test-clock/reset/mode logic, lockup elements, test points and other required
   structures only under an explicit architecture/library contract. Missing library
   semantics block insertion; do not create functional stand-ins and call them
   mapped scan cells. Real-design pilots may use generated insertion outputs,
   provided their origin and verification remain distinct from owner signoff.
4. **Testability to patterns:** prove test-mode/clock/reset controllability, check
   chain stitching and shift/capture sequencing across clock domains, then add
   stuck-at fault simulation before an external ATPG adapter. Transition faults,
   compression, lockup latches and memory test require separate modeled scopes.
   Verify emitted patterns with an independent fault simulator and downstream
   loader; use a versioned deterministic JSON pattern intermediate, then the
   particular STIL/WGL/tester subset requested by the actual downstream flow.
5. **Production qualification:** named cell library, mapped block, chain/mode
   configuration and fault model. Establish pattern replay, coverage accounting,
   ATPG/fault-simulator agreement and approved exclusions. Never infer coverage
   of physical defects, delay faults or memories from a stuck-at result.
   Qualify both analyzer accuracy and insertion correctness: normal-mode
   equivalence, verified test behavior, synthesis/STA compatibility, area/timing
   impact and successful downstream pattern replay on the emitted design.

## Evidence and release criteria

- Inputs: mapped netlist/top, cell semantics, chain endpoints, shift/capture
  clocks/resets/modes, fault model and exclusions. Outputs: ordered chains,
  control proofs/counterexamples, fault inventory, deterministic patterns,
  replay results, unknowns and per-fault disposition.
  Insertion also consumes original RTL/netlists and an approved test architecture;
  it emits derived RTL/netlists, cell/port changes, scan maps and constraints.
- Denominators: publish raw enumerated faults, equivalence-collapse mapping,
  excluded faults with reasons, eligible faults, detected, proven untestable,
  aborted and unknown. Report raw detection = detected/raw and eligible detection
  = detected/eligible; any testable-fault ratio must separately define subtraction
  of proven untestable faults. Zero denominator is unavailable, not 100%.
- Corpus: existing nine cases; multiple chains, cycles, fanout, constant SI/SE,
  missing pins, scan cells absent from state inventory, black boxes, clock/reset
  mode contradictions; tiny circuits with exhaustively enumerated faults and
  independently known patterns; downstream round-trip fixtures.
  Add original/transformed equivalence pairs, excluded-state handling, repeated
  insertion rejection/idempotence policy, unsupported library cells and injected
  stitching/mode errors in generated test fixtures.
- Oracles: library truth tables, separate graph traversal, exhaustive tiny fault
  simulation, external ATPG and independent gate-level pattern replay. Structural
  reachability is never an oracle for fault detection.
- Version matrix: Python 3.9/3.14; pinned Yosys, library and scan-insertion tool;
  name ATPG/fault-simulation/tester tool versions before extending qualification.
  No compatible ATPG or tester integration is claimed today.
- Targets: 100k scan cells <=10 s/1 GiB; tiny exhaustive fault corpus <=60 s;
  pilot 10k stuck-at faults/1k patterns <=10 min/4 GiB, with explicit aborts.
  Initial insertion target: 100k eligible flops <=60 s/4 GiB excluding equivalence
  solving; report cell/area growth and timing deltas against owner-agreed budgets.
- Release: no dropped state/fault inventory, exact chain replay, no unexplained
  oracle discrepancy, documented detection target agreed with the block owner
  before running (not retrofitted to measured coverage), all exclusions reviewed,
  repeatable patterns and stable hashes. Until then publish structural evidence.

## Qualification contract

This is a staged plan, not a production qualification claim. No stage is earned
by a green unit suite alone. Keep existing passing behavior and raw diagnostics.
Preserve the immutable application RTL/DV inputs. Intentional DFT/DFD insertion
is authorized product work: emit a separate derived design with an explicit
transformation manifest. Never edit the golden inputs, disable assertions or
introduce dummy VIP merely to manufacture a passing pilot. A failed pilot is an artifact to retain, not a test to remove.

Named pilot pins (full SHAs, never floating branches):
- Caliptra RTL v2.1.2: `49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e`, generic simulation primitives;
  Adams Bridge v2.0.3: `b77e3d899e828d626cfc2a0d26a6b5704cc121e0` when needed.
- OpenTitan: `7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19`; select the named IP fileset, generic technology,
  and record all FuseSoC flags, parameters, generated files, and their digests.
  The later configuration-blocker evidence at `a78922f14a8cc20c7ee569f322a04626f2ac6127`
  is a separate revision, not interchangeable qualification evidence.

Every release candidate needs an immutable evidence bundle: tool Git SHA and
binary hashes; OS/architecture, Python/compiler/simulator/solver versions;
design and submodule SHAs; top, parameters, defines, ordered files/includes,
constraints, libraries, seeds; input/output hashes; exact argv, raw stdout/stderr,
exit codes, wall time and peak RSS. Repeat twice in clean independent workspaces;
compare canonical findings and explain any nondeterminism. Archive the bundle
with the release and publish a supported/unsupported configuration table.

Review every expected finding and every oracle disagreement. Seed known defects
in separate test fixtures and require their detection; never alter golden pilot RTL to manufacture a pass. Derived insertion outputs
are permitted and must be verified against the golden input and approved policy.
Unknowns and exclusions remain counted and visible. Waivers require a stable
finding/configuration identity, owner, independent reviewer, rationale, evidence
hash/link, expiry, and revalidation on any relevant input change. A waiver is a
review disposition, not a proof. No unreviewed waiver or unexplained oracle
mismatch is allowed in the qualified scope. Outside that scope report UNKNOWN
or a clear unsupported error. A version or dependency change reopens qualification.

Performance numbers below are acceptance targets, not measurements. Measure on
a named Linux x86-64 runner with 8 cores and 16 GiB RAM; record hardware and
median of five runs. No automatic threshold relaxation. macOS arm64 is a second
portability lane, not a substitute for the qualification runner.

## Portfolio priority and real-flow blockers

1. **QD-Lint first:** source/configuration fidelity is prerequisite evidence for
   every downstream analysis. OpenTitan pinmux's conditional `fileset_ip` versus
   `fileset_top` selects different register packages. A local pinned matrix probe
   at `a78922f...` reproduced an omitted-package failure from wrong setup flags;
   it was not an RTL defect. Caliptra's generic/technology primitive roots also
   select different sources. Audit these choices before caching or baselining.
2. **QD-BFM second:** Caliptra's README requires licensed Avery AXI and QVIP AHB
   dependencies in full UVMF flows. A bounded independent AXI adapter is useful,
   but cannot cure simulator/UVM/firmware dependencies or replace their APIs.
3. **QD-CDC, then QD-DFD:** real reset/synchronizer and lifecycle/debug cones are
   available; getting complete elaboration and constraints is the next blocker.
   VCD observations and cell annotations cannot establish safety on their own.
4. **QD-UPF and QD-DFT:** do standards/library/topology inventory now; owner-approved
   power intent and scan-mapped collateral are unverified. Do not invent these
   inputs or mistake lack of collateral for a demonstrated design failure.

Primary source anchors (review pinned source, not just current web documentation):
- [Caliptra dependency and configuration README](https://github.com/chipsalliance/caliptra-rtl/blob/49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e/README.md).
- [OpenTitan pinmux fileset selection](https://github.com/lowRISC/opentitan/blob/a78922f14a8cc20c7ee569f322a04626f2ac6127/hw/ip/pinmux/pinmux_reg.core).
- [OpenTitan lifecycle architecture](https://github.com/lowRISC/opentitan/tree/7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19/hw/ip/lc_ctrl/doc).
- [OpenTitan TL DV agent](https://github.com/lowRISC/opentitan/tree/7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19/hw/dv/sv/tl_agent).
