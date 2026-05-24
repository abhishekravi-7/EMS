package com.employee.system.entity;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.math.BigDecimal;
import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class Salary {
    
    private Long id;
    private Employee employee;
    private Integer salaryMonth; // 1-12
    private Integer salaryYear; // 2024, 2025, etc.
    private BigDecimal baseSalary;
    private BigDecimal dearnessAllowance = BigDecimal.ZERO;
    private BigDecimal houseRentAllowance = BigDecimal.ZERO;
    private BigDecimal otherAllowances = BigDecimal.ZERO;
    private BigDecimal totalAllowances = BigDecimal.ZERO;
    private BigDecimal incomeTax = BigDecimal.ZERO;
    private BigDecimal providentFund = BigDecimal.ZERO;
    private BigDecimal otherDeductions = BigDecimal.ZERO;
    private BigDecimal totalDeductions = BigDecimal.ZERO;
    private BigDecimal netSalary = BigDecimal.ZERO;
    private String paymentStatus; // PENDING, PAID, REJECTED
    private LocalDate paymentDate;
    private String remarks;
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
