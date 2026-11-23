/* sail-arm's definitions that a64.roots reaches (sailgen --extract), as they are in:
     instrs64.sail
     v8_base.sail
   BSD 3-Clause Clear License: LICENSE beside this file. Do not edit: a system's fixup goes in its overlay
   (README.md beside this file) */

val execute_aarch64_instrs_integer_arithmetic_add_sub_carry : forall 'd 'datasize 'm 'n ('setflags : Bool) ('sub_op : Bool),
  (0 <= 'n & 'n <= 31 & 0 <= 'm & 'm <= 31 & 'datasize in {32, 64} & 0 <= 'd & 'd <= 31).
  (int('d), int('datasize), int('m), int('n), bool('setflags), bool('sub_op)) -> unit

function execute_aarch64_instrs_integer_arithmetic_add_sub_carry (d, datasize, m, n, setflags, sub_op) = {
    result : bits('datasize) = undefined;
    let operand1 : bits('datasize) = X_read(n, datasize);
    operand2 : bits('datasize) = X_read(m, datasize);
    nzcv : bits(4) = undefined;
    if sub_op then {
        operand2 = not_vec(operand2)
    };
    (result, nzcv) = AddWithCarry(operand1, operand2, PSTATE.C);
    if setflags then {
        (PSTATE.N @ PSTATE.Z @ PSTATE.C @ PSTATE.V) = nzcv
    };
    X_set(d, datasize) = result
}

val decode_adc_aarch64_instrs_integer_arithmetic_add_sub_carry : (bits(5), bits(5), bits(5), bits(1), bits(1), bits(1)) -> unit

function decode_adc_aarch64_instrs_integer_arithmetic_add_sub_carry (Rd, Rn, Rm, S, op, sf) = {
    let 'd = UInt(Rd);
    let 'n = UInt(Rn);
    let 'm = UInt(Rm);
    let 'datasize = if sf == 0b1 then 64 else 32;
    let sub_op : bool = op == 0b1;
    let setflags : bool = S == 0b1;
    execute_aarch64_instrs_integer_arithmetic_add_sub_carry(d, datasize, m, n, setflags, sub_op)
}

function clause __DecodeA64_DataProcReg ((pc, ([_, bitzero, bitzero, bitone, bitone, bitzero, bitone, bitzero, bitzero, bitzero, bitzero, _, _, _, _, _, bitzero, bitzero, bitzero, bitzero, bitzero, bitzero, _, _, _, _, _, _, _, _, _, _] as __opcode)) if SEE < 6) = {
    SEE = 6;
    let Rd = Slice(__opcode, 0, 5);
    let Rn = Slice(__opcode, 5, 5);
    let Rm = Slice(__opcode, 16, 5);
    let S = Slice(__opcode, 29, 1);
    let op = Slice(__opcode, 30, 1);
    let sf = Slice(__opcode, 31, 1);
    decode_adc_aarch64_instrs_integer_arithmetic_add_sub_carry(Rd, Rn, Rm, S, op, sf)
}

val decode_cfinv_aarch64_instrs_integer_flags_cfinv : bits(4) -> unit

function decode_cfinv_aarch64_instrs_integer_flags_cfinv CRm = {
    if not_bool(HaveFlagManipulateExt()) then {
        throw(Error_Undefined())
    };
    execute_aarch64_instrs_integer_flags_cfinv()
}

function clause __DecodeA64_BranchExcSys ((pc, (0b11010101000000000100000000011111 as __opcode)) if SEE < 123) = {
    SEE = 123;
    let CRm = Slice(__opcode, 8, 4);
    if (([__opcode[8]] != 0b0 | [__opcode[9]] != 0b0) | [__opcode[10]] != 0b0) | [__opcode[11]] != 0b0 then {
        throw(Error_ConstrainedUnpredictable())
    } else {
        decode_cfinv_aarch64_instrs_integer_flags_cfinv(CRm)
    }
}

val AddWithCarry : forall 'N, 'N > 0.
  (bits('N), bits('N), bits(1)) -> (bits('N), bits(4))

function AddWithCarry (x, y, carry_in) = {
    let 'unsigned_sum = UInt(x) + UInt(y) + UInt(carry_in);
    let 'signed_sum = SInt(x) + SInt(y) + UInt(carry_in);
    let result : bits('N) = unsigned_sum['N - 1 .. 0];
    let n : bits(1) = [result['N - 1]];
    let z : bits(1) = if IsZero(result) then 0b1 else 0b0;
    let c : bits(1) = if UInt(result) == unsigned_sum then 0b0 else 0b1;
    let v : bits(1) = if SInt(result) == signed_sum then 0b0 else 0b1;
    return((result, ((n @ z) @ c) @ v))
}
