#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# tools/build-site.sh SCARLETNX [OUT]: the whole site, made from its sources into OUT (_site), as GitHub Pages
# serves it: the main page and its images, the ISA manuals (ARM's and the GPUs'), the NVN API, the nn API, the 3DS
# IPC, the Android API and the driver bugs (tools/gen-manual.py, from a ScarletNX checkout) in manual/, ScarletNX's documentation
# (tools/gen-docs.py, from its docs/) in manual/snx/, the book (tools/gen-book.py, from book/) in manual/cs-book/.
# Then tools/check-site.py checks every page of it. Nothing it makes is committed: .github/workflows/site.yml runs
# it and deploys OUT.
#
# One part failing doesn't take the site down. Each generator runs alone, and makes what it can: a manual, a page
# or a document it can't make is a page in its place that says why. A generator that stops, a part whose pages fail
# check-site.py, and a part the main page links to that nothing made each become such a page (tools/stand-in.py).
# The exit status is 0 for the whole site, 3 for a site made in part (each failure on stderr, and a warning of the
# run in GitHub's Actions), and 1 when there is no site to deploy (the main page itself fails its checks).
cd "$(dirname "$0")/.." || exit 1
[ -n "$1" ] || { echo "usage: tools/build-site.sh SCARLETNX [OUT]" >&2; exit 2; }
scarletnx=$1
out=${2:-_site}
rm -rf "$out"
mkdir -p "$out" || exit 1
cp index.html "$out/" && cp -R assets "$out/" || exit 1
partial=0

# STEP STATUS PART: a generator's status: 3 is a part made in part, another a part not made
ran() {
    case $2 in
    0) ;;
    3) partial=1 ;;
    *) partial=1
       echo "build-site: $1 stopped (status $2): $3/ is not made" >&2
       [ "$GITHUB_ACTIONS" = true ] && echo "::warning title=build-site::$1 stopped (status $2): $3/ is not made" >&2
       python3 tools/stand-in.py "$out" "$3" "$1 stopped (status $2)" ;;
    esac
}
python3 tools/gen-manual.py "$scarletnx" "$out/manual"
ran tools/gen-manual.py $? manual
python3 tools/gen-docs.py "$scarletnx/docs" "$out/manual/snx"
ran tools/gen-docs.py $? manual/snx
python3 tools/gen-book.py book "$out/manual/cs-book"
ran tools/gen-book.py $? manual/cs-book

# what the main page links to that nothing made
for part in $(grep -o 'href="manual/[^"]*/"' index.html | sed 's/^href="//; s|/"$||' | sort -u); do
    [ -f "$out/$part/index.html" ] && continue
    partial=1
    echo "build-site: $part/ is not made" >&2
    python3 tools/stand-in.py "$out" "$part" "nothing made it (its sources are not in the checkout, or its generator stopped first)"
done

python3 tools/check-site.py --drop "$out"
case $? in 0) ;; 3) partial=1 ;; *) exit 1 ;; esac
python3 tools/check-site.py "$out" || exit 1
[ "$partial" = 0 ] || { echo "build-site: the site is made in part (above)" >&2; exit 3; }
