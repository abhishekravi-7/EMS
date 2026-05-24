package com.employee.system.repository;

import com.employee.system.entity.Holiday;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.*;
import java.util.stream.Collectors;

@Repository
public class HolidayRepository {
    private static final Map<Long, Holiday> holidays = new HashMap<>();
    private static Long nextId = 1L;

    public HolidayRepository() {
        initializeDummyHolidays();
    }

    private void initializeDummyHolidays() {
        if (holidays.isEmpty()) {
            holidays.put(1L, new Holiday(1L, LocalDate.of(2024, 1, 26), "Republic Day"));
            holidays.put(2L, new Holiday(2L, LocalDate.of(2024, 8, 15), "Independence Day"));
            holidays.put(3L, new Holiday(3L, LocalDate.of(2024, 10, 2), "Gandhi Jayanti"));
            nextId = 4L;
        }
    }

    public List<Holiday> findAll() {
        return new ArrayList<>(holidays.values());
    }

    public List<Holiday> findBetween(LocalDate start, LocalDate end) {
        return holidays.values().stream()
            .filter(h -> !h.getDate().isBefore(start) && !h.getDate().isAfter(end))
            .collect(Collectors.toList());
    }
}
