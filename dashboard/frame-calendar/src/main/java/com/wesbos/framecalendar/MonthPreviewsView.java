package com.wesbos.framecalendar;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.view.MotionEvent;
import android.view.View;
import java.util.function.Consumer;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

final class MonthPreviewsView extends View {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final List<CalendarLayout> layouts = new ArrayList<>();
    private YearMonth month;
    private ZoneId zone;
    private Consumer<YearMonth> onMonthSelected;

    MonthPreviewsView(Context context) {
        super(context);
        setBackgroundColor(CalendarView.BACKGROUND);
        setContentDescription("Next three months. Shaded dates have calendar events. Tap a month to open it.");
    }

    void show(YearMonth displayedMonth, List<Event> events, ZoneId zone) {
        month = displayedMonth;
        this.zone = zone;
        layouts.clear();
        layouts.addAll(CalendarLayout.followingMonths(month, events, zone));
        invalidate();
    }

    void setOnMonthSelected(Consumer<YearMonth> listener) {
        onMonthSelected = listener;
        setClickable(listener != null);
    }

    /** Index of the preview column under x, or -1 outside the view. */
    static int previewAt(float x, int width, int count) {
        if (width <= 0 || x < 0 || x >= width) return -1;
        int index = (int) (x / (width / 3f));
        return index < count ? index : -1;
    }

    @Override public boolean onTouchEvent(MotionEvent event) {
        if (onMonthSelected == null || month == null) return super.onTouchEvent(event);
        if (event.getActionMasked() == MotionEvent.ACTION_UP) {
            int index = previewAt(event.getX(), getWidth(), layouts.size());
            if (index >= 0) {
                playSoundEffect(android.view.SoundEffectConstants.CLICK);
                onMonthSelected.accept(month.plusMonths(index + 1));
            }
        }
        return true;
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        if (layouts.isEmpty()) return;
        float width = getWidth() / 3f;
        float rowHeight = (getHeight() - 48) / 6f;
        LocalDate today = LocalDate.now(zone);
        paint.setColor(CalendarView.BORDER);
        paint.setStrokeWidth(1);
        canvas.drawLine(0, 0, getWidth(), 0, paint);
        for (int preview = 0; preview < layouts.size(); preview++) {
            CalendarLayout layout = layouts.get(preview);
            YearMonth shown = month.plusMonths(preview + 1);
            float left = preview * width + 20;
            float dayWidth = (width - 40) / 7f;
            label(canvas, shown.format(DateTimeFormatter.ofPattern("MMMM yyyy", Locale.UK)),
                    (preview + .5f) * width, 21, 15, CalendarView.TEXT);
            for (int day = 0; day < 7; day++) {
                label(canvas, new String[]{"S", "M", "T", "W", "T", "F", "S"}[day],
                        left + (day + .5f) * dayWidth, 41, 10, CalendarView.MUTED);
            }
            for (int day = 0; day < layout.days.size(); day++) {
                LocalDate date = layout.first.plusDays(day);
                if (!CalendarLayout.showPreviewDate(preview, shown, date)) continue;
                float x = left + (day % 7 + .5f) * dayWidth;
                float y = 48 + (day / 7 + .5f) * rowHeight;
                boolean inMonth = YearMonth.from(date).equals(shown);
                if (!layout.days.get(day).isEmpty()) {
                    paint.setColor(inMonth ? CalendarView.BORDER : 0xff313244);
                    canvas.drawRoundRect(new RectF(x - dayWidth * .4f, y - rowHeight * .45f,
                            x + dayWidth * .4f, y + rowHeight * .45f), 4, 4, paint);
                }
                if (date.equals(today)) {
                    paint.setColor(CalendarView.TODAY);
                    canvas.drawCircle(x, y, rowHeight * .45f, paint);
                }
                label(canvas, Integer.toString(date.getDayOfMonth()), x, y + 4, 12,
                        date.equals(today) ? CalendarView.BACKGROUND
                                : inMonth ? CalendarView.TEXT : CalendarView.MUTED);
            }
        }
    }

    private void label(Canvas canvas, String text, float x, float y, float size, int color) {
        paint.setColor(color);
        paint.setTextSize(size);
        paint.setTypeface(Typeface.create("sans-serif", Typeface.NORMAL));
        paint.setTextAlign(Paint.Align.CENTER);
        canvas.drawText(text, x, y, paint);
    }
}
