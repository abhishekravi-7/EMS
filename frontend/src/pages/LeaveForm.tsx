import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { leaveService } from '../services/leaveService';

const LeaveForm: React.FC = () => {
  const navigate = useNavigate();
  const [employeeId, setEmployeeId] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [leaveType, setLeaveType] = useState('CASUAL');
  const [reason, setReason] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await leaveService.applyLeave({
        employeeId: Number(employeeId),
        startDate,
        endDate,
        leaveType,
        reason
      });
      navigate('/leaves');
    } catch (error) {
      console.error(error);
      alert('Failed to apply leave. Check dates and conflicts.');
    }
  };

  return (
    <div className="card" style={{ maxWidth: '600px', margin: '0 auto', padding: '30px' }}>
      <h2>Apply for Leave</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Employee ID</label>
          <input type="number" className="form-control" value={employeeId} onChange={e => setEmployeeId(e.target.value)} required />
        </div>
        <div className="form-group">
          <label>Start Date</label>
          <input type="date" className="form-control" value={startDate} onChange={e => setStartDate(e.target.value)} required />
        </div>
        <div className="form-group">
          <label>End Date</label>
          <input type="date" className="form-control" value={endDate} onChange={e => setEndDate(e.target.value)} required />
        </div>
        <div className="form-group">
          <label>Leave Type</label>
          <select className="form-control" value={leaveType} onChange={e => setLeaveType(e.target.value)}>
            <option value="SICK">Sick Leave</option>
            <option value="CASUAL">Casual Leave</option>
            <option value="EARNED">Earned Leave</option>
          </select>
        </div>
        <div className="form-group">
          <label>Reason</label>
          <textarea className="form-control" value={reason} onChange={e => setReason(e.target.value)} required rows={3}></textarea>
        </div>
        <button type="submit" className="btn btn-primary" style={{ marginTop: '20px' }}>Submit Application</button>
      </form>
    </div>
  );
};

export default LeaveForm;

