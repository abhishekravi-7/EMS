package com.employee.system.service;

import com.employee.system.dto.AttendanceDTO;
import com.employee.system.entity.Attendance;
import com.employee.system.entity.Employee;
import com.employee.system.repository.AttendanceRepository;
import com.employee.system.repository.EmployeeRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDate;
import java.time.LocalTime;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class AttendanceServiceTest {

    @Mock
    private AttendanceRepository attendanceRepository;

    @Mock
    private EmployeeRepository employeeRepository;

    @InjectMocks
    private AttendanceService attendanceService;

    private Employee employee;
    private Attendance attendance;
    private AttendanceDTO attendanceDTO;

    @BeforeEach
    void setUp() {
        employee = new Employee();
        employee.setId(1L);
        employee.setFirstName("John");
        employee.setLastName("Doe");

        attendance = new Attendance();
        attendance.setId(10L);
        attendance.setEmployee(employee);
        attendance.setAttendanceDate(LocalDate.of(2024, 5, 24));
        attendance.setStatus("PRESENT");
        attendance.setCheckInTime(LocalTime.of(9, 0));
        attendance.setCheckOutTime(LocalTime.of(17, 30));

        attendanceDTO = new AttendanceDTO();
        attendanceDTO.setEmployeeId(1L);
        attendanceDTO.setAttendanceDate(LocalDate.of(2024, 5, 24));
        attendanceDTO.setStatus("PRESENT");
        attendanceDTO.setCheckInTime(LocalTime.of(9, 0));
        attendanceDTO.setCheckOutTime(LocalTime.of(17, 30));
    }

    @Test
    void testMarkAttendance_Success() {
        when(employeeRepository.findById(1L)).thenReturn(Optional.of(employee));
        when(attendanceRepository.save(any(Attendance.class))).thenReturn(attendance);

        AttendanceDTO result = attendanceService.markAttendance(attendanceDTO);

        assertNotNull(result);
        assertEquals(10L, result.getId());
        assertEquals("PRESENT", result.getStatus());
        verify(attendanceRepository, times(1)).save(any(Attendance.class));
    }

    @Test
    void testMarkAttendance_EmployeeNotFound() {
        when(employeeRepository.findById(1L)).thenReturn(Optional.empty());

        assertThrows(RuntimeException.class, () -> attendanceService.markAttendance(attendanceDTO));
        verify(attendanceRepository, never()).save(any(Attendance.class));
    }

    @Test
    void testGetAttendanceById_Success() {
        when(attendanceRepository.findById(10L)).thenReturn(Optional.of(attendance));

        AttendanceDTO result = attendanceService.getAttendanceById(10L);

        assertNotNull(result);
        assertEquals(10L, result.getId());
    }

    @Test
    void testGetAttendanceById_NotFound() {
        when(attendanceRepository.findById(10L)).thenReturn(Optional.empty());

        assertThrows(RuntimeException.class, () -> attendanceService.getAttendanceById(10L));
    }

    @Test
    void testGetAttendanceByEmployeeAndDate() {
        when(employeeRepository.findById(1L)).thenReturn(Optional.of(employee));
        when(attendanceRepository.findByEmployeeAndAttendanceDate(employee, LocalDate.of(2024, 5, 24)))
                .thenReturn(Optional.of(attendance));

        AttendanceDTO result = attendanceService.getAttendanceByEmployeeAndDate(1L, LocalDate.of(2024, 5, 24));

        assertNotNull(result);
        assertEquals(10L, result.getId());
    }

    @Test
    void testGetAttendanceByEmployee() {
        when(employeeRepository.findById(1L)).thenReturn(Optional.of(employee));
        when(attendanceRepository.findByEmployee(employee)).thenReturn(Collections.singletonList(attendance));

        List<AttendanceDTO> result = attendanceService.getAttendanceByEmployee(1L);

        assertFalse(result.isEmpty());
        assertEquals(1, result.size());
    }

    @Test
    void testGetAttendanceByDateRange() {
        LocalDate start = LocalDate.of(2024, 5, 1);
        LocalDate end = LocalDate.of(2024, 5, 31);
        when(employeeRepository.findById(1L)).thenReturn(Optional.of(employee));
        when(attendanceRepository.findByEmployeeAndAttendanceDateBetween(employee, start, end))
                .thenReturn(Collections.singletonList(attendance));

        List<AttendanceDTO> result = attendanceService.getAttendanceByDateRange(1L, start, end);

        assertFalse(result.isEmpty());
    }

    @Test
    void testGetAllAttendanceByDateRange() {
        LocalDate start = LocalDate.of(2024, 5, 1);
        LocalDate end = LocalDate.of(2024, 5, 31);
        when(attendanceRepository.findByAttendanceDateBetween(start, end))
                .thenReturn(Collections.singletonList(attendance));

        List<AttendanceDTO> result = attendanceService.getAllAttendanceByDateRange(start, end);

        assertFalse(result.isEmpty());
    }

    @Test
    void testUpdateAttendance() {
        when(attendanceRepository.findById(10L)).thenReturn(Optional.of(attendance));
        when(attendanceRepository.save(any(Attendance.class))).thenReturn(attendance);

        attendanceDTO.setStatus("LATE");
        AttendanceDTO result = attendanceService.updateAttendance(10L, attendanceDTO);

        assertNotNull(result);
        assertEquals("LATE", result.getStatus());
    }

    @Test
    void testDeleteAttendance() {
        when(attendanceRepository.findById(10L)).thenReturn(Optional.of(attendance));

        assertDoesNotThrow(() -> attendanceService.deleteAttendance(10L));
        verify(attendanceRepository, times(1)).delete(attendance);
    }

    @Test
    void testGetAttendanceSummary() {
        LocalDate start = LocalDate.of(2024, 5, 1);
        LocalDate end = LocalDate.of(2024, 5, 31);
        when(employeeRepository.findById(1L)).thenReturn(Optional.of(employee));
        when(attendanceRepository.countPresentDays(employee, start, end)).thenReturn(1L);
        when(attendanceRepository.countAbsentDays(employee, start, end)).thenReturn(0L);
        when(attendanceRepository.findByEmployeeAndAttendanceDateBetween(employee, start, end))
                .thenReturn(Arrays.asList(attendance));

        AttendanceSummary result = attendanceService.getAttendanceSummary(1L, start, end);

        assertNotNull(result);
        assertEquals(1L, result.getEmployeeId());
        assertEquals(1, result.getTotalDays());
        assertEquals(1, result.getPresentDays());
    }
}
