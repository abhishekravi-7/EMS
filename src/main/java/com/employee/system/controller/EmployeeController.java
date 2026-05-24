package com.employee.system.controller;

import com.employee.system.dto.EmployeeDTO;
import com.employee.system.service.EmployeeService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/employees")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class EmployeeController {
    
    private final EmployeeService employeeService;
    
    // Create Employee
    @PostMapping
    public ResponseEntity<EmployeeDTO> createEmployee(@RequestBody EmployeeDTO employeeDTO) {
        EmployeeDTO createdEmployee = employeeService.createEmployee(employeeDTO);
        return ResponseEntity.status(HttpStatus.CREATED).body(createdEmployee);
    }
    
    // Get Employee by ID
    @GetMapping("/{id}")
    public ResponseEntity<EmployeeDTO> getEmployeeById(@PathVariable Long id) {
        EmployeeDTO employee = employeeService.getEmployeeById(id);
        return ResponseEntity.ok(employee);
    }
    
    // Get Employee by Employee ID
    @GetMapping("/emp/{employeeId}")
    public ResponseEntity<EmployeeDTO> getEmployeeByEmployeeId(@PathVariable String employeeId) {
        EmployeeDTO employee = employeeService.getEmployeeByEmployeeId(employeeId);
        return ResponseEntity.ok(employee);
    }
    
    // Get All Employees
    @GetMapping
    public ResponseEntity<List<EmployeeDTO>> getAllEmployees() {
        List<EmployeeDTO> employees = employeeService.getAllEmployees();
        return ResponseEntity.ok(employees);
    }
    
    // Get Employees by Department
    @GetMapping("/department/{department}")
    public ResponseEntity<List<EmployeeDTO>> getEmployeesByDepartment(@PathVariable String department) {
        List<EmployeeDTO> employees = employeeService.getEmployeesByDepartment(department);
        return ResponseEntity.ok(employees);
    }
    
    // Get Employees by Designation
    @GetMapping("/designation/{designation}")
    public ResponseEntity<List<EmployeeDTO>> getEmployeesByDesignation(@PathVariable String designation) {
        List<EmployeeDTO> employees = employeeService.getEmployeesByDesignation(designation);
        return ResponseEntity.ok(employees);
    }
    
    // Search Employees by Name
    @GetMapping("/search")
    public ResponseEntity<List<EmployeeDTO>> searchEmployeesByName(@RequestParam String name) {
        List<EmployeeDTO> employees = employeeService.searchEmployeesByName(name);
        return ResponseEntity.ok(employees);
    }
    
    // Update Employee
    @PutMapping("/{id}")
    public ResponseEntity<EmployeeDTO> updateEmployee(@PathVariable Long id, @RequestBody EmployeeDTO employeeDTO) {
        EmployeeDTO updatedEmployee = employeeService.updateEmployee(id, employeeDTO);
        return ResponseEntity.ok(updatedEmployee);
    }
    
    // Change Employee Status
    @PatchMapping("/{id}/status")
    public ResponseEntity<EmployeeDTO> changeEmployeeStatus(
        @PathVariable Long id,
        @RequestParam String status
    ) {
        EmployeeDTO updatedEmployee = employeeService.changeEmployeeStatus(id, status);
        return ResponseEntity.ok(updatedEmployee);
    }
    
    // Delete Employee
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteEmployee(@PathVariable Long id) {
        employeeService.deleteEmployee(id);
        return ResponseEntity.noContent().build();
    }
    
    // Get Active Employees Count
    @GetMapping("/stats/active-count")
    public ResponseEntity<Long> getActiveEmployeesCount() {
        long count = employeeService.getActiveEmployeesCount();
        return ResponseEntity.ok(count);
    }
}
