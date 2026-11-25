#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# tools/build-site.sh SCARLETNX [OUT]: the whole site, made from its sources into OUT (_site), as GitHub Pages
# serves it: the main page and its images, the ISA manuals (ARM's and the GPUs') and the NVN API (tools/gen-manual.py, from a ScarletNX
# checkout) in manual/, ScarletNX's documentation (tools/gen-docs.py, from its docs/) in manual/snx/, the book
# (tools/gen-book.py, from book/) in manual/cs-book/. Then tools/check-site.py
# checks every page of it. Nothing it makes is committed: .github/workflows/site.yml runs it and deploys OUT.
set -e
cd "$(dirname "$0")/.."
[ -n "$1" ] || { echo "usage: tools/build-site.sh SCARLETNX [OUT]" >&2; exit 2; }
scarletnx=$1
out=${2:-_site}
rm -rf "$out"
mkdir -p "$out"
cp index.html "$out/"
cp -R assets "$out/"
python3 tools/gen-manual.py "$scarletnx" "$out/manual"
python3 tools/gen-docs.py "$scarletnx/docs" "$out/manual/snx"
python3 tools/gen-book.py book "$out/manual/cs-book"
python3 tools/check-site.py "$out"
