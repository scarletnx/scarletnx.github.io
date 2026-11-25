// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright 2026 the ScarletNX contributors
// The handlers' lines of ScarletNX's hle/hook/libc*.c and os_sync.c, cut for tests/check-manual.sh
u64 hook_memmove(CPU* c, u64 dst, u64 src, u64 size) { return dst; }
i32 libc_strcmp(CPU* c, u64 a, u64 b) { return 0; }
#define CTYPE(name)                                                                                                    \
    i32 libc_##name(CPU* c, i32 ch) {                                                                                  \
        return 0;                                                                                                      \
    }
CTYPE(isalnum)
void os_light_event_init_old(CPU* c, LightEventLayout* L, u64 e, int signaled, u32 mode) {}
void string_init(CPU* c, u64 self, u64 s) {}
void alloc_vector_free(CPU* c, u64 self) {}
int alloc_vector_shape(u64 addr) { return 1; }
