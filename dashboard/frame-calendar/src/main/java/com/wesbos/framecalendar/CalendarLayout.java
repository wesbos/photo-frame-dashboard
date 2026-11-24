package com.wesbos.framecalendar;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;
import java.time.temporal.TemporalAdjusters;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

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
    final List<List<Span>> spans = new ArrayList<>();
    final List<List<Event>> days = new ArrayList<>();

    CalendarLayout(YearMonth month, List<Event> events, ZoneId zone) {
        first = month.atDay(1).with(TemporalAdjusters.previousOrSame(DayOfWeek.SUNDAY));
        weeks = (int) (ChronoUnit.DAYS.between(first, month.atEndOfMonth()) / 7) + 1;
        for (int i = 0; i < weeks * 7; i++) days.add(new ArrayList<>());
        List<Event> sorted = new ArrayList<>(events);
        sorted.sort(Comparator.comparing((Event e) -> e.firstDay(zone))
                .thenComparing((Event e) -> -ChronoUnit.DAYS.between(e.firstDay(zone), e.lastDay(zone)))
                .thenComparing(e -> e.start));
        for (int week = 0; week < weeks; week++) {
            LocalDate from = first.plusDays(week * 7L), to = from.plusDays(6);
            List<Span> row = new ArrayList<>();
            List<Integer> laneEnds = new ArrayList<>();
            for (Event event : sorted) {
                LocalDate a = event.firstDay(zone), b = event.lastDay(zone);
                if (b.isBefore(from) || a.isAfter(to)) continue;
                int left = (int) Math.max(0, ChronoUnit.DAYS.between(from, a));
                int right = (int) Math.min(6, ChronoUnit.DAYS.between(from, b));
                if (event.allDay || b.isAfter(a)) {
                    int lane = 0;
                    while (lane < laneEnds.size() && laneEnds.get(lane) >= left) lane++;
                    if (lane == laneEnds.size()) laneEnds.add(right);
                    else laneEnds.set(lane, right);
                    row.add(new Span(event, left, right, lane));
                }
                for (int day = left; day <= right; day++) days.get(week * 7 + day).add(event);
            }
            spans.add(row);
        }
        for (List<Event> day : days) day.sort(Comparator.comparing((Event e) -> !e.allDay)
                .thenComparing(e -> e.start));
    }
}
