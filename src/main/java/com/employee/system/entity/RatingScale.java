package com.employee.system.entity;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class RatingScale {
    
    private Long id;
    private Integer ratingValue; // 1, 2, 3, 4, 5
    private String ratingLabel; // Poor, Below Average, Average, Good, Excellent
    private String ratingDescription; // Detailed description of what this rating means
    private String colorCode; // For UI - Red, Orange, Yellow, Green, Blue
    private Integer minimumScore; // Minimum score for this rating
    private Integer maximumScore; // Maximum score for this rating
    private Boolean isActive;
}
