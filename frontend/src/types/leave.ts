export interface Leave {
  id: number;
  employee: Employee;
  startDate: string;
  endDate: string;
  leaveType: 'SICK' | 'CASUAL' | 'EARNED';
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  reason: string;
  days: number;
  createdAt?: string;
  updatedAt?: string;
}

