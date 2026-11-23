/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Copyright 2026 the ScarletNX contributors */
/* SM53's integer, logic, video and predicate instructions (sm53_int.roots; back end sm53_int_spirv.h). The translator's
   helpers that carry its work stay its and the Sail calls them (emit_int.c's: shader_integer_add with the condition
   code, shader_integer_compare, shader_integer_mul_high, shader_xmad_half, the video operands and their end,
   shader_prmt_byte, shader_vm_select, shader_cc_test, the flags of a logic result). Each instruction is its
   emit_int branch, its constants made where those made them (Bits32 of a value known when the translator runs) and
   its booleans' raw operations (Raw*) where those did not fold the true and false constants out */


/* x + y as Maxwell's IADD does it (shader_integer_add): avg 2 negates x, 1 y, 3 adds one; .X the carry in; .CC the flags */
val IntegerAdd : (bits(32), bits(32), int, int, int) -> bits(32)

/* an integer form's right operand by its place in the roots line, the register (0), the constant (1), the immediate */
function RightOf(form : int) -> bits(32) = Right(if form == 0 then 0 else if form == 1 then 1 else 2)

function execute_MOV32I() -> unit = R_write(Dst(), Field(20, 32))

function execute_IADD() -> unit = {
    let left = R_read(RegA());
    let right = RightOf(Form());
    R_write(Dst(), IntegerAdd(left, right, UInt(Field(48, 2)), UInt(Field(43, 1)), UInt(Field(47, 1))))
}
