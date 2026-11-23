#!/bin/sh
# tools/gen-manual.py makes a manual of tests/sail (a few instructions cut from ScarletNX's Sail) that
# tools/check-site.py passes, laid out as it should be; and check-site.py holds a manual page to its exception
cd "$(dirname "$0")/.." || exit 1
fail() { echo "check-manual: $*"; exit 1; }

python3 tools/check-site.py tests/pages/manual/ok.html >/dev/null || fail "manual/ok.html failed"
out=$(python3 tools/check-site.py tests/pages/manual/bad.html) && fail "manual/bad.html passed"
for what in 'stylesheet other than manual.css' '<style>' 'onload attribute' 'style attribute' 'inline <script>'; do
    case "$out" in *"$what"*) ;; *) fail "manual/bad.html: no failure for $what" ;; esac
done

tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
python3 tools/gen-manual.py tests/sail "$tmp/manual" --commit 0123456789abcdef0123456789abcdef01234567 >/dev/null ||
    fail "the generator failed"
python3 tools/check-site.py $(find "$tmp/manual" -name '*.html') >/dev/null || fail "a generated page failed check-site.py"
for f in index.html manual.css search.js LICENSE-sail-arm.txt a64/index.html a64/adc.html a64/cfinv.html \
         a64/fn/AddWithCarry.html a64/fn/Strip.html a64/data.js a32/index.html a32/BX.html a32/T16.html a32/data.js; do
    [ -f "$tmp/manual/$f" ] || fail "no $f"
done
has() { grep -qF -- "$2" "$tmp/manual/$1" || fail "$1 has no $2"; }
has a64/adc.html '<h1>ADC</h1>'
has a64/adc.html '<td colspan="5" class="lr">Rd</td>'                                 # a field the encoding leaves free
has a64/adc.html '<td colspan="1" class="droppedname">op</td>'                        # a field it fixes, named under it
has a64/adc.html 'x0011010000xxxxx000000xxxxxxxxxx'
has a64/adc.html '<a href="fn/AddWithCarry.html">AddWithCarry</a>'                   # the shared pseudocode
has a64/adc.html '>Operation <a class="src" href="https://github.com/scarletnx/ScarletNX/blob/0123456789abcdef'
has a64/cfinv.html '<td colspan="4" class="droppedname">CRm</td>'                     # a field fixed whole
has a64/fn/AddWithCarry.html '<a href="../adc.html">ADC</a>'                         # used by
has a64/fn/Strip.html "ScarletNX's fixup"
has a32/BX.html 'cond != 1111'
has a32/BX.html 'ArchVersion() &lt; 5'                                                # arm.sail's own clause
has a32/BX.html '<td colspan="4" class="lr">Rm</td>'                                 # a field passed straight in
has a64/data.js '"ADC","a64/adc.html#Integer_arithmetic_add_sub_carry","A64"'
has a32/data.js '"BX","a32/BX.html#A1","A32","A1","ffffff0","12fff10","f0000000","f0000000"'

# the GPUs': the opcode from the encodings' file, the decoder's fields and the Sail's, the operation and its fusions
for f in sm53/index.html sm53/IADD.html sm53/MOV32I.html sm53/KIL.html sm53/fn/IntegerAdd.html sm53/data.js \
         sm86/index.html sm86/IADD3.html sm86/UIADD3.html sm86/EXIT.html sm86/fn/CarryIn.html sm86/data.js; do
    [ -f "$tmp/manual/$f" ] || fail "no $f"
done
has sm53/IADD.html '<h2 class="classheading" id="IADD_C">IADD (cbuf)</h2>'
has sm53/IADD.html '<td colspan="8" class="lr">Rd</td>'                              # Dst() of sm53.sail
has sm53/IADD.html '<td colspan="5" class="lr">cbuf.bank</td>'                        # the right operand by the form
has sm53/IADD.html 'bits 63:48: 0011 100- 0001 0---'
has sm53/IADD.html 'with <code>Form()</code> 2'

has sm53/IADD.html '<tr><td>[43]</td><td>43</td><td>execute_IADD</td></tr>'          # a field the Sail reads
has sm53/KIL.html 'has no operation for it'

has sm86/IADD3.html '<td colspan="3" class="lr">q</td>'                               # let q = UInt(Field(84, 3))
has sm86/IADD3.html 'CarryIn(87)'                                                     # PredAt(lo) with lo = 87
has sm86/IADD3.html '<td>7 (111)</td><td>Rb at 64</td><td>URc at 32</td>'
has sm86/IADD3.html 'Fusion IADD3_WIDE'
has sm86/UIADD3.html '<td colspan="6" class="lr">URd</td>'
has sm86/data.js '["IADD3","sm86/IADD3.html#IADD3","SM86","form 1","fff","210","0","0","0"]'
has sm53/data.js '["IADD","sm53/IADD.html#IADD_I","SM53","IADD (imm)","fef8","3810","0","0","3"]'

# the same Sail makes the same manual
python3 tools/gen-manual.py tests/sail "$tmp/again" --commit 0123456789abcdef0123456789abcdef01234567 >/dev/null
diff -r "$tmp/manual" "$tmp/again" >/dev/null || fail "two runs differ"
echo "check-manual: passed"
