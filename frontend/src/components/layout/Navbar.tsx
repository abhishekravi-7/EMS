import React from 'react';

import { FiLogOut } from 'react-icons/fi';

interface NavbarProps {
  onLogout: () => void;
}

const Navbar: React.FC<NavbarProps> = ({ onLogout }) => {
  const handleLogout = () => {
    localStorage.removeItem('isAuthenticated');
    onLogout();
  };

  return (
    <header className="navbar">
      <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>
        Employee Management System
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        <button 
          onClick={handleLogout}
          style={{ display: 'flex', alignItems: 'center', gap: '5px', background: 'none', border: 'none', cursor: 'pointer', color: '#e74c3c', fontWeight: 'bold' }}
        >
          <FiLogOut /> Logout
        </button>
        <div style={{
          width: '35px', height: '35px', backgroundColor: '#3498db', color: 'white',
          borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold'
        }}>
          A
        </div>
      </div>
    </header>
  );
};

export default Navbar;
