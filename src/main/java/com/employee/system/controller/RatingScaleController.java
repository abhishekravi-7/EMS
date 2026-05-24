package com.employee.system.controller;

import com.employee.system.dto.RatingScaleDTO;
import com.employee.system.service.RatingScaleService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/rating-scales")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class RatingScaleController {
    
    private final RatingScaleService ratingScaleService;
    
    @GetMapping("/{id}")
    public ResponseEntity<RatingScaleDTO> getRatingScaleById(@PathVariable Long id) {
        RatingScaleDTO ratingScale = ratingScaleService.getRatingScaleById(id);
        return ResponseEntity.ok(ratingScale);
    }
    
    @GetMapping("/value/{value}")
    public ResponseEntity<RatingScaleDTO> getRatingScaleByValue(@PathVariable Integer value) {
        RatingScaleDTO ratingScale = ratingScaleService.getRatingScaleByValue(value);
        return ResponseEntity.ok(ratingScale);
    }
    
    @GetMapping("/active")
    public ResponseEntity<List<RatingScaleDTO>> getAllActiveRatingScales() {
        List<RatingScaleDTO> ratingScales = ratingScaleService.getAllActiveRatingScales();
        return ResponseEntity.ok(ratingScales);
    }
    
    @GetMapping
    public ResponseEntity<List<RatingScaleDTO>> getAllRatingScales() {
        List<RatingScaleDTO> ratingScales = ratingScaleService.getAllRatingScales();
        return ResponseEntity.ok(ratingScales);
    }
    
    @PostMapping
    public ResponseEntity<RatingScaleDTO> createRatingScale(@RequestBody RatingScaleDTO ratingScaleDTO) {
        RatingScaleDTO createdRatingScale = ratingScaleService.createRatingScale(ratingScaleDTO);
        return ResponseEntity.status(HttpStatus.CREATED).body(createdRatingScale);
    }
    
    @PutMapping("/{id}")
    public ResponseEntity<RatingScaleDTO> updateRatingScale(
        @PathVariable Long id,
        @RequestBody RatingScaleDTO ratingScaleDTO
    ) {
        RatingScaleDTO updatedRatingScale = ratingScaleService.updateRatingScale(id, ratingScaleDTO);
        return ResponseEntity.ok(updatedRatingScale);
    }
    
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteRatingScale(@PathVariable Long id) {
        ratingScaleService.deleteRatingScale(id);
        return ResponseEntity.noContent().build();
    }
}
