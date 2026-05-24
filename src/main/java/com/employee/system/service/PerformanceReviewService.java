package com.employee.system.service;

import com.employee.system.dto.PerformanceReviewDTO;
import com.employee.system.entity.Employee;
import com.employee.system.entity.PerformanceReview;
import com.employee.system.repository.EmployeeRepository;
import com.employee.system.repository.PerformanceReviewRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class PerformanceReviewService {
    
    private final PerformanceReviewRepository reviewRepository;
    private final EmployeeRepository employeeRepository;
    
    public PerformanceReviewDTO createReview(PerformanceReviewDTO reviewDTO) {
        Employee employee = employeeRepository.findById(reviewDTO.getEmployeeId())
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + reviewDTO.getEmployeeId()));
        
        Employee manager = employeeRepository.findById(reviewDTO.getReviewedById())
            .orElseThrow(() -> new RuntimeException("Manager not found with id: " + reviewDTO.getReviewedById()));
        
        PerformanceReview review = new PerformanceReview();
        review.setEmployee(employee);
        review.setReviewedBy(manager);
        review.setReviewPeriod(reviewDTO.getReviewPeriod());
        review.setReviewDate(reviewDTO.getReviewDate() != null ? reviewDTO.getReviewDate() : LocalDate.now());
        review.setOverallRating(reviewDTO.getOverallRating());
        review.setTechnicalSkillsRating(reviewDTO.getTechnicalSkillsRating());
        review.setBehavioralRating(reviewDTO.getBehavioralRating());
        review.setLeadershipRating(reviewDTO.getLeadershipRating());
        review.setTeamworkRating(reviewDTO.getTeamworkRating());
        review.setStrengths(reviewDTO.getStrengths());
        review.setAreasForImprovement(reviewDTO.getAreasForImprovement());
        review.setComments(reviewDTO.getComments());
        review.setStatus(reviewDTO.getStatus() != null ? reviewDTO.getStatus() : "DRAFT");
        
        PerformanceReview savedReview = reviewRepository.save(review);
        return convertToDTO(savedReview);
    }
    
    public PerformanceReviewDTO getReviewById(Long id) {
        PerformanceReview review = reviewRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Performance review not found with id: " + id));
        return convertToDTO(review);
    }
    
    public List<PerformanceReviewDTO> getReviewsByEmployee(Long employeeId) {
        Employee employee = employeeRepository.findById(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + employeeId));
        
        return reviewRepository.findByEmployee(employee)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    public List<PerformanceReviewDTO> getReviewsByManager(Long managerId) {
        Employee manager = employeeRepository.findById(managerId)
            .orElseThrow(() -> new RuntimeException("Manager not found with id: " + managerId));
        
        return reviewRepository.findByReviewedBy(manager)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    public List<PerformanceReviewDTO> getReviewsByPeriod(String period) {
        return reviewRepository.findByReviewPeriod(period)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    public PerformanceReviewDTO updateReview(Long id, PerformanceReviewDTO reviewDTO) {
        PerformanceReview review = reviewRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Performance review not found with id: " + id));
        
        review.setOverallRating(reviewDTO.getOverallRating());
        review.setTechnicalSkillsRating(reviewDTO.getTechnicalSkillsRating());
        review.setBehavioralRating(reviewDTO.getBehavioralRating());
        review.setLeadershipRating(reviewDTO.getLeadershipRating());
        review.setTeamworkRating(reviewDTO.getTeamworkRating());
        review.setStrengths(reviewDTO.getStrengths());
        review.setAreasForImprovement(reviewDTO.getAreasForImprovement());
        review.setComments(reviewDTO.getComments());
        review.setStatus(reviewDTO.getStatus());
        
        PerformanceReview updatedReview = reviewRepository.save(review);
        return convertToDTO(updatedReview);
    }
    
    public void deleteReview(Long id) {
        PerformanceReview review = reviewRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Performance review not found with id: " + id));
        reviewRepository.delete(review);
    }
    
    private PerformanceReviewDTO convertToDTO(PerformanceReview review) {
        PerformanceReviewDTO dto = new PerformanceReviewDTO();
        dto.setId(review.getId());
        dto.setEmployeeId(review.getEmployee().getId());
        dto.setEmployeeName(review.getEmployee().getFirstName() + " " + review.getEmployee().getLastName());
        dto.setReviewedById(review.getReviewedBy().getId());
        dto.setReviewedByName(review.getReviewedBy().getFirstName() + " " + review.getReviewedBy().getLastName());
        dto.setReviewPeriod(review.getReviewPeriod());
        dto.setReviewDate(review.getReviewDate());
        dto.setOverallRating(review.getOverallRating());
        dto.setTechnicalSkillsRating(review.getTechnicalSkillsRating());
        dto.setBehavioralRating(review.getBehavioralRating());
        dto.setLeadershipRating(review.getLeadershipRating());
        dto.setTeamworkRating(review.getTeamworkRating());
        dto.setStrengths(review.getStrengths());
        dto.setAreasForImprovement(review.getAreasForImprovement());
        dto.setComments(review.getComments());
        dto.setStatus(review.getStatus());
        dto.setCreatedAt(review.getCreatedAt());
        dto.setUpdatedAt(review.getUpdatedAt());
        return dto;
    }
}
