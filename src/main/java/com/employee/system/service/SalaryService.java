package com.employee.system.service;

import com.employee.system.dto.SalaryDTO;
import com.employee.system.entity.Employee;
import com.employee.system.entity.Salary;
import com.employee.system.repository.EmployeeRepository;
import com.employee.system.repository.SalaryRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class SalaryService {
    
    private final SalaryRepository salaryRepository;
    private final EmployeeRepository employeeRepository;
    
    // Create/Add Salary
    public SalaryDTO addSalary(SalaryDTO salaryDTO) {
        Employee employee = employeeRepository.findById(salaryDTO.getEmployeeId())
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + salaryDTO.getEmployeeId()));
        
        Salary salary = new Salary();
        salary.setEmployee(employee);
        salary.setSalaryMonth(salaryDTO.getSalaryMonth());
        salary.setSalaryYear(salaryDTO.getSalaryYear());
        salary.setBaseSalary(salaryDTO.getBaseSalary());
        salary.setDearnessAllowance(salaryDTO.getDearnessAllowance() != null ? salaryDTO.getDearnessAllowance() : BigDecimal.ZERO);
        salary.setHouseRentAllowance(salaryDTO.getHouseRentAllowance() != null ? salaryDTO.getHouseRentAllowance() : BigDecimal.ZERO);
        salary.setOtherAllowances(salaryDTO.getOtherAllowances() != null ? salaryDTO.getOtherAllowances() : BigDecimal.ZERO);
        
        // Calculate total allowances
        BigDecimal totalAllowances = salary.getDearnessAllowance()
            .add(salary.getHouseRentAllowance())
            .add(salary.getOtherAllowances());
        salary.setTotalAllowances(totalAllowances);
        
        salary.setIncomeTax(salaryDTO.getIncomeTax() != null ? salaryDTO.getIncomeTax() : BigDecimal.ZERO);
        salary.setProvidentFund(salaryDTO.getProvidentFund() != null ? salaryDTO.getProvidentFund() : BigDecimal.ZERO);
        salary.setOtherDeductions(salaryDTO.getOtherDeductions() != null ? salaryDTO.getOtherDeductions() : BigDecimal.ZERO);
        
        // Calculate total deductions
        BigDecimal totalDeductions = salary.getIncomeTax()
            .add(salary.getProvidentFund())
            .add(salary.getOtherDeductions());
        salary.setTotalDeductions(totalDeductions);
        
        // Calculate net salary
        BigDecimal netSalary = salary.getBaseSalary()
            .add(totalAllowances)
            .subtract(totalDeductions);
        salary.setNetSalary(netSalary);
        
        salary.setPaymentStatus(salaryDTO.getPaymentStatus() != null ? salaryDTO.getPaymentStatus() : "PENDING");
        salary.setPaymentDate(salaryDTO.getPaymentDate());
        salary.setRemarks(salaryDTO.getRemarks());
        
        Salary savedSalary = salaryRepository.save(salary);
        return convertToDTO(savedSalary);
    }
    
    // Get Salary by ID
    public SalaryDTO getSalaryById(Long id) {
        Salary salary = salaryRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Salary not found with id: " + id));
        return convertToDTO(salary);
    }
    
    // Get Salary for Employee and Month/Year
    public SalaryDTO getSalaryByEmployeeAndMonth(Long employeeId, Integer month, Integer year) {
        Employee employee = employeeRepository.findById(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + employeeId));
        
        Salary salary = salaryRepository.findByEmployeeAndSalaryMonthAndSalaryYear(employee, month, year)
            .orElseThrow(() -> new RuntimeException("Salary not found for employee for month: " + month + " and year: " + year));
        return convertToDTO(salary);
    }
    
    // Get All Salary Records for Employee
    public List<SalaryDTO> getSalaryByEmployee(Long employeeId) {
        Employee employee = employeeRepository.findById(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + employeeId));
        
        return salaryRepository.findByEmployee(employee)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    // Get Annual Salary for Employee
    public List<SalaryDTO> getAnnualSalary(Long employeeId, Integer year) {
        Employee employee = employeeRepository.findById(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + employeeId));
        
        return salaryRepository.findByEmployeeAndSalaryYear(employee, year)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    // Get All Pending Salaries
    public List<SalaryDTO> getPendingSalaries() {
        return salaryRepository.findByPaymentStatus("PENDING")
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    // Get All Paid Salaries
    public List<SalaryDTO> getPaidSalaries() {
        return salaryRepository.findByPaymentStatus("PAID")
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    // Update Salary
    public SalaryDTO updateSalary(Long id, SalaryDTO salaryDTO) {
        Salary salary = salaryRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Salary not found with id: " + id));
        
        salary.setBaseSalary(salaryDTO.getBaseSalary());
        salary.setDearnessAllowance(salaryDTO.getDearnessAllowance() != null ? salaryDTO.getDearnessAllowance() : BigDecimal.ZERO);
        salary.setHouseRentAllowance(salaryDTO.getHouseRentAllowance() != null ? salaryDTO.getHouseRentAllowance() : BigDecimal.ZERO);
        salary.setOtherAllowances(salaryDTO.getOtherAllowances() != null ? salaryDTO.getOtherAllowances() : BigDecimal.ZERO);
        
        BigDecimal totalAllowances = salary.getDearnessAllowance()
            .add(salary.getHouseRentAllowance())
            .add(salary.getOtherAllowances());
        salary.setTotalAllowances(totalAllowances);
        
        salary.setIncomeTax(salaryDTO.getIncomeTax() != null ? salaryDTO.getIncomeTax() : BigDecimal.ZERO);
        salary.setProvidentFund(salaryDTO.getProvidentFund() != null ? salaryDTO.getProvidentFund() : BigDecimal.ZERO);
        salary.setOtherDeductions(salaryDTO.getOtherDeductions() != null ? salaryDTO.getOtherDeductions() : BigDecimal.ZERO);
        
        BigDecimal totalDeductions = salary.getIncomeTax()
            .add(salary.getProvidentFund())
            .add(salary.getOtherDeductions());
        salary.setTotalDeductions(totalDeductions);
        
        BigDecimal netSalary = salary.getBaseSalary()
            .add(totalAllowances)
            .subtract(totalDeductions);
        salary.setNetSalary(netSalary);
        
        salary.setPaymentStatus(salaryDTO.getPaymentStatus());
        salary.setPaymentDate(salaryDTO.getPaymentDate());
        salary.setRemarks(salaryDTO.getRemarks());
        
        Salary updatedSalary = salaryRepository.save(salary);
        return convertToDTO(updatedSalary);
    }
    
    // Process Payment
    public SalaryDTO processPayment(Long id) {
        Salary salary = salaryRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Salary not found with id: " + id));
        
        salary.setPaymentStatus("PAID");
        salary.setPaymentDate(java.time.LocalDate.now());
        Salary updatedSalary = salaryRepository.save(salary);
        return convertToDTO(updatedSalary);
    }
    
    // Delete Salary
    public void deleteSalary(Long id) {
        Salary salary = salaryRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Salary not found with id: " + id));
        salaryRepository.delete(salary);
    }
    
    // Get Total Paid Salaries
    public BigDecimal getTotalPaidSalaries() {
        BigDecimal total = salaryRepository.getTotalPaidSalaries();
        return total != null ? total : BigDecimal.ZERO;
    }
    
    // Helper method to convert Entity to DTO
    private SalaryDTO convertToDTO(Salary salary) {
        SalaryDTO dto = new SalaryDTO();
        dto.setId(salary.getId());
        dto.setEmployeeId(salary.getEmployee().getId());
        dto.setEmployeeName(salary.getEmployee().getFirstName() + " " + salary.getEmployee().getLastName());
        dto.setSalaryMonth(salary.getSalaryMonth());
        dto.setSalaryYear(salary.getSalaryYear());
        dto.setBaseSalary(salary.getBaseSalary());
        dto.setDearnessAllowance(salary.getDearnessAllowance());
        dto.setHouseRentAllowance(salary.getHouseRentAllowance());
        dto.setOtherAllowances(salary.getOtherAllowances());
        dto.setTotalAllowances(salary.getTotalAllowances());
        dto.setIncomeTax(salary.getIncomeTax());
        dto.setProvidentFund(salary.getProvidentFund());
        dto.setOtherDeductions(salary.getOtherDeductions());
        dto.setTotalDeductions(salary.getTotalDeductions());
        dto.setNetSalary(salary.getNetSalary());
        dto.setPaymentStatus(salary.getPaymentStatus());
        dto.setPaymentDate(salary.getPaymentDate());
        dto.setRemarks(salary.getRemarks());
        dto.setCreatedAt(salary.getCreatedAt());
        dto.setUpdatedAt(salary.getUpdatedAt());
        return dto;
    }
}
