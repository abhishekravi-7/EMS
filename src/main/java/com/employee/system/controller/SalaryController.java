package com.employee.system.controller;

import com.employee.system.dto.SalaryDTO;
import com.employee.system.service.SalaryService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.List;

@RestController
@RequestMapping("/api/salary")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class SalaryController {
    
    private final SalaryService salaryService;
    
    // Add/Create Salary
    @PostMapping
    public ResponseEntity<SalaryDTO> addSalary(@RequestBody SalaryDTO salaryDTO) {
        SalaryDTO createdSalary = salaryService.addSalary(salaryDTO);
        return ResponseEntity.status(HttpStatus.CREATED).body(createdSalary);
    }
    
    // Get Salary by ID
    @GetMapping("/{id}")
    public ResponseEntity<SalaryDTO> getSalaryById(@PathVariable Long id) {
        SalaryDTO salary = salaryService.getSalaryById(id);
        return ResponseEntity.ok(salary);
    }
    
    // Get Salary for Employee and Month/Year
    @GetMapping("/employee/{employeeId}/month")
    public ResponseEntity<SalaryDTO> getSalaryByEmployeeAndMonth(
        @PathVariable Long employeeId,
        @RequestParam Integer month,
        @RequestParam Integer year
    ) {
        SalaryDTO salary = salaryService.getSalaryByEmployeeAndMonth(employeeId, month, year);
        return ResponseEntity.ok(salary);
    }
    
    // Get All Salary Records for Employee
    @GetMapping("/employee/{employeeId}")
    public ResponseEntity<List<SalaryDTO>> getSalaryByEmployee(@PathVariable Long employeeId) {
        List<SalaryDTO> salaryList = salaryService.getSalaryByEmployee(employeeId);
        return ResponseEntity.ok(salaryList);
    }
    
    // Get Annual Salary for Employee
    @GetMapping("/employee/{employeeId}/annual")
    public ResponseEntity<List<SalaryDTO>> getAnnualSalary(
        @PathVariable Long employeeId,
        @RequestParam Integer year
    ) {
        List<SalaryDTO> salaryList = salaryService.getAnnualSalary(employeeId, year);
        return ResponseEntity.ok(salaryList);
    }
    
    // Get All Pending Salaries
    @GetMapping("/pending")
    public ResponseEntity<List<SalaryDTO>> getPendingSalaries() {
        List<SalaryDTO> salaryList = salaryService.getPendingSalaries();
        return ResponseEntity.ok(salaryList);
    }
    
    // Get All Paid Salaries
    @GetMapping("/paid")
    public ResponseEntity<List<SalaryDTO>> getPaidSalaries() {
        List<SalaryDTO> salaryList = salaryService.getPaidSalaries();
        return ResponseEntity.ok(salaryList);
    }
    
    // Update Salary
    @PutMapping("/{id}")
    public ResponseEntity<SalaryDTO> updateSalary(
        @PathVariable Long id,
        @RequestBody SalaryDTO salaryDTO
    ) {
        SalaryDTO updatedSalary = salaryService.updateSalary(id, salaryDTO);
        return ResponseEntity.ok(updatedSalary);
    }
    
    // Process Payment
    @PatchMapping("/{id}/pay")
    public ResponseEntity<SalaryDTO> processPayment(@PathVariable Long id) {
        SalaryDTO updatedSalary = salaryService.processPayment(id);
        return ResponseEntity.ok(updatedSalary);
    }
    
    // Delete Salary
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteSalary(@PathVariable Long id) {
        salaryService.deleteSalary(id);
        return ResponseEntity.noContent().build();
    }
    
    // Get Total Paid Salaries
    @GetMapping("/stats/total-paid")
    public ResponseEntity<BigDecimal> getTotalPaidSalaries() {
        BigDecimal total = salaryService.getTotalPaidSalaries();
        return ResponseEntity.ok(total);
    }
}
