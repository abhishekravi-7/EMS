package com.employee.system.entity;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class SelfAssessment {
    
    private Long id;
    private Employee employee;
    private String assessmentPeriod; // Q1 2024, Q2 2024, Annual 2024, etc.
    private LocalDate assessmentDate;
    private Integer selfRating; // 1-5
    private Integer technicalSkillsRating; // 1-5
    private Integer behavioralRating; // 1-5
    private Integer leadershipRating; // 1-5
    private Integer teamworkRating; // 1-5
    private String accomplishments;
    private String strengthsIdentified;
    private String improvementAreas;
    private String careerGoals;
    private String supportRequired;
    private String status; // DRAFT, SUBMITTED, REVIEWED
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
