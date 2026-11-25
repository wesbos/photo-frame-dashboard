package com.wesbos.framecalendar;

import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;
import java.util.Collections;

final class CalendarRange {
    final LocalDate from, until;
    final ZoneId zone;

    private CalendarRange(LocalDate from, LocalDate until, ZoneId zone) {
        this.from = from;
        this.until = until;
        this.zone = zone;
    }

    static CalendarRange around(YearMonth month, ZoneId zone) {
        CalendarLayout first = new CalendarLayout(month.minusMonths(1), Collections.emptyList(), zone);
        CalendarLayout last = new CalendarLayout(month.plusMonths(15), Collections.emptyList(), zone);
        return new CalendarRange(first.first, last.first.plusDays(last.weeks * 7L), zone);
    }

    boolean covers(YearMonth month, ZoneId requestedZone) {
        if (!zone.equals(requestedZone)) return false;
        CalendarLayout first = new CalendarLayout(month, Collections.emptyList(), zone);
        CalendarLayout last = new CalendarLayout(month.plusMonths(3), Collections.emptyList(), zone);
        return !first.first.isBefore(from)
                && !last.first.plusDays(last.weeks * 7L).isAfter(until);
    }
}
