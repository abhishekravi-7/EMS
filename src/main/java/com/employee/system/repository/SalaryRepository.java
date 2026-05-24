package com.employee.system.repository;

import com.employee.system.entity.Employee;
import com.employee.system.entity.Salary;
import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import java.util.stream.Collectors;

@Repository
public class SalaryRepository {
    
    private static final Map<Long, Salary> salaries = new HashMap<>();
    private static Long nextId = 1L;
    
    public SalaryRepository() {
        initializeDummyData();
    }
    
    private void initializeDummyData() {
        if (salaries.isEmpty()) {
            Employee emp1 = new Employee(1L, "EMP001", "John", "Doe", "john.doe@company.com", "9876543210",
                "IT", "Senior Developer", LocalDate.of(2020, 1, 15),
                "ACTIVE", "123 Main St", LocalDate.of(1990, 5, 20), "MALE",
                LocalDate.now(), LocalDate.now());
            
            Salary salary1 = new Salary(
                1L, emp1, 5, 2024,
                new BigDecimal("50000"),
                new BigDecimal("5000"),
                new BigDecimal("10000"),
                new BigDecimal("2000"),
                new BigDecimal("17000"),
                new BigDecimal("5000"),
                new BigDecimal("3000"),
                new BigDecimal("500"),
                new BigDecimal("8500"),
                new BigDecimal("58500"),
                "PAID",
                LocalDate.of(2024, 5, 31),
                "May salary",
                LocalDate.now(),
                LocalDate.now()
            );
            salaries.put(1L, salary1);
            
            Salary salary2 = new Salary(
                2L, emp1, 4, 2024,
                new BigDecimal("50000"),
                new BigDecimal("5000"),
                new BigDecimal("10000"),
                new BigDecimal("2000"),
                new BigDecimal("17000"),
                new BigDecimal("5000"),
                new BigDecimal("3000"),
                new BigDecimal("500"),
                new BigDecimal("8500"),
                new BigDecimal("58500"),
                "PENDING",
                null,
                "April salary",
                LocalDate.now(),
                LocalDate.now()
            );
            salaries.put(2L, salary2);
            
            nextId = 3L;
        }
    }
    
    public Salary save(Salary salary) {
        if (salary.getId() == null) {
            salary.setId(nextId++);
            salary.setCreatedAt(LocalDate.now());
        }
        salary.setUpdatedAt(LocalDate.now());
        salaries.put(salary.getId(), salary);
        return salary;
    }
    
    public Optional<Salary> findById(Long id) {
        return Optional.ofNullable(salaries.get(id));
    }
    
    public List<Salary> findByEmployee(Employee employee) {
        return salaries.values().stream()
            .filter(s -> s.getEmployee().getId().equals(employee.getId()))
            .collect(Collectors.toList());
    }
    
    public Optional<Salary> findByEmployeeAndSalaryMonthAndSalaryYear(Employee employee, Integer month, Integer year) {
        return salaries.values().stream()
            .filter(s -> s.getEmployee().getId().equals(employee.getId()) &&
                        s.getSalaryMonth().equals(month) &&
                        s.getSalaryYear().equals(year))
            .findFirst();
    }
    
    public List<Salary> findByEmployeeAndSalaryYear(Employee employee, Integer year) {
        return salaries.values().stream()
            .filter(s -> s.getEmployee().getId().equals(employee.getId()) &&
                        s.getSalaryYear().equals(year))
            .collect(Collectors.toList());
    }
    
    public List<Salary> findByPaymentStatus(String paymentStatus) {
        return salaries.values().stream()
            .filter(s -> s.getPaymentStatus().equalsIgnoreCase(paymentStatus))
            .collect(Collectors.toList());
    }
    
    public List<Salary> findAll() {
        return new ArrayList<>(salaries.values());
    }
    
    public Optional<Salary> findMonthlySalary(Employee employee, Integer month, Integer year) {
        return salaries.values().stream()
            .filter(s -> s.getEmployee().getId().equals(employee.getId()) &&
                        s.getSalaryMonth().equals(month) &&
                        s.getSalaryYear().equals(year))
            .findFirst();
    }
    
    public List<Salary> findYearlySalary(Employee employee, Integer year) {
        return salaries.values().stream()
            .filter(s -> s.getEmployee().getId().equals(employee.getId()) &&
                        s.getSalaryYear().equals(year))
            .sorted(Comparator.comparingInt(Salary::getSalaryMonth))
            .collect(Collectors.toList());
    }
    
    public long countPaidSalaries() {
        return salaries.values().stream()
            .filter(s -> "PAID".equals(s.getPaymentStatus()))
            .count();
    }
    
    public BigDecimal getTotalPaidSalaries() {
        return salaries.values().stream()
            .filter(s -> "PAID".equals(s.getPaymentStatus()))
            .map(Salary::getNetSalary)
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    }
    
    public void delete(Salary salary) {
        salaries.remove(salary.getId());
    }
}
