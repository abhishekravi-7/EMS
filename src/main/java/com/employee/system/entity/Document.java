package com.employee.system.entity;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class Document {
    private Long id;
    private Employee employee;
    private String docType; // RESUME, PAN, AADHAAR, EXPERIENCE, EDUCATION, OTHER
    private String originalFileName;
    private String storedFileName;
    private String contentType;
    private Long size;
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
