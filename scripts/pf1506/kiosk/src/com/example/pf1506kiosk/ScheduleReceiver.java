package com.example.pf1506kiosk;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.PowerManager;
import android.util.Log;

import java.util.Calendar;

/**
 * Overnight screen schedule, run on the frame itself (no USB/server needed).
 *
 * QUIET_START (02:00): tells MainActivity quiet hours began; it turns the screen fully off
 *   if nobody is using it (a dimmed screen), otherwise at the next idle timeout.
 * QUIET_END (07:00): wakes the CPU and turns the screen on; MainActivity then dims after
 *   its normal idle timeout, so a tap works again.
 */
public class ScheduleReceiver extends BroadcastReceiver {
    static final String TAG = "FrameKiosk";
    static final int QUIET_START_HOUR = 2;
    static final int QUIET_END_HOUR = 7;
    static final String ACTION_QUIET_START = "com.example.pf1506kiosk.QUIET_START";
    static final String ACTION_QUIET_END = "com.example.pf1506kiosk.QUIET_END";

    static boolean inQuietHours() {
        int h = Calendar.getInstance().get(Calendar.HOUR_OF_DAY);
        return h >= QUIET_START_HOUR && h < QUIET_END_HOUR;
    }

    /** (Re)schedules both alarms for their next occurrence in local time. */
    static void schedule(Context c) {
        AlarmManager am = c.getSystemService(AlarmManager.class);
        setAt(c, am, ACTION_QUIET_START, QUIET_START_HOUR, 1);
        setAt(c, am, ACTION_QUIET_END, QUIET_END_HOUR, 2);
    }

    private static void setAt(Context c, AlarmManager am, String action, int hour, int requestCode) {
        Calendar next = Calendar.getInstance();
        next.set(Calendar.HOUR_OF_DAY, hour);
        next.set(Calendar.MINUTE, 0);
        next.set(Calendar.SECOND, 0);
        next.set(Calendar.MILLISECOND, 0);
        if (next.getTimeInMillis() <= System.currentTimeMillis()) next.add(Calendar.DAY_OF_MONTH, 1);
        Intent i = new Intent(action).setClass(c, ScheduleReceiver.class);
        PendingIntent pi = PendingIntent.getBroadcast(c, requestCode, i,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, next.getTimeInMillis(), pi);
        Log.i(TAG, action.substring(action.lastIndexOf('.') + 1) + " scheduled for " + next.getTime());
    }

    @Override
    public void onReceive(Context c, Intent intent) {
        String action = intent.getAction();
        Log.i(TAG, "alarm: " + action);
        if (ACTION_QUIET_START.equals(action)) {
            // Tell the running activity; starting it instead would resume it and its
            // setTurnScreenOn(true) would switch the screen straight back on.
            c.sendBroadcast(new Intent(MainActivity.ACTION_QUIET_NOW).setPackage(c.getPackageName()));
        } else if (ACTION_QUIET_END.equals(action)) {
            PowerManager pm = c.getSystemService(PowerManager.class);
            @SuppressWarnings("deprecation")
            PowerManager.WakeLock wl = pm.newWakeLock(PowerManager.FULL_WAKE_LOCK
                    | PowerManager.ACQUIRE_CAUSES_WAKEUP | PowerManager.ON_AFTER_RELEASE, "framekiosk:morning");
            wl.acquire(5_000);
            c.startActivity(new Intent(c, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        }
        schedule(c);
    }
}
