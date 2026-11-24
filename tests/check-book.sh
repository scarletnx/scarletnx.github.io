#!/bin/sh
# tools/gen-book.py makes the book from book/ into pages tools/check-site.py passes, and refuses a book whose
# text quotes what a program does not print
cd "$(dirname "$0")/.." || exit 1
fail() { echo "check-book: $*"; exit 1; }

tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
python3 tools/gen-book.py book "$tmp/site/manual/cs-book" >/dev/null || fail "the book was not made"
python3 tools/check-site.py "$tmp/site" >/dev/null || fail "a page of the book failed check-site.py"
for f in index.html refs.html book.css 01-limits.html 20-refinekv-practice.html; do
    [ -f "$tmp/site/manual/cs-book/$f" ] || fail "no $f"
done
grep -q 'rel="next" href="refs.html"' "$tmp/site/manual/cs-book/20-refinekv-practice.html" ||
    fail "the last chapter does not lead to the references"

# a program's .out that it no longer prints (01-limits/limit.c is run, not recorded)
cp -R book "$tmp/book"
printf 'x = 1e-1   naive 0.5\n' > "$tmp/book/01-limits/limit.out"
out=$(python3 tools/gen-book.py "$tmp/book" "$tmp/bad" 2>&1) && fail "a wrong .out passed"
case "$out" in *"01-limits/limit.c"*"not its .out"*) ;; *) fail "a wrong .out failed otherwise: $out" ;; esac
echo "check-book: passed"
