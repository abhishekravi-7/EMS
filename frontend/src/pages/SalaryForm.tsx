import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { salaryService } from '../services/salaryService';

const SalaryForm: React.FC = () => {
  const navigate = useNavigate();
  const [employeeId, setEmployeeId] = useState('');
  const [month, setMonth] = useState('');
  const [year, setYear] = useState('');
  const [baseSalary, setBaseSalary] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await salaryService.addSalary({
        employeeId: Number(employeeId),
        salaryMonth: Number(month),
        salaryYear: Number(year),
        baseSalary: Number(baseSalary),
        dearnessAllowance: 0,
        houseRentAllowance: 0,
        otherAllowances: 0,
        incomeTax: 0,
        providentFund: 0,
        otherDeductions: 0,
        paymentStatus: 'PENDING',
        remarks: ''
      });
      navigate('/salary');
    } catch (error) {
      console.error(error);
    }
  };

  return (
    <div className="card" style={{ maxWidth: '600px', margin: '0 auto', padding: '30px' }}>
      <h2>Add Salary Record</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Employee ID</label>
          <input type="number" className="form-control" value={employeeId} onChange={e => setEmployeeId(e.target.value)} required />
        </div>
        <div className="form-group">
          <label>Month (1-12)</label>
          <input type="number" className="form-control" min="1" max="12" value={month} onChange={e => setMonth(e.target.value)} required />
        </div>
        <div className="form-group">
          <label>Year</label>
          <input type="number" className="form-control" value={year} onChange={e => setYear(e.target.value)} required />
        </div>
        <div className="form-group">
          <label>Base Salary</label>
          <input type="number" className="form-control" value={baseSalary} onChange={e => setBaseSalary(e.target.value)} required />
        </div>
        <button type="submit" className="btn btn-primary" style={{ marginTop: '20px' }}>Submit</button>
      </form>
    </div>
  );
};

export default SalaryForm;

