package com.employee.system.controller;

import com.employee.system.dto.DocumentDTO;
import com.employee.system.service.DocumentService;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.net.MalformedURLException;
import java.util.List;

@RestController
@RequestMapping("/api/documents")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class DocumentController {

    private final DocumentService documentService;

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<DocumentDTO> upload(
        @RequestParam("file") MultipartFile file,
        @RequestParam("employeeId") Long employeeId,
        @RequestParam("docType") String docType
    ) throws IOException {
        DocumentDTO dto = documentService.uploadDocument(file, employeeId, docType);
        return ResponseEntity.status(201).body(dto);
    }

    @GetMapping("/employee/{employeeId}")
    public ResponseEntity<List<DocumentDTO>> listByEmployee(@PathVariable Long employeeId) {
        return ResponseEntity.ok(documentService.listByEmployee(employeeId));
    }

    @GetMapping("/download/{id}")
    public ResponseEntity<Resource> download(@PathVariable Long id) throws MalformedURLException {
        Resource resource = documentService.downloadDocument(id);
        String filename = resource.getFilename();
        return ResponseEntity.ok()
            .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + filename + "\"")
            .body(resource);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) throws IOException {
        documentService.deleteDocument(id);
        return ResponseEntity.noContent().build();
    }
}
