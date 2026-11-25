package com.wesbos.framecalendar;

import java.time.DayOfWeek;
import java.time.Instant;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.temporal.ChronoUnit;
import java.time.temporal.TemporalAdjusters;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

final class CalendarLayout {
    static final class Span {
        final Event event;
        final int first, last, lane;
        Span(Event event, int first, int last, int lane) {
            this.event = event;
            this.first = first;
            this.last = last;
            this.lane = lane;
        }
    }

    final LocalDate first;
    final int weeks;
    final List<List<Span>> entries = new ArrayList<>();
    final List<List<Event>> days = new ArrayList<>();

    static List<CalendarLayout> followingMonths(YearMonth month, List<Event> events, ZoneId zone) {
        List<CalendarLayout> result = new ArrayList<>();
        for (int i = 1; i <= 3; i++) result.add(new CalendarLayout(month.plusMonths(i), events, zone));
        return result;
    }

    static boolean showPreviewDate(int index, YearMonth month, LocalDate date) {
        return YearMonth.from(date).equals(month)
                || (index == 0 && date.isBefore(month.atDay(1)))
                || (index == 2 && date.isAfter(month.atEndOfMonth()));
    }

    static int availableRows(float height, float scale) {
        return Math.max(0, (int) ((height - 29 * scale) / (18 * scale)));
    }

    static int visibleEvents(int count, int rows) {
        return count > rows ? Math.max(0, rows - 1) : count;
    }

    /** Today's cell when it overflows: bars keep their lanes, single-cell entries are packed into the free lanes. */
    static final class TodayCell {
        final Set<Span> fixed = new HashSet<>();
        final List<Span> moved = new ArrayList<>();
        int hidden;
        int moreLane;
    }

    static boolean ended(Event event, Instant now) {
        if (event.allDay) return false;
        ZonedDateTime end = event.end.isAfter(event.start) ? event.end : event.start;
        return !end.toInstant().isAfter(now);
    }

    /** Hides finished appointments (earliest first) into "more" so the rest of today stays visible. */
    static TodayCell today(List<Span> week, int column, List<Event> events, int rows, Instant now) {
        TodayCell cell = new TodayCell();
        Set<Event> hide = new HashSet<>();
        int excess = events.size() - Math.max(0, rows - 1);
        for (Event event : events) {
            if (hide.size() >= excess) break;
            if (ended(event, now)) hide.add(event);
        }
        int remaining = events.size() - hide.size();
        int limit = remaining > rows || !hide.isEmpty() ? Math.max(0, rows - 1) : remaining;
        boolean[] used = new boolean[Math.max(limit, 0)];
        List<Span> movable = new ArrayList<>();
        for (Span span : week) {
            if (span.first > column || span.last < column || hide.contains(span.event)) continue;
            if (span.first == column && span.last == column) movable.add(span);
            else if (span.lane < limit) { cell.fixed.add(span); used[span.lane] = true; }
        }
        movable.sort(Comparator.comparingInt(span -> span.lane));
        int lane = 0;
        for (Span span : movable) {
            while (lane < limit && used[lane]) lane++;
            if (lane >= limit) break;
            cell.moved.add(new Span(span.event, column, column, lane));
            used[lane++] = true;
        }
        cell.hidden = events.size() - cell.fixed.size() - cell.moved.size();
        cell.moreLane = limit;
        return cell;
    }

    CalendarLayout(YearMonth month, List<Event> events, ZoneId zone) {
        first = month.atDay(1).with(TemporalAdjusters.previousOrSame(DayOfWeek.SUNDAY));
        weeks = (int) (ChronoUnit.DAYS.between(first, month.atEndOfMonth()) / 7) + 1;
        for (int i = 0; i < weeks * 7; i++) days.add(new ArrayList<>());
        List<Event> sorted = new ArrayList<>(events);
        sorted.sort(Comparator.comparing((Event e) -> !e.allDay).thenComparing(e -> e.start));
        for (int week = 0; week < weeks; week++) {
            LocalDate from = first.plusDays(week * 7L), to = from.plusDays(6);
            List<Span> row = new ArrayList<>();
            int[] nextLane = new int[7];
            for (Event event : sorted) {
                LocalDate a = event.firstDay(zone), b = event.lastDay(zone);
                if (b.isBefore(from) || a.isAfter(to)) continue;
                int left = (int) Math.max(0, ChronoUnit.DAYS.between(from, a));
                int right = (int) Math.min(6, ChronoUnit.DAYS.between(from, b));
                int segment = left, lane = nextLane[left];
                for (int day = left; day <= right; day++) {
                    if (nextLane[day] != lane) {
                        row.add(new Span(event, segment, day - 1, lane));
                        segment = day;
                        lane = nextLane[day];
                    }
                    nextLane[day]++;
                    days.get(week * 7 + day).add(event);
                }
                row.add(new Span(event, segment, right, lane));
            }
            entries.add(row);
        }
    }
}
