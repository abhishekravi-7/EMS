package com.employee.system.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDate;
import java.time.LocalTime;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class AttendanceDTO {
    
    private Long id;
    private Long employeeId;
    private String employeeName;
    private LocalDate attendanceDate;
    private String status;
    private LocalTime checkInTime;
    private LocalTime checkOutTime;
    private String remarks;
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
