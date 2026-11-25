// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright 2026 the ScarletNX contributors
// After ScarletNX's android/view/View.java, for tests/check-manual.sh
package android.view;

import android.content.Context;

/** A rectangle of the screen that draws itself and takes input. */
public class View {
    /** Visibility: drawn. */
    public static final int VISIBLE = 0x00000000;

    public View(Context context) {}

    /** What a click calls. */
    public interface OnClickListener {
        void onClick(View v);
        default boolean onLongClick(View v) { return false; }
    }

    /** The layout's direction. */
    public enum Direction { LTR, RTL, INHERIT }

    @Deprecated
    public void setDrawingCacheEnabled(boolean enabled) {}
}
