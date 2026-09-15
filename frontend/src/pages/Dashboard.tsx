import React, { useEffect, useState } from 'react';
import { employeeService } from '../services/employeeService';
import { salaryService } from '../services/salaryService';
import { FiUsers, FiDollarSign } from 'react-icons/fi';

const Dashboard: React.FC = () => {
  const [activeCount, setActiveCount] = useState<number>(0);
  const [totalPaid, setTotalPaid] = useState<number>(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [employeesCount, paidSalaries] = await Promise.all([
          employeeService.getActiveCount(),
          salaryService.getTotalPaid()
        ]);
        setActiveCount(employeesCount);
        setTotalPaid(paidSalaries);
      } catch (error) {
        console.error("Error fetching dashboard data", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) return <div>Loading dashboard...</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Dashboard Overview</h2>
      </div>
      
      <div className="dashboard-grid">
        <div className="card stat-card">
          <div className="stat-icon">
            <FiUsers />
          </div>
          <div>
            <div style={{ color: '#7f8c8d', fontSize: '14px' }}>Active Employees</div>
            <div className="stat-value">{activeCount}</div>
          </div>
        </div>

        <div className="card stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#e9f7ef', color: '#2ecc71' }}>
            <FiDollarSign />
          </div>
          <div>
            <div style={{ color: '#7f8c8d', fontSize: '14px' }}>Total Paid Salaries</div>
            <div className="stat-value">${totalPaid?.toLocaleString() || 0}</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
