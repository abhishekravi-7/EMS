package com.employee.system.entity;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class Leave {
    private Long id;
    private Employee employee;
    private LocalDate startDate;
    private LocalDate endDate;
    private String leaveType; // SICK, CASUAL, EARNED
    private String status; // PENDING, APPROVED, REJECTED, CANCELLED
    private String reason;
    private Integer days;
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
