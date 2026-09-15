import api from './api';
import type { Salary } from '../types';

export const salaryService = {
  addSalary: async (data: any) => {
    const response = await api.post<Salary>('/salary', data);
    return response.data;
  },
  
  getById: async (id: number) => {
    const response = await api.get<Salary>(`/salary/${id}`);
    return response.data;
  },

  getForEmployee: async (employeeId: number) => {
    const response = await api.get<Salary[]>(`/salary/employee/${employeeId}`);
    return response.data;
  },

  getPending: async () => {
    const response = await api.get<Salary[]>('/salary/pending');
    return response.data;
  },

  getPaid: async () => {
    const response = await api.get<Salary[]>('/salary/paid');
    return response.data;
  },

  update: async (id: number, data: any) => {
    const response = await api.put<Salary>(`/salary/${id}`, data);
    return response.data;
  },

  processPayment: async (id: number) => {
    const response = await api.patch<Salary>(`/salary/${id}/pay`);
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/salary/${id}`);
  },

  getTotalPaid: async () => {
    const response = await api.get<number>('/salary/stats/total-paid');
    return response.data;
  }
};

