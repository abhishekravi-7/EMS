import React from 'react';
import { NavLink } from 'react-router-dom';
import { FiHome, FiUsers, FiCalendar, FiDollarSign } from 'react-icons/fi';

const Sidebar: React.FC = () => {
  const navItems = [
    { name: 'Dashboard', path: '/', icon: <FiHome /> },
    { name: 'Employees', path: '/employees', icon: <FiUsers /> },
    { name: 'Attendance', path: '/attendance', icon: <FiCalendar /> },
    { name: 'Salary', path: '/salary', icon: <FiDollarSign /> },
  ];

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        EMS Admin
      </div>
      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.name}
            to={item.path}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            {item.icon}
            <span>{item.name}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
};

export default Sidebar;
