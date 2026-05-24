package com.employee.system.repository;

import com.employee.system.entity.Employee;
import com.employee.system.entity.SelfAssessment;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.*;
import java.util.stream.Collectors;

@Repository
public class SelfAssessmentRepository {
    
    private static final Map<Long, SelfAssessment> assessments = new HashMap<>();
    private static Long nextId = 1L;
    
    public SelfAssessmentRepository() {
        initializeDummyData();
    }
    
    private void initializeDummyData() {
        if (assessments.isEmpty()) {
            Employee emp1 = new Employee(1L, "EMP001", "John", "Doe", "john.doe@company.com", "9876543210",
                "IT", "Senior Developer", LocalDate.of(2020, 1, 15),
                "ACTIVE", "123 Main St", LocalDate.of(1990, 5, 20), "MALE",
                LocalDate.now(), LocalDate.now());
            
            assessments.put(1L, new SelfAssessment(
                1L, emp1, "Q1 2024", LocalDate.of(2024, 4, 10),
                4, 5, 4, 4, 4,
                "Completed microservices design, Mentored 2 junior developers",
                "Strong technical skills, Good problem solving, Reliable team member",
                "Need to improve public speaking, More involvement in strategic planning",
                "Become a tech lead in 2 years, Architect complex systems",
                "Advanced training in system design, Mentorship opportunity",
                "SUBMITTED", LocalDate.now(), LocalDate.now()
            ));
            
            nextId = 2L;
        }
    }
    
    public SelfAssessment save(SelfAssessment assessment) {
        if (assessment.getId() == null) {
            assessment.setId(nextId++);
            assessment.setCreatedAt(LocalDate.now());
        }
        assessment.setUpdatedAt(LocalDate.now());
        assessments.put(assessment.getId(), assessment);
        return assessment;
    }
    
    public Optional<SelfAssessment> findById(Long id) {
        return Optional.ofNullable(assessments.get(id));
    }
    
    public List<SelfAssessment> findByEmployee(Employee employee) {
        return assessments.values().stream()
            .filter(a -> a.getEmployee().getId().equals(employee.getId()))
            .collect(Collectors.toList());
    }
    
    public List<SelfAssessment> findByStatus(String status) {
        return assessments.values().stream()
            .filter(a -> a.getStatus().equalsIgnoreCase(status))
            .collect(Collectors.toList());
    }
    
    public List<SelfAssessment> findByAssessmentPeriod(String period) {
        return assessments.values().stream()
            .filter(a -> a.getAssessmentPeriod().equalsIgnoreCase(period))
            .collect(Collectors.toList());
    }
    
    public Optional<SelfAssessment> findByEmployeeAndPeriod(Employee employee, String period) {
        return assessments.values().stream()
            .filter(a -> a.getEmployee().getId().equals(employee.getId()) &&
                        a.getAssessmentPeriod().equalsIgnoreCase(period))
            .findFirst();
    }
    
    public List<SelfAssessment> findAll() {
        return new ArrayList<>(assessments.values());
    }
    
    public void delete(SelfAssessment assessment) {
        assessments.remove(assessment.getId());
    }
}
