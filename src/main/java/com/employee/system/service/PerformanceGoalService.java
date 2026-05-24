package com.employee.system.service;

import com.employee.system.dto.PerformanceGoalDTO;
import com.employee.system.entity.Employee;
import com.employee.system.entity.PerformanceGoal;
import com.employee.system.repository.EmployeeRepository;
import com.employee.system.repository.PerformanceGoalRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class PerformanceGoalService {
    
    private final PerformanceGoalRepository goalRepository;
    private final EmployeeRepository employeeRepository;
    
    public PerformanceGoalDTO createGoal(PerformanceGoalDTO goalDTO) {
        Employee employee = employeeRepository.findById(goalDTO.getEmployeeId())
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + goalDTO.getEmployeeId()));
        
        PerformanceGoal goal = new PerformanceGoal();
        goal.setEmployee(employee);
        goal.setGoalTitle(goalDTO.getGoalTitle());
        goal.setGoalDescription(goalDTO.getGoalDescription());
        goal.setCategory(goalDTO.getCategory());
        goal.setStartDate(goalDTO.getStartDate());
        goal.setTargetDate(goalDTO.getTargetDate());
        goal.setStatus(goalDTO.getStatus() != null ? goalDTO.getStatus() : "DRAFT");
        goal.setPriority(goalDTO.getPriority());
        goal.setProgressPercentage(goalDTO.getProgressPercentage() != null ? goalDTO.getProgressPercentage() : 0);
        goal.setKeyResults(goalDTO.getKeyResults());
        goal.setRemarks(goalDTO.getRemarks());
        
        PerformanceGoal savedGoal = goalRepository.save(goal);
        return convertToDTO(savedGoal);
    }
    
    public PerformanceGoalDTO getGoalById(Long id) {
        PerformanceGoal goal = goalRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Performance goal not found with id: " + id));
        return convertToDTO(goal);
    }
    
    public List<PerformanceGoalDTO> getGoalsByEmployee(Long employeeId) {
        Employee employee = employeeRepository.findById(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + employeeId));
        
        return goalRepository.findByEmployee(employee)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    public List<PerformanceGoalDTO> getActiveGoals() {
        return goalRepository.findByStatus("ACTIVE")
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    public List<PerformanceGoalDTO> getGoalsByStatus(String status) {
        return goalRepository.findByStatus(status)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    public PerformanceGoalDTO updateGoal(Long id, PerformanceGoalDTO goalDTO) {
        PerformanceGoal goal = goalRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Performance goal not found with id: " + id));
        
        goal.setGoalTitle(goalDTO.getGoalTitle());
        goal.setGoalDescription(goalDTO.getGoalDescription());
        goal.setCategory(goalDTO.getCategory());
        goal.setTargetDate(goalDTO.getTargetDate());
        goal.setStatus(goalDTO.getStatus());
        goal.setPriority(goalDTO.getPriority());
        goal.setProgressPercentage(goalDTO.getProgressPercentage());
        goal.setKeyResults(goalDTO.getKeyResults());
        goal.setRemarks(goalDTO.getRemarks());
        
        PerformanceGoal updatedGoal = goalRepository.save(goal);
        return convertToDTO(updatedGoal);
    }
    
    public PerformanceGoalDTO updateGoalProgress(Long id, Integer progressPercentage) {
        PerformanceGoal goal = goalRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Performance goal not found with id: " + id));
        
        goal.setProgressPercentage(progressPercentage);
        PerformanceGoal updatedGoal = goalRepository.save(goal);
        return convertToDTO(updatedGoal);
    }
    
    public void deleteGoal(Long id) {
        PerformanceGoal goal = goalRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Performance goal not found with id: " + id));
        goalRepository.delete(goal);
    }
    
    private PerformanceGoalDTO convertToDTO(PerformanceGoal goal) {
        PerformanceGoalDTO dto = new PerformanceGoalDTO();
        dto.setId(goal.getId());
        dto.setEmployeeId(goal.getEmployee().getId());
        dto.setEmployeeName(goal.getEmployee().getFirstName() + " " + goal.getEmployee().getLastName());
        dto.setGoalTitle(goal.getGoalTitle());
        dto.setGoalDescription(goal.getGoalDescription());
        dto.setCategory(goal.getCategory());
        dto.setStartDate(goal.getStartDate());
        dto.setTargetDate(goal.getTargetDate());
        dto.setStatus(goal.getStatus());
        dto.setPriority(goal.getPriority());
        dto.setProgressPercentage(goal.getProgressPercentage());
        dto.setKeyResults(goal.getKeyResults());
        dto.setRemarks(goal.getRemarks());
        dto.setCreatedAt(goal.getCreatedAt());
        dto.setUpdatedAt(goal.getUpdatedAt());
        return dto;
    }
}
