#!/bin/sh
# tools/check-site.py passes the site as it is and names every failure of a page made of them
cd "$(dirname "$0")/.." || exit 1
python3 tools/check-site.py || exit 1
out=$(python3 tools/check-site.py tests/pages/bad.html) && { echo "bad.html passed"; exit 1; }
for what in 'onload attribute' '<style>' 'style attribute' 'stylesheet' '<script>' 'javascript: link' '<canvas>' '<video>'; do
    case "$out" in *"$what"*) ;; *) echo "bad.html: no failure for $what"; exit 1 ;; esac
done
head -c 17000 /dev/zero | tr '\0' 'x' > tests/pages/big.html
python3 tools/check-site.py tests/pages/big.html | grep -q 'over 16384' || { echo "a 17000-byte page passed"; rm -f tests/pages/big.html; exit 1; }
rm -f tests/pages/big.html
# the book (manual/cs-book/): MathJax, figures and its stylesheet, 64 KB pages, and no more
python3 tools/check-site.py tests/pages/manual/cs-book/ok.html >/dev/null || { echo "cs-book/ok.html failed"; exit 1; }
out=$(python3 tools/check-site.py tests/pages/manual/cs-book/bad.html) && { echo "cs-book/bad.html passed"; exit 1; }
for what in 'stylesheet other than book.css' 'script from https://example.com' '<canvas>' 'style attribute'; do
    case "$out" in *"$what"*) ;; *) echo "cs-book/bad.html: no failure for $what"; exit 1 ;; esac
done
big=tests/pages/manual/cs-book/big.html
head -c 60000 /dev/zero | tr '\0' 'x' > $big
python3 tools/check-site.py $big >/dev/null || { echo "a 60000-byte page of the book failed"; rm -f $big; exit 1; }
head -c 66000 /dev/zero | tr '\0' 'x' > $big
python3 tools/check-site.py $big | grep -q 'over 65536' || { echo "a 66000-byte page of the book passed"; rm -f $big; exit 1; }
rm -f $big
echo "check-site: passed"
