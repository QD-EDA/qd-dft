# Pinned Linux scan-pilot lane

The separate `Caliptra scan pilot` workflow runs on pull requests, main pushes and
manual dispatch. The existing Python smoke workflow remains unchanged. It builds
an explicit compatibility lane for the generic insertion pilot:

| Input | Immutable revision |
|---|---|
| Yosys 0.44 | `80ba43d26264738c93900129dc0aab7fab36c53f` |
| Icarus Verilog 12.0 | `4fd5291632232fbe1ba49b2c26bb6b2bf1c6c9cf` |
| Caliptra RTL v2.1.2 | `49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e` |

These are additional tested versions, not substitutions for the earlier local
Yosys 0.68+80/Icarus 13 evidence. Source revisions are verified after fetching.
Yosys builds with GCC and ENABLE_ABC=0: this pilot uses no ABC mapping pass.
No existing analysis or test is disabled. Icarus is built with its standard
configure/make flow. No application RTL/DV is changed.

Build instructions are based on the pinned upstream
[Yosys README](https://github.com/YosysHQ/yosys/blob/80ba43d26264738c93900129dc0aab7fab36c53f/README.md)
and [Icarus README](https://github.com/steveicarus/iverilog/blob/4fd5291632232fbe1ba49b2c26bb6b2bf1c6c9cf/README.md).

On Ubuntu 24.04 with the dependencies listed in `.github/workflows/scan-pilot.yml`:

```sh
bash ci/run_scan_pilot.sh /tmp/new-qd-scan-build
```

The directory must not exist. The script fetches only the named source revisions,
builds and installs into its own prefix, runs the Python suite, and invokes
run_caliptra_scan_pilot.py. Tool-source tracked diffs must remain empty after
building. This is a generic four-bit scan-bank pilot, not a chip-level scan flow.

The job has a 35-minute limit; individual pilot commands retain their 120-second
limit. Positive equivalence and simulation must pass, and both planted faults
must fail at the expected checks. The job archives evidence on success or failure:
source IDs, installed file hashes, OS/compiler/Python/package inventory, build
logs, Python tests, pilot input hashes, netlists, manifest, generated scripts,
exact argv, status, timing, stdout/stderr and aggregate pilot resource usage.
The workflow uses read-only repository permissions and immutable action commits.
Artifacts are retained for 30 days. They are CI evidence, not permanent release
bundles; a qualified release must preserve its own immutable archive.

## Limits

The hosted Ubuntu image, apt repositories, compiler and system dependencies are
recorded rather than hermetically pinned. Binary identity is measured, not
promised reproducible from source alone. This lane is independent of the local
macOS development workspace, but uses the same QD harness and property. It does
not add an independent commercial DFT oracle, physical library, STA, ATPG or fault
coverage. All unsupported cases and UNKNOWN qualification in
GENERIC_INSERTION_EVIDENCE.md remain in force.

## Verified first Linux run

[Run 35899115255](https://github.com/QD-EDA/qd-dft/actions/runs/35899115255)
passed for code commit `0e83365de7aab8206a8567f5cb1e1c5ebfc8701b`.
The archived artifact `caliptra-scan-35899115255-1` has GitHub digest
`sha256:31ce156302af0cbd3c4116744e7b7b5fe1e3f3ba058dd95c10002ea14f346c1b`.
Its logs were downloaded and inspected: all four output equivalence cells were
proved, the injected functional fault left one unproven cell and exited 1,
the independent simulation passed all 16 capture/shift patterns plus X/reset
checks, and the broken scan link failed at the expected comparison. All 21
Python tests passed. No result is inferred solely from the workflow badge.

Host: Ubuntu 24.04.5 x86-64, Python 3.12.3, GCC 13.3.0. The built tools report
Yosys 0.44 (`80ba43d26`, no dirty marker) and Icarus/vvp 12.0. The full uncached
job took 15m49s. Pilot wall time was 0.25 s and maximum RSS 21,248 KiB from GNU
time (the pilot and child processes, not the toolchain build). Insertion took
0.0401 s, equivalence 0.0075 s and positive simulation 0.0041 s. These are tiny-pilot
measurements, not scalability qualification. Build caching remains future work;
no checks were removed to reach a timing target.

The downloaded evidence is also retained locally under
`../evidence/dft-pinned-linux/run35899115255/`. This expands the observed matrix
with an independent Linux host and clean pinned tool sources; the full production
qualification requirements remain unmet.
