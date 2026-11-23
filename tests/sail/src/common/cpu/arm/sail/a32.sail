/* sail-arm's definitions that a32.roots reaches (sailgen --extract), as they are in:
     instrs32.sail
     v8_base.sail
   BSD 3-Clause Clear License: LICENSE beside this file. Do not edit: a system's fixup goes in its overlay
   (README.md beside this file) */

val execute_aarch32_instrs_BX_Op_A_txt : forall 'm, (0 <= 'm & 'm <= 15).
  int('m) -> unit

function execute_aarch32_instrs_BX_Op_A_txt m = {
    BXWritePC(R_read(m), BranchType_INDIR)
}

val decode_aarch32_instrs_BX_A1enc_A_txt : (bits(4), bits(4)) -> unit

function decode_aarch32_instrs_BX_A1enc_A_txt (cond, Rm) = {
    if ConditionPassed() then {
        assert(cond != 0b1111);
        let 'm = UInt(Rm);
        execute_aarch32_instrs_BX_Op_A_txt(m)
    };
    ()
}

function clause __DecodeA32_DataProMisc ((pc, ([_, _, _, _, bitzero, bitzero, bitzero, bitone, bitzero, bitzero, bitone, bitzero, bitone, bitone, bitone, bitone, bitone, bitone, bitone, bitone, bitone, bitone, bitone, bitone, bitzero, bitzero, bitzero, bitone, _, _, _, _] as __opcode)) if Slice(__opcode, 28, 4) != 0b1111 & SEE < 2874) = {
    SEE = 2874;
    let cond = Slice(__opcode, 28, 4);
    let Rm = Slice(__opcode, 0, 4);
    if (((((((((([__opcode[16]] != 0b1 | [__opcode[17]] != 0b1) | [__opcode[18]] != 0b1) | [__opcode[19]] != 0b1) | [__opcode[12]] != 0b1) | [__opcode[13]] != 0b1) | [__opcode[14]] != 0b1) | [__opcode[15]] != 0b1) | [__opcode[8]] != 0b1) | [__opcode[9]] != 0b1) | [__opcode[10]] != 0b1) | [__opcode[11]] != 0b1 then {
        throw(Error_ConstrainedUnpredictable())
    } else {
        decode_aarch32_instrs_BX_A1enc_A_txt(cond, Rm)
    }
}

val decode_aarch32_instrs_BX_T1enc_A_txt : bits(4) -> unit

function decode_aarch32_instrs_BX_T1enc_A_txt Rm = {
    if ConditionPassed() then {
        let 'm = UInt(Rm);
        if InITBlock() & not_bool(LastInITBlock()) then {
            throw(Error_Unpredictable())
        };
        execute_aarch32_instrs_BX_Op_A_txt(m)
    };
    ()
}

function clause __DecodeT16 ((pc, ([bitzero, bitone, bitzero, bitzero, bitzero, bitone, bitone, bitone, bitzero, _, _, _, _, bitzero, bitzero, bitzero] as __opcode)) if SEE < 2875) = {
    SEE = 2875;
    let Rm = Slice(__opcode, 3, 4);
    if ([__opcode[0]] != 0b0 | [__opcode[1]] != 0b0) | [__opcode[2]] != 0b0 then {
        throw(Error_ConstrainedUnpredictable())
    } else {
        decode_aarch32_instrs_BX_T1enc_A_txt(Rm)
    }
}

