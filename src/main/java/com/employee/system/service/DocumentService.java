package com.employee.system.service;

import com.employee.system.dto.DocumentDTO;
import com.employee.system.entity.Document;
import com.employee.system.entity.Employee;
import com.employee.system.repository.DocumentRepository;
import com.employee.system.repository.EmployeeRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import jakarta.annotation.PostConstruct;
import java.net.MalformedURLException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class DocumentService {

    private final DocumentRepository documentRepository;
    private final EmployeeRepository employeeRepository;

    private final Path uploadsDir = Paths.get("uploads");

    @PostConstruct
    public void init() {
        try {
            Files.createDirectories(uploadsDir);
        } catch (IOException e) {
            throw new RuntimeException("Unable to create uploads directory", e);
        }
    }

    public DocumentDTO uploadDocument(MultipartFile file, Long employeeId, String docType) throws IOException {
        Employee employee = employeeRepository.findById(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found: " + employeeId));

        String original = sanitizeFilename(file.getOriginalFilename());
        String stored = UUID.randomUUID().toString() + "_" + original;

        Path target = uploadsDir.resolve(stored);
        Files.copy(file.getInputStream(), target, StandardCopyOption.REPLACE_EXISTING);

        Document d = new Document();
        d.setEmployee(employee);
        d.setDocType(docType);
        d.setOriginalFileName(original);
        d.setStoredFileName(stored);
        d.setContentType(file.getContentType());
        d.setSize(file.getSize());

        Document saved = documentRepository.save(d);
        return toDTO(saved);
    }

    public Resource downloadDocument(Long id) throws MalformedURLException {
        Document d = documentRepository.findById(id).orElseThrow(() -> new RuntimeException("Document not found: " + id));
        Path file = uploadsDir.resolve(d.getStoredFileName());
        Resource resource = new UrlResource(file.toUri());
        if (!resource.exists()) throw new RuntimeException("Stored file missing");
        return resource;
    }

    public List<DocumentDTO> listByEmployee(Long employeeId) {
        Employee employee = employeeRepository.findById(employeeId).orElseThrow(() -> new RuntimeException("Employee not found: " + employeeId));
        return documentRepository.findByEmployee(employee).stream().map(this::toDTO).collect(Collectors.toList());
    }

    public void deleteDocument(Long id) throws IOException {
        Document d = documentRepository.findById(id).orElseThrow(() -> new RuntimeException("Document not found: " + id));
        Path file = uploadsDir.resolve(d.getStoredFileName());
        Files.deleteIfExists(file);
        documentRepository.delete(d);
    }

    private String sanitizeFilename(String name) {
        if (name == null) return "unnamed";
        return Paths.get(name).getFileName().toString().replaceAll("[^a-zA-Z0-9._-]", "_");
    }

    private DocumentDTO toDTO(Document d) {
        DocumentDTO dto = new DocumentDTO();
        dto.setId(d.getId());
        dto.setEmployeeId(d.getEmployee() != null ? d.getEmployee().getId() : null);
        dto.setDocType(d.getDocType());
        dto.setOriginalFileName(d.getOriginalFileName());
        dto.setStoredFileName(d.getStoredFileName());
        dto.setContentType(d.getContentType());
        dto.setSize(d.getSize());
        dto.setCreatedAt(d.getCreatedAt());
        dto.setUpdatedAt(d.getUpdatedAt());
        return dto;
    }
}
