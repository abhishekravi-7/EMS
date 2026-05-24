package com.employee.system.repository;

import com.employee.system.entity.Leave;
import com.employee.system.entity.Employee;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.*;
import java.util.stream.Collectors;

@Repository
public class LeaveRepository {

    private static final Map<Long, Leave> leaves = new HashMap<>();
    private static Long nextId = 1L;

    public LeaveRepository() {
        initializeDummyData();
    }

    private void initializeDummyData() {
        // no-op initial data; leaves will be created via API
    }

    public Leave save(Leave leave) {
        if (leave.getId() == null) {
            leave.setId(nextId++);
            leave.setCreatedAt(LocalDate.now());
        }
        leave.setUpdatedAt(LocalDate.now());
        leaves.put(leave.getId(), leave);
        return leave;
    }

    public Optional<Leave> findById(Long id) {
        return Optional.ofNullable(leaves.get(id));
    }

    public List<Leave> findByEmployee(Employee employee) {
        return leaves.values().stream()
            .filter(l -> l.getEmployee() != null && l.getEmployee().getId().equals(employee.getId()))
            .collect(Collectors.toList());
    }

    public List<Leave> findByStatus(String status) {
        return leaves.values().stream()
            .filter(l -> status.equals(l.getStatus()))
            .collect(Collectors.toList());
    }

    public List<Leave> findByEmployeeAndDateRange(Employee employee, LocalDate start, LocalDate end) {
        return leaves.values().stream()
            .filter(l -> l.getEmployee() != null && l.getEmployee().getId().equals(employee.getId())
                && !(l.getEndDate().isBefore(start) || l.getStartDate().isAfter(end)))
            .collect(Collectors.toList());
    }

    public boolean hasOverlappingLeave(Employee employee, LocalDate start, LocalDate end) {
        return leaves.values().stream()
            .filter(l -> l.getEmployee() != null && l.getEmployee().getId().equals(employee.getId())
                && ("PENDING".equals(l.getStatus()) || "APPROVED".equals(l.getStatus())))
            .anyMatch(l -> !(l.getEndDate().isBefore(start) || l.getStartDate().isAfter(end)));
    }

    public long countTakenDaysByTypeAndYear(Employee employee, String type, int year) {
        return leaves.values().stream()
            .filter(l -> l.getEmployee() != null && l.getEmployee().getId().equals(employee.getId())
                && type.equals(l.getLeaveType())
                && l.getStartDate().getYear() == year)
            .mapToLong(l -> l.getDays() != null ? l.getDays() : 0)
            .sum();
    }

    public void delete(Leave leave) {
        leaves.remove(leave.getId());
    }
}
