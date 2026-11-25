// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright 2026 the ScarletNX contributors
// After ScarletNX's android/app/Activity.java, for tests/check-manual.sh
package android.app;

import android.content.Context;
import android.view.View;
import java.util.ArrayList;

/**
 * A screen of the app. The runtime (snx.android.Device) makes it and drives its lifecycle in Android's order.
 */
public class Activity extends Context implements View.OnClickListener {
    public static final int RESULT_CANCELED = 0, RESULT_OK = -1;
    private final ArrayList<String> titles = new ArrayList<>();
    int packagePrivate;

    public Activity() {}

    // ---- the lifecycle the app overrides ----
    protected void onCreate(android.os.Bundle savedInstanceState) {}
    protected void onResume() { titles.clear(); }

    // ---- content ----
    /** The content: a layout's resource, inflated into the window. */
    public void setContentView(int layoutResID) { titles.add("x"); }
    /** The content: a view. See {@link View} and {@code setContentView(int)}. */
    public void setContentView(View view) { titles.add("y"); }

    public Object getSystemService(String name) { return null; }
    public void onClick(View v) {}
    public void startLockTask() { throw new UnsupportedOperationException("no lock task"); }

    /** What a result is. */
    public record Result(int code, android.content.Context from) {}

    private void hidden() {}
}

class NotApi {}
