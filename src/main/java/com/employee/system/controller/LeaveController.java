package com.employee.system.controller;

import com.employee.system.dto.LeaveBalanceDTO;
import com.employee.system.dto.LeaveDTO;
import com.employee.system.service.LeaveService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/leaves")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class LeaveController {

    private final LeaveService leaveService;

    @PostMapping
    public ResponseEntity<LeaveDTO> applyLeave(@RequestBody LeaveDTO dto) {
        LeaveDTO created = leaveService.applyLeave(dto);
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }

    @PutMapping("/{id}/approve")
    public ResponseEntity<LeaveDTO> approveLeave(@PathVariable Long id, @RequestParam(defaultValue = "true") boolean approve) {
        LeaveDTO updated = leaveService.approveLeave(id, approve);
        return ResponseEntity.ok(updated);
    }

    @GetMapping("/employee/{employeeId}")
    public ResponseEntity<List<LeaveDTO>> getLeavesByEmployee(@PathVariable Long employeeId) {
        return ResponseEntity.ok(leaveService.getLeavesByEmployee(employeeId));
    }

    @GetMapping("/status/{status}")
    public ResponseEntity<List<LeaveDTO>> getLeavesByStatus(@PathVariable String status) {
        return ResponseEntity.ok(leaveService.getLeavesByStatus(status));
    }

    @GetMapping("/{id}")
    public ResponseEntity<LeaveDTO> getLeaveById(@PathVariable Long id) {
        return ResponseEntity.ok(leaveService.getLeaveById(id));
    }

    @GetMapping("/employee/{employeeId}/balance/{year}")
    public ResponseEntity<LeaveBalanceDTO> getLeaveBalance(@PathVariable Long employeeId, @PathVariable int year) {
        return ResponseEntity.ok(leaveService.getLeaveBalance(employeeId, year));
    }
}
