package com.employee.system.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class RatingScaleDTO {
    
    private Long id;
    private Integer ratingValue;
    private String ratingLabel;
    private String ratingDescription;
    private String colorCode;
    private Integer minimumScore;
    private Integer maximumScore;
    private Boolean isActive;
}
