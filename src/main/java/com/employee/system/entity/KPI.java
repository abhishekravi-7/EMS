package com.employee.system.entity;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.math.BigDecimal;
import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class KPI {
    
    private Long id;
    private Employee employee;
    private String kpiName;
    private String kpiDescription;
    private String measurementUnit; // Percentage, Count, Amount, Hours, etc.
    private BigDecimal targetValue;
    private BigDecimal currentValue = BigDecimal.ZERO;
    private BigDecimal weight; // Weightage in overall performance (0-100)
    private String frequency; // MONTHLY, QUARTERLY, YEARLY
    private LocalDate startDate;
    private LocalDate endDate;
    private String status; // ACTIVE, COMPLETED, PAUSED
    private String remarks;
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
