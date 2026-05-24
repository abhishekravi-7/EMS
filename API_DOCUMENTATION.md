# Employee Management System - API Documentation

## Project Overview
This is a comprehensive Employee Management System built with Spring Boot 4.0.6 and Java 17. It provides complete CRUD functionality for employees, attendance tracking, and salary management.

## Features
- **Employee Management**: Create, read, update, delete employee records
- **Attendance Tracking**: Mark attendance, track attendance reports, generate attendance summaries
- **Salary Management**: Manage employee salaries, calculate deductions and allowances, process payments

## Technology Stack
- Spring Boot 4.0.6
- Java 17
- Spring Data JPA
- MySQL 8.0
- Lombok
- Maven

## Prerequisites
- Java 17 or higher
- MySQL Server running on localhost:3306
- Maven 3.6+

## Database Configuration
**File**: `application.properties`

Default configuration:
```properties
spring.datasource.url=jdbc:mysql://localhost:3306/employee_system
spring.datasource.username=root
spring.datasource.password=root
```

**To change database credentials:**
1. Open `src/main/resources/application.properties`
2. Update the `spring.datasource.username` and `spring.datasource.password`
3. Restart the application

The database `employee_system` will be created automatically if it doesn't exist.

## Building and Running

### Build the project:
```bash
mvn clean install
```

### Run the application:
```bash
mvn spring-boot:run
```

Or run the JAR file:
```bash
java -jar target/system-0.0.1-SNAPSHOT.jar
```

The application will start on `http://localhost:8080`

---

## API ENDPOINTS

### 1. EMPLOYEE MANAGEMENT

#### Create Employee
```
POST /api/employees
Content-Type: application/json

{
  "employeeId": "EMP001",
  "firstName": "John",
  "lastName": "Doe",
  "email": "john.doe@company.com",
  "phoneNumber": "9876543210",
  "department": "IT",
  "designation": "Senior Developer",
  "dateOfJoining": "2023-01-15",
  "status": "ACTIVE",
  "address": "123 Main St",
  "dateOfBirth": "1990-05-20",
  "gender": "MALE"
}

Response: 201 Created
{
  "id": 1,
  "employeeId": "EMP001",
  "firstName": "John",
  "lastName": "Doe",
  ... (all fields)
}
```

#### Get Employee by ID
```
GET /api/employees/{id}

Response: 200 OK
{
  "id": 1,
  "employeeId": "EMP001",
  ... (employee details)
}
```

#### Get Employee by Employee ID
```
GET /api/employees/emp/{employeeId}

Example: GET /api/employees/emp/EMP001
Response: 200 OK
```

#### Get All Employees
```
GET /api/employees

Response: 200 OK
[
  { ... },
  { ... }
]
```

#### Get Employees by Department
```
GET /api/employees/department/{department}

Example: GET /api/employees/department/IT
Response: 200 OK
```

#### Get Employees by Designation
```
GET /api/employees/designation/{designation}

Example: GET /api/employees/designation/Senior%20Developer
Response: 200 OK
```

#### Search Employees by Name
```
GET /api/employees/search?name={name}

Example: GET /api/employees/search?name=John
Response: 200 OK
```

#### Update Employee
```
PUT /api/employees/{id}
Content-Type: application/json

{
  "firstName": "Jane",
  "lastName": "Doe",
  ... (other fields to update)
}

Response: 200 OK
```

#### Change Employee Status
```
PATCH /api/employees/{id}/status?status={status}

Status values: ACTIVE, INACTIVE, ON_LEAVE

Example: PATCH /api/employees/1/status?status=ON_LEAVE
Response: 200 OK
```

#### Delete Employee
```
DELETE /api/employees/{id}

Response: 204 No Content
```

#### Get Active Employees Count
```
GET /api/employees/stats/active-count

Response: 200 OK
10
```

---

### 2. ATTENDANCE MANAGEMENT

#### Mark Attendance
```
POST /api/attendance
Content-Type: application/json

{
  "employeeId": 1,
  "attendanceDate": "2024-05-24",
  "status": "PRESENT",
  "checkInTime": "09:00:00",
  "checkOutTime": "17:30:00",
  "remarks": "Regular working day"
}

Status values: PRESENT, ABSENT, LATE, HALF_DAY, ON_LEAVE

Response: 201 Created
```

#### Get Attendance by ID
```
GET /api/attendance/{id}

Response: 200 OK
```

#### Get Attendance for Employee on Specific Date
```
GET /api/attendance/employee/{employeeId}/date?date={date}

Example: GET /api/attendance/employee/1/date?date=2024-05-24
Response: 200 OK
```

#### Get All Attendance Records for Employee
```
GET /api/attendance/employee/{employeeId}

Response: 200 OK
[
  { ... },
  { ... }
]
```

#### Get Attendance Records for Date Range (Specific Employee)
```
GET /api/attendance/employee/{employeeId}/range?startDate={date}&endDate={date}

Example: GET /api/attendance/employee/1/range?startDate=2024-05-01&endDate=2024-05-31
Response: 200 OK
```

#### Get Attendance Records for Date Range (All Employees)
```
GET /api/attendance/range?startDate={date}&endDate={date}

Example: GET /api/attendance/range?startDate=2024-05-01&endDate=2024-05-31
Response: 200 OK
```

#### Update Attendance
```
PUT /api/attendance/{id}
Content-Type: application/json

{
  "status": "LATE",
  "checkInTime": "09:15:00",
  "checkOutTime": "17:30:00",
  "remarks": "Late due to traffic"
}

Response: 200 OK
```

#### Delete Attendance
```
DELETE /api/attendance/{id}

Response: 204 No Content
```

#### Get Attendance Summary for Employee
```
GET /api/attendance/employee/{employeeId}/summary?startDate={date}&endDate={date}

Example: GET /api/attendance/employee/1/summary?startDate=2024-05-01&endDate=2024-05-31

Response: 200 OK
{
  "employeeId": 1,
  "totalDays": 22,
  "presentDays": 20,
  "absentDays": 2,
  "lateDays": 1,
  "halfDays": 0,
  "leaveDays": 0
}
```

---

### 3. SALARY MANAGEMENT

#### Add Salary
```
POST /api/salary
Content-Type: application/json

{
  "employeeId": 1,
  "salaryMonth": 5,
  "salaryYear": 2024,
  "baseSalary": 50000.00,
  "dearnessAllowance": 5000.00,
  "houseRentAllowance": 10000.00,
  "otherAllowances": 2000.00,
  "incomeTax": 5000.00,
  "providentFund": 3000.00,
  "otherDeductions": 500.00,
  "paymentStatus": "PENDING",
  "remarks": "Monthly salary"
}

Response: 201 Created
```

#### Get Salary by ID
```
GET /api/salary/{id}

Response: 200 OK
```

#### Get Salary for Employee and Month/Year
```
GET /api/salary/employee/{employeeId}/month?month={month}&year={year}

Example: GET /api/salary/employee/1/month?month=5&year=2024
Response: 200 OK
```

#### Get All Salary Records for Employee
```
GET /api/salary/employee/{employeeId}

Response: 200 OK
[
  { ... },
  { ... }
]
```

#### Get Annual Salary for Employee
```
GET /api/salary/employee/{employeeId}/annual?year={year}

Example: GET /api/salary/employee/1/annual?year=2024
Response: 200 OK
```

#### Get All Pending Salaries
```
GET /api/salary/pending

Response: 200 OK
[
  { ... },
  { ... }
]
```

#### Get All Paid Salaries
```
GET /api/salary/paid

Response: 200 OK
[
  { ... },
  { ... }
]
```

#### Update Salary
```
PUT /api/salary/{id}
Content-Type: application/json

{
  "baseSalary": 52000.00,
  "dearnessAllowance": 5200.00,
  ... (other fields)
}

Response: 200 OK
```

#### Process Payment
```
PATCH /api/salary/{id}/pay

Response: 200 OK
{
  ... salary details with paymentStatus = "PAID"
}
```

#### Delete Salary
```
DELETE /api/salary/{id}

Response: 204 No Content
```

#### Get Total Paid Salaries
```
GET /api/salary/stats/total-paid

Response: 200 OK
150000.00
```

---

## Error Handling

The API uses standard HTTP status codes and returns detailed error responses:

```json
{
  "timestamp": "2024-05-24T10:30:00",
  "status": 404,
  "error": "Resource Not Found",
  "message": "Employee not found with id: 999",
  "path": "/api/employees/999"
}
```

### Common Status Codes:
- `200 OK` - Successful GET/PUT request
- `201 Created` - Successful POST request
- `204 No Content` - Successful DELETE request
- `400 Bad Request` - Invalid request data
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server-side error

---

## Database Schema

### Employee Table
- id (PK)
- employeeId (UNIQUE)
- firstName
- lastName
- email (UNIQUE)
- phoneNumber
- department
- designation
- dateOfJoining
- status
- address
- dateOfBirth
- gender
- createdAt
- updatedAt

### Attendance Table
- id (PK)
- employee_id (FK)
- attendanceDate
- status
- checkInTime
- checkOutTime
- remarks
- createdAt
- updatedAt

### Salary Table
- id (PK)
- employee_id (FK)
- salaryMonth
- salaryYear
- baseSalary
- dearnessAllowance
- houseRentAllowance
- otherAllowances
- totalAllowances
- incomeTax
- providentFund
- otherDeductions
- totalDeductions
- netSalary
- paymentStatus
- paymentDate
- remarks
- createdAt
- updatedAt

---

## Testing with cURL

### Create an Employee:
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

### Get All Employees:
```bash
curl -X GET http://localhost:8080/api/employees
```

### Mark Attendance:
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

---

## Troubleshooting

### Issue: Database Connection Error
**Solution:**
1. Ensure MySQL is running: `mysql -u root -p`
2. Check credentials in application.properties
3. Verify database exists or allow auto-creation

### Issue: Port 8080 Already in Use
**Solution:**
Change port in application.properties:
```properties
server.port=8081
```

### Issue: Validation Errors
**Solution:**
Ensure all required fields are provided in the request body, check data types and formats.

---

## Future Enhancements
- User authentication and authorization
- Email notifications
- Salary slip generation (PDF)
- Advanced reporting and analytics
- Mobile app integration
- Batch operations for attendance
- Performance metrics and dashboards

---

## Support
For any issues or questions, please contact the development team or refer to the Spring Boot documentation.
