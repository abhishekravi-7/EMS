import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { attendanceService } from '../services/attendanceService';

const AttendanceForm: React.FC = () => {
  const navigate = useNavigate();
  const [employeeId, setEmployeeId] = useState('');
  const [date, setDate] = useState('');
  const [status, setStatus] = useState('PRESENT');
  const [checkIn, setCheckIn] = useState('');
  const [checkOut, setCheckOut] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await attendanceService.markAttendance({
        employeeId: Number(employeeId),
        attendanceDate: date,
        status,
        checkInTime: checkIn,
        checkOutTime: checkOut,
        remarks: ''
      });
      navigate('/attendance');
    } catch (error) {
      console.error(error);
    }
  };

  return (
    <div className="card" style={{ maxWidth: '600px', margin: '0 auto', padding: '30px' }}>
      <h2>Mark Attendance</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Employee ID</label>
          <input type="number" className="form-control" value={employeeId} onChange={e => setEmployeeId(e.target.value)} required />
        </div>
        <div className="form-group">
          <label>Date</label>
          <input type="date" className="form-control" value={date} onChange={e => setDate(e.target.value)} required />
        </div>
        <div className="form-group">
          <label>Status</label>
          <select className="form-control" value={status} onChange={e => setStatus(e.target.value)}>
            <option value="PRESENT">Present</option>
            <option value="ABSENT">Absent</option>
            <option value="LATE">Late</option>
          </select>
        </div>
        <div className="form-group">
          <label>Check In</label>
          <input type="time" className="form-control" value={checkIn} onChange={e => setCheckIn(e.target.value)} />
        </div>
        <div className="form-group">
          <label>Check Out</label>
          <input type="time" className="form-control" value={checkOut} onChange={e => setCheckOut(e.target.value)} />
        </div>
        <button type="submit" className="btn btn-primary" style={{ marginTop: '20px' }}>Submit</button>
      </form>
    </div>
  );
};

export default AttendanceForm;

