import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import DashboardLayout from './layouts/DashboardLayout';

// Pages
import Landing from './pages/Landing';
import Overview from './pages/Overview';
import LiveActivity from './pages/LiveActivity';
import Alerts from './pages/Alerts';
import Incidents from './pages/Incidents';
import Users from './pages/Users';
import SensitiveFiles from './pages/SensitiveFiles';
import RiskPosture from './pages/RiskPosture';
import Investigation from './pages/Investigation';
import Enforcement from './pages/Enforcement';
import SystemHealth from './pages/SystemHealth';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        
        <Route path="/dashboard" element={<DashboardLayout />}>
          <Route index element={<Overview />} />
          <Route path="activity" element={<LiveActivity />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="incidents" element={<Incidents />} />
          <Route path="users" element={<Users />} />
          <Route path="files" element={<SensitiveFiles />} />
          <Route path="risk" element={<RiskPosture />} />
          <Route path="investigation" element={<Investigation />} />
          <Route path="enforcement" element={<Enforcement />} />
          <Route path="health" element={<SystemHealth />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
