// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright 2026 the ScarletNX contributors
// After ScarletNX's android/content/Context.java, for tests/check-manual.sh
package android.content;

/** The app's view of the system: its resources, its files and its services. */
public abstract class Context {
    public static final String WINDOW_SERVICE = "window";
    public static final int MODE_PRIVATE = 0x0000;

    public abstract Object getSystemService(String name);

    /** The service of a class, by its name; null for one the runtime has none of. */
    public final <T> T getSystemService(Class<T> serviceClass) { return null; }
}
