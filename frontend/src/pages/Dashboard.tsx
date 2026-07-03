import React from 'react';

const Dashboard = () => {
  return (
    <div>
      <h1 className="page-title">Business Overview</h1>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem' }}>
        <div className="card">
          <h3 style={{ color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Monthly Cashflow</h3>
          <p style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--accent)' }}>+ ₹1,45,000</p>
        </div>
        <div className="card">
          <h3 style={{ color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Eligible Schemes</h3>
          <p style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--primary)' }}>3 Available</p>
        </div>
        <div className="card">
          <h3 style={{ color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Recent Documents</h3>
          <p style={{ fontSize: '1.25rem', fontWeight: '500' }}>Udyam Certificate (Verified)</p>
        </div>
      </div>
      
      <div className="card" style={{ marginTop: '2rem' }}>
        <h2 style={{ marginBottom: '1rem' }}>Quick Actions</h2>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <button className="btn-primary">Upload Bank Statement</button>
          <button className="btn-primary" style={{ backgroundColor: 'var(--border)' }}>Ask AI Advisor</button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
