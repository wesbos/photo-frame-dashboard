package com.wesbos.framecalendar;

import android.app.AlertDialog;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.view.MotionEvent;
import android.view.View;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

final class CalendarView extends View {
    static final int BACKGROUND = 0xff1e1e2e, TEXT = 0xffcdd6f4, MUTED = 0xffa6adc8,
            BORDER = 0xff45475a, TODAY = 0xffcba6f7;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final float scale;
    private CalendarLayout layout;
    private YearMonth month;
    private ZoneId zone;
    private float dayWidth, weekHeight;
    private final List<Hit> hits = new ArrayList<>();

    private static final class Hit {
        final RectF box;
        final Event event;
        Hit(RectF box, Event event) { this.box = box; this.event = event; }
    }

    CalendarView(Context context) {
        super(context);
        scale = getResources().getDisplayMetrics().density;
        setBackgroundColor(BACKGROUND);
        setFocusable(true);
        setContentDescription("Monthly calendar. Tap a day to see all its events.");
    }

    void show(YearMonth month, List<Event> events, ZoneId zone) {
        this.month = month;
        this.zone = zone;
        layout = new CalendarLayout(month, events, zone);
        invalidate();
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        if (layout == null) return;
        hits.clear();
        dayWidth = getWidth() / 7f;
        float heading = 30 * scale;
        weekHeight = (getHeight() - heading) / layout.weeks;
        String[] weekdays = {"SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"};
        for (int d = 0; d < 7; d++) {
            label(canvas, weekdays[d], d * dayWidth + dayWidth / 2, 20 * scale, 11, MUTED, true);
        }
        paint.setColor(BORDER);
        paint.setStrokeWidth(scale);
        for (int day = 0; day <= 7; day++) canvas.drawLine(day * dayWidth, heading, day * dayWidth, getHeight(), paint);
        LocalDate today = LocalDate.now(zone);
        for (int week = 0; week < layout.weeks; week++) {
            float top = heading + week * weekHeight;
            paint.setColor(BORDER);
            canvas.drawLine(0, top, getWidth(), top, paint);
            List<CalendarLayout.Span> spans = layout.spans.get(week);
            int maxLanes = Math.max(1, (int) ((weekHeight - 55 * scale) / (22 * scale)));
            int usedLanes = 0;
            for (CalendarLayout.Span span : spans) {
                if (span.lane >= maxLanes) continue;
                usedLanes = Math.max(usedLanes, span.lane + 1);
                RectF box = new RectF(span.first * dayWidth + 3 * scale,
                        top + (31 + span.lane * 22) * scale,
                        (span.last + 1) * dayWidth - 3 * scale, top + (51 + span.lane * 22) * scale);
                paint.setColor(CalendarStore.COLORS[span.event.source]);
                canvas.drawRoundRect(box, 4 * scale, 4 * scale, paint);
                canvas.save();
                canvas.clipRect(box);
                label(canvas, ellipsis(span.event.title, box.width() - 12 * scale, 12),
                        box.left + 6 * scale, box.top + 14 * scale, 12, BACKGROUND, false);
                canvas.restore();
                hits.add(new Hit(box, span.event));
            }
            for (int d = 0; d < 7; d++) {
                LocalDate date = layout.first.plusDays(week * 7L + d);
                float left = d * dayWidth;
                if (date.equals(today)) {
                    paint.setColor(TODAY);
                    canvas.drawCircle(left + dayWidth / 2, top + 15 * scale, 12 * scale, paint);
                }
                String number = date.getDayOfMonth() == 1
                        ? date.format(DateTimeFormatter.ofPattern("d MMM", Locale.UK))
                        : Integer.toString(date.getDayOfMonth());
                label(canvas, number, left + dayWidth / 2, top + 19 * scale, 12,
                        date.equals(today) ? BACKGROUND : date.getMonth() == month.getMonth() ? TEXT : MUTED, true);
                float y = top + (47 + usedLanes * 22) * scale;
                List<Event> dayEvents = layout.days.get(week * 7 + d);
                int hidden = 0;
                for (CalendarLayout.Span span : spans) {
                    if (span.lane >= maxLanes && d >= span.first && d <= span.last) hidden++;
                }
                for (Event event : dayEvents) {
                    if (event.allDay || event.lastDay(zone).isAfter(event.firstDay(zone))) continue;
                    if (y > top + weekHeight - 25 * scale) { hidden++; continue; }
                    paint.setColor(CalendarStore.COLORS[event.source]);
                    canvas.drawCircle(left + 9 * scale, y - 4 * scale, 3 * scale, paint);
                    String text = event.start.withZoneSameInstant(zone).format(DateTimeFormatter.ofPattern("HH:mm"))
                            + " " + event.title;
                    label(canvas, ellipsis(text, dayWidth - 26 * scale, 12), left + 17 * scale, y, 12, TEXT, false);
                    hits.add(new Hit(new RectF(left, y - 16 * scale, left + dayWidth, y + 4 * scale), event));
                    y += 21 * scale;
                }
                if (hidden > 0) label(canvas, hidden + " more", left + 8 * scale,
                        top + weekHeight - 8 * scale, 11, MUTED, false);
            }
        }
    }

    private void label(Canvas c, String text, float x, float y, float size, int color, boolean center) {
        paint.setColor(color);
        paint.setTextSize(size * scale);
        paint.setTypeface(Typeface.create("sans-serif", Typeface.NORMAL));
        paint.setTextAlign(center ? Paint.Align.CENTER : Paint.Align.LEFT);
        c.drawText(text, x, y, paint);
    }

    private String ellipsis(String text, float width, float size) {
        paint.setTextSize(size * scale);
        if (paint.measureText(text) <= width) return text;
        int count = paint.breakText(text, true, Math.max(0, width - paint.measureText("...")), null);
        return text.substring(0, count) + "...";
    }

    @Override public boolean onTouchEvent(MotionEvent event) {
        if (event.getAction() != MotionEvent.ACTION_UP) return true;
        performClick();
        if (layout == null || event.getY() < 30 * scale) return true;
        for (Hit hit : hits) {
            if (hit.box.contains(event.getX(), event.getY())) {
                showEvent(hit.event);
                return true;
            }
        }
        int day = Math.min(6, (int) (event.getX() / dayWidth));
        int week = Math.min(layout.weeks - 1, (int) ((event.getY() - 30 * scale) / weekHeight));
        List<Event> events = layout.days.get(week * 7 + day);
        String[] titles = new String[events.size()];
        for (int i = 0; i < titles.length; i++) {
            Event item = events.get(i);
            titles[i] = (item.allDay ? "All day" : item.start.withZoneSameInstant(zone)
                    .format(DateTimeFormatter.ofPattern("HH:mm"))) + "  " + item.title;
        }
        new AlertDialog.Builder(getContext())
                .setTitle(layout.first.plusDays(week * 7L + day).format(DateTimeFormatter.ofPattern("EEEE d MMMM", Locale.UK)))
                .setItems(titles, (dialog, which) -> showEvent(events.get(which)))
                .setNegativeButton("Close", null).show();
        return true;
    }

    private void showEvent(Event event) {
        DateTimeFormatter format = DateTimeFormatter.ofPattern(event.allDay ? "EEE d MMM" : "EEE d MMM HH:mm", Locale.UK);
        String details = CalendarStore.NAMES[event.source] + "\n"
                + event.start.withZoneSameInstant(zone).format(format) + " - "
                + (event.allDay ? event.end.minusDays(1) : event.end).withZoneSameInstant(zone).format(format)
                + (event.location.isEmpty() ? "" : "\n\n" + event.location)
                + (event.description.isEmpty() ? "" : "\n\n" + event.description);
        new AlertDialog.Builder(getContext()).setTitle(event.title).setMessage(details)
                .setPositiveButton("Close", null).show();
    }

    @Override public boolean performClick() { super.performClick(); return true; }
}
