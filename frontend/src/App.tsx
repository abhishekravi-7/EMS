import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import EmployeeList from './pages/EmployeeList';
import EmployeeForm from './pages/EmployeeForm';
import AttendanceList from './pages/AttendanceList';
import SalaryList from './pages/SalaryList';
import Login from './pages/Login';

import AttendanceForm from './pages/AttendanceForm';
import SalaryForm from './pages/SalaryForm';
import LeaveList from './pages/LeaveList';
import LeaveForm from './pages/LeaveForm';

const App: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);

  useEffect(() => {
    const auth = localStorage.getItem('isAuthenticated');
    if (auth === 'true') {
      setIsAuthenticated(true);
    }
  }, []);

  if (!isAuthenticated) {
    return <Login onLogin={setIsAuthenticated} />;
  }

  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout onLogout={() => setIsAuthenticated(false)} />}>
          <Route index element={<Dashboard />} />
          <Route path="employees" element={<EmployeeList />} />
          <Route path="employees/new" element={<EmployeeForm />} />
          <Route path="attendance" element={<AttendanceList />} />
          <Route path="attendance/new" element={<AttendanceForm />} />
          <Route path="leaves" element={<LeaveList />} />
          <Route path="leaves/new" element={<LeaveForm />} />
          <Route path="salary" element={<SalaryList />} />
          <Route path="salary/new" element={<SalaryForm />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
};

export default App;
