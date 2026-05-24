package com.employee.system.service;

import com.employee.system.dto.LeaveBalanceDTO;
import com.employee.system.dto.LeaveDTO;
import com.employee.system.entity.Employee;
import com.employee.system.entity.Holiday;
import com.employee.system.entity.Leave;
import com.employee.system.repository.EmployeeRepository;
import com.employee.system.repository.HolidayRepository;
import com.employee.system.repository.LeaveRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class LeaveService {

    private final LeaveRepository leaveRepository;
    private final EmployeeRepository employeeRepository;
    private final HolidayRepository holidayRepository;

    // Default yearly entitlements
    private final Map<String, Integer> defaultEntitlements = Map.of(
        "SICK", 10,
        "CASUAL", 7,
        "EARNED", 15
    );

    public LeaveDTO applyLeave(LeaveDTO dto) {
        Employee employee = employeeRepository.findById(dto.getEmployeeId())
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + dto.getEmployeeId()));

        if (dto.getStartDate() == null || dto.getEndDate() == null || dto.getEndDate().isBefore(dto.getStartDate())) {
            throw new RuntimeException("Invalid leave date range");
        }

        // Conflict detection
        if (leaveRepository.hasOverlappingLeave(employee, dto.getStartDate(), dto.getEndDate())) {
            throw new RuntimeException("Leave conflict detected for the requested period");
        }

        int daysRequested = calculateWorkingDays(dto.getStartDate(), dto.getEndDate());

        int year = dto.getStartDate().getYear();
        int entitlement = defaultEntitlements.getOrDefault(dto.getLeaveType(), 0);
        long taken = leaveRepository.countTakenDaysByTypeAndYear(employee, dto.getLeaveType(), year);

        if (taken + daysRequested > entitlement) {
            throw new RuntimeException("Insufficient leave balance. Requested: " + daysRequested + ", Available: " + (entitlement - taken));
        }

        Leave leave = new Leave();
        leave.setEmployee(employee);
        leave.setStartDate(dto.getStartDate());
        leave.setEndDate(dto.getEndDate());
        leave.setLeaveType(dto.getLeaveType());
        leave.setReason(dto.getReason());
        leave.setDays(daysRequested);
        leave.setStatus(dto.getStatus() != null ? dto.getStatus() : "PENDING");

        Leave saved = leaveRepository.save(leave);
        return toDTO(saved);
    }

    public LeaveDTO approveLeave(Long id, boolean approve) {
        Leave leave = leaveRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Leave not found with id: " + id));
        leave.setStatus(approve ? "APPROVED" : "REJECTED");
        Leave updated = leaveRepository.save(leave);
        return toDTO(updated);
    }

    public LeaveDTO getLeaveById(Long id) {
        Leave leave = leaveRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Leave not found with id: " + id));
        return toDTO(leave);
    }

    public List<LeaveDTO> getLeavesByEmployee(Long employeeId) {
        Employee employee = employeeRepository.findById(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + employeeId));
        return leaveRepository.findByEmployee(employee).stream().map(this::toDTO).collect(Collectors.toList());
    }

    public List<LeaveDTO> getLeavesByStatus(String status) {
        return leaveRepository.findByStatus(status).stream().map(this::toDTO).collect(Collectors.toList());
    }

    public LeaveBalanceDTO getLeaveBalance(Long employeeId, int year) {
        Employee employee = employeeRepository.findById(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + employeeId));

        Map<String, Integer> balances = new HashMap<>();
        for (Map.Entry<String, Integer> e : defaultEntitlements.entrySet()) {
            long taken = leaveRepository.countTakenDaysByTypeAndYear(employee, e.getKey(), year);
            balances.put(e.getKey(), Math.max(0, e.getValue() - (int) taken));
        }

        return new LeaveBalanceDTO(employeeId, balances);
    }

    private int calculateWorkingDays(LocalDate start, LocalDate end) {
        long days = ChronoUnit.DAYS.between(start, end) + 1;
        List<Holiday> holidays = holidayRepository.findBetween(start, end);
        long holidayCount = holidays.size();
        int working = (int) Math.max(0, days - holidayCount);
        return working;
    }

    private LeaveDTO toDTO(Leave l) {
        LeaveDTO dto = new LeaveDTO();
        dto.setId(l.getId());
        dto.setEmployeeId(l.getEmployee() != null ? l.getEmployee().getId() : null);
        dto.setEmployeeName(l.getEmployee() != null ? l.getEmployee().getFirstName() + " " + l.getEmployee().getLastName() : null);
        dto.setStartDate(l.getStartDate());
        dto.setEndDate(l.getEndDate());
        dto.setLeaveType(l.getLeaveType());
        dto.setStatus(l.getStatus());
        dto.setReason(l.getReason());
        dto.setDays(l.getDays());
        dto.setCreatedAt(l.getCreatedAt());
        dto.setUpdatedAt(l.getUpdatedAt());
        return dto;
    }
}
