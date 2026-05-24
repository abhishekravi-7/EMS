package com.employee.system.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.math.BigDecimal;
import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class KPIDTO {
    
    private Long id;
    private Long employeeId;
    private String employeeName;
    private String kpiName;
    private String kpiDescription;
    private String measurementUnit;
    private BigDecimal targetValue;
    private BigDecimal currentValue;
    private BigDecimal weight;
    private String frequency;
    private LocalDate startDate;
    private LocalDate endDate;
    private String status;
    private String remarks;
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
