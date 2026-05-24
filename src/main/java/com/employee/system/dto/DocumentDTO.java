package com.employee.system.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class DocumentDTO {
    private Long id;
    private Long employeeId;
    private String docType;
    private String originalFileName;
    private String storedFileName;
    private String contentType;
    private Long size;
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
