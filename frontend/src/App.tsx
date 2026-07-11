import { Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import DocumentHub from './pages/DocumentHub';
import AIAdvisor from './pages/AIAdvisor';
import SchemeMatcher from './pages/SchemeMatcher';
import './App.css';

function App() {
  return (
    <div className="app-container">
      <nav className="sidebar">
        <div className="brand">
          <h2>BizCom AI</h2>
        </div>
        <ul className="nav-links">
          <li><Link to="/">Dashboard</Link></li>
          <li><Link to="/documents">Document Hub</Link></li>
          <li><Link to="/advisor">AI Advisor</Link></li>
          <li><Link to="/schemes">Scheme Matcher</Link></li>
        </ul>
      </nav>
      
      <main className="main-content">
        <header className="topbar">
          <div className="user-profile">
            <span>Welcome, MSME Owner</span>
          </div>
        </header>
        <div className="page-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/documents" element={<DocumentHub />} />
            <Route path="/advisor" element={<AIAdvisor />} />
            <Route path="/schemes" element={<SchemeMatcher />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

export default App;
