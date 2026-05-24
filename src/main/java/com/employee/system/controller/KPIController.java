package com.employee.system.controller;

import com.employee.system.dto.KPIDTO;
import com.employee.system.service.KPIService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.List;

@RestController
@RequestMapping("/api/kpis")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class KPIController {
    
    private final KPIService kpiService;
    
    @PostMapping
    public ResponseEntity<KPIDTO> createKPI(@RequestBody KPIDTO kpiDTO) {
        KPIDTO createdKPI = kpiService.createKPI(kpiDTO);
        return ResponseEntity.status(HttpStatus.CREATED).body(createdKPI);
    }
    
    @GetMapping("/{id}")
    public ResponseEntity<KPIDTO> getKPIById(@PathVariable Long id) {
        KPIDTO kpi = kpiService.getKPIById(id);
        return ResponseEntity.ok(kpi);
    }
    
    @GetMapping("/employee/{employeeId}")
    public ResponseEntity<List<KPIDTO>> getKPIsByEmployee(@PathVariable Long employeeId) {
        List<KPIDTO> kpis = kpiService.getKPIsByEmployee(employeeId);
        return ResponseEntity.ok(kpis);
    }
    
    @GetMapping("/active")
    public ResponseEntity<List<KPIDTO>> getActiveKPIs() {
        List<KPIDTO> kpis = kpiService.getActiveKPIs();
        return ResponseEntity.ok(kpis);
    }
    
    @GetMapping("/frequency/{frequency}")
    public ResponseEntity<List<KPIDTO>> getKPIsByFrequency(@PathVariable String frequency) {
        List<KPIDTO> kpis = kpiService.getKPIsByFrequency(frequency);
        return ResponseEntity.ok(kpis);
    }
    
    @PutMapping("/{id}")
    public ResponseEntity<KPIDTO> updateKPI(@PathVariable Long id, @RequestBody KPIDTO kpiDTO) {
        KPIDTO updatedKPI = kpiService.updateKPI(id, kpiDTO);
        return ResponseEntity.ok(updatedKPI);
    }
    
    @PatchMapping("/{id}/progress")
    public ResponseEntity<KPIDTO> updateKPIProgress(
        @PathVariable Long id,
        @RequestParam BigDecimal currentValue
    ) {
        KPIDTO updatedKPI = kpiService.updateKPIProgress(id, currentValue);
        return ResponseEntity.ok(updatedKPI);
    }
    
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteKPI(@PathVariable Long id) {
        kpiService.deleteKPI(id);
        return ResponseEntity.noContent().build();
    }
}
