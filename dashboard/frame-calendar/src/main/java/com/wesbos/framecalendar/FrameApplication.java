package com.wesbos.framecalendar;

import android.app.Application;
import org.mozilla.geckoview.GeckoRuntime;
import org.mozilla.geckoview.GeckoRuntimeSettings;

public class FrameApplication extends Application {
    private GeckoRuntime runtime;

    synchronized GeckoRuntime runtime() {
        if (runtime == null) {
            runtime = GeckoRuntime.create(this, new GeckoRuntimeSettings.Builder()
                    .preferredColorScheme(GeckoRuntimeSettings.COLOR_SCHEME_DARK)
                    .consoleOutput(false)
                    .remoteDebuggingEnabled(false).build());
        }
        return runtime;
    }
}
