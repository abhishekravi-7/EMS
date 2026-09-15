import React, { useEffect, useState } from 'react';
import { attendanceService } from '../services/attendanceService';
import type { Attendance } from '../types';
import Table from '../components/common/Table';
import StatusBadge from '../components/common/StatusBadge';

const AttendanceList: React.FC = () => {
  const [records, setRecords] = useState<Attendance[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAttendance = async () => {
      try {
        const today = new Date();
        const firstDay = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
        const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0];
        
        const data = await attendanceService.getAllRange(firstDay, lastDay);
        setRecords(data);
      } catch (error) {
        console.error("Failed to fetch attendance records", error);
      } finally {
        setLoading(false);
      }
    };
    fetchAttendance();
  }, []);

  const columns = [
    { 
      header: 'Employee', 
      accessor: (row: Attendance) => `${row.employee.firstName} ${row.employee.lastName} (${row.employee.employeeId})` 
    },
    { header: 'Date', accessor: 'attendanceDate' as keyof Attendance },
    { 
      header: 'Status', 
      accessor: (row: Attendance) => <StatusBadge status={row.status} /> 
    },
    { header: 'Check In', accessor: 'checkInTime' as keyof Attendance },
    { header: 'Check Out', accessor: 'checkOutTime' as keyof Attendance },
  ];

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Attendance Log</h2>
        <a href="/attendance/new" className="btn btn-primary">Mark Attendance</a>
      </div>
      
      {loading ? (
        <div>Loading attendance...</div>
      ) : (
        <Table<Attendance> 
          data={records} 
          columns={columns} 
          keyExtractor={(row) => row.id} 
        />
      )}
    </div>
  );
};

export default AttendanceList;
