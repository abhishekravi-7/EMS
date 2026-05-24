package com.employee.system.repository;

import com.employee.system.entity.Employee;
import com.employee.system.entity.KPI;
import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import java.util.stream.Collectors;

@Repository
public class KPIRepository {
    
    private static final Map<Long, KPI> kpis = new HashMap<>();
    private static Long nextId = 1L;
    
    public KPIRepository() {
        initializeDummyData();
    }
    
    private void initializeDummyData() {
        if (kpis.isEmpty()) {
            Employee emp1 = new Employee(1L, "EMP001", "John", "Doe", "john.doe@company.com", "9876543210",
                "IT", "Senior Developer", LocalDate.of(2020, 1, 15),
                "ACTIVE", "123 Main St", LocalDate.of(1990, 5, 20), "MALE",
                LocalDate.now(), LocalDate.now());
            
            kpis.put(1L, new KPI(
                1L, emp1, "Code Quality", "Maintain code quality with proper testing",
                "Percentage", new BigDecimal("95"), new BigDecimal("92"),
                new BigDecimal("25"), "MONTHLY", LocalDate.of(2024, 1, 1),
                LocalDate.of(2024, 12, 31), "ACTIVE", "Test coverage and code reviews",
                LocalDate.now(), LocalDate.now()
            ));
            
            kpis.put(2L, new KPI(
                2L, emp1, "Sprint Velocity", "Complete planned story points in sprint",
                "Count", new BigDecimal("40"), new BigDecimal("38"),
                new BigDecimal("30"), "MONTHLY", LocalDate.of(2024, 1, 1),
                LocalDate.of(2024, 12, 31), "ACTIVE", "Average per sprint",
                LocalDate.now(), LocalDate.now()
            ));
            
            kpis.put(3L, new KPI(
                3L, emp1, "Bug Resolution Time", "Resolve critical bugs within 24 hours",
                "Hours", new BigDecimal("24"), new BigDecimal("20"),
                new BigDecimal("20"), "MONTHLY", LocalDate.of(2024, 1, 1),
                LocalDate.of(2024, 12, 31), "ACTIVE", "Average resolution time",
                LocalDate.now(), LocalDate.now()
            ));
            
            nextId = 4L;
        }
    }
    
    public KPI save(KPI kpi) {
        if (kpi.getId() == null) {
            kpi.setId(nextId++);
            kpi.setCreatedAt(LocalDate.now());
        }
        kpi.setUpdatedAt(LocalDate.now());
        kpis.put(kpi.getId(), kpi);
        return kpi;
    }
    
    public Optional<KPI> findById(Long id) {
        return Optional.ofNullable(kpis.get(id));
    }
    
    public List<KPI> findByEmployee(Employee employee) {
        return kpis.values().stream()
            .filter(k -> k.getEmployee().getId().equals(employee.getId()))
            .collect(Collectors.toList());
    }
    
    public List<KPI> findByStatus(String status) {
        return kpis.values().stream()
            .filter(k -> k.getStatus().equalsIgnoreCase(status))
            .collect(Collectors.toList());
    }
    
    public List<KPI> findByEmployeeAndStatus(Employee employee, String status) {
        return kpis.values().stream()
            .filter(k -> k.getEmployee().getId().equals(employee.getId()) &&
                        k.getStatus().equalsIgnoreCase(status))
            .collect(Collectors.toList());
    }
    
    public List<KPI> findByFrequency(String frequency) {
        return kpis.values().stream()
            .filter(k -> k.getFrequency().equalsIgnoreCase(frequency))
            .collect(Collectors.toList());
    }
    
    public List<KPI> findAll() {
        return new ArrayList<>(kpis.values());
    }
    
    public void delete(KPI kpi) {
        kpis.remove(kpi.getId());
    }
}
