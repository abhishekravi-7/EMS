package com.employee.system.controller;

import com.employee.system.dto.PerformanceGoalDTO;
import com.employee.system.service.PerformanceGoalService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/performance-goals")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class PerformanceGoalController {
    
    private final PerformanceGoalService goalService;
    
    @PostMapping
    public ResponseEntity<PerformanceGoalDTO> createGoal(@RequestBody PerformanceGoalDTO goalDTO) {
        PerformanceGoalDTO createdGoal = goalService.createGoal(goalDTO);
        return ResponseEntity.status(HttpStatus.CREATED).body(createdGoal);
    }
    
    @GetMapping("/{id}")
    public ResponseEntity<PerformanceGoalDTO> getGoalById(@PathVariable Long id) {
        PerformanceGoalDTO goal = goalService.getGoalById(id);
        return ResponseEntity.ok(goal);
    }
    
    @GetMapping("/employee/{employeeId}")
    public ResponseEntity<List<PerformanceGoalDTO>> getGoalsByEmployee(@PathVariable Long employeeId) {
        List<PerformanceGoalDTO> goals = goalService.getGoalsByEmployee(employeeId);
        return ResponseEntity.ok(goals);
    }
    
    @GetMapping
    public ResponseEntity<List<PerformanceGoalDTO>> getAllGoals() {
        List<PerformanceGoalDTO> goals = goalService.getActiveGoals();
        return ResponseEntity.ok(goals);
    }
    
    @GetMapping("/status/{status}")
    public ResponseEntity<List<PerformanceGoalDTO>> getGoalsByStatus(@PathVariable String status) {
        List<PerformanceGoalDTO> goals = goalService.getGoalsByStatus(status);
        return ResponseEntity.ok(goals);
    }
    
    @PutMapping("/{id}")
    public ResponseEntity<PerformanceGoalDTO> updateGoal(@PathVariable Long id, @RequestBody PerformanceGoalDTO goalDTO) {
        PerformanceGoalDTO updatedGoal = goalService.updateGoal(id, goalDTO);
        return ResponseEntity.ok(updatedGoal);
    }
    
    @PatchMapping("/{id}/progress")
    public ResponseEntity<PerformanceGoalDTO> updateGoalProgress(
        @PathVariable Long id,
        @RequestParam Integer progressPercentage
    ) {
        PerformanceGoalDTO updatedGoal = goalService.updateGoalProgress(id, progressPercentage);
        return ResponseEntity.ok(updatedGoal);
    }
    
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteGoal(@PathVariable Long id) {
        goalService.deleteGoal(id);
        return ResponseEntity.noContent().build();
    }
}
