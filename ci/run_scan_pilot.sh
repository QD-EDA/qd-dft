#!/usr/bin/env bash
# Rebuild the bounded pilot toolchain from immutable upstream commits.
set -euo pipefail
repo=$(pwd)
work=${1:?usage: ci/run_scan_pilot.sh NEW_WORK_DIRECTORY}
mkdir "$work"
work=$(cd "$work" && pwd)
mkdir "$work/evidence" "$work/prefix"
exec > >(tee "$work/evidence/bootstrap.log") 2>&1
set -x
fetch() {
  git init "$work/$1"
  git -C "$work/$1" remote add origin "$2"
  git -C "$work/$1" fetch --depth 1 origin "$3"
  git -C "$work/$1" checkout --detach FETCH_HEAD
  test "$(git -C "$work/$1" rev-parse HEAD)" = "$3"
}
fetch yosys https://github.com/YosysHQ/yosys.git 80ba43d26264738c93900129dc0aab7fab36c53f
fetch iverilog https://github.com/steveicarus/iverilog.git 4fd5291632232fbe1ba49b2c26bb6b2bf1c6c9cf
fetch caliptra https://github.com/chipsalliance/caliptra-rtl.git 49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e
for source in yosys iverilog caliptra; do
  git -C "$work/$source" rev-parse HEAD >> "$work/evidence/source-revisions.txt"
done
uname -a > "$work/evidence/host.txt"
cat /etc/os-release >> "$work/evidence/host.txt"
python3 --version >> "$work/evidence/host.txt"
g++ --version >> "$work/evidence/host.txt"
dpkg-query -W > "$work/evidence/packages.txt"
git rev-parse HEAD > "$work/evidence/qd-dft-revision.txt"
(
  cd "$work/yosys"
  make config-gcc
  make -j2 ENABLE_ABC=0 PREFIX="$work/prefix"
  make install ENABLE_ABC=0 PREFIX="$work/prefix"
  git diff --exit-code
) > "$work/evidence/yosys-build.log" 2>&1
(
  cd "$work/iverilog"
  sh autoconf.sh
  ./configure --prefix="$work/prefix"
  make -j2
  make install
  git diff --exit-code
) > "$work/evidence/iverilog-build.log" 2>&1
find "$work/prefix" -type f -print0 | sort -z | xargs -0 sha256sum > "$work/evidence/tool-files.sha256"
export PATH="$work/prefix/bin:$PATH"
cd "$repo"
python3 -m unittest discover -s tests -v > "$work/evidence/python-tests.log" 2>&1
/usr/bin/time -v -o "$work/evidence/pilot-resource.log" \
  python3 run_caliptra_scan_pilot.py "$work/caliptra" "$work/evidence/pilot" \
  > "$work/evidence/pilot.log" 2>&1
