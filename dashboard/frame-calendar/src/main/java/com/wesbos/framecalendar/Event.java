package com.wesbos.framecalendar;

import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZonedDateTime;

final class Event {
    final String title, location, description;
    final ZonedDateTime start, end;
    final boolean allDay;
    final int source;

    Event(String title, String location, String description, ZonedDateTime start,
            ZonedDateTime end, boolean allDay, int source) {
        this.title = title;
        this.location = location;
        this.description = description;
        this.start = start;
        this.end = end;
        this.allDay = allDay;
        this.source = source;
    }

    LocalDate firstDay(ZoneId zone) {
        return allDay ? start.toLocalDate() : start.withZoneSameInstant(zone).toLocalDate();
    }

    LocalDate lastDay(ZoneId zone) {
        if (!end.isAfter(start)) return firstDay(zone);
        return allDay ? end.toLocalDate().minusDays(1)
                : end.withZoneSameInstant(zone).minusNanos(1).toLocalDate();
    }
}
