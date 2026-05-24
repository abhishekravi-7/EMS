package com.employee.system.repository;

import com.employee.system.entity.Employee;
import com.employee.system.entity.PerformanceReview;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.*;
import java.util.stream.Collectors;

@Repository
public class PerformanceReviewRepository {
    
    private static final Map<Long, PerformanceReview> reviews = new HashMap<>();
    private static Long nextId = 1L;
    
    public PerformanceReviewRepository() {
        initializeDummyData();
    }
    
    private void initializeDummyData() {
        if (reviews.isEmpty()) {
            Employee emp1 = new Employee(1L, "EMP001", "John", "Doe", "john.doe@company.com", "9876543210",
                "IT", "Senior Developer", LocalDate.of(2020, 1, 15),
                "ACTIVE", "123 Main St", LocalDate.of(1990, 5, 20), "MALE",
                LocalDate.now(), LocalDate.now());
            
            Employee emp2 = new Employee(2L, "EMP002", "Jane", "Smith", "jane.smith@company.com", "9876543211",
                "HR", "HR Manager", LocalDate.of(2019, 3, 10),
                "ACTIVE", "456 Oak Ave", LocalDate.of(1988, 8, 15), "FEMALE",
                LocalDate.now(), LocalDate.now());
            
            reviews.put(1L, new PerformanceReview(
                1L, emp1, emp2, "Q1 2024", LocalDate.of(2024, 4, 15),
                4, 5, 4, 4, 4,
                "Excellent technical skills, strong code quality, great mentoring",
                "Need to improve documentation, communication in larger meetings",
                "John has shown exceptional growth this quarter. Continue the good work.",
                "COMPLETED", LocalDate.now(), LocalDate.now()
            ));
            
            nextId = 2L;
        }
    }
    
    public PerformanceReview save(PerformanceReview review) {
        if (review.getId() == null) {
            review.setId(nextId++);
            review.setCreatedAt(LocalDate.now());
        }
        review.setUpdatedAt(LocalDate.now());
        reviews.put(review.getId(), review);
        return review;
    }
    
    public Optional<PerformanceReview> findById(Long id) {
        return Optional.ofNullable(reviews.get(id));
    }
    
    public List<PerformanceReview> findByEmployee(Employee employee) {
        return reviews.values().stream()
            .filter(r -> r.getEmployee().getId().equals(employee.getId()))
            .collect(Collectors.toList());
    }
    
    public List<PerformanceReview> findByReviewedBy(Employee manager) {
        return reviews.values().stream()
            .filter(r -> r.getReviewedBy().getId().equals(manager.getId()))
            .collect(Collectors.toList());
    }
    
    public List<PerformanceReview> findByStatus(String status) {
        return reviews.values().stream()
            .filter(r -> r.getStatus().equalsIgnoreCase(status))
            .collect(Collectors.toList());
    }
    
    public List<PerformanceReview> findByReviewPeriod(String period) {
        return reviews.values().stream()
            .filter(r -> r.getReviewPeriod().equalsIgnoreCase(period))
            .collect(Collectors.toList());
    }
    
    public Optional<PerformanceReview> findByEmployeeAndPeriod(Employee employee, String period) {
        return reviews.values().stream()
            .filter(r -> r.getEmployee().getId().equals(employee.getId()) &&
                        r.getReviewPeriod().equalsIgnoreCase(period))
            .findFirst();
    }
    
    public List<PerformanceReview> findAll() {
        return new ArrayList<>(reviews.values());
    }
    
    public void delete(PerformanceReview review) {
        reviews.remove(review.getId());
    }
}
