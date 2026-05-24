package com.employee.system.repository;

import com.employee.system.entity.Employee;
import com.employee.system.entity.ManagerFeedback;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.*;
import java.util.stream.Collectors;

@Repository
public class ManagerFeedbackRepository {
    
    private static final Map<Long, ManagerFeedback> feedbacks = new HashMap<>();
    private static Long nextId = 1L;
    
    public ManagerFeedbackRepository() {
        initializeDummyData();
    }
    
    private void initializeDummyData() {
        if (feedbacks.isEmpty()) {
            Employee emp1 = new Employee(1L, "EMP001", "John", "Doe", "john.doe@company.com", "9876543210",
                "IT", "Senior Developer", LocalDate.of(2020, 1, 15),
                "ACTIVE", "123 Main St", LocalDate.of(1990, 5, 20), "MALE",
                LocalDate.now(), LocalDate.now());
            
            Employee manager = new Employee(2L, "EMP002", "Jane", "Smith", "jane.smith@company.com", "9876543211",
                "HR", "HR Manager", LocalDate.of(2019, 3, 10),
                "ACTIVE", "456 Oak Ave", LocalDate.of(1988, 8, 15), "FEMALE",
                LocalDate.now(), LocalDate.now());
            
            feedbacks.put(1L, new ManagerFeedback(
                1L, emp1, manager, "Formal", "Performance",
                "Excellent work on the microservices project. Your code quality and attention to detail is commendable.",
                5, "Continue leading code review sessions", LocalDate.of(2024, 5, 20),
                "SHARED", LocalDate.now(), LocalDate.now()
            ));
            
            feedbacks.put(2L, new ManagerFeedback(
                2L, emp1, manager, "Informal", "Development",
                "Work on improving your communication in team meetings. Share your ideas more openly.",
                3, "Attend communication workshop next month", LocalDate.of(2024, 5, 15),
                "SHARED", LocalDate.now(), LocalDate.now()
            ));
            
            nextId = 3L;
        }
    }
    
    public ManagerFeedback save(ManagerFeedback feedback) {
        if (feedback.getId() == null) {
            feedback.setId(nextId++);
            feedback.setCreatedAt(LocalDate.now());
        }
        feedback.setUpdatedAt(LocalDate.now());
        feedbacks.put(feedback.getId(), feedback);
        return feedback;
    }
    
    public Optional<ManagerFeedback> findById(Long id) {
        return Optional.ofNullable(feedbacks.get(id));
    }
    
    public List<ManagerFeedback> findByEmployee(Employee employee) {
        return feedbacks.values().stream()
            .filter(f -> f.getEmployee().getId().equals(employee.getId()))
            .collect(Collectors.toList());
    }
    
    public List<ManagerFeedback> findByProvidedBy(Employee manager) {
        return feedbacks.values().stream()
            .filter(f -> f.getProvidedBy().getId().equals(manager.getId()))
            .collect(Collectors.toList());
    }
    
    public List<ManagerFeedback> findByStatus(String status) {
        return feedbacks.values().stream()
            .filter(f -> f.getStatus().equalsIgnoreCase(status))
            .collect(Collectors.toList());
    }
    
    public List<ManagerFeedback> findByFeedbackType(String type) {
        return feedbacks.values().stream()
            .filter(f -> f.getFeedbackType().equalsIgnoreCase(type))
            .collect(Collectors.toList());
    }
    
    public List<ManagerFeedback> findByEmployeeAndCategory(Employee employee, String category) {
        return feedbacks.values().stream()
            .filter(f -> f.getEmployee().getId().equals(employee.getId()) &&
                        f.getFeedbackCategory().equalsIgnoreCase(category))
            .collect(Collectors.toList());
    }
    
    public List<ManagerFeedback> findAll() {
        return new ArrayList<>(feedbacks.values());
    }
    
    public void delete(ManagerFeedback feedback) {
        feedbacks.remove(feedback.getId());
    }
}
