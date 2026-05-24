package com.employee.system.service;

import com.employee.system.dto.AttendanceDTO;
import com.employee.system.entity.Attendance;
import com.employee.system.entity.Employee;
import com.employee.system.repository.AttendanceRepository;
import com.employee.system.repository.EmployeeRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class AttendanceService {
    
    private final AttendanceRepository attendanceRepository;
    private final EmployeeRepository employeeRepository;
    
    // Mark Attendance
    public AttendanceDTO markAttendance(AttendanceDTO attendanceDTO) {
        Employee employee = employeeRepository.findById(attendanceDTO.getEmployeeId())
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + attendanceDTO.getEmployeeId()));
        
        Attendance attendance = new Attendance();
        attendance.setEmployee(employee);
        attendance.setAttendanceDate(attendanceDTO.getAttendanceDate());
        attendance.setStatus(attendanceDTO.getStatus());
        attendance.setCheckInTime(attendanceDTO.getCheckInTime());
        attendance.setCheckOutTime(attendanceDTO.getCheckOutTime());
        attendance.setRemarks(attendanceDTO.getRemarks());
        
        Attendance savedAttendance = attendanceRepository.save(attendance);
        return convertToDTO(savedAttendance);
    }
    
    // Get Attendance by ID
    public AttendanceDTO getAttendanceById(Long id) {
        Attendance attendance = attendanceRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Attendance not found with id: " + id));
        return convertToDTO(attendance);
    }
    
    // Get Attendance for Employee on specific date
    public AttendanceDTO getAttendanceByEmployeeAndDate(Long employeeId, LocalDate date) {
        Employee employee = employeeRepository.findById(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + employeeId));
        
        Attendance attendance = attendanceRepository.findByEmployeeAndAttendanceDate(employee, date)
            .orElseThrow(() -> new RuntimeException("Attendance not found for employee on date: " + date));
        return convertToDTO(attendance);
    }
    
    // Get All Attendance Records for Employee
    public List<AttendanceDTO> getAttendanceByEmployee(Long employeeId) {
        Employee employee = employeeRepository.findById(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + employeeId));
        
        return attendanceRepository.findByEmployee(employee)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    // Get Attendance Records for Date Range
    public List<AttendanceDTO> getAttendanceByDateRange(Long employeeId, LocalDate startDate, LocalDate endDate) {
        Employee employee = employeeRepository.findById(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + employeeId));
        
        return attendanceRepository.findByEmployeeAndAttendanceDateBetween(employee, startDate, endDate)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    // Get All Attendance Records for Date Range (all employees)
    public List<AttendanceDTO> getAllAttendanceByDateRange(LocalDate startDate, LocalDate endDate) {
        return attendanceRepository.findByAttendanceDateBetween(startDate, endDate)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    // Update Attendance
    public AttendanceDTO updateAttendance(Long id, AttendanceDTO attendanceDTO) {
        Attendance attendance = attendanceRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Attendance not found with id: " + id));
        
        attendance.setStatus(attendanceDTO.getStatus());
        attendance.setCheckInTime(attendanceDTO.getCheckInTime());
        attendance.setCheckOutTime(attendanceDTO.getCheckOutTime());
        attendance.setRemarks(attendanceDTO.getRemarks());
        
        Attendance updatedAttendance = attendanceRepository.save(attendance);
        return convertToDTO(updatedAttendance);
    }
    
    // Delete Attendance
    public void deleteAttendance(Long id) {
        Attendance attendance = attendanceRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Attendance not found with id: " + id));
        attendanceRepository.delete(attendance);
    }
    
    // Get Attendance Summary for Employee
    public AttendanceSummary getAttendanceSummary(Long employeeId, LocalDate startDate, LocalDate endDate) {
        Employee employee = employeeRepository.findById(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + employeeId));
        
        long presentDays = attendanceRepository.countPresentDays(employee, startDate, endDate);
        long absentDays = attendanceRepository.countAbsentDays(employee, startDate, endDate);
        
        List<Attendance> attendanceList = attendanceRepository.findByEmployeeAndAttendanceDateBetween(employee, startDate, endDate);
        
        return AttendanceSummary.builder()
            .employeeId(employeeId)
            .totalDays(attendanceList.size())
            .presentDays(presentDays)
            .absentDays(absentDays)
            .lateDays(attendanceList.stream().filter(a -> "LATE".equals(a.getStatus())).count())
            .halfDays(attendanceList.stream().filter(a -> "HALF_DAY".equals(a.getStatus())).count())
            .leaveDays(attendanceList.stream().filter(a -> "ON_LEAVE".equals(a.getStatus())).count())
            .build();
    }
    
    // Helper method to convert Entity to DTO
    private AttendanceDTO convertToDTO(Attendance attendance) {
        AttendanceDTO dto = new AttendanceDTO();
        dto.setId(attendance.getId());
        dto.setEmployeeId(attendance.getEmployee().getId());
        dto.setEmployeeName(attendance.getEmployee().getFirstName() + " " + attendance.getEmployee().getLastName());
        dto.setAttendanceDate(attendance.getAttendanceDate());
        dto.setStatus(attendance.getStatus());
        dto.setCheckInTime(attendance.getCheckInTime());
        dto.setCheckOutTime(attendance.getCheckOutTime());
        dto.setRemarks(attendance.getRemarks());
        dto.setCreatedAt(attendance.getCreatedAt());
        dto.setUpdatedAt(attendance.getUpdatedAt());
        return dto;
    }
}
