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
        assertEquals(5, layout.entries.get(0).get(0).first);
        assertEquals(6, layout.entries.get(0).get(0).last);
        assertEquals(0, layout.entries.get(1).get(0).first);
        assertEquals(2, layout.entries.get(1).get(0).last);
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
        assertNotEquals(layout.entries.get(0).get(0).lane, layout.entries.get(0).get(1).lane);
    }

    @Test public void appointmentsUseEachDaysAvailableRowsInChronologicalOrder() {
        ZonedDateTime sunday = FROM.atStartOfDay(LONDON);
        Event firstBar = new Event("First bar", "", "", sunday, sunday.plusDays(2), true, 0);
        Event secondBar = new Event("Second bar", "", "", sunday, sunday.plusDays(2), true, 1);
        ZonedDateTime wednesday = sunday.plusDays(3);
        Event afternoon = new Event("Afternoon", "", "", wednesday.plusHours(16), wednesday.plusHours(17), false, 0);
        Event morning = new Event("Morning", "", "", wednesday.plusHours(9), wednesday.plusHours(10), false, 0);
        Event overnight = new Event("Overnight", "", "", wednesday.plusHours(18), wednesday.plusDays(1).plusHours(8), false, 0);
        CalendarLayout layout = new CalendarLayout(YearMonth.of(2026, 12),
                Arrays.asList(afternoon, firstBar, overnight, morning, secondBar), LONDON);
        List<CalendarLayout.Span> entries = layout.entries.get(0);
        CalendarLayout.Span morningEntry = entries.stream().filter(e -> e.event == morning).findFirst().get();
        CalendarLayout.Span afternoonEntry = entries.stream().filter(e -> e.event == afternoon).findFirst().get();
        CalendarLayout.Span overnightEntry = entries.stream().filter(e -> e.event == overnight).findFirst().get();
        assertEquals(0, morningEntry.lane);
        assertEquals(1, afternoonEntry.lane);
        assertEquals(2, overnightEntry.lane);
        assertEquals(Arrays.asList(morning, afternoon, overnight), layout.days.get(3));
    }

    @Test public void spanningEventsDoNotLeaveEmptyRowsOnLessBusyDays() {
        ZonedDateTime sunday = FROM.atStartOfDay(LONDON);
        Event sundayOnly = new Event("Sunday", "", "", sunday, sunday.plusDays(1), true, 0);
        Event trip = new Event("Trip", "", "", sunday, sunday.plusDays(4), true, 1);
        Event monday = new Event("Meeting", "", "", sunday.plusDays(1).plusHours(9),
                sunday.plusDays(1).plusHours(10), false, 0);
        CalendarLayout layout = new CalendarLayout(YearMonth.of(2026, 12),
                Arrays.asList(sundayOnly, trip, monday), LONDON);
        List<CalendarLayout.Span> row = layout.entries.get(0);
        assertTrue(row.stream().anyMatch(span -> span.event == trip && span.first == 0
                && span.last == 0 && span.lane == 1));
        assertTrue(row.stream().anyMatch(span -> span.event == trip && span.first == 1
                && span.last == 3 && span.lane == 0));
        assertTrue(row.stream().anyMatch(span -> span.event == monday && span.first == 1
                && span.lane == 1));
        assertEquals(Arrays.asList(trip, monday), layout.days.get(1));
    }

    @Test public void eventCapacityUsesTheLastRowUnlessOverflowNeedsIt() {
        int rows = CalendarLayout.availableRows(104, 1);
        assertEquals(4, rows);
        assertEquals(4, CalendarLayout.visibleEvents(4, rows));
        assertEquals(3, CalendarLayout.visibleEvents(5, rows));
        assertEquals(0, CalendarLayout.visibleEvents(1, 0));
        assertEquals(3, CalendarLayout.availableRows(87, 1));
    }

    @Test public void calendarWaitsForTheConfiguredMinimumDate() {
        assertFalse(CalendarClock.isReady(LocalDate.of(1970, 1, 1)));
        assertFalse(CalendarClock.isReady(LocalDate.of(2026, 3, 9)));
        assertTrue(CalendarClock.isReady(LocalDate.of(2026, 3, 10)));
        assertTrue(CalendarClock.isReady(LocalDate.of(2026, 11, 25)));
    }

    @Test public void exactCrossCalendarDuplicatesPreferMartin() {
        ZonedDateTime start = FROM.atTime(9, 0).atZone(LONDON);
        Event family = new Event("Meeting", "Office", "Notes", start, start.plusHours(1), false, 1);
        Event martin = new Event("Meeting", "Office", "Notes", start.withZoneSameInstant(ZoneId.of("America/New_York")),
                start.plusHours(1).withZoneSameInstant(ZoneId.of("America/New_York")), false, 0);
        Event different = new Event("Meeting", "Office", "Different notes", start, start.plusHours(1), false, 2);
        assertEquals(Arrays.asList(martin, different),
                EventDeduplicator.unique(Arrays.asList(family, different, martin)));
        assertEquals(Collections.singletonList(martin),
                EventDeduplicator.unique(Arrays.asList(martin, family, martin)));
        assertEquals(Arrays.asList(martin, martin), EventDeduplicator.unique(Arrays.asList(martin, martin)));
    }

    @Test public void similarAppointmentsRemainDistinct() {
        ZonedDateTime start = FROM.atTime(9, 0).atZone(LONDON);
        Event original = new Event("Meeting", "Office", "Notes", start, start.plusHours(1), false, 0);
        Event later = new Event("Meeting", "Office", "Notes", start.plusHours(1), start.plusHours(2), false, 1);
        Event elsewhere = new Event("Meeting", "Home", "Notes", start, start.plusHours(1), false, 1);
        List<Event> distinct = Arrays.asList(original, later, elsewhere);
        assertEquals(distinct, EventDeduplicator.unique(distinct));
    }

    @Test public void allDayDuplicatesCompareCalendarDatesNotTimeZones() {
        ZonedDateTime start = FROM.atStartOfDay(LONDON);
        Event family = new Event("Holiday", "", "", start, start.plusDays(1), true, 1);
        ZonedDateTime otherZone = FROM.atStartOfDay(ZoneId.of("America/New_York"));
        Event martin = new Event("Holiday", "", "", otherZone, otherZone.plusDays(1), true, 0);
        assertEquals(Collections.singletonList(martin), EventDeduplicator.unique(Arrays.asList(family, martin)));
    }

    @Test public void previewAdjacentDatesAppearOnlyAtTheOuterEdges() {
        YearMonth december = YearMonth.of(2026, 12);
        YearMonth january = december.plusMonths(1);
        YearMonth february = december.plusMonths(2);
        assertTrue(CalendarLayout.showPreviewDate(0, december, LocalDate.of(2026, 11, 29)));
        assertFalse(CalendarLayout.showPreviewDate(0, december, LocalDate.of(2027, 1, 1)));
        assertFalse(CalendarLayout.showPreviewDate(1, january, LocalDate.of(2026, 12, 31)));
        assertTrue(CalendarLayout.showPreviewDate(1, january, LocalDate.of(2027, 1, 1)));
        assertFalse(CalendarLayout.showPreviewDate(1, january, LocalDate.of(2027, 2, 1)));
        assertFalse(CalendarLayout.showPreviewDate(2, february, LocalDate.of(2027, 1, 31)));
        assertTrue(CalendarLayout.showPreviewDate(2, february, LocalDate.of(2027, 3, 1)));
    }

    @Test public void cacheCoversTwelveMonthsOfBrowsingIncludingPreviews() throws Exception {
        YearMonth november = YearMonth.of(2026, 11);
        CalendarRange range = CalendarRange.around(november, LONDON);
        assertTrue(range.covers(november.minusMonths(1), LONDON));
        for (int i = 0; i <= 12; i++) assertTrue(range.covers(november.plusMonths(i), LONDON));
        assertFalse(range.covers(november.plusMonths(13), LONDON));
        assertFalse(range.covers(november, ZoneId.of("America/New_York")));
        String text = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + event(
                "UID:future\r\nDTSTART;VALUE=DATE:20261110\r\nDTEND;VALUE=DATE:20261111\r\n"
                + "RRULE:FREQ=MONTHLY;COUNT=16\r\nSUMMARY:Monthly\r\n") + "END:VCALENDAR\r\n";
        List<Event> events = IcsReader.read(text, range.from, range.until, LONDON, 0);
        assertEquals(16, events.size());
        assertEquals(LocalDate.of(2027, 11, 10), events.get(12).firstDay(LONDON));
        assertEquals(LocalDate.of(2028, 2, 10), events.get(15).firstDay(LONDON));
    }

    @Test public void midnightEndDoesNotLeakIntoNextDay() {
        ZonedDateTime start = LocalDate.of(2026, 12, 1).atTime(22, 0).atZone(LONDON);
        Event item = new Event("Late", "", "", start, start.plusHours(2), false, 0);
        assertEquals(LocalDate.of(2026, 12, 1), item.lastDay(LONDON));
    }

    @Test public void previewsCoverFollowingMonthsAndShadeRecurrencesAndSpanningEvents() throws Exception {
        YearMonth displayed = YearMonth.of(2026, 11);
        CalendarLayout last = new CalendarLayout(displayed.plusMonths(3), Collections.emptyList(), LONDON);
        LocalDate until = last.first.plusDays(last.weeks * 7L);
        String text = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
                + event("UID:monthly\r\nDTSTART;VALUE=DATE:20261110\r\nDTEND;VALUE=DATE:20261111\r\n"
                        + "RRULE:FREQ=MONTHLY;COUNT=4\r\nSUMMARY:Monthly\r\n")
                + event("UID:year-end\r\nDTSTART;VALUE=DATE:20261231\r\nDTEND;VALUE=DATE:20270103\r\n"
                        + "SUMMARY:New year trip\r\n") + "END:VCALENDAR\r\n";
        List<Event> events = IcsReader.read(text, displayed.atDay(1), until, LONDON, 0);
        List<CalendarLayout> previews = CalendarLayout.followingMonths(displayed, events, LONDON);
        assertEquals(3, previews.size());
        for (int i = 0; i < previews.size(); i++) {
            CalendarLayout preview = previews.get(i);
            LocalDate tenth = displayed.plusMonths(i + 1).atDay(10);
            int offset = (int) java.time.temporal.ChronoUnit.DAYS.between(preview.first, tenth);
            assertEquals(1, preview.days.get(offset).size());
            assertTrue(preview.days.get(offset + 1).isEmpty());
        }
        CalendarLayout january = previews.get(1);
        int first = (int) java.time.temporal.ChronoUnit.DAYS.between(january.first, LocalDate.of(2027, 1, 1));
        assertEquals(1, january.days.get(first).size());
        assertEquals(1, january.days.get(first + 1).size());
        assertTrue(january.days.get(first + 2).isEmpty());
        assertEquals(LocalDate.of(2027, 2, 1), previews.get(2).first.plusDays(1));
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
