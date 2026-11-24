#!/bin/sh
# tools/gen-docs.py makes a few documents written for it (their Markdown, a long one to cut) into pages
# tools/check-site.py passes, with their links where they should go
cd "$(dirname "$0")/.." || exit 1
fail() { echo "check-docs: $*"; exit 1; }

tmp=$(mktemp -d) || exit 1
trap '[ -n "$KEEP" ] || rm -rf "$tmp"' EXIT
mkdir -p "$tmp/docs/guide"
cat > "$tmp/docs/README.md" <<'EOF'
<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# The documents

- [A long guide](guide/long.md): see [its tables](guide/long.md#tables-3) and the [source](../src/main.c)
  - nested, with `<id>` as text and **strong** and *emphasis*
1. one
2. two

```sh
echo "a <b> & c"
```
EOF
python3 - "$tmp/docs/guide/long.md" <<'EOF'
import sys
out = ['# A long guide', '', 'It is cut at its sections.', '']
for k in range(1, 6):
    out += [f'## Tables {k}', '', f'Back to [the documents](../README.md) and to [section 1](#tables-1).', '',
            '| name | value |', '| --- | ---: |'] + [f'| row {k}.{i} with some words to fill it | {i} |' for i in range(400)]
    out += ['']
open(sys.argv[1], 'w').write('\n'.join(out))
EOF
python3 tools/gen-docs.py "$tmp/docs" "$tmp/site/manual/snx" --commit 0123456789abcdef0123456789abcdef01234567 >/dev/null ||
    fail "the documents were not made"
cp tools/manual/manual.css "$tmp/site/manual/"
python3 tools/check-site.py "$tmp/site" >/dev/null || fail "a page failed check-site.py"
d=$tmp/site/manual/snx
[ -f "$d/index.html" ] && [ -f "$d/guide/long.html" ] && [ -f "$d/guide/long/tables-3.html" ] ||
    fail "pages missing: $(cd "$d" && find . -name '*.html' | tr '\n' ' ')"
ls "$d"/guide/long/tables-1-*.html >/dev/null 2>&1 || fail "a section over 16 KB was not cut"
grep -q '<th>name</th>' "$d"/guide/long/tables-1-2.html || fail "a cut table does not repeat its header"
grep -q 'href="guide/long/tables-3.html#tables-3"' "$d/index.html" || fail "a heading's link is not to its page"
grep -q 'href="https://github.com/scarletnx/ScarletNX/blob/0123456789abcdef0123456789abcdef01234567/src/main.c"' \
    "$d/index.html" || fail "a link out of docs/ is not to the repository"
grep -q '<code>&lt;id&gt;</code>' "$d/index.html" || fail "code is not escaped"
grep -q 'echo &quot;a &lt;b&gt; &amp; c&quot;\|echo "a &lt;b&gt; &amp; c"' "$d/index.html" || fail "a fence is not escaped"
grep -q '<strong>strong</strong> and <em>emphasis</em>' "$d/index.html" || fail "no emphasis"
grep -q '<ol>' "$d/index.html" && grep -q '<ul>' "$d/index.html" || fail "no lists"
grep -q 'href="../../index.html"' "$d/guide/long/tables-2.html" || fail "a link back to README.md is not to index.html"
grep -q 'href="tables-1.html#tables-1"' "$d/guide/long/tables-2.html" || fail "a link to another section's heading"
echo "check-docs: passed"
