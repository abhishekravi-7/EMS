package com.employee.system.service;

import com.employee.system.dto.ManagerFeedbackDTO;
import com.employee.system.entity.Employee;
import com.employee.system.entity.ManagerFeedback;
import com.employee.system.repository.EmployeeRepository;
import com.employee.system.repository.ManagerFeedbackRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class ManagerFeedbackService {
    
    private final ManagerFeedbackRepository feedbackRepository;
    private final EmployeeRepository employeeRepository;
    
    public ManagerFeedbackDTO provideFeedback(ManagerFeedbackDTO feedbackDTO) {
        Employee employee = employeeRepository.findById(feedbackDTO.getEmployeeId())
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + feedbackDTO.getEmployeeId()));
        
        Employee manager = employeeRepository.findById(feedbackDTO.getProvidedById())
            .orElseThrow(() -> new RuntimeException("Manager not found with id: " + feedbackDTO.getProvidedById()));
        
        ManagerFeedback feedback = new ManagerFeedback();
        feedback.setEmployee(employee);
        feedback.setProvidedBy(manager);
        feedback.setFeedbackType(feedbackDTO.getFeedbackType());
        feedback.setFeedbackCategory(feedbackDTO.getFeedbackCategory());
        feedback.setFeedbackText(feedbackDTO.getFeedbackText());
        feedback.setRating(feedbackDTO.getRating());
        feedback.setActionItems(feedbackDTO.getActionItems());
        feedback.setFeedbackDate(feedbackDTO.getFeedbackDate() != null ? feedbackDTO.getFeedbackDate() : LocalDate.now());
        feedback.setStatus(feedbackDTO.getStatus() != null ? feedbackDTO.getStatus() : "DRAFT");
        
        ManagerFeedback savedFeedback = feedbackRepository.save(feedback);
        return convertToDTO(savedFeedback);
    }
    
    public ManagerFeedbackDTO getFeedbackById(Long id) {
        ManagerFeedback feedback = feedbackRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Manager feedback not found with id: " + id));
        return convertToDTO(feedback);
    }
    
    public List<ManagerFeedbackDTO> getFeedbackByEmployee(Long employeeId) {
        Employee employee = employeeRepository.findById(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + employeeId));
        
        return feedbackRepository.findByEmployee(employee)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    public List<ManagerFeedbackDTO> getFeedbackByManager(Long managerId) {
        Employee manager = employeeRepository.findById(managerId)
            .orElseThrow(() -> new RuntimeException("Manager not found with id: " + managerId));
        
        return feedbackRepository.findByProvidedBy(manager)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    public List<ManagerFeedbackDTO> getFeedbackByType(String type) {
        return feedbackRepository.findByFeedbackType(type)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    public List<ManagerFeedbackDTO> getFeedbackByCategory(Long employeeId, String category) {
        Employee employee = employeeRepository.findById(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + employeeId));
        
        return feedbackRepository.findByEmployeeAndCategory(employee, category)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    public ManagerFeedbackDTO updateFeedback(Long id, ManagerFeedbackDTO feedbackDTO) {
        ManagerFeedback feedback = feedbackRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Manager feedback not found with id: " + id));
        
        feedback.setFeedbackType(feedbackDTO.getFeedbackType());
        feedback.setFeedbackCategory(feedbackDTO.getFeedbackCategory());
        feedback.setFeedbackText(feedbackDTO.getFeedbackText());
        feedback.setRating(feedbackDTO.getRating());
        feedback.setActionItems(feedbackDTO.getActionItems());
        feedback.setStatus(feedbackDTO.getStatus());
        
        ManagerFeedback updatedFeedback = feedbackRepository.save(feedback);
        return convertToDTO(updatedFeedback);
    }
    
    public void deleteFeedback(Long id) {
        ManagerFeedback feedback = feedbackRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Manager feedback not found with id: " + id));
        feedbackRepository.delete(feedback);
    }
    
    private ManagerFeedbackDTO convertToDTO(ManagerFeedback feedback) {
        ManagerFeedbackDTO dto = new ManagerFeedbackDTO();
        dto.setId(feedback.getId());
        dto.setEmployeeId(feedback.getEmployee().getId());
        dto.setEmployeeName(feedback.getEmployee().getFirstName() + " " + feedback.getEmployee().getLastName());
        dto.setProvidedById(feedback.getProvidedBy().getId());
        dto.setProvidedByName(feedback.getProvidedBy().getFirstName() + " " + feedback.getProvidedBy().getLastName());
        dto.setFeedbackType(feedback.getFeedbackType());
        dto.setFeedbackCategory(feedback.getFeedbackCategory());
        dto.setFeedbackText(feedback.getFeedbackText());
        dto.setRating(feedback.getRating());
        dto.setActionItems(feedback.getActionItems());
        dto.setFeedbackDate(feedback.getFeedbackDate());
        dto.setStatus(feedback.getStatus());
        dto.setCreatedAt(feedback.getCreatedAt());
        dto.setUpdatedAt(feedback.getUpdatedAt());
        return dto;
    }
}
