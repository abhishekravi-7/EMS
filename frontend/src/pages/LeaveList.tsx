import React, { useEffect, useState } from 'react';
import { leaveService } from '../services/leaveService';
import Table from '../components/common/Table';
import StatusBadge from '../components/common/StatusBadge';

const LeaveList: React.FC = () => {
  const [records, setRecords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchLeaves = async () => {
      try {
        const data = await leaveService.getAll();
        setRecords(data);
      } catch (error) {
        console.error("Failed to fetch leave records", error);
      } finally {
        setLoading(false);
      }
    };
    fetchLeaves();
  }, []);

  const columns = [
    { 
      header: 'Employee', 
      accessor: (row: any) => row.employeeName || `EMP-${row.employeeId}`
    },
    { header: 'Start Date', accessor: 'startDate' },
    { header: 'End Date', accessor: 'endDate' },
    { header: 'Type', accessor: 'leaveType' },
    { header: 'Days', accessor: 'days' },
    { 
      header: 'Status', 
      accessor: (row: any) => <StatusBadge status={row.status} /> 
    },
  ];

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Leave Applications</h2>
        <a href="/leaves/new" className="btn btn-primary">Apply Leave</a>
      </div>
      
      {loading ? (
        <div>Loading leave records...</div>
      ) : (
        <Table<any> 
          data={records} 
          columns={columns} 
          keyExtractor={(row) => row.id} 
        />
      )}
    </div>
  );
};

export default LeaveList;

