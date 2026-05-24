package com.employee.system.service;

import com.employee.system.dto.SelfAssessmentDTO;
import com.employee.system.entity.Employee;
import com.employee.system.entity.SelfAssessment;
import com.employee.system.repository.EmployeeRepository;
import com.employee.system.repository.SelfAssessmentRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class SelfAssessmentService {
    
    private final SelfAssessmentRepository assessmentRepository;
    private final EmployeeRepository employeeRepository;
    
    public SelfAssessmentDTO createAssessment(SelfAssessmentDTO assessmentDTO) {
        Employee employee = employeeRepository.findById(assessmentDTO.getEmployeeId())
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + assessmentDTO.getEmployeeId()));
        
        SelfAssessment assessment = new SelfAssessment();
        assessment.setEmployee(employee);
        assessment.setAssessmentPeriod(assessmentDTO.getAssessmentPeriod());
        assessment.setAssessmentDate(assessmentDTO.getAssessmentDate() != null ? assessmentDTO.getAssessmentDate() : LocalDate.now());
        assessment.setSelfRating(assessmentDTO.getSelfRating());
        assessment.setTechnicalSkillsRating(assessmentDTO.getTechnicalSkillsRating());
        assessment.setBehavioralRating(assessmentDTO.getBehavioralRating());
        assessment.setLeadershipRating(assessmentDTO.getLeadershipRating());
        assessment.setTeamworkRating(assessmentDTO.getTeamworkRating());
        assessment.setAccomplishments(assessmentDTO.getAccomplishments());
        assessment.setStrengthsIdentified(assessmentDTO.getStrengthsIdentified());
        assessment.setImprovementAreas(assessmentDTO.getImprovementAreas());
        assessment.setCareerGoals(assessmentDTO.getCareerGoals());
        assessment.setSupportRequired(assessmentDTO.getSupportRequired());
        assessment.setStatus(assessmentDTO.getStatus() != null ? assessmentDTO.getStatus() : "DRAFT");
        
        SelfAssessment savedAssessment = assessmentRepository.save(assessment);
        return convertToDTO(savedAssessment);
    }
    
    public SelfAssessmentDTO getAssessmentById(Long id) {
        SelfAssessment assessment = assessmentRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Self assessment not found with id: " + id));
        return convertToDTO(assessment);
    }
    
    public List<SelfAssessmentDTO> getAssessmentsByEmployee(Long employeeId) {
        Employee employee = employeeRepository.findById(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + employeeId));
        
        return assessmentRepository.findByEmployee(employee)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    public List<SelfAssessmentDTO> getAssessmentsByPeriod(String period) {
        return assessmentRepository.findByAssessmentPeriod(period)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    public List<SelfAssessmentDTO> getAssessmentsByStatus(String status) {
        return assessmentRepository.findByStatus(status)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    public SelfAssessmentDTO updateAssessment(Long id, SelfAssessmentDTO assessmentDTO) {
        SelfAssessment assessment = assessmentRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Self assessment not found with id: " + id));
        
        assessment.setSelfRating(assessmentDTO.getSelfRating());
        assessment.setTechnicalSkillsRating(assessmentDTO.getTechnicalSkillsRating());
        assessment.setBehavioralRating(assessmentDTO.getBehavioralRating());
        assessment.setLeadershipRating(assessmentDTO.getLeadershipRating());
        assessment.setTeamworkRating(assessmentDTO.getTeamworkRating());
        assessment.setAccomplishments(assessmentDTO.getAccomplishments());
        assessment.setStrengthsIdentified(assessmentDTO.getStrengthsIdentified());
        assessment.setImprovementAreas(assessmentDTO.getImprovementAreas());
        assessment.setCareerGoals(assessmentDTO.getCareerGoals());
        assessment.setSupportRequired(assessmentDTO.getSupportRequired());
        assessment.setStatus(assessmentDTO.getStatus());
        
        SelfAssessment updatedAssessment = assessmentRepository.save(assessment);
        return convertToDTO(updatedAssessment);
    }
    
    public void deleteAssessment(Long id) {
        SelfAssessment assessment = assessmentRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Self assessment not found with id: " + id));
        assessmentRepository.delete(assessment);
    }
    
    private SelfAssessmentDTO convertToDTO(SelfAssessment assessment) {
        SelfAssessmentDTO dto = new SelfAssessmentDTO();
        dto.setId(assessment.getId());
        dto.setEmployeeId(assessment.getEmployee().getId());
        dto.setEmployeeName(assessment.getEmployee().getFirstName() + " " + assessment.getEmployee().getLastName());
        dto.setAssessmentPeriod(assessment.getAssessmentPeriod());
        dto.setAssessmentDate(assessment.getAssessmentDate());
        dto.setSelfRating(assessment.getSelfRating());
        dto.setTechnicalSkillsRating(assessment.getTechnicalSkillsRating());
        dto.setBehavioralRating(assessment.getBehavioralRating());
        dto.setLeadershipRating(assessment.getLeadershipRating());
        dto.setTeamworkRating(assessment.getTeamworkRating());
        dto.setAccomplishments(assessment.getAccomplishments());
        dto.setStrengthsIdentified(assessment.getStrengthsIdentified());
        dto.setImprovementAreas(assessment.getImprovementAreas());
        dto.setCareerGoals(assessment.getCareerGoals());
        dto.setSupportRequired(assessment.getSupportRequired());
        dto.setStatus(assessment.getStatus());
        dto.setCreatedAt(assessment.getCreatedAt());
        dto.setUpdatedAt(assessment.getUpdatedAt());
        return dto;
    }
}
