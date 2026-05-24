package com.employee.system.controller;

import com.employee.system.dto.ManagerFeedbackDTO;
import com.employee.system.service.ManagerFeedbackService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/manager-feedback")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class ManagerFeedbackController {
    
    private final ManagerFeedbackService feedbackService;
    
    @PostMapping
    public ResponseEntity<ManagerFeedbackDTO> provideFeedback(@RequestBody ManagerFeedbackDTO feedbackDTO) {
        ManagerFeedbackDTO createdFeedback = feedbackService.provideFeedback(feedbackDTO);
        return ResponseEntity.status(HttpStatus.CREATED).body(createdFeedback);
    }
    
    @GetMapping("/{id}")
    public ResponseEntity<ManagerFeedbackDTO> getFeedbackById(@PathVariable Long id) {
        ManagerFeedbackDTO feedback = feedbackService.getFeedbackById(id);
        return ResponseEntity.ok(feedback);
    }
    
    @GetMapping("/employee/{employeeId}")
    public ResponseEntity<List<ManagerFeedbackDTO>> getFeedbackByEmployee(@PathVariable Long employeeId) {
        List<ManagerFeedbackDTO> feedbackList = feedbackService.getFeedbackByEmployee(employeeId);
        return ResponseEntity.ok(feedbackList);
    }
    
    @GetMapping("/manager/{managerId}")
    public ResponseEntity<List<ManagerFeedbackDTO>> getFeedbackByManager(@PathVariable Long managerId) {
        List<ManagerFeedbackDTO> feedbackList = feedbackService.getFeedbackByManager(managerId);
        return ResponseEntity.ok(feedbackList);
    }
    
    @GetMapping("/type/{type}")
    public ResponseEntity<List<ManagerFeedbackDTO>> getFeedbackByType(@PathVariable String type) {
        List<ManagerFeedbackDTO> feedbackList = feedbackService.getFeedbackByType(type);
        return ResponseEntity.ok(feedbackList);
    }
    
    @GetMapping("/employee/{employeeId}/category/{category}")
    public ResponseEntity<List<ManagerFeedbackDTO>> getFeedbackByCategory(
        @PathVariable Long employeeId,
        @PathVariable String category
    ) {
        List<ManagerFeedbackDTO> feedbackList = feedbackService.getFeedbackByCategory(employeeId, category);
        return ResponseEntity.ok(feedbackList);
    }
    
    @PutMapping("/{id}")
    public ResponseEntity<ManagerFeedbackDTO> updateFeedback(
        @PathVariable Long id,
        @RequestBody ManagerFeedbackDTO feedbackDTO
    ) {
        ManagerFeedbackDTO updatedFeedback = feedbackService.updateFeedback(id, feedbackDTO);
        return ResponseEntity.ok(updatedFeedback);
    }
    
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteFeedback(@PathVariable Long id) {
        feedbackService.deleteFeedback(id);
        return ResponseEntity.noContent().build();
    }
}
