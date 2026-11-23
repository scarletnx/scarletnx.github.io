/* SPDX-License-Identifier: GPL-3.0-or-later
   Copyright 2026 the ScarletNX contributors */

// The ARM7TDMI's BX takes no notice of bits 2 to 0, which should be zero (the later architectures' (0)(0)(0): no clause
// has such a halfword there): it branches with them set, before ARMv5. Sail-arm's BX T1 with no IT block to check
val decode_aarch32_legacy_BX : bits(4) -> unit
function decode_aarch32_legacy_BX Rm = {
    if ConditionPassed() then {
        execute_aarch32_instrs_BX_Op_A_txt(UInt(Rm))
    };
    ()
}
function clause __DecodeT16 ((pc, ([bitzero, bitone, bitzero, bitzero, bitzero, bitone, bitone, bitone, bitzero, _, _, _, _, _, _, _] as __opcode)) if ArchVersion() < 5) = {
    decode_aarch32_legacy_BX(Slice(__opcode, 3, 4))
}
