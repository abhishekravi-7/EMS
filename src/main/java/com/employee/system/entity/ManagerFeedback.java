package com.employee.system.entity;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class ManagerFeedback {
    
    private Long id;
    private Employee employee;
    private Employee providedBy; // Manager giving feedback
    private String feedbackType; // Formal, Informal, Scheduled, Ad-hoc
    private String feedbackCategory; // Performance, Behavior, Competency, Development
    private String feedbackText;
    private Integer rating; // 1-5 (for this specific feedback)
    private String actionItems;
    private LocalDate feedbackDate;
    private String status; // DRAFT, SHARED, ACKNOWLEDGED
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
