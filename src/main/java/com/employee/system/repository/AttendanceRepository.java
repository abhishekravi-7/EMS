package com.employee.system.repository;

import com.employee.system.entity.Attendance;
import com.employee.system.entity.Employee;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.*;
import java.util.stream.Collectors;

@Repository
public class AttendanceRepository {
    
    private static final Map<Long, Attendance> attendanceRecords = new HashMap<>();
    private static Long nextId = 1L;
    
    public AttendanceRepository() {
        initializeDummyData();
    }
    
    private void initializeDummyData() {
        if (attendanceRecords.isEmpty()) {
            Employee emp1 = new Employee(1L, "EMP001", "John", "Doe", "john.doe@company.com", "9876543210",
                "IT", "Senior Developer", LocalDate.of(2020, 1, 15),
                "ACTIVE", "123 Main St", LocalDate.of(1990, 5, 20), "MALE",
                LocalDate.now(), LocalDate.now());
            
            attendanceRecords.put(1L, new Attendance(
                1L, emp1, LocalDate.of(2024, 5, 20), "PRESENT",
                java.time.LocalTime.of(9, 0), java.time.LocalTime.of(17, 30), "Regular day",
                LocalDate.now(), LocalDate.now()
            ));
            
            attendanceRecords.put(2L, new Attendance(
                2L, emp1, LocalDate.of(2024, 5, 21), "PRESENT",
                java.time.LocalTime.of(9, 5), java.time.LocalTime.of(17, 30), "Regular day",
                LocalDate.now(), LocalDate.now()
            ));
            
            attendanceRecords.put(3L, new Attendance(
                3L, emp1, LocalDate.of(2024, 5, 22), "ABSENT",
                null, null, "Sick leave",
                LocalDate.now(), LocalDate.now()
            ));
            
            nextId = 4L;
        }
    }
    
    public Attendance save(Attendance attendance) {
        if (attendance.getId() == null) {
            attendance.setId(nextId++);
            attendance.setCreatedAt(LocalDate.now());
        }
        attendance.setUpdatedAt(LocalDate.now());
        attendanceRecords.put(attendance.getId(), attendance);
        return attendance;
    }
    
    public Optional<Attendance> findById(Long id) {
        return Optional.ofNullable(attendanceRecords.get(id));
    }
    
    public List<Attendance> findByEmployee(Employee employee) {
        return attendanceRecords.values().stream()
            .filter(a -> a.getEmployee().getId().equals(employee.getId()))
            .collect(Collectors.toList());
    }
    
    public Optional<Attendance> findByEmployeeAndAttendanceDate(Employee employee, LocalDate date) {
        return attendanceRecords.values().stream()
            .filter(a -> a.getEmployee().getId().equals(employee.getId()) &&
                        a.getAttendanceDate().equals(date))
            .findFirst();
    }
    
    public List<Attendance> findByEmployeeAndAttendanceDateBetween(Employee employee, LocalDate startDate, LocalDate endDate) {
        return attendanceRecords.values().stream()
            .filter(a -> a.getEmployee().getId().equals(employee.getId()) &&
                        !a.getAttendanceDate().isBefore(startDate) &&
                        !a.getAttendanceDate().isAfter(endDate))
            .collect(Collectors.toList());
    }
    
    public List<Attendance> findByAttendanceDateBetween(LocalDate startDate, LocalDate endDate) {
        return attendanceRecords.values().stream()
            .filter(a -> !a.getAttendanceDate().isBefore(startDate) &&
                        !a.getAttendanceDate().isAfter(endDate))
            .collect(Collectors.toList());
    }
    
    public List<Attendance> findByEmployeeAndDateRangeAndStatus(Employee employee, LocalDate startDate, LocalDate endDate, String status) {
        return attendanceRecords.values().stream()
            .filter(a -> a.getEmployee().getId().equals(employee.getId()) &&
                        !a.getAttendanceDate().isBefore(startDate) &&
                        !a.getAttendanceDate().isAfter(endDate) &&
                        a.getStatus().equals(status))
            .collect(Collectors.toList());
    }
    
    public long countPresentDays(Employee employee, LocalDate startDate, LocalDate endDate) {
        return attendanceRecords.values().stream()
            .filter(a -> a.getEmployee().getId().equals(employee.getId()) &&
                        !a.getAttendanceDate().isBefore(startDate) &&
                        !a.getAttendanceDate().isAfter(endDate) &&
                        "PRESENT".equals(a.getStatus()))
            .count();
    }
    
    public long countAbsentDays(Employee employee, LocalDate startDate, LocalDate endDate) {
        return attendanceRecords.values().stream()
            .filter(a -> a.getEmployee().getId().equals(employee.getId()) &&
                        !a.getAttendanceDate().isBefore(startDate) &&
                        !a.getAttendanceDate().isAfter(endDate) &&
                        "ABSENT".equals(a.getStatus()))
            .count();
    }
    
    public void delete(Attendance attendance) {
        attendanceRecords.remove(attendance.getId());
    }
}
