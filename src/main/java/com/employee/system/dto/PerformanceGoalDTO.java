package com.employee.system.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class PerformanceGoalDTO {
    
    private Long id;
    private Long employeeId;
    private String employeeName;
    private String goalTitle;
    private String goalDescription;
    private String category;
    private LocalDate startDate;
    private LocalDate targetDate;
    private String status;
    private String priority;
    private Integer progressPercentage;
    private String keyResults;
    private String remarks;
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
