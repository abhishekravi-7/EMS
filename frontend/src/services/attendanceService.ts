import api from './api';
import type { Attendance, AttendanceSummary } from '../types';

export const attendanceService = {
  markAttendance: async (data: any) => {
    const response = await api.post<Attendance>('/attendance', data);
    return response.data;
  },
  
  getById: async (id: number) => {
    const response = await api.get<Attendance>(`/attendance/${id}`);
    return response.data;
  },

  getForEmployee: async (employeeId: number) => {
    const response = await api.get<Attendance[]>(`/attendance/employee/${employeeId}`);
    return response.data;
  },

  getAllRange: async (startDate: string, endDate: string) => {
    const response = await api.get<Attendance[]>('/attendance/range', { params: { startDate, endDate } });
    return response.data;
  },

  update: async (id: number, data: any) => {
    const response = await api.put<Attendance>(`/attendance/${id}`, data);
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/attendance/${id}`);
  },

  getSummary: async (employeeId: number, startDate: string, endDate: string) => {
    const response = await api.get<AttendanceSummary>(`/attendance/employee/${employeeId}/summary`, { params: { startDate, endDate } });
    return response.data;
  }
};

