package com.employee.system.controller;

import com.employee.system.dto.AttendanceDTO;
import com.employee.system.service.AttendanceService;
import com.employee.system.service.AttendanceSummary;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;

@RestController
@RequestMapping("/api/attendance")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class AttendanceController {
    
    private final AttendanceService attendanceService;
    
    // Mark Attendance
    @PostMapping
    public ResponseEntity<AttendanceDTO> markAttendance(@RequestBody AttendanceDTO attendanceDTO) {
        AttendanceDTO createdAttendance = attendanceService.markAttendance(attendanceDTO);
        return ResponseEntity.status(HttpStatus.CREATED).body(createdAttendance);
    }
    
    // Get Attendance by ID
    @GetMapping("/{id}")
    public ResponseEntity<AttendanceDTO> getAttendanceById(@PathVariable Long id) {
        AttendanceDTO attendance = attendanceService.getAttendanceById(id);
        return ResponseEntity.ok(attendance);
    }
    
    // Get Attendance for Employee on specific date
    @GetMapping("/employee/{employeeId}/date")
    public ResponseEntity<AttendanceDTO> getAttendanceByEmployeeAndDate(
        @PathVariable Long employeeId,
        @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date
    ) {
        AttendanceDTO attendance = attendanceService.getAttendanceByEmployeeAndDate(employeeId, date);
        return ResponseEntity.ok(attendance);
    }
    
    // Get All Attendance Records for Employee
    @GetMapping("/employee/{employeeId}")
    public ResponseEntity<List<AttendanceDTO>> getAttendanceByEmployee(@PathVariable Long employeeId) {
        List<AttendanceDTO> attendanceList = attendanceService.getAttendanceByEmployee(employeeId);
        return ResponseEntity.ok(attendanceList);
    }
    
    // Get Attendance Records for Date Range for specific Employee
    @GetMapping("/employee/{employeeId}/range")
    public ResponseEntity<List<AttendanceDTO>> getAttendanceByDateRange(
        @PathVariable Long employeeId,
        @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate startDate,
        @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate endDate
    ) {
        List<AttendanceDTO> attendanceList = attendanceService.getAttendanceByDateRange(employeeId, startDate, endDate);
        return ResponseEntity.ok(attendanceList);
    }
    
    // Get All Attendance Records for Date Range (all employees)
    @GetMapping("/range")
    public ResponseEntity<List<AttendanceDTO>> getAllAttendanceByDateRange(
        @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate startDate,
        @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate endDate
    ) {
        List<AttendanceDTO> attendanceList = attendanceService.getAllAttendanceByDateRange(startDate, endDate);
        return ResponseEntity.ok(attendanceList);
    }
    
    // Update Attendance
    @PutMapping("/{id}")
    public ResponseEntity<AttendanceDTO> updateAttendance(
        @PathVariable Long id,
        @RequestBody AttendanceDTO attendanceDTO
    ) {
        AttendanceDTO updatedAttendance = attendanceService.updateAttendance(id, attendanceDTO);
        return ResponseEntity.ok(updatedAttendance);
    }
    
    // Delete Attendance
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteAttendance(@PathVariable Long id) {
        attendanceService.deleteAttendance(id);
        return ResponseEntity.noContent().build();
    }
    
    // Get Attendance Summary for Employee
    @GetMapping("/employee/{employeeId}/summary")
    public ResponseEntity<AttendanceSummary> getAttendanceSummary(
        @PathVariable Long employeeId,
        @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate startDate,
        @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate endDate
    ) {
        AttendanceSummary summary = attendanceService.getAttendanceSummary(employeeId, startDate, endDate);
        return ResponseEntity.ok(summary);
    }
}
