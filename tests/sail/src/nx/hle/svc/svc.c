// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright 2026 the ScarletNX contributors
// The handlers' lines of ScarletNX's hle/svc/svc.c, cut for tests/check-manual.sh
static Result svc_SetHeapSize(u64* out_address, u64 size) { return 0; }
static Result svc_CreateThread(u32* out_handle, u64 func, u64 arg, u64 stack_bottom, i32 priority, i32 core_id) { return 0; }
static void svc_SleepThread(i64 ns) {}
static Result svc_GetThreadCoreMask(i32* out_core_id, u64* out_affinity_mask, u32 thread_handle) { return 0; }
