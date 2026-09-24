# qd-dft

## Product direction

QD-DFT will both analyze testability and implement design-for-test by inserting the necessary design elements into RTL or netlists for an explicitly supported scope. Scan-cell mapping, chain stitching and test controls are implementation outputs, alongside fault simulation, ATPG integration and evidence. The original checker audits structure. An optional generic mux-scan insertion pilot now supports a tightly bounded flop-bank scope; technology mapping and production qualification remain unfinished.

## Current prototype

`qd-dft` checks declared scan-chain connectivity and recognized state cells in a Yosys `write_json` netlist. The checker does not insert scan or generate ATPG patterns, measure stuck-at/transition fault coverage, or replace DFT signoff. A reported structural ratio is not fault coverage; `fault_coverage` is always `null`.

## Requirements and quick start

Python 3 is required. Yosys is not required to use the included JSON fixture.

```sh
python3 qd_dft.py check tests/fixtures/tiny_chain.json --top top --policy tests/policy.json --json
python3 -m unittest discover -s tests -v
```

The example reports `ready` for the two-cell chain. The policy maps the top-level test-mode, scan-in, and scan-out ports; recognized state/scan cell types; and each scan cell's input/output pins. See [tests/policy.json](tests/policy.json). Optional clock/reset pin names are recorded as UNKNOWN behavior because this checker does not model their semantics. Text output summarizes status and counts; `--json` prints the structured result, including diagnostics and any available ratio.

## Results and limits

- `ready`: all recognized state cells are connected in the declared structural scan chain and no structural error or unknown cell was found. This does not prove test-mode activation or usable test clocks/resets.
- `unknown`: an unrecognized or black-box cell exists, or there are no recognized state cells. The tool does not treat this as signoff.
- `error`: a declared endpoint/chain is broken, a recognized state cell is unscanned, or declared scan connectivity has a fanout, cycle, or reachability error.

Exit codes: `0` for `ready` or `unknown`; `1` for structural `error`; `2` for invalid JSON, missing files, or a missing top. A ratio is available only for a non-empty recognized state inventory with no structural errors. Clock controllability, reset behavior, test-mode activation, cell semantics, electrical integrity, and fault coverage are outside scope.

See [the staged qualification roadmap](ROADMAP.md) for named pilots, unsupported
cases, independent oracles, performance targets and release gates.

## Strict automation gate

Add `--strict` to retain the structural results while making unverified behavior
fail the automation gate. Exit codes are `1` for structural errors, `2` for input
errors and `3` for UNKNOWN. No current input can earn a strict pass: cell behavior,
test-mode activation and clock/reset operation are not implemented proofs.
Without the flag, the existing report and exit behavior remain unchanged.

Strict JSON adds `legacy_status`, `unverified`, `scan_chain` (visited cells, possibly
partial or ambiguous when errors exist), and `cell_inventory`. The inventory lists
every cell directly in the selected top, its declared roles, connections and raw
source attribute. It does not recursively expand hierarchy or discover state
hidden inside macros. Policy declarations are assumptions, not verified models.
The structural ratio denominator is only the declared recognized state cells;
it is neither a complete physical state inventory nor a fault denominator.

See [strict inventory evidence](STRICT_EVIDENCE.md) for commands and limitations.

## Optional generic scan insertion

```sh
python3 qd_scan_insert.py original.json --top TOP --clock clk_i --reset rst_ni --output-dir new-output
```

This creates a separate generic mux-based scan netlist and chain manifest for a
single-clock, common-reset bank of scalar Yosys `$_DFF_PN0_` cells. It rejects
unsupported configurations and existing output directories. Generation success
is not qualification: fault coverage remains unavailable. See
[the insertion contract and Caliptra evidence](GENERIC_INSERTION_EVIDENCE.md)
for exact inputs, outputs, simulation/equivalence commands and limitations.

The separate [pinned Linux CI lane](PINNED_CI_EVIDENCE.md) builds Yosys 0.44 and
Icarus 12.0 from fixed source commits, runs the Caliptra insertion pilot and
archives evidence for 30 days. This supplements the Python smoke checks; it does
not qualify a technology library or production scan flow.

## Audit the generated chain

```sh
python3 qd_scan_audit.py original.json new-output/scan.json new-output/manifest.json --json
```

The optional audit checks both file hashes, regenerates the declared generic
transform from the original, and compares every netlist cell, port, connection
and manifest field. It reports an ordered chain, `status: unknown`, and null
fault coverage on a consistent pair; a mismatch exits 1. This catches corruption
or edits to an insertion artifact, even when its output hash is updated. It is
not an independent proof of the insertion algorithm: the pinned Caliptra pilot
uses separate Yosys equivalence and Icarus shift/capture simulation for that.
The input hash must be compared to a trusted design pin outside this command.
Cell semantics, test controls, mapping, timing and fault coverage remain UNKNOWN.
