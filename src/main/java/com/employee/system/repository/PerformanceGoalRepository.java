package com.employee.system.repository;

import com.employee.system.entity.Employee;
import com.employee.system.entity.PerformanceGoal;
import org.springframework.stereotype.Repository;

import java.util.*;
import java.util.stream.Collectors;

@Repository
public class PerformanceGoalRepository {
    
    private static final Map<Long, PerformanceGoal> goals = new HashMap<>();
    private static Long nextId = 1L;
    
    public PerformanceGoalRepository() {
        initializeDummyData();
    }
    
    private void initializeDummyData() {
        if (goals.isEmpty()) {
            Employee emp1 = new Employee(1L, "EMP001", "John", "Doe", "john.doe@company.com", "9876543210",
                "IT", "Senior Developer", java.time.LocalDate.of(2020, 1, 15),
                "ACTIVE", "123 Main St", java.time.LocalDate.of(1990, 5, 20), "MALE",
                java.time.LocalDate.now(), java.time.LocalDate.now());
            
            goals.put(1L, new PerformanceGoal(
                1L, emp1, "Develop Microservices Architecture", "Design and implement microservices for order management",
                "Technical", java.time.LocalDate.of(2024, 1, 1), java.time.LocalDate.of(2024, 6, 30),
                "ACTIVE", "HIGH", 75, "Complete design doc, Implement 3 services, 90% test coverage",
                "On track with development", java.time.LocalDate.now(), java.time.LocalDate.now()
            ));
            
            goals.put(2L, new PerformanceGoal(
                2L, emp1, "Mentor 2 Junior Developers", "Guide and mentor junior team members on best practices",
                "Behavioral", java.time.LocalDate.of(2024, 1, 1), java.time.LocalDate.of(2024, 12, 31),
                "ACTIVE", "MEDIUM", 60, "Conduct weekly sessions, Code reviews, Career development plans",
                "Regular mentoring sessions ongoing", java.time.LocalDate.now(), java.time.LocalDate.now()
            ));
            
            nextId = 3L;
        }
    }
    
    public PerformanceGoal save(PerformanceGoal goal) {
        if (goal.getId() == null) {
            goal.setId(nextId++);
            goal.setCreatedAt(java.time.LocalDate.now());
        }
        goal.setUpdatedAt(java.time.LocalDate.now());
        goals.put(goal.getId(), goal);
        return goal;
    }
    
    public Optional<PerformanceGoal> findById(Long id) {
        return Optional.ofNullable(goals.get(id));
    }
    
    public List<PerformanceGoal> findByEmployee(Employee employee) {
        return goals.values().stream()
            .filter(g -> g.getEmployee().getId().equals(employee.getId()))
            .collect(Collectors.toList());
    }
    
    public List<PerformanceGoal> findByStatus(String status) {
        return goals.values().stream()
            .filter(g -> g.getStatus().equalsIgnoreCase(status))
            .collect(Collectors.toList());
    }
    
    public List<PerformanceGoal> findByEmployeeAndStatus(Employee employee, String status) {
        return goals.values().stream()
            .filter(g -> g.getEmployee().getId().equals(employee.getId()) &&
                        g.getStatus().equalsIgnoreCase(status))
            .collect(Collectors.toList());
    }
    
    public List<PerformanceGoal> findAll() {
        return new ArrayList<>(goals.values());
    }
    
    public void delete(PerformanceGoal goal) {
        goals.remove(goal.getId());
    }
}
