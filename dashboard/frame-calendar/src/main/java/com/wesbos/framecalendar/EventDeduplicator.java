package com.wesbos.framecalendar;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

final class EventDeduplicator {
    static List<Event> unique(List<Event> events) {
        Map<List<Object>, Event> preferred = new HashMap<>();
        Set<List<Object>> crossCalendar = new HashSet<>();
        for (Event event : events) {
            List<Object> key = key(event);
            Event existing = preferred.get(key);
            if (existing == null) preferred.put(key, event);
            else {
                if (existing.source != event.source) crossCalendar.add(key);
                if (event.source == 0) preferred.put(key, event);
            }
        }
        List<Event> result = new ArrayList<>();
        Set<List<Object>> emitted = new HashSet<>();
        for (Event event : events) {
            List<Object> key = key(event);
            if (!crossCalendar.contains(key)) result.add(event);
            else if (emitted.add(key)) result.add(preferred.get(key));
        }
        return result;
    }

    private static List<Object> key(Event event) {
        return Arrays.<Object>asList(event.title, event.location, event.description, event.allDay,
                event.allDay ? event.start.toLocalDate() : event.start.toInstant(),
                event.allDay ? event.end.toLocalDate() : event.end.toInstant());
    }
}
