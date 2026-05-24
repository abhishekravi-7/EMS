package com.employee.system.service;

import com.employee.system.dto.RatingScaleDTO;
import com.employee.system.entity.RatingScale;
import com.employee.system.repository.RatingScaleRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class RatingScaleService {

    private final RatingScaleRepository ratingScaleRepository;

    public RatingScaleDTO getRatingScaleById(Long id) {
        RatingScale rs = ratingScaleRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Rating scale not found with id: " + id));
        return toDTO(rs);
    }

    public RatingScaleDTO getRatingScaleByValue(Integer value) {
        RatingScale rs = ratingScaleRepository.findByRatingValue(value)
            .orElseThrow(() -> new RuntimeException("Rating scale not found with value: " + value));
        return toDTO(rs);
    }

    public List<RatingScaleDTO> getAllActiveRatingScales() {
        return ratingScaleRepository.findAllActive().stream()
            .map(this::toDTO)
            .collect(Collectors.toList());
    }

    public List<RatingScaleDTO> getAllRatingScales() {
        return ratingScaleRepository.findAll().stream()
            .map(this::toDTO)
            .collect(Collectors.toList());
    }

    public RatingScaleDTO createRatingScale(RatingScaleDTO dto) {
        RatingScale rs = new RatingScale();
        rs.setRatingValue(dto.getRatingValue());
        rs.setRatingLabel(dto.getRatingLabel());
        rs.setRatingDescription(dto.getRatingDescription());
        rs.setColorCode(dto.getColorCode());
        rs.setMinimumScore(dto.getMinimumScore());
        rs.setMaximumScore(dto.getMaximumScore());
        rs.setIsActive(dto.getIsActive() != null ? dto.getIsActive() : true);
        RatingScale saved = ratingScaleRepository.save(rs);
        return toDTO(saved);
    }

    public RatingScaleDTO updateRatingScale(Long id, RatingScaleDTO dto) {
        RatingScale rs = ratingScaleRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Rating scale not found with id: " + id));
        rs.setRatingValue(dto.getRatingValue());
        rs.setRatingLabel(dto.getRatingLabel());
        rs.setRatingDescription(dto.getRatingDescription());
        rs.setColorCode(dto.getColorCode());
        rs.setMinimumScore(dto.getMinimumScore());
        rs.setMaximumScore(dto.getMaximumScore());
        rs.setIsActive(dto.getIsActive());
        RatingScale updated = ratingScaleRepository.save(rs);
        return toDTO(updated);
    }

    public void deleteRatingScale(Long id) {
        RatingScale rs = ratingScaleRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Rating scale not found with id: " + id));
        ratingScaleRepository.delete(rs);
    }

    private RatingScaleDTO toDTO(RatingScale rs) {
        RatingScaleDTO dto = new RatingScaleDTO();
        dto.setId(rs.getId());
        dto.setRatingValue(rs.getRatingValue());
        dto.setRatingLabel(rs.getRatingLabel());
        dto.setRatingDescription(rs.getRatingDescription());
        dto.setColorCode(rs.getColorCode());
        dto.setMinimumScore(rs.getMinimumScore());
        dto.setMaximumScore(rs.getMaximumScore());
        dto.setIsActive(rs.getIsActive());
        return dto;
    }
}
