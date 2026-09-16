import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Activity, 
  AlertTriangle, 
  ShieldAlert, 
  Users, 
  FileLock2, 
  Target, 
  Search, 
  ShieldCheck, 
  Settings, 
  ActivitySquare
} from 'lucide-react';

const DashboardLayout = () => {
  const navItems = [
    { name: 'SOC Overview', path: '/', icon: LayoutDashboard },
    { name: 'Live Activity', path: '/activity', icon: Activity },
    { name: 'Alerts', path: '/alerts', icon: AlertTriangle },
    { name: 'Incidents', path: '/incidents', icon: ShieldAlert },
    { name: 'Users / UEBA', path: '/users', icon: Users },
    { name: 'Sensitive Files', path: '/files', icon: FileLock2 },
    { name: 'Risk Posture', path: '/risk', icon: Target },
    { name: 'Investigation', path: '/investigation', icon: Search },
    { name: 'Enforcement', path: '/enforcement', icon: ShieldCheck },
    { name: 'System Health', path: '/health', icon: ActivitySquare },
  ];

  return (
    <div className="flex h-screen bg-[#0a0a0a] text-gray-100 font-sans overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-[#121212] border-r border-[#262626] flex flex-col">
        <div className="p-6 flex items-center gap-3 border-b border-[#262626]">
          <ShieldAlert className="text-emerald-500" size={28} />
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white">SaaS Monitor</h1>
            <p className="text-xs text-gray-400 font-medium tracking-wide">ENTERPRISE SOC</p>
          </div>
        </div>
        
        <nav className="flex-1 overflow-y-auto py-6 px-3 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.name}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all duration-200 text-sm font-medium ${
                  isActive 
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.1)]' 
                    : 'text-gray-400 hover:text-white hover:bg-[#1e1e1e]'
                }`
              }
            >
              <item.icon size={18} />
              {item.name}
            </NavLink>
          ))}
        </nav>
        
        <div className="p-4 border-t border-[#262626]">
          <div className="flex items-center gap-3 px-4 py-2 text-sm text-gray-400 hover:text-white cursor-pointer transition">
            <Settings size={18} />
            <span>Settings</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Top Header Background Glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-32 bg-emerald-500/5 blur-[100px] pointer-events-none rounded-full" />
        
        <div className="flex-1 overflow-y-auto p-8 relative z-10 custom-scrollbar">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default DashboardLayout;
