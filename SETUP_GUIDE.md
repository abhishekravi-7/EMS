# Employee Management System - Quick Start Guide

## Overview
A comprehensive Employee Management System with CRUD functionality, Attendance Tracking, and Salary Management built with Spring Boot.

## Project Structure

```
src/
├── main/
│   ├── java/com/employee/system/
│   │   ├── controller/          # REST API Controllers
│   │   │   ├── EmployeeController.java
│   │   │   ├── AttendanceController.java
│   │   │   └── SalaryController.java
│   │   ├── service/             # Business Logic
│   │   │   ├── EmployeeService.java
│   │   │   ├── AttendanceService.java
│   │   │   ├── SalaryService.java
│   │   │   └── AttendanceSummary.java
│   │   ├── entity/              # JPA Entities
│   │   │   ├── Employee.java
│   │   │   ├── Attendance.java
│   │   │   └── Salary.java
│   │   ├── repository/          # Data Access Layer
│   │   │   ├── EmployeeRepository.java
│   │   │   ├── AttendanceRepository.java
│   │   │   └── SalaryRepository.java
│   │   ├── dto/                 # Data Transfer Objects
│   │   │   ├── EmployeeDTO.java
│   │   │   ├── AttendanceDTO.java
│   │   │   └── SalaryDTO.java
│   │   ├── exception/           # Exception Handling
│   │   │   ├── ErrorResponse.java
│   │   │   └── GlobalExceptionHandler.java
│   │   ├── response/            # Response Wrappers
│   │   │   └── ApiResponse.java
│   │   └── SystemApplication.java
│   └── resources/
│       └── application.properties
└── test/
    └── java/com/employee/system/
        └── SystemApplicationTests.java
```

## Setup Instructions

### 1. Prerequisites
- Java 17 or higher
- MySQL Server 8.0+
- Maven 3.6+
- IDE: IntelliJ IDEA / Eclipse / VS Code

### 2. Database Setup

#### Create Database (Optional - will be auto-created):
```sql
CREATE DATABASE employee_system;
USE employee_system;
```

#### Update Database Credentials:
Edit `src/main/resources/application.properties`:

```properties
spring.datasource.url=jdbc:mysql://localhost:3306/employee_system?createDatabaseIfNotExist=true
spring.datasource.username=root          # Change if different
spring.datasource.password=root          # Change if different
```

### 3. Build the Project

```bash
# Clean and build
mvn clean install

# Or with tests skipped (faster)
mvn clean install -DskipTests
```

### 4. Run the Application

**Option 1: Using Maven**
```bash
mvn spring-boot:run
```

**Option 2: Running JAR**
```bash
java -jar target/system-0.0.1-SNAPSHOT.jar
```

**Option 3: Using IDE**
- Right-click `SystemApplication.java` → Run

### 5. Verify Application is Running

Access the application at: `http://localhost:8080`

Check logs for startup messages:
```
Started SystemApplication in X seconds
```

## Key Features

### 📋 Employee Management
- Create, Read, Update, Delete employees
- Search employees by name, department, designation
- Track employee status (ACTIVE, INACTIVE, ON_LEAVE)
- Employee statistics (active count, etc.)

### 📅 Attendance Tracking
- Mark daily attendance with check-in/check-out times
- Track attendance status (PRESENT, ABSENT, LATE, HALF_DAY, ON_LEAVE)
- Generate attendance reports for date ranges
- Attendance summary (present days, absent days, late days, etc.)

### 💰 Salary Management
- Create and manage employee salaries
- Calculate allowances (DA, HRA, other allowances)
- Calculate deductions (Income Tax, PF, other deductions)
- Automatic net salary calculation
- Track payment status (PENDING, PAID, REJECTED)
- Annual salary reports

## API Endpoints Summary

### Employee Endpoints
```
POST   /api/employees                           - Create employee
GET    /api/employees                           - Get all employees
GET    /api/employees/{id}                      - Get employee by ID
GET    /api/employees/emp/{employeeId}          - Get by Employee ID
GET    /api/employees/department/{dept}         - Get by department
GET    /api/employees/designation/{design}      - Get by designation
GET    /api/employees/search?name=               - Search by name
PUT    /api/employees/{id}                      - Update employee
PATCH  /api/employees/{id}/status?status=       - Change status
DELETE /api/employees/{id}                      - Delete employee
GET    /api/employees/stats/active-count        - Get active count
```

### Attendance Endpoints
```
POST   /api/attendance                          - Mark attendance
GET    /api/attendance/{id}                     - Get attendance
GET    /api/attendance/employee/{empId}         - Get all by employee
GET    /api/attendance/employee/{empId}/date    - Get by date
GET    /api/attendance/employee/{empId}/range   - Get date range
GET    /api/attendance/range                    - Get all for date range
PUT    /api/attendance/{id}                     - Update attendance
DELETE /api/attendance/{id}                     - Delete attendance
GET    /api/attendance/employee/{empId}/summary - Get attendance summary
```

### Salary Endpoints
```
POST   /api/salary                              - Add salary
GET    /api/salary/{id}                         - Get salary
GET    /api/salary/employee/{empId}             - Get all by employee
GET    /api/salary/employee/{empId}/month       - Get monthly salary
GET    /api/salary/employee/{empId}/annual      - Get annual salaries
GET    /api/salary/pending                      - Get pending salaries
GET    /api/salary/paid                         - Get paid salaries
PUT    /api/salary/{id}                         - Update salary
PATCH  /api/salary/{id}/pay                     - Process payment
DELETE /api/salary/{id}                         - Delete salary
GET    /api/salary/stats/total-paid             - Get total paid amount
```

## Testing the API

### Using cURL (Command Line)

**Create an Employee:**
```bash
curl -X POST http://localhost:8080/api/employees \
  -H "Content-Type: application/json" \
  -d '{
    "employeeId": "EMP001",
    "firstName": "John",
    "lastName": "Doe",
    "email": "john.doe@company.com",
    "phoneNumber": "9876543210",
    "department": "IT",
    "designation": "Developer",
    "dateOfJoining": "2023-01-15",
    "status": "ACTIVE",
    "dateOfBirth": "1990-05-20",
    "gender": "MALE"
  }'
```

**Get All Employees:**
```bash
curl http://localhost:8080/api/employees
```

**Mark Attendance:**
```bash
curl -X POST http://localhost:8080/api/attendance \
  -H "Content-Type: application/json" \
  -d '{
    "employeeId": 1,
    "attendanceDate": "2024-05-24",
    "status": "PRESENT",
    "checkInTime": "09:00:00",
    "checkOutTime": "17:30:00"
  }'
```

### Using Postman
1. Create a new Collection
2. Import the endpoints
3. Set Base URL: `http://localhost:8080`
4. Create requests with proper headers and body

## Configuration

### application.properties Key Settings

```properties
# Database
spring.datasource.url=jdbc:mysql://localhost:3306/employee_system
spring.datasource.username=root
spring.datasource.password=root

# JPA/Hibernate
spring.jpa.hibernate.ddl-auto=update    # or validate, create-drop, create
spring.jpa.show-sql=false                # Set to true to see SQL queries

# Server
server.port=8080

# Logging
logging.level.com.employee.system=DEBUG
```

### Important Configurations Explained

**`ddl-auto` Options:**
- `update` - Creates/updates tables as needed (Recommended for development)
- `create` - Drops and creates tables on startup
- `create-drop` - Creates tables, drops on shutdown
- `validate` - Validates schema matches entities

## Database Tables

### employees
Stores employee information with personal details, department, and status.

### attendance
Tracks daily attendance with check-in/out times and status.

### salary
Maintains salary records with allowances, deductions, and payment status.

## Troubleshooting

### Database Connection Error
```
com.mysql.cj.jdbc.exceptions.CommunicationsException
```
**Solution:**
1. Verify MySQL is running: `mysql -u root -p`
2. Check connection details in application.properties
3. Ensure database is created (auto-created by default)

### Port Already in Use
```
Address already in use: bind
```
**Solution:**
Change `server.port=8081` in application.properties

### No Tables Found
```
Table 'employee_system.employee' doesn't exist
```
**Solution:**
1. Check `spring.jpa.hibernate.ddl-auto=update`
2. Restart application
3. Check database creation

## Next Steps

1. **Customize Entities** - Add more fields as needed
2. **Add Validation** - Implement @Valid annotations
3. **Add Security** - Configure Spring Security
4. **Add Authentication** - Implement JWT tokens
5. **Create Frontend** - React/Angular UI
6. **Add Reports** - Generate PDF/Excel reports
7. **Add Caching** - Redis for performance
8. **Deploy** - Docker/Cloud deployment

## Additional Resources

- [API Documentation](./API_DOCUMENTATION.md)
- [Spring Boot Docs](https://spring.io/projects/spring-boot)
- [Spring Data JPA Docs](https://spring.io/projects/spring-data-jpa)
- [MySQL Docs](https://dev.mysql.com/doc/)

## Support

For issues or questions:
1. Check logs in console
2. Review API Documentation
3. Verify database connection
4. Check request/response formats

---

**Happy Coding! 🚀**
