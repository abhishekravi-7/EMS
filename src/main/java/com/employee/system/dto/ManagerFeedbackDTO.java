package com.employee.system.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class ManagerFeedbackDTO {
    
    private Long id;
    private Long employeeId;
    private String employeeName;
    private Long providedById;
    private String providedByName;
    private String feedbackType;
    private String feedbackCategory;
    private String feedbackText;
    private Integer rating;
    private String actionItems;
    private LocalDate feedbackDate;
    private String status;
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
