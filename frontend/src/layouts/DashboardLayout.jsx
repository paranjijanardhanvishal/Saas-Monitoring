import React, { useEffect, useMemo, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Activity,
  Bell,
  BrainCircuit,
  ChevronRight,
  FileLock2,
  Gavel,
  HeartPulse,
  LayoutDashboard,
  LogOut,
  Menu,
  Search,
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
  Target,
  Users,
  X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Badge, consentTone, cx } from '../components/ui';

const NAV_GROUPS = [
  {
    label: 'Overview',
    items: [
      { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
      { name: 'Risk Posture', path: '/risk-posture', icon: Target },
      { name: 'Live Activity', path: '/live-activity', icon: Activity },
    ],
  },
  {
    label: 'Identity & behaviour',
    items: [
      { name: 'Users', path: '/users', icon: Users, adminOnly: true },
      { name: 'UEBA', path: '/ueba', icon: BrainCircuit },
      { name: 'Investigation', path: '/investigation', icon: Search, adminOnly: true },
    ],
  },
  {
    label: 'Data protection',
    items: [{ name: 'Sensitive Files', path: '/sensitive-files', icon: FileLock2 }],
  },
  {
    label: 'Response',
    items: [
      { name: 'Alerts', path: '/alerts', icon: Bell },
      { name: 'Incidents', path: '/incidents', icon: ShieldAlert },
      { name: 'Enforcement', path: '/enforcement', icon: Gavel, adminOnly: true },
    ],
  },
  {
    label: 'Operations',
    items: [{ name: 'System Health', path: '/system-health', icon: HeartPulse, adminOnly: true }],
  },
];

export default function DashboardLayout() {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const groups = useMemo(
    () =>
      NAV_GROUPS.map((group) => ({
        ...group,
        items: group.items.filter((item) => !item.adminOnly || isAdmin),
      })).filter((group) => group.items.length > 0),
    [isAdmin],
  );

  const flatItems = useMemo(() => groups.flatMap((group) => group.items), [groups]);
  const activeItem = flatItems.find(
    (item) => location.pathname === item.path || location.pathname.startsWith(`${item.path}/`),
  );

  if (!user) return null;

  const consentState = user.monitoring_enabled;
  const monitoringPaused = user.role === 'USER' && consentState !== 'ALLOWED';

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex h-16 shrink-0 items-center gap-3 border-b border-slate-800 px-5">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-400">
          <ShieldCheck size={19} />
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-bold tracking-tight text-white">SaaS Security Monitor</p>
          <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">SOC console</p>
        </div>
        <button
          type="button"
          className="ml-auto rounded-md p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-label="Close navigation"
        >
          <X size={18} />
        </button>
      </div>

      <nav className="custom-scrollbar flex-1 overflow-y-auto px-3 py-4">
        {groups.map((group) => (
          <div key={group.label} className="mb-5">
            <p className="mb-1.5 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-600">
              {group.label}
            </p>
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    className={({ isActive }) =>
                      cx(
                        'group flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition',
                        isActive
                          ? 'bg-blue-500/10 text-blue-300 ring-1 ring-inset ring-blue-500/20'
                          : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-100',
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon size={16} className={isActive ? 'text-blue-400' : 'text-slate-500 group-hover:text-slate-300'} />
                        <span className="truncate">{item.name}</span>
                        {isActive ? <ChevronRight size={13} className="ml-auto text-blue-400/70" /> : null}
                      </>
                    )}
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="shrink-0 border-t border-slate-800 p-3">
        <Link
          to="/consent"
          className="mb-2 flex items-center justify-between gap-2 rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2 text-xs text-slate-400 transition hover:border-slate-700 hover:text-slate-200"
        >
          <span className="flex items-center gap-2">
            {consentState === 'ALLOWED' ? (
              <ShieldCheck size={14} className="text-emerald-400" />
            ) : (
              <ShieldOff size={14} className="text-amber-400" />
            )}
            Privacy &amp; consent
          </span>
          <Badge tone={consentTone(consentState)}>{consentState.replace('_', ' ')}</Badge>
        </Link>
        <div className="flex items-center gap-2 rounded-lg px-2 py-1.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-slate-700 bg-slate-800 text-xs font-bold text-slate-300">
            {(user.display_name || user.user_id || '?').slice(0, 2).toUpperCase()}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-slate-200">
              {user.display_name || user.user_id}
            </p>
            <p className="truncate text-[10px] text-slate-500">{user.email || user.user_id}</p>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="rounded-md p-2 text-slate-500 transition hover:bg-slate-800 hover:text-red-300"
            title="Sign out"
            aria-label="Sign out"
          >
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen overflow-hidden bg-[#0b0f19] text-slate-200">
      <aside className="hidden w-64 shrink-0 border-r border-slate-800 bg-[#0a0f1a] lg:block">
        {sidebar}
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
            className="absolute inset-0 bg-black/60"
          />
          <aside className="relative h-full w-72 border-r border-slate-800 bg-[#0a0f1a] shadow-2xl">
            {sidebar}
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-slate-800 bg-[#0d1320]/90 px-4 backdrop-blur sm:px-6">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="rounded-md p-2 text-slate-400 hover:bg-slate-800 hover:text-white lg:hidden"
            aria-label="Open navigation"
          >
            <Menu size={19} />
          </button>

          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-white">
              {activeItem?.name || 'Security console'}
            </p>
            <p className="hidden text-[11px] text-slate-500 sm:block">
              {isAdmin ? 'Administrator scope: all monitored users' : 'Your authorised data only'}
            </p>
          </div>

          <div className="ml-auto flex items-center gap-2">
            {user.enforcement_status === 'RESTRICTED' ? (
              <Badge tone="red">Account restricted</Badge>
            ) : null}
            <Badge tone={isAdmin ? 'blue' : 'neutral'}>{user.role}</Badge>
            <Badge tone={consentTone(consentState)} className="hidden sm:inline-flex">
              {consentState.replace('_', ' ')}
            </Badge>
          </div>
        </header>

        {monitoringPaused ? (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-amber-900/40 bg-amber-950/20 px-4 py-2.5 text-xs text-amber-200 sm:px-6">
            <ShieldOff size={14} className="shrink-0 text-amber-400" />
            <span>
              Endpoint monitoring is <strong>paused</strong> because consent is{' '}
              {consentState.replace('_', ' ')}. The backend rejects endpoint events until you allow
              monitoring.
            </span>
            <Link to="/consent" className="font-semibold text-amber-100 underline underline-offset-2 hover:text-white">
              Review consent
            </Link>
          </div>
        ) : null}

        <main className="custom-scrollbar flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1500px] p-4 sm:p-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
