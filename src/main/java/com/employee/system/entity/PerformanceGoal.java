package com.employee.system.entity;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class PerformanceGoal {
    
    private Long id;
    private Employee employee;
    private String goalTitle;
    private String goalDescription;
    private String category; // Technical, Behavioral, Sales, etc.
    private LocalDate startDate;
    private LocalDate targetDate;
    private String status; // DRAFT, ACTIVE, COMPLETED, CANCELLED
    private String priority; // HIGH, MEDIUM, LOW
    private Integer progressPercentage; // 0-100
    private String keyResults; // Measurable outcomes
    private String remarks;
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
