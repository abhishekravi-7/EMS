package com.employee.system.service;

import com.employee.system.dto.EmployeeDTO;
import com.employee.system.entity.Employee;
import com.employee.system.repository.EmployeeRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class EmployeeService {
    
    private final EmployeeRepository employeeRepository;
    
    // Create Employee
    public EmployeeDTO createEmployee(EmployeeDTO employeeDTO) {
        Employee employee = new Employee();
        employee.setEmployeeId(employeeDTO.getEmployeeId());
        employee.setFirstName(employeeDTO.getFirstName());
        employee.setLastName(employeeDTO.getLastName());
        employee.setEmail(employeeDTO.getEmail());
        employee.setPhoneNumber(employeeDTO.getPhoneNumber());
        employee.setDepartment(employeeDTO.getDepartment());
        employee.setDesignation(employeeDTO.getDesignation());
        employee.setDateOfJoining(employeeDTO.getDateOfJoining());
        employee.setStatus(employeeDTO.getStatus() != null ? employeeDTO.getStatus() : "ACTIVE");
        employee.setAddress(employeeDTO.getAddress());
        employee.setDateOfBirth(employeeDTO.getDateOfBirth());
        employee.setGender(employeeDTO.getGender());
        
        Employee savedEmployee = employeeRepository.save(employee);
        return convertToDTO(savedEmployee);
    }
    
    // Get Employee by ID
    public EmployeeDTO getEmployeeById(Long id) {
        Employee employee = employeeRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + id));
        return convertToDTO(employee);
    }
    
    // Get Employee by Employee ID
    public EmployeeDTO getEmployeeByEmployeeId(String employeeId) {
        Employee employee = employeeRepository.findByEmployeeId(employeeId)
            .orElseThrow(() -> new RuntimeException("Employee not found with employee id: " + employeeId));
        return convertToDTO(employee);
    }
    
    // Get All Employees
    public List<EmployeeDTO> getAllEmployees() {
        return employeeRepository.findAll()
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    // Get Employees by Department
    public List<EmployeeDTO> getEmployeesByDepartment(String department) {
        return employeeRepository.findByDepartment(department)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    // Get Employees by Designation
    public List<EmployeeDTO> getEmployeesByDesignation(String designation) {
        return employeeRepository.findByDesignation(designation)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    // Search Employees by Name
    public List<EmployeeDTO> searchEmployeesByName(String name) {
        return employeeRepository.searchByName(name)
            .stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());
    }
    
    // Update Employee
    public EmployeeDTO updateEmployee(Long id, EmployeeDTO employeeDTO) {
        Employee employee = employeeRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + id));
        
        employee.setFirstName(employeeDTO.getFirstName());
        employee.setLastName(employeeDTO.getLastName());
        employee.setEmail(employeeDTO.getEmail());
        employee.setPhoneNumber(employeeDTO.getPhoneNumber());
        employee.setDepartment(employeeDTO.getDepartment());
        employee.setDesignation(employeeDTO.getDesignation());
        employee.setStatus(employeeDTO.getStatus());
        employee.setAddress(employeeDTO.getAddress());
        employee.setGender(employeeDTO.getGender());
        
        Employee updatedEmployee = employeeRepository.save(employee);
        return convertToDTO(updatedEmployee);
    }
    
    // Delete Employee
    public void deleteEmployee(Long id) {
        Employee employee = employeeRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + id));
        employeeRepository.delete(employee);
    }
    
    // Get Active Employees Count
    public long getActiveEmployeesCount() {
        return employeeRepository.countActiveEmployees();
    }
    
    // Change Employee Status
    public EmployeeDTO changeEmployeeStatus(Long id, String status) {
        Employee employee = employeeRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Employee not found with id: " + id));
        employee.setStatus(status);
        Employee updatedEmployee = employeeRepository.save(employee);
        return convertToDTO(updatedEmployee);
    }
    
    // Helper method to convert Entity to DTO
    private EmployeeDTO convertToDTO(Employee employee) {
        EmployeeDTO dto = new EmployeeDTO();
        dto.setId(employee.getId());
        dto.setEmployeeId(employee.getEmployeeId());
        dto.setFirstName(employee.getFirstName());
        dto.setLastName(employee.getLastName());
        dto.setEmail(employee.getEmail());
        dto.setPhoneNumber(employee.getPhoneNumber());
        dto.setDepartment(employee.getDepartment());
        dto.setDesignation(employee.getDesignation());
        dto.setDateOfJoining(employee.getDateOfJoining());
        dto.setStatus(employee.getStatus());
        dto.setAddress(employee.getAddress());
        dto.setDateOfBirth(employee.getDateOfBirth());
        dto.setGender(employee.getGender());
        dto.setCreatedAt(employee.getCreatedAt());
        dto.setUpdatedAt(employee.getUpdatedAt());
        return dto;
    }
}
