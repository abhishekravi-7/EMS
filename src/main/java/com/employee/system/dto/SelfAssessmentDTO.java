package com.employee.system.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class SelfAssessmentDTO {
    
    private Long id;
    private Long employeeId;
    private String employeeName;
    private String assessmentPeriod;
    private LocalDate assessmentDate;
    private Integer selfRating;
    private Integer technicalSkillsRating;
    private Integer behavioralRating;
    private Integer leadershipRating;
    private Integer teamworkRating;
    private String accomplishments;
    private String strengthsIdentified;
    private String improvementAreas;
    private String careerGoals;
    private String supportRequired;
    private String status;
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
