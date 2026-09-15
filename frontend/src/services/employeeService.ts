import api from './api';
import type { Employee } from '../types';

export const employeeService = {
  getAll: async () => {
    const response = await api.get<Employee[]>('/employees');
    return response.data;
  },
  
  getById: async (id: number) => {
    const response = await api.get<Employee>(`/employees/${id}`);
    return response.data;
  },

  getByEmployeeId: async (employeeId: string) => {
    const response = await api.get<Employee>(`/employees/emp/${employeeId}`);
    return response.data;
  },

  create: async (employee: Partial<Employee>) => {
    const response = await api.post<Employee>('/employees', employee);
    return response.data;
  },

  update: async (id: number, employee: Partial<Employee>) => {
    const response = await api.put<Employee>(`/employees/${id}`, employee);
    return response.data;
  },

  updateStatus: async (id: number, status: string) => {
    const response = await api.patch<Employee>(`/employees/${id}/status`, null, { params: { status } });
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/employees/${id}`);
  },

  getActiveCount: async () => {
    const response = await api.get<number>('/employees/stats/active-count');
    return response.data;
  }
};

