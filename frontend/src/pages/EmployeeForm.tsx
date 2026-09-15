import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { employeeService } from '../services/employeeService';
import type { Employee } from '../types';

const EmployeeForm: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<Partial<Employee>>({
    employeeId: '',
    firstName: '',
    lastName: '',
    email: '',
    phoneNumber: '',
    department: '',
    designation: '',
    dateOfJoining: '',
    status: 'ACTIVE',
    address: '',
    dateOfBirth: '',
    gender: 'MALE'
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await employeeService.create(formData);
      navigate('/employees');
    } catch (error) {
      console.error("Error creating employee", error);
      alert("Failed to create employee");
    }
  };

  return (
    <div className="card">
      <div className="page-header">
        <h2>Add New Employee</h2>
        <button className="btn" onClick={() => navigate('/employees')}>Cancel</button>
      </div>
      
      <form onSubmit={handleSubmit}>
        <div className="dashboard-grid" style={{ marginBottom: '20px' }}>
          <div className="form-group">
            <label>Employee ID</label>
            <input name="employeeId" className="form-control" onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>First Name</label>
            <input name="firstName" className="form-control" onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Last Name</label>
            <input name="lastName" className="form-control" onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Email</label>
            <input type="email" name="email" className="form-control" onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Phone Number</label>
            <input name="phoneNumber" className="form-control" onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Department</label>
            <input name="department" className="form-control" onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Designation</label>
            <input name="designation" className="form-control" onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Date of Joining</label>
            <input type="date" name="dateOfJoining" className="form-control" onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Date of Birth</label>
            <input type="date" name="dateOfBirth" className="form-control" onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Gender</label>
            <select name="gender" className="form-control" onChange={handleChange}>
              <option value="MALE">Male</option>
              <option value="FEMALE">Female</option>
              <option value="OTHER">Other</option>
            </select>
          </div>
        </div>
        
        <div className="form-group">
          <label>Address</label>
          <input name="address" className="form-control" onChange={handleChange} required />
        </div>

        <button type="submit" className="btn btn-primary">Save Employee</button>
      </form>
    </div>
  );
};

export default EmployeeForm;

