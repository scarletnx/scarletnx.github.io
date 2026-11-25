// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright 2026 the ScarletNX contributors
// The handlers' lines of ScarletNX's nn/time.c, cut for tests/check-manual.sh
u32 nntime_initialize(CPU* c) { return 0; }
i64 nntime_steady_now(CPU* c) { return 0; }
void nntime_steady_now_out(CPU* c, u64 out) {}
bool nntime_span_between(CPU* c, u64 out, u64 a, u64 b) { return false; }
