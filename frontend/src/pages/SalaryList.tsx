import React, { useEffect, useState } from 'react';
import { salaryService } from '../services/salaryService';
import type { Salary } from '../types';
import Table from '../components/common/Table';
import StatusBadge from '../components/common/StatusBadge';
import { FiCheckCircle } from 'react-icons/fi';

const SalaryList: React.FC = () => {
  const [salaries, setSalaries] = useState<Salary[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'ALL' | 'PENDING' | 'PAID'>('ALL');

  const fetchSalaries = async () => {
    setLoading(true);
    try {
      let data: Salary[] = [];
      if (filter === 'PENDING') {
        data = await salaryService.getPending();
      } else if (filter === 'PAID') {
        data = await salaryService.getPaid();
      } else {
        const [pending, paid] = await Promise.all([
          salaryService.getPending(),
          salaryService.getPaid()
        ]);
        data = [...pending, ...paid];
      }
      setSalaries(data);
    } catch (error) {
      console.error("Failed to fetch salaries", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSalaries();
  }, [filter]);

  const handleProcessPayment = async (id: number) => {
    if (window.confirm("Process this payment?")) {
      await salaryService.processPayment(id);
      fetchSalaries();
    }
  };

  const columns = [
    { 
      header: 'Employee', 
      accessor: (row: Salary) => `${row.employee.firstName} ${row.employee.lastName} (${row.employee.employeeId})` 
    },
    { 
      header: 'Period', 
      accessor: (row: Salary) => `${row.salaryMonth}/${row.salaryYear}` 
    },
    { header: 'Net Salary', accessor: (row: Salary) => `$${row.netSalary?.toFixed(2) || 0}` },
    { 
      header: 'Status', 
      accessor: (row: Salary) => <StatusBadge status={row.status || row.paymentStatus} /> 
    },
    {
      header: 'Actions',
      accessor: (row: Salary) => (
        row.paymentStatus === 'PENDING' ? (
          <button 
            onClick={() => handleProcessPayment(row.id)}
            style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#2ecc71', border: 'none', background: 'none', cursor: 'pointer' }}
          >
            <FiCheckCircle />
            <span>Process Payment</span>
          </button>
        ) : (
          <span style={{ color: '#bdc3c7', fontSize: '14px' }}>Paid</span>
        )
      )
    }
  ];

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Salary Records</h2>
        <a href="/salary/new" className="btn btn-primary">Add Salary</a>
      </div>
      <div style={{ display: 'flex', gap: '10px' }}>
          {['ALL', 'PENDING', 'PAID'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f as any)}
              style={{
                padding: '6px 12px',
                borderRadius: '16px',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 'bold',
                backgroundColor: filter === f ? '#3498db' : '#e0e0e0',
                color: filter === f ? 'white' : '#333'
              }}
            >
              {f}
            </button>
          ))}
        </div>

      {loading ? (
        <div>Loading salaries...</div>
      ) : (
        <Table<Salary> 
          data={salaries} 
          columns={columns} 
          keyExtractor={(row) => row.id} 
        />
      )}
    </div>
  );
};

export default SalaryList;
