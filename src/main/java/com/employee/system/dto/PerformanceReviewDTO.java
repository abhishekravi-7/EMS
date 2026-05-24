package com.employee.system.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class PerformanceReviewDTO {
    
    private Long id;
    private Long employeeId;
    private String employeeName;
    private Long reviewedById;
    private String reviewedByName;
    private String reviewPeriod;
    private LocalDate reviewDate;
    private Integer overallRating;
    private Integer technicalSkillsRating;
    private Integer behavioralRating;
    private Integer leadershipRating;
    private Integer teamworkRating;
    private String strengths;
    private String areasForImprovement;
    private String comments;
    private String status;
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
