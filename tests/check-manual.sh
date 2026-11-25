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
has a64/adc.html '<td colspan="5" class="lr f">Rd</td>'                                 # a field the encoding leaves free
has a64/adc.html '<td colspan="1" class="droppedname">op</td>'                        # a field it fixes, named under it
has a64/adc.html 'x0011010000xxxxx000000xxxxxxxxxx'
has a64/adc.html '<a href="fn/AddWithCarry.html">AddWithCarry</a>'                   # the shared pseudocode
has a64/adc.html '>Operation <a class="src" href="https://github.com/scarletnx/ScarletNX/blob/0123456789abcdef'
has a64/cfinv.html '<td colspan="4" class="droppedname">CRm</td>'                     # a field fixed whole
has a64/adc.html '<p class="legend">'                                                # the colours' legend
has a64/adc.html '<td class="l b">1</td>'                                             # a fixed bit, coloured
has a64/fn/AddWithCarry.html '<a href="../adc.html">ADC</a>'                         # used by
has a64/fn/Strip.html "ScarletNX's fixup"
has a32/BX.html 'cond != 1111'
has a32/BX.html 'ArchVersion() &lt; 5'                                                # arm.sail's own clause
has a32/BX.html '<td colspan="4" class="lr f">Rm</td>'                                 # a field passed straight in
has a64/data.js '"ADC","a64/adc.html#Integer_arithmetic_add_sub_carry","A64"'
has a32/data.js '"BX","a32/BX.html#A1","A32","A1","ffffff0","12fff10","f0000000","f0000000"'

# the GPUs': the opcode from the encodings' file, the decoder's fields and the Sail's, the operation and its fusions
for f in sm53/index.html sm53/IADD.html sm53/MOV32I.html sm53/KIL.html sm53/fn/IntegerAdd.html sm53/data.js \
         sm86/index.html sm86/IADD3.html sm86/UIADD3.html sm86/EXIT.html sm86/fn/CarryIn.html sm86/data.js; do
    [ -f "$tmp/manual/$f" ] || fail "no $f"
done
has sm53/IADD.html '<h2 class="classheading" id="IADD_C">IADD (cbuf)</h2>'
has sm53/IADD.html '<td colspan="8" class="lr f">Rd</td>'                              # Dst() of sm53.sail
has sm53/IADD.html '<td colspan="5" class="lr f">cbuf.bank</td>'                        # the right operand by the form
has sm53/IADD.html 'bits 63:48: 0011 100- 0001 0---'
has sm53/IADD.html 'with <code>Form()</code> 2'

has sm53/IADD.html '<tr><td>[43]</td><td>43</td><td>execute_IADD</td></tr>'          # a field the Sail reads
has sm53/KIL.html 'has no operation for it'

has sm86/IADD3.html '<td colspan="3" class="lr f">q</td>'                               # let q = UInt(Field(84, 3))
has sm86/IADD3.html 'CarryIn(87)'                                                     # PredAt(lo) with lo = 87
has sm86/IADD3.html '<td>7 (111)</td><td>Rb at 64</td><td>URc at 32</td>'
has sm86/IADD3.html 'Fusion IADD3_WIDE'
has sm86/UIADD3.html '<td colspan="6" class="lr f">URd</td>'
has sm86/data.js '["IADD3","sm86/IADD3.html#IADD3","SM86","form 1","fff","210","0","0","0"]'
has sm53/data.js '["IADD","sm53/IADD.html#IADD_I","SM53","IADD (imm)","fef8","3810","0","0","3"]'

# the PICA200's and the USSE's: every bit and field from the encodings' file (a format's, a field put together from
# several places), which of the Sail's functions read each, the overlapping patterns' order, and the whole word's
# mask and value
for f in pica/index.html pica/ADD.html pica/MADI.html pica/arithmetic.html pica/flow-control.html pica/fn/Source.html \
         pica/data.js usse/index.html usse/LIMM.html usse/VMOV.html usse/SOP3.html usse/moves.html usse/data.js; do
    [ -f "$tmp/manual/$f" ] || fail "no $f"
done
has pica/ADD.html '<td colspan="5" class="lr f">dest</td>'                              # @arith's field
has pica/ADD.html 'bits 31:0: 0000 00xx xxxx xxxx xxxx xxxx xxxx xxxx'
has pica/ADD.html 'Its format is <code>@arith</code>: format 1: src1 takes the address register'
has pica/ADD.html '<tr><td>dest</td><td>25:21</td><td>ArithDest</td></tr>'               # Field(21, 5), through a call
has pica/ADD.html 'with <code>Form()</code> 0'
has pica/MADI.html '<td class="l b">1</td><td class="b">1</td><td class="r b">0</td>'    # a 3-bit opcode
has pica/arithmetic.html '<a href="ADD.html">ADD</a>'                                      # the Sail's section
has pica/fn/Source.html '<a href="../MAD.html">MAD</a>'                                   # execute_MAD's page: the roots line's first
has pica/data.js '["MOV","pica/MOV.html#MOV","PICA","Arithmetic","fc000000","4c000000","0","0","17"]'
has usse/LIMM.html '<td colspan="6" class="lr f">imm[31:26]</td>'                         # %limm_imm's first piece
has usse/LIMM.html '<tr><td>imm</td><td>49:44, 40:36, 20:0</td><td>execute_LIMM</td></tr>'
has usse/LIMM.html 'the decoder tries them in this order'
has usse/LIMM.html '<a href="SMP.html">SMP</a>'
has usse/VMOV.html '<tr><td>dest_ext</td><td>51</td><td>Bit(51)</td></tr>'                 # Bit(lo) with lo = 51
has usse/SOP3.html 'has no operation for it'
has usse/moves.html '<a href="VMOV.html">VMOV</a>'                                        # the family of usse_data.roots
has usse/data.js '["LIMM","usse/LIMM.html#LIMM","USSE","Moves","ff30000000000000","fc20000000000000","0","0","31"]'
has sm53/index.html '<a href="../usse/">USSE ISA</a>'
has index.html '<a href="pica/">PICA200 ISA</a>'

# the NVN API: signatures and handlers from nvn.hook, Switch 2's marks from tools/manual/nvn-drivers.txt, nvn.h's
# enums, and the formats' Vulkan equivalents from vk/format.c
for f in nvn/index.html nvn/device.html nvn/command_buffer.html nvn/enums.html nvn/types.html nvn/missing.html \
         nvn/f/nvnDeviceFinalize.html nvn/f/nvnBootstrapLoader.html nvn/e/NVNformat.html nvn/e/NVNshaderStage.html \
         nvn/t/NVNdlssParameters.html nvn/data.js; do
    [ -f "$tmp/manual/$f" ] || fail "no $f"
done
has nvn/f/nvnDeviceFinalize.html '<pre class="sig">void nvnDeviceFinalize(<a href="../t/NVNdevice.html">NVNdevice</a>* d)</pre>'
has nvn/f/nvnDeviceFinalize.html '/src/nx/gpu/nvn/nvn_object.c#L5"><code>nvn_DeviceFinalize</code>'
# nvn.hook's doc comments (## @brief, @param, @return; a line going on with the one before), names linked
has nvn/f/nvnDeviceFinalize.html '<p>End a device: its object is not valid any more, and nothing is freed</p>'
has nvn/f/nvnDeviceFinalize.html '<td><code>d</code></td><td><a href="../t/NVNdevice.html">NVNdevice</a>*</td><td>Pointer to the device, NULL is invalid. If it is the current device (the last nvnDeviceInitialize made), ScarletNX has no current device after it</td>'
has nvn/f/nvnDeviceGetDepthMode.html '<h2>Returns</h2><p>The mode nvnDeviceSetDepthMode gave, <a href="../e/NVNdepthMode.html#NVN_DEPTH_MODE_NEAR_IS_MINUS_W">NVN_DEPTH_MODE_NEAR_IS_MINUS_W</a> after <a href="../f/nvnDeviceFinalize.html">nvnDeviceFinalize</a></p>'
has nvn/device.html '<td>Get the depth mode of a device</td>'
grep -q '<h2>Parameters' "$tmp/manual/nvn/f/nvnCommandBufferSetConservativeRasterEnable.html" &&
    fail "a function with no doc comment has a parameters' table"
has nvn/f/nvnCommandBufferSetComputeWorkloadPriority.html '<span class="s2">Switch 2</span>'
has nvn/f/nvnCommandBufferSetComputeWorkloadPriority.html "<p>Switch 2&#x27;s (API 231): a priority"
has nvn/f/nvnCommandBufferPopDebugGroupId.html '<span class="s1">Switch 1</span>'               # NVN2 dropped it
grep -q 'a priority' "$tmp/manual/nvn/f/nvnCommandBufferSetConservativeRasterEnable.html" &&
    fail "a Switch 2 comment ran on into a function both have"
has nvn/e/NVNshaderStage.html '<td id="NVN_SHADER_STAGE_MESH">NVN_SHADER_STAGE_MESH <span class="s2">Switch 2</span>'
has nvn/e/NVNformat.html 'VkFormat.html#:~:text=VK_FORMAT_BC1_RGBA_UNORM_BLOCK%20specifies">VK_FORMAT_BC1_RGBA_UNORM_BLOCK</a>'
has nvn/e/NVNformat.html '>VK_FORMAT_D24_UNORM_S8_UINT</a>'                                   # through the depth targets
has nvn/e/NVNformat.html '>VK_FORMAT_ASTC_4x4_UNORM_BLOCK</a>'
has nvn/e/NVNformat.html '>VK_FORMAT_R8G8B8A8_UNORM</a> (converted to it on upload)'
has nvn/t/NVNdlssParameters.html '<h1>NVNdlssParameters <span class="s2">Switch 2</span></h1>'
has nvn/data.js '["nvnCommandBufferSetComputeWorkloadPriority","nvn/f/nvnCommandBufferSetComputeWorkloadPriority.html","NVN","function, Switch 2"]'
has nvn/index.html 'data-load="../nvn/data.js"'

# the 3DS IPC: src/3ds/services/*.swipc's commands, word by word as swipc --ctr lays them out (tools/swipc/ctr.inc),
# and the handlers in the services' C
for f in 3ds-ipc/index.html 3ds-ipc/srv.html 3ds-ipc/hid_USER.html 3ds-ipc/fs_USER.html 3ds-ipc/data.js; do
    [ -f "$tmp/manual/$f" ] || fail "no $f"
done
has 3ds-ipc/srv.html 'command 0x5: request 0x00050100, response 0x00050042'                # 3dbrew's headers
has 3ds-ipc/srv.html '<tr><td>2</td><td><code>name, bytes 4-7</code>: bytes&lt;8&gt;</td></tr>'
has 3ds-ipc/srv.html '<tr><td>2</td><td>0x10: moved handle, 1</td></tr>'
has 3ds-ipc/srv.html "<tr><td>1</td><td>0x20: the calling process's ID follows</td></tr>"  # RegisterClient's pid
has 3ds-ipc/srv.html 'uint32_t snx_ctr_srv_GetServiceHandle(SnxCtrIpc* c, const uint8_t* a_name, uint32_t a_length, uint32_t a_flags, uint32_t* a_session)'
has 3ds-ipc/srv.html '/src/3ds/services/srv.c#L28">srv.c, line 28</a>'
has 3ds-ipc/hid_USER.html 'command 0xa: request 0x000a0000, response 0x000a0047'
has 3ds-ipc/hid_USER.html '<tr><td>2</td><td>0x14000000: copied handles, 6</td></tr>'      # six copied: one descriptor
has 3ds-ipc/hid_USER.html 'which has the same commands'                                    # the comment over the interface
has 3ds-ipc/fs_USER.html '<tr><td>2</td><td><code>archive, high word</code>: u64</td></tr>'
has 3ds-ipc/data.js '["GetServiceHandle","3ds-ipc/srv.html#GetServiceHandle","3DS","srv: 0x5","ffff0000","50000","0","0","5"]'
has index.html '<a href="3ds-ipc/">3DS IPC</a>'
has nvn/index.html '<a href="../3ds-ipc/">3DS IPC</a>'

# the same Sail makes the same manual
python3 tools/gen-manual.py tests/sail "$tmp/again" --commit 0123456789abcdef0123456789abcdef01234567 >/dev/null
diff -r "$tmp/manual" "$tmp/again" >/dev/null || fail "two runs differ"
echo "check-manual: passed"
