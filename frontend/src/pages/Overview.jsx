import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  Bell,
  Clock3,
  Database,
  Laptop,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Target,
  Users,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { errorMessage, getDashboardOverview } from '../api';
import {
  Badge,
  EmptyState,
  ErrorState,
  formatDateTime,
  formatNumber,
  formatScore,
  LoadingState,
  PageHeader,
  Panel,
  severityTone,
  StatCard,
  statusTone,
  timeAgo,
} from '../components/ui';

const SEVERITY_COLORS = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#f59e0b',
  LOW: '#10b981',
};

const RISK_COLORS = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#f59e0b',
  LOW: '#10b981',
};

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-700 bg-[#111827] px-3 py-2 text-xs shadow-xl">
      <p className="font-semibold text-slate-200">{label}</p>
      {payload.map((entry) => (
        <p key={entry.dataKey || entry.name} className="mt-0.5 text-slate-400">
          {entry.name}: <span className="font-semibold text-slate-100">{entry.value}</span>
        </p>
      ))}
    </div>
  );
}

export default function Overview() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const mounted = useRef(true);

  const load = useCallback(async ({ silent = false } = {}) => {
    if (silent) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const result = await getDashboardOverview();
      if (mounted.current) setData(result);
    } catch (err) {
      if (mounted.current) setError(errorMessage(err, 'Could not load dashboard overview.'));
    } finally {
      if (mounted.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    load();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') load({ silent: true });
    }, 20000);
    return () => {
      mounted.current = false;
      window.clearInterval(timer);
    };
  }, [load]);

  const hourly = useMemo(
    () =>
      (data?.events?.by_hour || []).map((row) => ({
        hour: row.hour?.slice(11, 16) || row.hour,
        events: row.count,
      })),
    [data],
  );

  const severityData = useMemo(
    () =>
      Object.entries(data?.alerts?.by_severity || {})
        .filter(([, count]) => Number(count) > 0)
        .map(([name, value]) => ({ name, value })),
    [data],
  );

  const riskData = useMemo(
    () =>
      Object.entries(data?.risk?.by_category || {})
        .filter(([, count]) => Number(count) > 0)
        .map(([name, value]) => ({ name, value })),
    [data],
  );

  const latestRisk = data?.risk?.latest;
  const scope = data?.scope;
  const isAdminScope = scope === 'ADMIN';

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Overview"
        title="Security operations dashboard"
        subtitle={
          isAdminScope
            ? 'Live aggregates across all monitored users, endpoints and SaaS activity.'
            : 'Live aggregates for your authorised account only. Administrators see the organisation-wide view.'
        }
        actions={
          <>
            {data?.generated_at ? (
              <span className="hidden text-[11px] text-slate-500 sm:inline">
                Updated {formatDateTime(data.generated_at)}
              </span>
            ) : null}
            <button type="button" onClick={() => load({ silent: true })} className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:bg-slate-800 disabled:opacity-50" disabled={refreshing || loading}>
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
              Refresh
            </button>
          </>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Events · 24h" value={formatNumber(data?.events?.last_24h)} hint={`${formatNumber(data?.events?.last_7d)} in the last 7 days`} icon={Activity} tone="blue" loading={loading} />
        <StatCard label="Open alerts" value={formatNumber(data?.alerts?.open)} hint={`${formatNumber(data?.alerts?.last_24h)} raised in 24h`} icon={Bell} tone={data?.alerts?.open ? 'amber' : 'green'} loading={loading} />
        <StatCard label="Open incidents" value={formatNumber(data?.incidents?.open)} hint={`${formatNumber(data?.incidents?.critical_open)} critical`} icon={ShieldAlert} tone={data?.incidents?.critical_open ? 'red' : 'green'} loading={loading} />
        <StatCard label="Active endpoints" value={formatNumber(data?.devices?.active)} hint={`${formatNumber(data?.devices?.stale)} stale · ${formatNumber(data?.devices?.revoked)} revoked`} icon={Laptop} tone={data?.devices?.stale ? 'amber' : 'green'} loading={loading} />
      </div>

      {isAdminScope ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Users in directory" value={formatNumber(data?.users?.total)} hint="Includes administrators" icon={Users} tone="neutral" loading={loading} />
          <StatCard label="Consented users" value={formatNumber(data?.users?.consented)} hint="ALLOWED monitoring" icon={ShieldCheck} tone="green" loading={loading} />
          <StatCard label="Awaiting consent" value={formatNumber(data?.users?.pending_consent)} hint="NOT_ASKED" icon={Clock3} tone="amber" loading={loading} />
          <StatCard label="Declined / revoked" value={formatNumber(data?.users?.declined_or_revoked)} hint="Monitoring disabled" icon={ShieldAlert} tone="orange" loading={loading} />
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel
          title="Event volume · last 24 hours"
          subtitle="Hourly count from the events collection"
          className="xl:col-span-2"
          bodyClassName="pt-5"
        >
          {loading && !data ? (
            <LoadingState />
          ) : hourly.length === 0 ? (
            <EmptyState icon={Activity} title="No events in the last 24 hours" message="Events appear after authorised endpoint agents or the SaaS proxy ingest activity." />
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={hourly} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="eventFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                  <XAxis dataKey="hour" stroke="#475569" fontSize={10} tickLine={false} axisLine={false} />
                  <YAxis stroke="#475569" fontSize={10} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area type="monotone" dataKey="events" name="Events" stroke="#3b82f6" strokeWidth={2} fill="url(#eventFill)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        <Panel title="Alerts by severity" subtitle="Open alerts only">
          {loading && !data ? (
            <LoadingState />
          ) : severityData.length === 0 ? (
            <EmptyState icon={ShieldCheck} title="No open alerts" message="Severity distribution appears when the risk engine raises alerts." />
          ) : (
            <>
              <div className="h-44 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={severityData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={68} paddingAngle={2} stroke="none">
                      {severityData.map((entry) => (
                        <Cell key={entry.name} fill={SEVERITY_COLORS[entry.name] || '#64748b'} />
                      ))}
                    </Pie>
                    <Tooltip content={<ChartTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                {Object.entries(data?.alerts?.by_severity || {}).map(([name, count]) => (
                  <div key={name} className="flex items-center justify-between rounded-md border border-slate-800 bg-slate-900/40 px-2 py-1.5 text-[11px]">
                    <span className="flex items-center gap-1.5 text-slate-400">
                      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: SEVERITY_COLORS[name] || '#64748b' }} />
                      {name}
                    </span>
                    <span className="font-semibold tabular-nums text-slate-200">{count}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel title="Risk distribution" subtitle="Assessments grouped by category">
          {loading && !data ? (
            <LoadingState />
          ) : riskData.length === 0 ? (
            <EmptyState icon={Target} title="No risk assessments yet" message="Assessments are produced when events are analysed by the risk pipeline." />
          ) : (
            <div className="h-52 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={riskData} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                  <XAxis dataKey="name" stroke="#475569" fontSize={10} tickLine={false} axisLine={false} />
                  <YAxis stroke="#475569" fontSize={10} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="value" name="Assessments" radius={[4, 4, 0, 0]} maxBarSize={48}>
                    {riskData.map((entry) => (
                      <Cell key={entry.name} fill={RISK_COLORS[entry.name] || '#64748b'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        <Panel
          title="Latest risk assessment"
          subtitle={latestRisk ? `Event ${latestRisk.event_id}` : 'No assessment available'}
          actions={
            <Link to="/risk-posture" className="text-xs font-semibold text-blue-400 hover:text-blue-300">
              Risk posture →
            </Link>
          }
        >
          {loading && !data ? (
            <LoadingState />
          ) : !latestRisk ? (
            <EmptyState icon={Target} title="No assessment yet" message="Once an authorised event is analysed, its explainable four-signal score appears here." />
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs text-slate-500">User</p>
                  <p className="text-sm font-semibold text-slate-100">{latestRisk.user_id || 'Unverified source'}</p>
                </div>
                <Badge tone={severityTone(latestRisk.risk_category)}>{latestRisk.risk_category}</Badge>
              </div>
              <div>
                <div className="mb-1 flex items-center justify-between text-[11px] text-slate-500">
                  <span>Combined score</span>
                  <span className="font-semibold text-slate-200">{formatScore(latestRisk.combined_score, 1)} / 100</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                  <div className="h-full rounded-full" style={{ width: `${Math.min(100, Number(latestRisk.combined_score) || 0)}%`, backgroundColor: RISK_COLORS[latestRisk.risk_category] || '#3b82f6' }} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                {[
                  ['Privacy', latestRisk.privacy_score],
                  ['Behaviour', latestRisk.behavioral_score],
                  ['Endpoint', latestRisk.endpoint_score],
                  ['Access', latestRisk.access_score],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-md border border-slate-800 bg-slate-900/40 px-2 py-1.5">
                    <p className="text-slate-500">{label}</p>
                    <p className="font-semibold tabular-nums text-slate-200">{formatScore(value, 1)}</p>
                  </div>
                ))}
              </div>
              <p className="text-[11px] leading-relaxed text-slate-500">
                {latestRisk.explanation?.[0] || latestRisk.risk_factors?.[0] || 'No explanatory factor recorded.'}
              </p>
              <p className="text-[10px] text-slate-600">{formatDateTime(latestRisk.timestamp)}</p>
            </div>
          )}
        </Panel>

        <Panel
          title="Endpoint fleet"
          subtitle="Enrollment and liveness"
          actions={
            <Link to={isAdminScope ? '/users' : '/consent'} className="text-xs font-semibold text-blue-400 hover:text-blue-300">
              {isAdminScope ? 'Manage users →' : 'Consent →'}
            </Link>
          }
        >
          <div className="space-y-3">
            {[
              { label: 'Active', value: data?.devices?.active, tone: 'green', icon: ShieldCheck },
              { label: 'Stale heartbeat', value: data?.devices?.stale, tone: 'amber', icon: Clock3 },
              { label: 'Revoked', value: data?.devices?.revoked, tone: 'red', icon: ShieldAlert },
            ].map((row) => {
              const Icon = row.icon;
              return (
                <div key={row.label} className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-2.5">
                  <span className="flex items-center gap-2 text-xs text-slate-400">
                    <Icon size={14} />
                    {row.label}
                  </span>
                  <span className="text-sm font-bold tabular-nums text-slate-100">{formatNumber(row.value)}</span>
                </div>
              );
            })}
            <p className="text-[10px] leading-relaxed text-slate-600">
              Stale devices have not sent a heartbeat within the configured liveness window. A revoked
              device must re-enroll with a new one-time token.
            </p>
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel
          title="Recent events"
          subtitle="Newest activity visible in your scope"
          actions={
            <Link to="/live-activity" className="text-xs font-semibold text-blue-400 hover:text-blue-300">
              Live activity →
            </Link>
          }
          bodyClassName="p-0"
        >
          {loading && !data ? (
            <LoadingState />
          ) : (data?.recent_events || []).length === 0 ? (
            <EmptyState icon={Activity} title="No events yet" message="Enrolled agents and the SaaS proxy populate this feed." />
          ) : (
            <div className="overflow-x-auto">
              <table className="soc-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Source</th>
                    <th>Type / action</th>
                    <th>User</th>
                    <th>Resource</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_events.map((event) => (
                    <tr key={event.event_id}>
                      <td className="whitespace-nowrap text-slate-400">{timeAgo(event.timestamp)}</td>
                      <td><Badge tone={event.source === 'endpoint_agent' ? 'cyan' : event.source === 'saas_proxy' ? 'purple' : 'neutral'}>{event.source}</Badge></td>
                      <td>
                        <p className="text-slate-200">{event.event_type}</p>
                        <p className="text-[10px] text-slate-500">{event.action}</p>
                      </td>
                      <td className="text-slate-400">{event.user_id || <span className="text-amber-400">unverified</span>}</td>
                      <td className="max-w-[14rem] truncate text-slate-400" title={event.resource_name || event.resource_id || ''}>
                        {event.resource_name || event.resource_id || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel
          title="Recent alerts"
          subtitle="Newest alerts visible in your scope"
          actions={
            <Link to="/alerts" className="text-xs font-semibold text-blue-400 hover:text-blue-300">
              All alerts →
            </Link>
          }
          bodyClassName="p-0"
        >
          {loading && !data ? (
            <LoadingState />
          ) : (data?.alerts?.recent || []).length === 0 ? (
            <EmptyState icon={ShieldCheck} title="No alerts" message="Alerts raised by the risk pipeline will appear here." />
          ) : (
            <div className="divide-y divide-slate-800">
              {data.alerts.recent.map((alert) => (
                <div key={alert.id || alert._id} className="flex items-start justify-between gap-3 px-4 py-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={severityTone(alert.severity)}>{alert.severity}</Badge>
                      <Badge tone={statusTone(alert.status)}>{alert.status}</Badge>
                    </div>
                    <p className="mt-1.5 truncate text-sm font-medium text-slate-200">{alert.title}</p>
                    <p className="mt-0.5 line-clamp-2 text-[11px] text-slate-500">{alert.reason}</p>
                    <p className="mt-1 text-[10px] text-slate-600">{alert.user_id || 'unverified source'} · {timeAgo(alert.timestamp)}</p>
                  </div>
                  {alert.risk_score != null ? (
                    <span className="shrink-0 rounded-md border border-slate-700 bg-slate-900 px-2 py-1 font-mono text-xs text-slate-300">
                      {formatScore(alert.risk_score, 0)}
                    </span>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      {isAdminScope ? (
        <Panel title="Data scope note" subtitle="What these aggregates mean">
          <div className="grid gap-3 text-xs leading-relaxed text-slate-400 md:grid-cols-3">
            <div className="flex gap-2"><Database size={15} className="mt-0.5 shrink-0 text-blue-400" /><span>All counts are computed from live MongoDB collections, not cached demo values.</span></div>
            <div className="flex gap-2"><AlertTriangle size={15} className="mt-0.5 shrink-0 text-amber-400" /><span>Proxy-ingested SaaS events are marked identity-unverified and are never attributed to a user by client-supplied identity.</span></div>
            <div className="flex gap-2"><Target size={15} className="mt-0.5 shrink-0 text-purple-400" /><span>Risk categories combine privacy, behaviour, endpoint and access signals with documented weights.</span></div>
          </div>
        </Panel>
      ) : null}
    </div>
  );
}
