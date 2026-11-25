#!/bin/sh
# tools/build-site.sh makes the site when a part of it fails: of tests/sail (which has no docs/), of a copy of it with
# a manual's sources, a schema and a Java file broken, of no checkout at all; and check-site.py --drop puts out of
# the site a part whose pages fail, a page in its place
cd "$(dirname "$0")/.." || exit 1
fail() { echo "check-build: $*"; exit 1; }
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT

# a part the checkout lacks (docs/): the rest is made, a page in its place, status 3
sh tools/build-site.sh tests/sail "$tmp/a" >"$tmp/a.log" 2>&1
[ $? = 3 ] || { cat "$tmp/a.log"; fail "tests/sail: not status 3"; }
grep -q 'Not made this time' "$tmp/a/manual/snx/index.html" || fail "tests/sail: no page in manual/snx/'s place"
[ -f "$tmp/a/manual/sm53/IADD.html" ] && [ -f "$tmp/a/manual/cs-book/index.html" ] || fail "tests/sail: a part is missing"

# sources broken: what reads them alone fails
cp -R tests/sail "$tmp/broken"
echo 'BROKEN      0101 ...' >>"$tmp/broken/src/3ds/gpu/pica.decode"
printf 'package android.broken\n' >"$tmp/broken/src/android/framework/android/app/Broken.java"
printf 'interface snx::ctr::bad is bad: {\n    [zz] Oops();\n}\n' >"$tmp/broken/src/3ds/services/bad.swipc"
rm "$tmp/broken/src/common/cpu/aarch64/sail/a64.sail"
sh tools/build-site.sh "$tmp/broken" "$tmp/b" >"$tmp/b.log" 2>&1
[ $? = 3 ] || { cat "$tmp/b.log"; fail "broken: not status 3"; }
grep -q 'could not be made from ScarletNX at [0-9a-z]*: <code>GenError: src/3ds/gpu/pica.decode: BROKEN: 7 bits, not 32</code>' \
    "$tmp/b/manual/pica/index.html" || fail "broken: pica's page doesn't say why"
grep -q 'could not be made' "$tmp/b/manual/a64/index.html" || fail "broken: no page in a64's place"
grep -q 'A64</a>: the AArch64 instruction set, as a Switch program runs it (not made this time)' "$tmp/b/manual/index.html" ||
    fail "broken: the manuals' index doesn't say A64 isn't made"
for f in usse/LIMM.html a32/BX.html 3ds-ipc/srv.html android/c/android.app.Activity.html nvn/index.html; do
    [ -f "$tmp/b/manual/$f" ] || fail "broken: no $f"
done
grep -q 'gen-manual: src/android/framework/android/app/Broken.java: IndexError' "$tmp/b.log" ||
    fail "broken: the Java file's failure isn't told"
grep -q '/tmp\|/home' "$tmp/b/manual/pica/index.html" && fail "broken: a page names the machine's paths"

# no checkout: every part the main page links to has a page
sh tools/build-site.sh "$tmp/none" "$tmp/c" >"$tmp/c.log" 2>&1
[ $? = 3 ] || { cat "$tmp/c.log"; fail "no checkout: not status 3"; }
for part in $(grep -o 'href="manual/[^"]*/"' index.html | sed 's/^href="//; s|"$||'); do
    [ -f "$tmp/c/${part}index.html" ] || fail "no checkout: nothing at $part"
done

# a page over the size: its part goes, the rest stays
mkdir -p "$tmp/d/manual/big" "$tmp/d/manual/fine"
cp tests/pages/manual/ok.html "$tmp/d/manual/fine/index.html"
python3 -c 'import sys; open(sys.argv[1], "w").write("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>x</title></head><body><p>" + "x" * 20000 + "</p></body></html>")' "$tmp/d/manual/big/index.html"
python3 tools/check-site.py --drop "$tmp/d" >/dev/null
[ $? = 3 ] || fail "--drop: not status 3"
grep -q 'Not made this time' "$tmp/d/manual/big/index.html" || fail "--drop: the big page's part stays"
cmp -s tests/pages/manual/ok.html "$tmp/d/manual/fine/index.html" || fail "--drop: a part that passes went"
python3 tools/check-site.py "$tmp/d" >/dev/null || fail "--drop: the site still fails"
echo "check-build: passed"
