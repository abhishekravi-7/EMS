import api from './api';

export const leaveService = {
  getAll: async () => {
    const response = await api.get('/leaves');
    return response.data;
  },
  applyLeave: async (data: any) => {
    const response = await api.post('/leaves', data);
    return response.data;
  }
};

