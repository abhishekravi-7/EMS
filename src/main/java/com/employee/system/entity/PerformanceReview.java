package com.employee.system.entity;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class PerformanceReview {
    
    private Long id;
    private Employee employee;
    private Employee reviewedBy; // Manager who conducted review
    private String reviewPeriod; // Q1 2024, Q2 2024, Annual 2024, etc.
    private LocalDate reviewDate;
    private Integer overallRating; // 1-5
    private Integer technicalSkillsRating; // 1-5
    private Integer behavioralRating; // 1-5
    private Integer leadershipRating; // 1-5
    private Integer teamworkRating; // 1-5
    private String strengths;
    private String areasForImprovement;
    private String comments;
    private String status; // DRAFT, COMPLETED, ARCHIVED
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
