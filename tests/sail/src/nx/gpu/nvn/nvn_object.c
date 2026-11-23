/* SPDX-License-Identifier: GPL-3.0-or-later
   Copyright 2026 the ScarletNX contributors */
/* Cut from ScarletNX's nvn_object.c for tests/check-manual.sh */

void nvn_DeviceFinalize(CPU* c, u64 d) {
    u64 was = d;
    (void)c;
    NVN_OBJ(NvnDevice, d)->magic = 0;
    atomic_compare_exchange_strong_explicit(&g_nvn.object.device, &was, 0, memory_order_relaxed, memory_order_relaxed);
}
