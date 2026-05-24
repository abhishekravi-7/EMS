package com.employee.system.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.math.BigDecimal;
import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class SalaryDTO {
    
    private Long id;
    private Long employeeId;
    private String employeeName;
    private Integer salaryMonth;
    private Integer salaryYear;
    private BigDecimal baseSalary;
    private BigDecimal dearnessAllowance;
    private BigDecimal houseRentAllowance;
    private BigDecimal otherAllowances;
    private BigDecimal totalAllowances;
    private BigDecimal incomeTax;
    private BigDecimal providentFund;
    private BigDecimal otherDeductions;
    private BigDecimal totalDeductions;
    private BigDecimal netSalary;
    private String paymentStatus;
    private LocalDate paymentDate;
    private String remarks;
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
