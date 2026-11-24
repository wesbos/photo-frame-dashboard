package com.wesbos.framecalendar;

import static org.junit.Assert.*;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import org.junit.Test;

public class CalendarTest {
    private static final ZoneId LONDON = ZoneId.of("Europe/London");
    private static final LocalDate FROM = LocalDate.of(2026, 11, 29), TO = LocalDate.of(2027, 1, 3);

    private List<Event> parse(String events) throws Exception {
        return IcsReader.read("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + events + "END:VCALENDAR\r\n", FROM, TO, LONDON, 0);
    }

    private String event(String properties) {
        return "BEGIN:VEVENT\r\n" + properties + "END:VEVENT\r\n";
    }

    @Test public void monthUsesSundayAndVariableWeekCount() {
        CalendarLayout december = new CalendarLayout(YearMonth.of(2026, 12), Collections.emptyList(), LONDON);
        assertEquals(FROM, december.first);
        assertEquals(5, december.weeks);
        assertEquals(6, new CalendarLayout(YearMonth.of(2026, 8), Collections.emptyList(), LONDON).weeks);
        assertEquals(4, new CalendarLayout(YearMonth.of(2026, 2), Collections.emptyList(), LONDON).weeks);
    }

    @Test public void allDayEndIsExclusiveAndSpansCrossWeekBoundary() throws Exception {
        List<Event> events = parse(event("UID:trip\r\nDTSTART;VALUE=DATE:20261204\r\nDTEND;VALUE=DATE:20261209\r\nSUMMARY:Trip\r\n"));
        assertEquals(1, events.size());
        assertEquals(LocalDate.of(2026, 12, 8), events.get(0).lastDay(LONDON));
        CalendarLayout layout = new CalendarLayout(YearMonth.of(2026, 12), events, LONDON);
        assertEquals(5, layout.spans.get(0).get(0).first);
        assertEquals(6, layout.spans.get(0).get(0).last);
        assertEquals(0, layout.spans.get(1).get(0).first);
        assertEquals(2, layout.spans.get(1).get(0).last);
        assertEquals(0, layout.days.get(10).size());
    }

    @Test public void recurringExceptionsReplacementsAndCancellation() throws Exception {
        String master = event("UID:weekly\r\nDTSTART:20261201T100000Z\r\nDTEND:20261201T110000Z\r\n"
                + "RRULE:FREQ=WEEKLY;COUNT=4\r\nEXDATE:20261208T100000Z\r\nSUMMARY:Normal\r\n");
        String moved = event("UID:weekly\r\nRECURRENCE-ID:20261215T100000Z\r\nDTSTART:20261216T120000Z\r\n"
                + "DTEND:20261216T130000Z\r\nSUMMARY:Moved\r\n");
        String cancelled = event("UID:weekly\r\nRECURRENCE-ID:20261222T100000Z\r\nSTATUS:CANCELLED\r\n");
        List<Event> events = parse(master + moved + cancelled);
        assertEquals(2, events.size());
        assertEquals(1, events.stream().filter(e -> e.title.equals("Moved")).count());
        assertEquals(LocalDate.of(2026, 12, 16), events.stream().filter(e -> e.title.equals("Moved")).findFirst().get().firstDay(LONDON));
    }

    @Test public void escapedAndFoldedTextAndMissingAllDayEnd() throws Exception {
        List<Event> events = parse(event("DTSTART;VALUE=DATE:20261201\r\nSUMMARY:Family\\, friends and a long\r\n"
                + "  title\r\nDESCRIPTION:First\\nSecond\r\n"));
        assertEquals("Family, friends and a long title", events.get(0).title);
        assertEquals("First\nSecond", events.get(0).description);
        assertEquals(events.get(0).firstDay(LONDON), events.get(0).lastDay(LONDON));
    }

    @Test public void recurrenceKeepsLocalHourAcrossDst() throws Exception {
        String text = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + event(
                "UID:dst\r\nDTSTART;TZID=Europe/London:20260322T090000\r\nDTEND;TZID=Europe/London:20260322T100000\r\n"
                + "RRULE:FREQ=WEEKLY;COUNT=3\r\nSUMMARY:Breakfast\r\n") + "END:VCALENDAR\r\n";
        List<Event> events = IcsReader.read(text, LocalDate.of(2026, 3, 1), LocalDate.of(2026, 4, 10), LONDON, 0);
        assertEquals(3, events.size());
        for (Event event : events) {
            assertEquals(9, event.start.withZoneSameInstant(LONDON).getHour());
            assertEquals(10, event.end.withZoneSameInstant(LONDON).getHour());
        }
    }

    @Test public void overlappingBarsUseSeparateLanes() {
        ZonedDateTime start = FROM.atStartOfDay(LONDON);
        Event a = new Event("A", "", "", start, start.plusDays(4), true, 0);
        Event b = new Event("B", "", "", start.plusDays(1), start.plusDays(6), true, 1);
        CalendarLayout layout = new CalendarLayout(YearMonth.of(2026, 12), Arrays.asList(a, b), LONDON);
        assertNotEquals(layout.spans.get(0).get(0).lane, layout.spans.get(0).get(1).lane);
    }

    @Test public void midnightEndDoesNotLeakIntoNextDay() {
        ZonedDateTime start = LocalDate.of(2026, 12, 1).atTime(22, 0).atZone(LONDON);
        Event item = new Event("Late", "", "", start, start.plusHours(2), false, 0);
        assertEquals(LocalDate.of(2026, 12, 1), item.lastDay(LONDON));
    }

    @Test public void allDayDurationWithoutEndDate() throws Exception {
        List<Event> events = parse(event("DTSTART;VALUE=DATE:20261201\r\nDURATION:P3D\r\nSUMMARY:Trip\r\n"));
        assertEquals(LocalDate.of(2026, 12, 3), events.get(0).lastDay(LONDON));
    }

    @Test public void floatingTimesUseConfiguredZoneRatherThanDeviceZone() throws Exception {
        ZoneId newYork = ZoneId.of("America/New_York");
        String text = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + event(
                "UID:floating\r\nDTSTART:20261201T090000\r\nDTEND:20261201T100000\r\n"
                + "RRULE:FREQ=DAILY;COUNT=3\r\nEXDATE:20261202T090000\r\nRDATE:20261204T090000\r\n"
                + "SUMMARY:Local appointment\r\n") + "END:VCALENDAR\r\n";
        List<Event> events = IcsReader.read(text, FROM, TO, newYork, 0);
        assertEquals(3, events.size());
        for (Event event : events) {
            assertEquals(9, event.start.withZoneSameInstant(newYork).getHour());
            assertEquals(10, event.end.withZoneSameInstant(newYork).getHour());
        }
    }

    @Test(expected = java.io.IOException.class) public void reportsUnsupportedFutureOverride() throws Exception {
        parse(event("UID:weekly\r\nRECURRENCE-ID;RANGE=THISANDFUTURE:20261201T100000Z\r\n"
                + "DTSTART:20261201T110000Z\r\nSUMMARY:Future change\r\n"));
    }

    @Test(expected = java.io.IOException.class) public void rejectsLoginHtmlInsteadOfCalendar() throws Exception {
        IcsReader.read("<html>Please log in</html>", FROM, TO, LONDON, 0);
    }
}
