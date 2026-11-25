package com.wesbos.framecalendar;

import java.time.LocalDate;

final class CalendarClock {
    private static final LocalDate EARLIEST_DATE = LocalDate.of(2026, 3, 10);

    static boolean isReady(LocalDate date) {
        return !date.isBefore(EARLIEST_DATE);
    }
}
