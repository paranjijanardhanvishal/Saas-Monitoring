import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { BarChart3, RefreshCw, Target, Users } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { errorMessage, getRiskAssessments, getRiskSummary } from '../api';
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
  timeAgo,
} from '../components/ui';

const RISK_COLORS = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#f59e0b',
  LOW: '#10b981',
};

const CATEGORIES = ['', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

export default function RiskPosture() {
  const [summary, setSummary] = useState(null);
  const [assessments, setAssessments] = useState([]);
  const [category, setCategory] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(
    async ({ silent = false, selectedCategory = category } = {}) => {
      if (silent) setRefreshing(true);
      else setLoading(true);
      setError('');
      try {
        const [summaryResult, assessmentResult] = await Promise.all([
          getRiskSummary(),
          getRiskAssessments({ limit: 100, category: selectedCategory || undefined }),
        ]);
        setSummary(summaryResult);
        setAssessments(Array.isArray(assessmentResult) ? assessmentResult : []);
      } catch (err) {
        setError(errorMessage(err, 'Could not load risk posture data.'));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [category],
  );

  useEffect(() => {
    load();
  }, [load]);

  const byCategory = useMemo(() => {
    const rows = summary?.by_category || [];
    return rows.map((row) => ({ name: row._id || 'UNKNOWN', value: row.count }));
  }, [summary]);

  const topUsers = summary?.top_users || [];
  const latest = assessments[0] || null;

  const averages = useMemo(() => {
    if (assessments.length === 0) return null;
    const totals = { privacy_score: 0, behavioral_score: 0, endpoint_score: 0, access_score: 0, combined_score: 0 };
    assessments.forEach((item) => {
      Object.keys(totals).forEach((key) => {
        totals[key] += Number(item[key]) || 0;
      });
    });
    return Object.fromEntries(
      Object.entries(totals).map(([key, total]) => [key, total / assessments.length]),
    );
  }, [assessments]);

  const weightEntries = useMemo(
    () => Object.entries(latest?.weights_used || {}).filter(([, value]) => Number.isFinite(Number(value))),
    [latest],
  );

  const handleCategory = (next) => {
    setCategory(next);
    load({ selectedCategory: next });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Risk posture"
        title="Explainable risk analysis"
        subtitle="Four-signal scoring across privacy sensitivity, behavioural deviation, endpoint context and access patterns. Signals are derived server-side from persisted events."
        actions={
          <>
            <select value={category} onChange={(event) => handleCategory(event.target.value)} className="rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-xs text-slate-100 outline-none focus:border-blue-500">
              {CATEGORIES.map((item) => (
                <option key={item} value={item}>{item || 'All categories'}</option>
              ))}
            </select>
            <button type="button" onClick={() => load({ silent: true })} className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:bg-slate-800 disabled:opacity-50" disabled={refreshing}>
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
              Refresh
            </button>
          </>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Assessments loaded" value={formatNumber(assessments.length)} hint={category ? `Category: ${category}` : 'Newest 100 assessments'} icon={Target} tone="blue" loading={loading} />
        <StatCard label="Average score" value={averages ? formatScore(averages.combined_score, 1) : '—'} hint="Across loaded assessments" icon={BarChart3} tone="purple" loading={loading} />
        <StatCard label="Critical + high" value={formatNumber(assessments.filter((item) => ['CRITICAL', 'HIGH'].includes(item.risk_category)).length)} hint="In the loaded window" icon={Target} tone="red" loading={loading} />
        <StatCard label="Users with risk" value={formatNumber(topUsers.length)} hint="Top users returned by the summary" icon={Users} tone="amber" loading={loading} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title="Category distribution" subtitle="Every stored risk assessment">
          {loading && !summary ? (
            <LoadingState />
          ) : byCategory.length === 0 ? (
            <EmptyState icon={Target} title="No assessments stored" message="Risk assessments are created when authorised events are analysed by the risk pipeline." />
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byCategory} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                  <XAxis dataKey="name" stroke="#475569" fontSize={10} tickLine={false} axisLine={false} />
                  <YAxis stroke="#475569" fontSize={10} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: '#111827', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }} labelStyle={{ color: '#e2e8f0' }} />
                  <Bar dataKey="value" name="Assessments" radius={[4, 4, 0, 0]} maxBarSize={64}>
                    {byCategory.map((entry) => (
                      <Cell key={entry.name} fill={RISK_COLORS[entry.name] || '#64748b'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        <Panel title="Signal averages" subtitle="Mean normalised score (0–100) in the loaded window">
          {loading && !summary ? (
            <LoadingState />
          ) : !averages ? (
            <EmptyState icon={BarChart3} title="No signal data" message="Signal averages appear once assessments are available." />
          ) : (
            <div className="space-y-4">
              {[
                ['Privacy sensitivity', averages.privacy_score, 'Privacy'],
                ['Behavior risk', averages.behavioral_score, 'EWMA / role'],
                ['Endpoint context', averages.endpoint_score, 'Endpoint'],
                ['Access patterns', averages.access_score, 'Access'],
              ].map(([label, value]) => (
                <div key={label}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="text-slate-400">{label}</span>
                    <span className="font-mono font-semibold text-slate-200">{formatScore(value, 1)}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                    <div className="h-full rounded-full bg-blue-500" style={{ width: `${Math.max(0, Math.min(100, Number(value) || 0))}%` }} />
                  </div>
                </div>
              ))}
              {weightEntries.length > 0 ? (
                <p className="text-[11px] leading-relaxed text-slate-500">
                  Latest weights: {weightEntries.map(([key, value]) => `${key.replace('_weight', '')} ${formatScore(value, 2)}`).join(' · ')}
                </p>
              ) : null}
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Highest-risk users" subtitle="Maximum combined score per user (summary endpoint)" bodyClassName="p-0">
        {loading && !summary ? (
          <LoadingState />
        ) : topUsers.length === 0 ? (
          <EmptyState icon={Users} title="No user risk data" message="The summary will list users once assessments exist." />
        ) : (
          <div className="overflow-x-auto">
            <table className="soc-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Max score</th>
                  <th>Assessments</th>
                  <th>Last seen</th>
                  <th>Investigate</th>
                </tr>
              </thead>
              <tbody>
                {topUsers.map((row) => (
                  <tr key={row.user_id || 'unknown'}>
                    <td className="font-medium text-slate-200">{row.user_id || '—'}</td>
                    <td className="font-mono text-slate-200">{formatScore(row.max_score, 1)}</td>
                    <td className="text-slate-400">{formatNumber(row.assessments)}</td>
                    <td className="whitespace-nowrap text-slate-400">{row.last_seen ? timeAgo(row.last_seen) : '—'}</td>
                    <td>
                      {row.user_id ? (
                        <Link to={`/investigation?user=${encodeURIComponent(row.user_id)}`} className="text-xs font-semibold text-blue-400 hover:text-blue-300">
                          Open profile →
                        </Link>
                      ) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel
        title="Assessment history"
        subtitle={`${assessments.length} assessment${assessments.length === 1 ? '' : 's'} loaded${category ? ` in ${category}` : ''}`}
        bodyClassName="p-0"
      >
        {loading ? (
          <LoadingState />
        ) : assessments.length === 0 ? (
          <EmptyState icon={Target} title="No assessments in this view" message="Adjust the category filter or wait for new analysed events." />
        ) : (
          <div className="overflow-x-auto">
            <table className="soc-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>User</th>
                  <th>Category</th>
                  <th>Combined</th>
                  <th>Privacy</th>
                  <th>Behaviour</th>
                  <th>Endpoint</th>
                  <th>Access</th>
                  <th>Confidence</th>
                  <th>Explanation</th>
                </tr>
              </thead>
              <tbody>
                {assessments.map((item) => (
                  <tr key={item.risk_id}>
                    <td className="whitespace-nowrap text-slate-400" title={formatDateTime(item.timestamp)}>{timeAgo(item.timestamp)}</td>
                    <td className="font-medium text-slate-200">{item.user_id || '—'}</td>
                    <td><Badge tone={severityTone(item.risk_category)}>{item.risk_category}</Badge></td>
                    <td className="font-mono font-semibold text-slate-100">{formatScore(item.combined_score, 1)}</td>
                    <td className="font-mono text-slate-400">{formatScore(item.privacy_score, 1)}</td>
                    <td className="font-mono text-slate-400">{formatScore(item.behavioral_score, 1)}</td>
                    <td className="font-mono text-slate-400">{formatScore(item.endpoint_score, 1)}</td>
                    <td className="font-mono text-slate-400">{formatScore(item.access_score, 1)}</td>
                    <td className="font-mono text-slate-400">{formatScore(item.signal_confidence, 2)}</td>
                    <td className="max-w-[20rem] text-[11px] text-slate-500">
                      <span className="line-clamp-2" title={(item.explanation || []).join(' ')}>
                        {(item.explanation || item.risk_factors || []).join(' ') || '—'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
