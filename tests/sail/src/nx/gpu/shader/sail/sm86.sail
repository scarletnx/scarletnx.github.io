/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Copyright 2026 the ScarletNX contributors */
/* SM86's instructions in Sail (sailgen --gpu): what each one computes, from the fields the decoder (sm86.decode)
   leaves in its 128 bits and the operands it found. sm86.roots names the decoder's opcodes each function runs, and
   sm86_spirv.h is the state: the registers, uniform registers and predicates of sm86_translate.c, the operands as its
   src_bits reads them. The field numbers and what they mean are the hand-written translator's notes, NAK's (Mesa's
   nak) and CuAssembler's sm_86 records */

/* the operands an ALU instruction names: a, b, c, and Second, the operand of a two-source instruction (b, or c in the
   forms that keep a register in b's place) */
enum Operand = {A, B, C, Second}

/* bits lo to lo + n - 1 of the instruction, known when the translator runs */
val Field : forall 'n. (int, int('n)) -> bits('n)
/* the instruction is a uniform one (SM86_K_UALU): its destination a uniform register, its predicates uniform */
val Uniform : unit -> bool
/* the operand's 32 bits: a register, a uniform register, an immediate or a constant buffer word */
val SrcBits : Operand -> bits(32)
/* the operand is negated (a register's or a constant's: an immediate has no modifier) */
val SrcNeg : Operand -> bool
/* the operand reads zero whatever the state: the zero register or the immediate 0 */
val IsZero : Operand -> bool
/* the operand is an immediate, and its value */
val SrcIsImm : Operand -> bool
val SrcImm : Operand -> int
/* the destination, a register or a uniform register, written */
val D_write : bits(32) -> unit
/* the destination register the decoder found */
val Dst : unit -> int
/* register r (RZ reads 0) */
val R_read : int -> bits(32)
val R_write : (int, bits(32)) -> unit
/* predicate p, negated when neg is 1, of the uniform predicates when u is 1 (PT reads true) */
val PredRead : (int, int, int) -> bool
/* written unless p is PT */
val PredWrite : (int, bool, int) -> unit
/* A fusion's instructions (sm86.roots' fuse lines): the same of its instruction k, 0 the first */
val FieldAt : forall 'n. (int, int, int('n)) -> bits('n)
val SrcBitsAt : (int, Operand) -> bits(32)
val SrcNegAt : (int, Operand) -> bool
val IsZeroAt : (int, Operand) -> bool
/* the operand of instruction k is the register instruction j writes (none for RZ) */
val ReadsDstAt : (int, Operand, int) -> bool
val D_writeAt : (int, bits(32)) -> unit
/* an instruction the translation refuses: why */
val Unsupported : string -> unit

let PT : int = 7
let RZ : int = 255

/* the predicate operand at lo (its number) and lo + 3 (its negation) */
function PredAt(lo : int) -> bool = PredRead(UInt(Field(lo, 3)), UInt(Field(lo + 3, 1)), Uniform())

/* an integer operand with its negation, 0 - x */
function SrcInt(s : Operand) -> bits(32) = {
    let v = SrcBits(s);
    if SrcNeg(s) then 0x00000000 - v else v
}

/* a term of a 64-bit sum: its two's complement as NAK's fold reads it, ~x + 1 in 33 bits. With the carries in (.X)
   the modifier is the complement alone, ~x: the low word's sum gave the + 1 as a carry. One game's 64-bit
   subtractions are IADD3 a, b, -c then IADD3.X a', b', ~c', and with ~c' + 1 their high word was one too many */
function Term64(s : Operand, x : bool) -> bits(64) = {
    let v = SrcBits(s);
    if not_bool(SrcNeg(s)) then ZeroExtend(v, 64) else {
        let n = ZeroExtend(not_vec(v), 64);
        if x then n else n + 0x0000000000000001
    }
}

/* a carry in, the predicate at lo, as a 64-bit term */
function CarryIn(lo : int) -> bits(64) = if PredAt(lo) then 0x0000000000000001 else 0x0000000000000000

/* IADD3 and UIADD3: a + b + c, with the carries out in the predicates p (81) and q (84) and, for .X (74), two carries
   in (87 and 77) */
function execute_IADD3() -> unit = {
    let p = UInt(Field(81, 3));
    let q = UInt(Field(84, 3));
    let x = Field(74, 1) == 0b1;
    if p >= PT & q >= PT & not_bool(x) then {
        /* the sum of the terms that aren't zero, a register's or an immediate's whatever the state */
        var sum : bits(32) = 0x00000000;
        var any : bool = false;
        if not_bool(IsZero(A)) then {
            sum = SrcInt(A);
            any = true
        };
        if not_bool(IsZero(B)) then {
            if any then { sum = sum + SrcInt(B) } else { sum = SrcInt(B) };
            any = true
        };
        if not_bool(IsZero(C)) then { if any then { sum = sum + SrcInt(C) } else { sum = SrcInt(C) } };
        D_write(sum)
    } else {
        /* the sum in 64 bits: its carries, and .X's two carries in */
        var sum : bits(64) = Term64(A, x) + Term64(B, x);
        sum = sum + Term64(C, x);
        if x then {
            sum = sum + CarryIn(87);
            sum = sum + CarryIn(77)
        };
        let high = sum[63 .. 32];
        D_write(sum[31 .. 0]);
        PredWrite(p, 0 < UInt(high), Uniform());
        PredWrite(q, 1 < UInt(high), Uniform())
    }
}

/* IADD3 lo, P, a, b, RZ then IADD3.X hi, a', b', RZ, P, !PT: the 64-bit sum (a':a) + (b':b), or with b and b' negated
   the difference, as NVIDIA's compiler adds a 64-bit offset to an address. Each instruction's sum is made in 64 bits
   for its carries; the pair is one 32-bit add, its carry, and the high words' add, with the same results: lo, the
   carry in P, hi. The low word's write must leave the high word's sources as they were */
function IADD3_WIDE_ok() -> bool = {
    let p = UInt(FieldAt(0, 81, 3));
    FieldAt(0, 74, 1) == 0b0 & p < PT & UInt(FieldAt(0, 84, 3)) == PT & IsZeroAt(0, C) & not_bool(SrcNegAt(0, C))
    & FieldAt(1, 74, 1) == 0b1 & UInt(FieldAt(1, 87, 3)) == p & FieldAt(1, 90, 1) == 0b0
    & FieldAt(1, 77, 4) == 0xf & UInt(FieldAt(1, 81, 3)) == PT & UInt(FieldAt(1, 84, 3)) == PT
    & IsZeroAt(1, C) & not_bool(SrcNegAt(1, C))
    & not_bool(SrcNegAt(0, A)) & not_bool(SrcNegAt(1, A)) & SrcNegAt(0, B) == SrcNegAt(1, B)
    & not_bool(ReadsDstAt(1, A, 0)) & not_bool(ReadsDstAt(1, B, 0))
}
function IADD3_WIDE() -> unit = {
    let a0 = SrcBitsAt(0, A);
    let b0 = SrcBitsAt(0, B);
    let a1 = SrcBitsAt(1, A);
    let b1 = SrcBitsAt(1, B);
    let sub = SrcNegAt(0, B);
    let lo = if sub then a0 - b0 else a0 + b0;
    /* the low word's carry: no borrow of a subtraction, a sum that wrapped */
    let carry = if sub then UInt(a0) >= UInt(b0) else UInt(lo) < UInt(a0);
    let hi = a1 + (if sub then not_vec(b1) else b1) + (if carry then 0x00000001 else 0x00000000);
    D_writeAt(0, lo);
    PredWrite(UInt(FieldAt(0, 81, 3)), carry, 0);
    D_writeAt(1, hi)
}
