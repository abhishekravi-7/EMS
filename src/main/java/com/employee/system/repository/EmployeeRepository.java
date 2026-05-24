package com.employee.system.repository;

import com.employee.system.entity.Employee;
import org.springframework.stereotype.Repository;

import java.util.*;
import java.util.stream.Collectors;

@Repository
public class EmployeeRepository {
    
    private static final Map<Long, Employee> employees = new HashMap<>();
    private static Long nextId = 1L;
    
    public EmployeeRepository() {
        initializeDummyData();
    }
    
    private void initializeDummyData() {
        if (employees.isEmpty()) {
            employees.put(1L, new Employee(
                1L, "EMP001", "John", "Doe", "john.doe@company.com", "9876543210",
                "IT", "Senior Developer", java.time.LocalDate.of(2020, 1, 15),
                "ACTIVE", "123 Main St", java.time.LocalDate.of(1990, 5, 20), "MALE",
                java.time.LocalDate.now(), java.time.LocalDate.now()
            ));
            
            employees.put(2L, new Employee(
                2L, "EMP002", "Jane", "Smith", "jane.smith@company.com", "9876543211",
                "HR", "HR Manager", java.time.LocalDate.of(2019, 3, 10),
                "ACTIVE", "456 Oak Ave", java.time.LocalDate.of(1988, 8, 15), "FEMALE",
                java.time.LocalDate.now(), java.time.LocalDate.now()
            ));
            
            employees.put(3L, new Employee(
                3L, "EMP003", "Robert", "Johnson", "robert.johnson@company.com", "9876543212",
                "IT", "Junior Developer", java.time.LocalDate.of(2021, 6, 1),
                "ACTIVE", "789 Pine Rd", java.time.LocalDate.of(1995, 12, 10), "MALE",
                java.time.LocalDate.now(), java.time.LocalDate.now()
            ));
            
            employees.put(4L, new Employee(
                4L, "EMP004", "Sarah", "Williams", "sarah.williams@company.com", "9876543213",
                "Finance", "Finance Executive", java.time.LocalDate.of(2018, 9, 5),
                "ACTIVE", "321 Elm St", java.time.LocalDate.of(1992, 3, 25), "FEMALE",
                java.time.LocalDate.now(), java.time.LocalDate.now()
            ));
            
            nextId = 5L;
        }
    }
    
    public Employee save(Employee employee) {
        if (employee.getId() == null) {
            employee.setId(nextId++);
            employee.setCreatedAt(java.time.LocalDate.now());
        }
        employee.setUpdatedAt(java.time.LocalDate.now());
        employees.put(employee.getId(), employee);
        return employee;
    }
    
    public Optional<Employee> findById(Long id) {
        return Optional.ofNullable(employees.get(id));
    }
    
    public Optional<Employee> findByEmployeeId(String employeeId) {
        return employees.values().stream()
            .filter(e -> e.getEmployeeId().equals(employeeId))
            .findFirst();
    }
    
    public Optional<Employee> findByEmail(String email) {
        return employees.values().stream()
            .filter(e -> e.getEmail().equals(email))
            .findFirst();
    }
    
    public List<Employee> findByDepartment(String department) {
        return employees.values().stream()
            .filter(e -> e.getDepartment().equalsIgnoreCase(department))
            .collect(Collectors.toList());
    }
    
    public List<Employee> findByDesignation(String designation) {
        return employees.values().stream()
            .filter(e -> e.getDesignation().equalsIgnoreCase(designation))
            .collect(Collectors.toList());
    }
    
    public List<Employee> findByStatus(String status) {
        return employees.values().stream()
            .filter(e -> e.getStatus().equalsIgnoreCase(status))
            .collect(Collectors.toList());
    }
    
    public List<Employee> findAll() {
        return new ArrayList<>(employees.values());
    }
    
    public List<Employee> searchByName(String name) {
        return employees.values().stream()
            .filter(e -> e.getFirstName().toLowerCase().contains(name.toLowerCase()) || 
                        e.getLastName().toLowerCase().contains(name.toLowerCase()))
            .collect(Collectors.toList());
    }
    
    public long countActiveEmployees() {
        return employees.values().stream()
            .filter(e -> "ACTIVE".equals(e.getStatus()))
            .count();
    }
    
    public void delete(Employee employee) {
        employees.remove(employee.getId());
    }
}
