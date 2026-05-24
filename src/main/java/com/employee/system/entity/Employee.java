package com.employee.system.entity;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class Employee {
    
    private Long id;
    private String employeeId;
    private String firstName;
    private String lastName;
    private String email;
    private String phoneNumber;
    private String department;
    private String designation;
    private LocalDate dateOfJoining;
    private String status; // ACTIVE, INACTIVE, ON_LEAVE
    private String address;
    private LocalDate dateOfBirth;
    private String gender;
    private LocalDate createdAt;
    private LocalDate updatedAt;
}
