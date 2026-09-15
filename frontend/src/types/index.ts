export interface Employee {
  id: number;
  employeeId: string;
  firstName: string;
  lastName: string;
  email: string;
  phoneNumber: string;
  department: string;
  designation: string;
  dateOfJoining: string;
  status: 'ACTIVE' | 'INACTIVE' | 'ON_LEAVE';
  address: string;
  dateOfBirth: string;
  gender: 'MALE' | 'FEMALE' | 'OTHER';
  createdAt?: string;
  updatedAt?: string;
}

export interface Attendance {
  id: number;
  employee: Employee;
  attendanceDate: string;
  status: 'PRESENT' | 'ABSENT' | 'LATE' | 'HALF_DAY' | 'ON_LEAVE';
  checkInTime: string;
  checkOutTime: string;
  remarks: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface AttendanceSummary {
  employeeId: number;
  totalDays: number;
  presentDays: number;
  absentDays: number;
  lateDays: number;
  halfDays: number;
  leaveDays: number;
}

export interface Salary {
  id: number;
  employee: Employee;
  salaryMonth: number;
  salaryYear: number;
  baseSalary: number;
  dearnessAllowance: number;
  houseRentAllowance: number;
  otherAllowances: number;
  totalAllowances?: number;
  incomeTax: number;
  providentFund: number;
  otherDeductions: number;
  totalDeductions?: number;
  netSalary?: number;
  paymentStatus: 'PENDING' | 'PAID';
  paymentDate?: string;
  remarks: string;
  createdAt?: string;
  updatedAt?: string;
}

