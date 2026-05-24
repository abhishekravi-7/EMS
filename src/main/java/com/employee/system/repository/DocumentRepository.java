package com.employee.system.repository;

import com.employee.system.entity.Document;
import com.employee.system.entity.Employee;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.*;
import java.util.stream.Collectors;

@Repository
public class DocumentRepository {

    private static final Map<Long, Document> docs = new HashMap<>();
    private static Long nextId = 1L;

    public Document save(Document d) {
        if (d.getId() == null) {
            d.setId(nextId++);
            d.setCreatedAt(LocalDate.now());
        }
        d.setUpdatedAt(LocalDate.now());
        docs.put(d.getId(), d);
        return d;
    }

    public Optional<Document> findById(Long id) {
        return Optional.ofNullable(docs.get(id));
    }

    public List<Document> findByEmployee(Employee e) {
        return docs.values().stream()
            .filter(d -> d.getEmployee() != null && d.getEmployee().getId().equals(e.getId()))
            .collect(Collectors.toList());
    }

    public List<Document> findByEmployeeAndType(Employee e, String type) {
        return docs.values().stream()
            .filter(d -> d.getEmployee() != null && d.getEmployee().getId().equals(e.getId()) && type.equals(d.getDocType()))
            .collect(Collectors.toList());
    }

    public void delete(Document d) {
        docs.remove(d.getId());
    }
}
