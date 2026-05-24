package com.employee.system.repository;

import com.employee.system.entity.RatingScale;
import org.springframework.stereotype.Repository;

import java.util.*;
import java.util.stream.Collectors;

@Repository
public class RatingScaleRepository {
    
    private static final Map<Long, RatingScale> ratingScales = new HashMap<>();
    private static Long nextId = 1L;
    
    public RatingScaleRepository() {
        initializeDummyData();
    }
    
    private void initializeDummyData() {
        if (ratingScales.isEmpty()) {
            ratingScales.put(1L, new RatingScale(
                1L, 1, "Poor", "Does not meet expectations, significant improvement needed", "Red", 0, 20, true
            ));
            
            ratingScales.put(2L, new RatingScale(
                2L, 2, "Below Average", "Below expectations but shows some competence", "Orange", 21, 40, true
            ));
            
            ratingScales.put(3L, new RatingScale(
                3L, 3, "Average", "Meets expectations, adequate performance", "Yellow", 41, 60, true
            ));
            
            ratingScales.put(4L, new RatingScale(
                4L, 4, "Good", "Exceeds expectations, strong performance", "Green", 61, 80, true
            ));
            
            ratingScales.put(5L, new RatingScale(
                5L, 5, "Excellent", "Significantly exceeds expectations, outstanding performance", "Blue", 81, 100, true
            ));
            
            nextId = 6L;
        }
    }
    
    public RatingScale save(RatingScale ratingScale) {
        if (ratingScale.getId() == null) {
            ratingScale.setId(nextId++);
        }
        ratingScales.put(ratingScale.getId(), ratingScale);
        return ratingScale;
    }
    
    public Optional<RatingScale> findById(Long id) {
        return Optional.ofNullable(ratingScales.get(id));
    }
    
    public Optional<RatingScale> findByRatingValue(Integer value) {
        return ratingScales.values().stream()
            .filter(r -> r.getRatingValue().equals(value))
            .findFirst();
    }
    
    public List<RatingScale> findAllActive() {
        return ratingScales.values().stream()
            .filter(RatingScale::getIsActive)
            .sorted(Comparator.comparingInt(RatingScale::getRatingValue))
            .collect(Collectors.toList());
    }
    
    public List<RatingScale> findAll() {
        return new ArrayList<>(ratingScales.values());
    }
    
    public void delete(RatingScale ratingScale) {
        ratingScales.remove(ratingScale.getId());
    }
}
