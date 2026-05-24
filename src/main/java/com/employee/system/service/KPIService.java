package com.employee.system.service;

import com.employee.system.dto.KPIDTO;
import com.employee.system.entity.Employee;
import com.employee.system.entity.KPI;
import com.employee.system.repository.EmployeeRepository;
import com.employee.system.repository.KPIRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class KPIService {
    
    private final KPIRepository kpiRepository;
    private final EmployeeRepository employeeRepository;
    
    public KPIDTO createKPI(KPIDTO kpiDTO) {
        Employee employee = employeeRepository.findById(kpiDTO.getEmployeeId())
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + kpiDTO.getEmployeeId()));
        
        KPI kpi = new KPI();
        kpi.setEmployee(employee);
        kpi.setKpiName(kpiDTO.getKpiName());
        kpi.setKpiDescription(kpiDTO.getKpiDescription());
        kpi.setMeasurementUnit(kpiDTO.getMeasurementUnit());
        kpi.setTargetValue(kpiDTO.getTargetValue());
        kpi.setCurrentValue(kpiDTO.getCurrentValue() != null ? kpiDTO.getCurrentValue() : BigDecimal.ZERO);
        kpi.setWeight(kpiDTO.getWeight());
        kpi.setFrequency(kpiDTO.getFrequency());
        kpi.setStartDate(kpiDTO.getStartDate());
        kpi.setEndDate(kpiDTO.getEndDate());
        kpi.setStatus(kpiDTO.getStatus() != null ? kpiDTO.getStatus() : "ACTIVE");
        kpi.setRemarks(kpiDTO.getRemarks());
        
        KPI savedKPI = kpiRepository.save(kpi);
        return convertToDTO(savedKPI);
    }
    
    public KPIDTO getKPIById(Long id) {
        KPI kpi = kpiRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("KPI not found with id: " + id));
        return convertToDTO(kpi);
    }
    
    public List<KPIDTO> getKPIsByEmployee(Long employeeId) {
        Employee employee = employeeRepository.findById(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + employeeId));
        
        return kpiRepository.findByEmployee(employee)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    public List<KPIDTO> getActiveKPIs() {
        return kpiRepository.findByStatus("ACTIVE")
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    public List<KPIDTO> getKPIsByFrequency(String frequency) {
        return kpiRepository.findByFrequency(frequency)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    public KPIDTO updateKPI(Long id, KPIDTO kpiDTO) {
        KPI kpi = kpiRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("KPI not found with id: " + id));
        
        kpi.setKpiName(kpiDTO.getKpiName());
        kpi.setKpiDescription(kpiDTO.getKpiDescription());
        kpi.setMeasurementUnit(kpiDTO.getMeasurementUnit());
        kpi.setTargetValue(kpiDTO.getTargetValue());
        kpi.setWeight(kpiDTO.getWeight());
        kpi.setFrequency(kpiDTO.getFrequency());
        kpi.setEndDate(kpiDTO.getEndDate());
        kpi.setStatus(kpiDTO.getStatus());
        kpi.setRemarks(kpiDTO.getRemarks());
        
        KPI updatedKPI = kpiRepository.save(kpi);
        return convertToDTO(updatedKPI);
    }
    
    public KPIDTO updateKPIProgress(Long id, BigDecimal currentValue) {
        KPI kpi = kpiRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("KPI not found with id: " + id));
        
        kpi.setCurrentValue(currentValue);
        KPI updatedKPI = kpiRepository.save(kpi);
        return convertToDTO(updatedKPI);
    }
    
    public void deleteKPI(Long id) {
        KPI kpi = kpiRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("KPI not found with id: " + id));
        kpiRepository.delete(kpi);
    }
    
    private KPIDTO convertToDTO(KPI kpi) {
        KPIDTO dto = new KPIDTO();
        dto.setId(kpi.getId());
        dto.setEmployeeId(kpi.getEmployee().getId());
        dto.setEmployeeName(kpi.getEmployee().getFirstName() + " " + kpi.getEmployee().getLastName());
        dto.setKpiName(kpi.getKpiName());
        dto.setKpiDescription(kpi.getKpiDescription());
        dto.setMeasurementUnit(kpi.getMeasurementUnit());
        dto.setTargetValue(kpi.getTargetValue());
        dto.setCurrentValue(kpi.getCurrentValue());
        dto.setWeight(kpi.getWeight());
        dto.setFrequency(kpi.getFrequency());
        dto.setStartDate(kpi.getStartDate());
        dto.setEndDate(kpi.getEndDate());
        dto.setStatus(kpi.getStatus());
        dto.setRemarks(kpi.getRemarks());
        dto.setCreatedAt(kpi.getCreatedAt());
        dto.setUpdatedAt(kpi.getUpdatedAt());
        return dto;
    }
}
