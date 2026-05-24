package com.employee.system.entity;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDate;
import java.time.LocalTime;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class Attendance {
    
    private Long id;
    private Employee employee;
    private LocalDate attendanceDate;
    private String status; // PRESENT, ABSENT, LATE, HALF_DAY, ON_LEAVE
    private LocalTime checkInTime;
    private LocalTime checkOutTime;
    private String remarks;
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
