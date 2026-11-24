package com.wesbos.framecalendar;

import biweekly.Biweekly;
import biweekly.ICalendar;
import biweekly.component.VEvent;
import biweekly.io.TimezoneAssignment;
import biweekly.property.DateOrDateTimeProperty;
import biweekly.property.ICalProperty;
import biweekly.util.ICalDate;
import biweekly.util.com.google.ical.compat.javautil.DateIterator;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.time.Duration;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TimeZone;

final class IcsReader {
    static List<Event> read(String text, LocalDate from, LocalDate to, ZoneId displayZone,
            int source) throws IOException {
        if (!text.contains("BEGIN:VCALENDAR") || !text.contains("END:VCALENDAR")) {
            throw new IOException("The response is not an iCalendar feed");
        }
        List<Event> result = new ArrayList<>();
        for (ICalendar calendar : Biweekly.parse(text).all()) {
            Map<String, Map<Long, VEvent>> exceptions = new HashMap<>();
            for (VEvent event : calendar.getEvents()) {
                TimeZone floatingZone = TimeZone.getTimeZone(displayZone.getId());
                for (DateOrDateTimeProperty property : new DateOrDateTimeProperty[]{
                        event.getDateStart(), event.getDateEnd(), event.getRecurrenceId()}) {
                    if (property != null) normalizeFloating(calendar, property, property.getValue(), floatingZone);
                }
                for (biweekly.property.ExceptionDates property : event.getExceptionDates()) {
                    for (ICalDate value : property.getValues()) normalizeFloating(calendar, property, value, floatingZone);
                }
                for (biweekly.property.RecurrenceDates property : event.getRecurrenceDates()) {
                    for (ICalDate value : property.getDates()) normalizeFloating(calendar, property, value, floatingZone);
                    for (biweekly.util.Period period : property.getPeriods()) {
                        normalizeFloating(calendar, property, period.getStartDate(), floatingZone);
                        normalizeFloating(calendar, property, period.getEndDate(), floatingZone);
                    }
                }
                if (event.getRecurrenceId() == null || event.getUid() == null) continue;
                if (event.getRecurrenceId().getParameters().get("RANGE").contains("THISANDFUTURE")) {
                    throw new IOException("THISANDFUTURE recurrence overrides are not supported");
                }
                exceptions.computeIfAbsent(event.getUid().getValue(), key -> new HashMap<>())
                        .put(event.getRecurrenceId().getValue().getTime(), event);
            }
            for (VEvent event : calendar.getEvents()) {
                if (event.getDateStart() == null) {
                    if (event.getStatus() != null && event.getStatus().isCancelled()) continue;
                    throw new IOException("An event has no start date");
                }
                if (event.getStatus() != null && event.getStatus().isCancelled()) continue;
                boolean allDay = !event.getDateStart().getValue().hasTime();
                TimezoneAssignment assignment = calendar.getTimezoneInfo().getTimezone(event.getDateStart());
                TimeZone recurrenceZone = allDay ? TimeZone.getDefault() : assignment != null ? assignment.getTimeZone()
                        : calendar.getTimezoneInfo().isFloating(event.getDateStart())
                        ? TimeZone.getTimeZone(displayZone.getId()) : TimeZone.getTimeZone("UTC");
                ZoneId zone = recurrenceZone.toZoneId();
                ZonedDateTime start = date(event.getDateStart().getValue(), allDay, displayZone, zone);
                ZonedDateTime end = event.getDateEnd() == null ? start.plusDays(allDay ? 1 : 0)
                        : date(event.getDateEnd().getValue(), allDay, displayZone, zone);
                Duration duration = Duration.between(start.toLocalDateTime(), end.toLocalDateTime());
                if (event.getDuration() != null) {
                    duration = Duration.ofMillis(event.getDuration().getValue().toMillis());
                }
                if (duration.isNegative()) throw new IOException("An event ends before it starts");
                String uid = event.getUid() == null ? "" : event.getUid().getValue();
                Map<Long, VEvent> overrides = exceptions.get(uid);
                DateIterator iterator = event.getDateIterator(recurrenceZone);
                LocalDate earliest = from.minusDays(Math.max(2, duration.toDays() + 2));
                iterator.advanceTo(Date.from(earliest.atStartOfDay(displayZone).toInstant()));
                int count = 0;
                while (iterator.hasNext()) {
                    if (++count > 20000) throw new IOException("Calendar recurrence expansion exceeds its limit");
                    Date occurrence = iterator.next();
                    ZonedDateTime a = date(occurrence, allDay, displayZone, zone);
                    if (!a.toLocalDate().isBefore(to.plusDays(2))) break;
                    if (event.getRecurrenceId() == null && overrides != null
                            && overrides.containsKey(occurrence.getTime())) continue;
                    ZonedDateTime b = a.toLocalDateTime().plus(duration).atZone(a.getZone());
                    if (allDay) b = a.plusDays(duration.toDays());
                    Event item = new Event(event.getSummary() == null ? "(Untitled)" : event.getSummary().getValue(),
                            event.getLocation() == null ? "" : event.getLocation().getValue(),
                            event.getDescription() == null ? "" : event.getDescription().getValue(),
                            a, b, allDay, source);
                    if (!item.lastDay(displayZone).isBefore(from) && item.firstDay(displayZone).isBefore(to)) {
                        result.add(item);
                    }
                }
            }
        }
        return result;
    }

    private static void normalizeFloating(ICalendar calendar, ICalProperty property, ICalDate value, TimeZone zone) {
        if (value != null && value.hasTime() && calendar.getTimezoneInfo().isFloating(property)) {
            value.setTime(value.getRawComponents().toDate(zone).getTime());
        }
    }

    private static ZonedDateTime date(Date value, boolean allDay, ZoneId display, ZoneId recurrence) {
        if (allDay) {
            // DATE values are parsed in the JVM's local zone, not UTC.
            SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd", Locale.ROOT);
            return LocalDate.parse(format.format(value)).atStartOfDay(display);
        }
        return value.toInstant().atZone(recurrence);
    }
}
