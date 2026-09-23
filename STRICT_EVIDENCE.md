# Strict inventory evidence

This slice adds an opt-in automation gate and deterministic top-level cell ledger.
It does not qualify DFT behavior, insert scan, simulate faults or generate patterns.

## Reproduction

On macOS, Python 3.14.7 and Apple system Python 3.9.6 each passed all 16 tests
(nine existing, seven added). No third-party Python packages are required.

```sh
python3 -m unittest discover -s tests -v
/usr/bin/python3 -m unittest discover -s tests -v
python3 qd_dft.py check tests/fixtures/tiny_chain.json --top top --policy tests/policy.json --strict --json
```

The final command must exit 3, report UNKNOWN, preserve `legacy_status: ready`,
report chain `u0, u1`, and report structural ratio 2/2 with null fault coverage.
Without `--strict` it continues to exit zero with the original report shape.
Existing CI discovers the added tests automatically; no test exclusions changed.

Positive checks establish inventory and traversal of the declared two-cell chain.
Negative checks cover broken links, scan-only declarations, malformed pin policies,
malformed JSON structures/bit arrays and ambiguous fanout. Boundary checks cover
empty designs, constant/X/Z scan-input bits and reversed cell ordering. The CLI
test checks compatibility and the distinct UNKNOWN exit code. The malformed
inputs are validated only in strict mode, preserving the legacy interface.

The simple independent connectivity oracle is the checked-in fixture wiring:
scan input bit 3 feeds u0, u0 output bit 7 feeds u1, and u1 output bit 4 feeds
the scan output. Both enables connect to test-mode bit 2. This only establishes
graph connectivity. The fixture SDFF is a black-box declaration, not a validated
library cell. No commercial DFT, fault simulator or ATPG oracle was used.

## Evidence boundary

`scan_chain` is a deterministic traversal, not proof of a valid chain when
diagnostics report errors. `cell_inventory` covers selected-top instances only;
source attributes are copied from input, not authenticated. Unknown cell types
remain visible. A scan type omitted from the state inventory gets an explicit
unverified reason. Neither policy naming nor a complete path proves a cell's
shift/capture behavior, clock/reset operation or mode reachability.

No OpenTitan or Caliptra DFT pilot passes here. Approved mapped scan libraries,
test protocols, exclusions and independent fault/ATPG results remain needed for
the roadmap's real-design qualification. No application RTL/DV was changed.
Local logs and the fixture report are under `../evidence/dft-strict-inventory/`;
they are development evidence, not published release artifacts.
