// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright 2026 the ScarletNX contributors
// After ScarletNX's snx/android/Device.java, for tests/check-manual.sh
package snx.android;

/** The device the app runs on, as ScarletNX's C answers for it. */
public final class Device {
    private Device() {}

    /** The display's density in dots per inch, which the host's window gives. */
    public static native int densityDpi();
}
