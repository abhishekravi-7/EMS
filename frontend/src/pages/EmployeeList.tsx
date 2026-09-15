import React, { useEffect, useState } from 'react';
import { employeeService } from '../services/employeeService';
import type { Employee } from '../types';
import Table from '../components/common/Table';
import StatusBadge from '../components/common/StatusBadge';
import { FiPlus, FiEdit2, FiTrash2, FiEye } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';

const EmployeeList: React.FC = () => {
  const navigate = useNavigate();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchEmployees = async () => {
    try {
      const data = await employeeService.getAll();
      setEmployees(data);
    } catch (error) {
      console.error("Failed to fetch employees", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmployees();
  }, []);

  const handleDelete = async (id: number) => {
    if (window.confirm("Are you sure you want to delete this employee?")) {
      await employeeService.delete(id);
      fetchEmployees();
    }
  };

  const columns = [
    { header: 'Emp ID', accessor: 'employeeId' as keyof Employee },
    { 
      header: 'Name', 
      accessor: (row: Employee) => `${row.firstName} ${row.lastName}` 
    },
    { header: 'Department', accessor: 'department' as keyof Employee },
    { header: 'Designation', accessor: 'designation' as keyof Employee },
    { 
      header: 'Status', 
      accessor: (row: Employee) => <StatusBadge status={row.status} /> 
    },
    {
      header: 'Actions',
      accessor: (row: Employee) => (
        <div style={{ display: 'flex', gap: '10px' }}>
          <button style={{ color: '#3498db', border: 'none', background: 'none', cursor: 'pointer' }}><FiEye size={18} /></button>
          <button style={{ color: '#2ecc71', border: 'none', background: 'none', cursor: 'pointer' }}><FiEdit2 size={18} /></button>
          <button onClick={() => handleDelete(row.id)} style={{ color: '#e74c3c', border: 'none', background: 'none', cursor: 'pointer' }}><FiTrash2 size={18} /></button>
        </div>
      )
    }
  ];

  if (loading) return <div>Loading employees...</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Employees</h2>
        <button className="btn btn-primary" onClick={() => navigate('/employees/new')}>
          <FiPlus />
          <span>Add Employee</span>
        </button>
      </div>

      <Table<Employee> 
        data={employees} 
        columns={columns} 
        keyExtractor={(row) => row.id} 
      />
    </div>
  );
};

export default EmployeeList;
