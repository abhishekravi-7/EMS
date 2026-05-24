package com.employee.system.controller;

import com.employee.system.dto.SelfAssessmentDTO;
import com.employee.system.service.SelfAssessmentService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/self-assessments")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class SelfAssessmentController {
    
    private final SelfAssessmentService assessmentService;
    
    @PostMapping
    public ResponseEntity<SelfAssessmentDTO> createAssessment(@RequestBody SelfAssessmentDTO assessmentDTO) {
        SelfAssessmentDTO createdAssessment = assessmentService.createAssessment(assessmentDTO);
        return ResponseEntity.status(HttpStatus.CREATED).body(createdAssessment);
    }
    
    @GetMapping("/{id}")
    public ResponseEntity<SelfAssessmentDTO> getAssessmentById(@PathVariable Long id) {
        SelfAssessmentDTO assessment = assessmentService.getAssessmentById(id);
        return ResponseEntity.ok(assessment);
    }
    
    @GetMapping("/employee/{employeeId}")
    public ResponseEntity<List<SelfAssessmentDTO>> getAssessmentsByEmployee(@PathVariable Long employeeId) {
        List<SelfAssessmentDTO> assessments = assessmentService.getAssessmentsByEmployee(employeeId);
        return ResponseEntity.ok(assessments);
    }
    
    @GetMapping("/period/{period}")
    public ResponseEntity<List<SelfAssessmentDTO>> getAssessmentsByPeriod(@PathVariable String period) {
        List<SelfAssessmentDTO> assessments = assessmentService.getAssessmentsByPeriod(period);
        return ResponseEntity.ok(assessments);
    }
    
    @GetMapping("/status/{status}")
    public ResponseEntity<List<SelfAssessmentDTO>> getAssessmentsByStatus(@PathVariable String status) {
        List<SelfAssessmentDTO> assessments = assessmentService.getAssessmentsByStatus(status);
        return ResponseEntity.ok(assessments);
    }
    
    @PutMapping("/{id}")
    public ResponseEntity<SelfAssessmentDTO> updateAssessment(
        @PathVariable Long id,
        @RequestBody SelfAssessmentDTO assessmentDTO
    ) {
        SelfAssessmentDTO updatedAssessment = assessmentService.updateAssessment(id, assessmentDTO);
        return ResponseEntity.ok(updatedAssessment);
    }
    
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteAssessment(@PathVariable Long id) {
        assessmentService.deleteAssessment(id);
        return ResponseEntity.noContent().build();
    }
}
