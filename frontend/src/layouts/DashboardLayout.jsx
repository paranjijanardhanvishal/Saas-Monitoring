import React from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
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
  ActivitySquare,
  Bell,
  User,
  LogOut
} from 'lucide-react';

const SidebarGroup = ({ title, items }) => (
  <div className="mb-6">
    <h3 className="px-4 text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">{title}</h3>
    <div className="space-y-0.5">
      {items.map((item) => (
        <NavLink
          key={item.name}
          to={item.path}
          end={item.path === '/dashboard'}
          className={({ isActive }) =>
            `flex items-center gap-3 px-4 py-2 rounded-lg transition-colors text-[13px] font-medium ${
              isActive 
                ? 'bg-blue-50 text-blue-600' 
                : 'text-slate-600 hover:bg-slate-100'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <item.icon size={16} className={isActive ? 'text-blue-600' : 'text-slate-400'} />
              {item.name}
            </>
          )}
        </NavLink>
      ))}
    </div>
  </div>
);

const DashboardLayout = () => {
  const location = useLocation();
  
  const overviewItems = [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Risk Posture', path: '/dashboard/risk', icon: Target },
  ];
  
  const monitoringItems = [
    { name: 'Live Activity', path: '/dashboard/activity', icon: Activity },
    { name: 'Sensitive Files', path: '/dashboard/files', icon: FileLock2 },
  ];
  
  const detectionItems = [
    { name: 'Alerts', path: '/dashboard/alerts', icon: AlertTriangle },
    { name: 'Incidents', path: '/dashboard/incidents', icon: ShieldAlert },
    { name: 'UEBA', path: '/dashboard/users', icon: Users },
    { name: 'Investigation', path: '/dashboard/investigation', icon: Search },
  ];

  const systemItems = [
    { name: 'Enforcement', path: '/dashboard/enforcement', icon: ShieldCheck },
    { name: 'System Health', path: '/dashboard/health', icon: ActivitySquare },
  ];

  // Helper to get current page name for breadcrumb
  const getCurrentPageName = () => {
    const path = location.pathname;
    if (path === '/dashboard') return 'Dashboard';
    if (path.includes('risk')) return 'Risk Posture';
    if (path.includes('activity')) return 'Live Activity';
    if (path.includes('files')) return 'Sensitive Files';
    if (path.includes('alerts')) return 'Alerts';
    if (path.includes('incidents')) return 'Incidents';
    if (path.includes('users')) return 'UEBA';
    if (path.includes('investigation')) return 'Investigation';
    if (path.includes('enforcement')) return 'Enforcement';
    if (path.includes('health')) return 'System Health';
    return 'Dashboard';
  };

  return (
    <div className="flex h-screen bg-slate-50 text-slate-800 font-sans overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col z-20">
        <div className="p-5 flex items-center gap-2 border-b border-slate-200 h-16">
          <div className="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center border border-blue-100">
            <ShieldCheck className="text-blue-600" size={20} />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-slate-900">SaaS Security Monitor</h1>
            <p className="text-[10px] text-slate-500 font-medium tracking-wide">ENTERPRISE SOC</p>
          </div>
        </div>
        
        <nav className="flex-1 overflow-y-auto py-5 px-3 custom-scrollbar">
          <SidebarGroup title="Overview" items={overviewItems} />
          <SidebarGroup title="Monitoring" items={monitoringItems} />
          <SidebarGroup title="Detection" items={detectionItems} />
          <SidebarGroup title="System" items={systemItems} />
        </nav>
        
        <div className="p-4 border-t border-slate-200">
          <div className="flex items-center gap-3 px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer transition">
            <LogOut size={16} />
            <span className="font-medium">Sign out</span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative">
        
        {/* Topbar */}
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 z-10 shrink-0">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-800">{getCurrentPageName()}</h2>
            <span className="text-slate-400">·</span>
            <span className="text-sm text-slate-500">Security Operations Center</span>
          </div>
          
          <div className="flex items-center gap-6">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
              <input 
                type="text" 
                placeholder="Search alerts, hosts, IPs..." 
                className="pl-9 pr-4 py-1.5 bg-slate-50 border border-slate-200 rounded-md text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 w-64"
              />
            </div>
            
            <div className="flex items-center gap-3 border-l border-slate-200 pl-6">
              <button className="text-slate-400 hover:text-slate-600">
                <Bell size={18} />
              </button>
              <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-full cursor-pointer">
                <User size={14} className="text-slate-600" />
                <span className="text-xs font-medium text-slate-700">admin-user</span>
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-6 relative z-0 custom-scrollbar">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default DashboardLayout;
