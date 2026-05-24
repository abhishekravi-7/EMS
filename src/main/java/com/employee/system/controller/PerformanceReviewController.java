package com.employee.system.controller;

import com.employee.system.dto.PerformanceReviewDTO;
import com.employee.system.service.PerformanceReviewService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/performance-reviews")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class PerformanceReviewController {
    
    private final PerformanceReviewService reviewService;
    
    @PostMapping
    public ResponseEntity<PerformanceReviewDTO> createReview(@RequestBody PerformanceReviewDTO reviewDTO) {
        PerformanceReviewDTO createdReview = reviewService.createReview(reviewDTO);
        return ResponseEntity.status(HttpStatus.CREATED).body(createdReview);
    }
    
    @GetMapping("/{id}")
    public ResponseEntity<PerformanceReviewDTO> getReviewById(@PathVariable Long id) {
        PerformanceReviewDTO review = reviewService.getReviewById(id);
        return ResponseEntity.ok(review);
    }
    
    @GetMapping("/employee/{employeeId}")
    public ResponseEntity<List<PerformanceReviewDTO>> getReviewsByEmployee(@PathVariable Long employeeId) {
        List<PerformanceReviewDTO> reviews = reviewService.getReviewsByEmployee(employeeId);
        return ResponseEntity.ok(reviews);
    }
    
    @GetMapping("/manager/{managerId}")
    public ResponseEntity<List<PerformanceReviewDTO>> getReviewsByManager(@PathVariable Long managerId) {
        List<PerformanceReviewDTO> reviews = reviewService.getReviewsByManager(managerId);
        return ResponseEntity.ok(reviews);
    }
    
    @GetMapping("/period/{period}")
    public ResponseEntity<List<PerformanceReviewDTO>> getReviewsByPeriod(@PathVariable String period) {
        List<PerformanceReviewDTO> reviews = reviewService.getReviewsByPeriod(period);
        return ResponseEntity.ok(reviews);
    }
    
    @PutMapping("/{id}")
    public ResponseEntity<PerformanceReviewDTO> updateReview(
        @PathVariable Long id,
        @RequestBody PerformanceReviewDTO reviewDTO
    ) {
        PerformanceReviewDTO updatedReview = reviewService.updateReview(id, reviewDTO);
        return ResponseEntity.ok(updatedReview);
    }
    
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteReview(@PathVariable Long id) {
        reviewService.deleteReview(id);
        return ResponseEntity.noContent().build();
    }
}
