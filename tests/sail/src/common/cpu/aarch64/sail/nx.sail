/* SPDX-License-Identifier: GPL-3.0-or-later
   Copyright 2026 the ScarletNX contributors */

// XPAC strips whatever the keys' state: the extended HLE profile has 39-bit virtual addresses and no top-byte
// ignore, so bit 55 selects the address range and fills bits 63:39
val Strip : (bits(64), bool) -> bits(64)
function Strip (A, data) = Replicate([A[55]], 25) @ A[38 .. 0]
