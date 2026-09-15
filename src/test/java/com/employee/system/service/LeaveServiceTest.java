package com.employee.system.service;

import com.employee.system.dto.LeaveBalanceDTO;
import com.employee.system.dto.LeaveDTO;
import com.employee.system.entity.Employee;
import com.employee.system.entity.Leave;
import com.employee.system.repository.EmployeeRepository;
import com.employee.system.repository.HolidayRepository;
import com.employee.system.repository.LeaveRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDate;
import java.util.Collections;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class LeaveServiceTest {

    @Mock
    private LeaveRepository leaveRepository;

    @Mock
    private EmployeeRepository employeeRepository;

    @Mock
    private HolidayRepository holidayRepository;

    @InjectMocks
    private LeaveService leaveService;

    private Employee employee;
    private Leave leave;
    private LeaveDTO leaveDTO;

    @BeforeEach
    void setUp() {
        employee = new Employee();
        employee.setId(1L);

        leave = new Leave();
        leave.setId(100L);
        leave.setEmployee(employee);
        leave.setStartDate(LocalDate.of(2024, 6, 1));
        leave.setEndDate(LocalDate.of(2024, 6, 5));
        leave.setLeaveType("SICK");
        leave.setStatus("PENDING");
        leave.setDays(5);

        leaveDTO = new LeaveDTO();
        leaveDTO.setEmployeeId(1L);
        leaveDTO.setStartDate(LocalDate.of(2024, 6, 1));
        leaveDTO.setEndDate(LocalDate.of(2024, 6, 5));
        leaveDTO.setLeaveType("SICK");
    }

    @Test
    void testApplyLeave_Success() {
        when(employeeRepository.findById(1L)).thenReturn(Optional.of(employee));
        when(leaveRepository.hasOverlappingLeave(employee, leaveDTO.getStartDate(), leaveDTO.getEndDate())).thenReturn(false);
        when(holidayRepository.findBetween(leaveDTO.getStartDate(), leaveDTO.getEndDate())).thenReturn(Collections.emptyList());
        when(leaveRepository.countTakenDaysByTypeAndYear(employee, "SICK", 2024)).thenReturn(0L);
        when(leaveRepository.save(any(Leave.class))).thenReturn(leave);

        LeaveDTO result = leaveService.applyLeave(leaveDTO);

        assertNotNull(result);
        assertEquals(100L, result.getId());
    }

    @Test
    void testApplyLeave_ConflictDetected() {
        when(employeeRepository.findById(1L)).thenReturn(Optional.of(employee));
        when(leaveRepository.hasOverlappingLeave(employee, leaveDTO.getStartDate(), leaveDTO.getEndDate())).thenReturn(true);

        assertThrows(RuntimeException.class, () -> leaveService.applyLeave(leaveDTO));
    }

    @Test
    void testApplyLeave_InsufficientBalance() {
        when(employeeRepository.findById(1L)).thenReturn(Optional.of(employee));
        when(leaveRepository.hasOverlappingLeave(employee, leaveDTO.getStartDate(), leaveDTO.getEndDate())).thenReturn(false);
        when(holidayRepository.findBetween(leaveDTO.getStartDate(), leaveDTO.getEndDate())).thenReturn(Collections.emptyList());
        when(leaveRepository.countTakenDaysByTypeAndYear(employee, "SICK", 2024)).thenReturn(10L); // Max is 10

        RuntimeException ex = assertThrows(RuntimeException.class, () -> leaveService.applyLeave(leaveDTO));
        assertTrue(ex.getMessage().contains("Insufficient leave balance"));
    }

    @Test
    void testApproveLeave_Approve() {
        when(leaveRepository.findById(100L)).thenReturn(Optional.of(leave));
        when(leaveRepository.save(any(Leave.class))).thenReturn(leave);

        LeaveDTO result = leaveService.approveLeave(100L, true);

        assertEquals("APPROVED", result.getStatus());
    }

    @Test
    void testApproveLeave_Reject() {
        when(leaveRepository.findById(100L)).thenReturn(Optional.of(leave));
        when(leaveRepository.save(any(Leave.class))).thenReturn(leave);

        LeaveDTO result = leaveService.approveLeave(100L, false);

        assertEquals("REJECTED", result.getStatus());
    }

    @Test
    void testGetLeaveById() {
        when(leaveRepository.findById(100L)).thenReturn(Optional.of(leave));

        LeaveDTO result = leaveService.getLeaveById(100L);

        assertNotNull(result);
        assertEquals(100L, result.getId());
    }

    @Test
    void testGetLeavesByEmployee() {
        when(employeeRepository.findById(1L)).thenReturn(Optional.of(employee));
        when(leaveRepository.findByEmployee(employee)).thenReturn(Collections.singletonList(leave));

        List<LeaveDTO> result = leaveService.getLeavesByEmployee(1L);

        assertFalse(result.isEmpty());
    }

    @Test
    void testGetLeavesByStatus() {
        when(leaveRepository.findByStatus("PENDING")).thenReturn(Collections.singletonList(leave));

        List<LeaveDTO> result = leaveService.getLeavesByStatus("PENDING");

        assertFalse(result.isEmpty());
    }

    @Test
    void testGetLeaveBalance() {
        when(employeeRepository.findById(1L)).thenReturn(Optional.of(employee));
        when(leaveRepository.countTakenDaysByTypeAndYear(eq(employee), anyString(), eq(2024))).thenReturn(2L);

        LeaveBalanceDTO result = leaveService.getLeaveBalance(1L, 2024);

        assertNotNull(result);
        assertEquals(1L, result.getEmployeeId());
        // 10 - 2 = 8 for SICK
        assertEquals(8, result.getBalances().get("SICK"));
    }
}

