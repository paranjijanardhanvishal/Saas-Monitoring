import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  BrainCircuit,
  RefreshCw,
  ShieldAlert,
  Target,
  TrendingUp,
} from 'lucide-react';
import {
  errorMessage,
  getBehaviorAnomalies,
  getBehaviorProfiles,
  getRiskSummary,
  getUserBehaviorProfile,
  getUserRiskAssessments,
} from '../api';
import {
  Badge,
  btnSecondary,
  Drawer,
  EmptyState,
  ErrorState,
  formatDateTime,
  formatNumber,
  formatScore,
  inputClass,
  KeyValue,
  LoadingState,
  PageHeader,
  Panel,
  severityTone,
  StatCard,
  timeAgo,
} from '../components/ui';

function ewmaEntries(ewma) {
  if (!ewma || typeof ewma !== 'object') return [];
  return Object.entries(ewma).filter(([, value]) => Number.isFinite(Number(value)));
}

function EwmaInline({ ewma }) {
  const entries = ewmaEntries(ewma).slice(0, 4);
  if (entries.length === 0) return <span className="text-slate-600">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {entries.map(([key, value]) => (
        <span key={key} className="rounded border border-slate-800 bg-slate-950/50 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
          {key.replaceAll('_', ' ')} {formatScore(value, 2)}
        </span>
      ))}
    </div>
  );
}

function EwmaGrid({ ewma }) {
  const entries = ewmaEntries(ewma);
  if (entries.length === 0) {
    return <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-500">No EWMA baseline values stored yet.</p>;
  }
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
          <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{key.replaceAll('_', ' ')}</p>
          <p className="mt-1 font-mono text-lg font-semibold text-slate-100">{formatScore(value, 2)}</p>
        </div>
      ))}
    </div>
  );
}

export default function Ueba() {
  const [profiles, setProfiles] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [userFilter, setUserFilter] = useState('');
  const [appliedUser, setAppliedUser] = useState('');
  const [roleOnly, setRoleOnly] = useState(false);

  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');

  const load = useCallback(
    async ({ silent = false, userId = appliedUser } = {}) => {
      if (silent) setRefreshing(true);
      else setLoading(true);
      setError('');
      try {
        const [profileResult, anomalyResult, summaryResult] = await Promise.all([
          getBehaviorProfiles({ limit: 100, user_id: userId || undefined }),
          getBehaviorAnomalies({ limit: 100, user_id: userId || undefined, only_anomalies: false, role_mismatches_only: roleOnly || undefined }),
          getRiskSummary(),
        ]);
        setProfiles(Array.isArray(profileResult) ? profileResult : []);
        setAnomalies(Array.isArray(anomalyResult) ? anomalyResult : []);
        setSummary(summaryResult || null);
      } catch (err) {
        setError(errorMessage(err, 'Could not load behavioural analytics.'));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [appliedUser, roleOnly],
  );

  useEffect(() => {
    load();
  }, [load]);

  const openProfile = useCallback(async (profile) => {
    setSelected(profile);
    setDetail(null);
    setDetailError('');
    setDetailLoading(true);
    try {
      const [freshProfile, userAnomalies, userRisks] = await Promise.all([
        getUserBehaviorProfile(profile.user_id),
        getBehaviorAnomalies({ user_id: profile.user_id, limit: 25 }),
        getUserRiskAssessments(profile.user_id, { limit: 25 }),
      ]);
      setDetail({
        profile: freshProfile,
        anomalies: Array.isArray(userAnomalies) ? userAnomalies : [],
        risks: Array.isArray(userRisks) ? userRisks : [],
      });
    } catch (err) {
      setDetailError(errorMessage(err, 'Could not load the behavioural profile.'));
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const closeDetail = () => {
    setSelected(null);
    setDetail(null);
    setDetailError('');
  };

  const applyFilter = () => {
    setAppliedUser(userFilter.trim());
    if (!userFilter.trim()) load({ userId: '' });
  };

  const stats = useMemo(() => {
    const anomalous = anomalies.filter((item) => item.is_anomaly);
    const deviations = anomalies
      .map((item) => Number(item.deviation))
      .filter((value) => Number.isFinite(value));
    const averageDeviation = deviations.length
      ? deviations.reduce((total, value) => total + value, 0) / deviations.length
      : null;
    return {
      profiles: profiles.length,
      findings: anomalies.length,
      anomalous: anomalous.length,
      roleMismatches: anomalies.filter((item) => item.role_mismatch).length,
      averageDeviation,
    };
  }, [profiles, anomalies]);

  const categoryRows = summary?.by_category || [];
  const topUsers = summary?.top_users || [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Identity & behaviour"
        title="User and entity behaviour analytics"
        subtitle="EWMA activity baselines and transparent business-role checks on attributed endpoint events. Findings are derived from live authorised activity; account and enrollment administration lives under Users."
        actions={
          <button type="button" onClick={() => load({ silent: true })} className={btnSecondary} disabled={refreshing}>
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-5">
        <input
          value={userFilter}
          onChange={(event) => setUserFilter(event.target.value)}
          onKeyDown={(event) => { if (event.key === 'Enter') applyFilter(); }}
          placeholder="Filter by exact user ID (optional)"
          className={inputClass}
        />
        <button type="button" className={btnSecondary} onClick={applyFilter}>Apply user filter</button>
        <button type="button" aria-pressed={roleOnly} className={roleOnly ? 'inline-flex items-center justify-center gap-2 rounded-lg border border-red-800/60 bg-red-950/30 px-4 py-2 text-sm font-semibold text-red-200 transition' : btnSecondary} onClick={() => setRoleOnly((value) => !value)}>
          <ShieldAlert size={14} />
          {roleOnly ? 'Showing role mismatches' : 'Role mismatches only'}
        </button>
        <button
          type="button"
          className={btnSecondary}
          onClick={() => { setUserFilter(''); setAppliedUser(''); load({ userId: '' }); }}
        >
          Clear filter
        </button>
        <p className="self-center text-[11px] text-slate-500">
          {appliedUser ? <>Scoped to <span className="font-mono text-slate-300">{appliedUser}</span></> : 'Showing all users in your authorised scope.'}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-5">
        <StatCard label="Behaviour profiles" value={formatNumber(stats.profiles)} hint="Loaded profiles" icon={BrainCircuit} tone="blue" loading={loading} />
        <StatCard label="Findings loaded" value={formatNumber(stats.findings)} hint="Recent analytical findings" icon={Activity} tone="purple" loading={loading} />
        <StatCard label="Flagged anomalies" value={formatNumber(stats.anomalous)} hint="Activity or role mismatch" icon={TrendingUp} tone="red" loading={loading} />
        <StatCard label="Role mismatches" value={formatNumber(stats.roleMismatches)} hint="Current filter window" icon={ShieldAlert} tone="orange" loading={loading} />
        <StatCard label="Average deviation" value={stats.averageDeviation == null ? '—' : formatScore(stats.averageDeviation, 2)} hint="Across loaded findings" icon={Target} tone="amber" loading={loading} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel title="Risk categories" subtitle="Server-side risk summary">
          {loading && !summary ? (
            <LoadingState />
          ) : categoryRows.length === 0 ? (
            <p className="text-xs text-slate-500">No risk assessments stored yet.</p>
          ) : (
            <div className="space-y-2">
              {categoryRows.map((row) => (
                <div key={row._id || 'UNKNOWN'} className="flex items-center justify-between gap-2">
                  <Badge tone={severityTone(row._id)}>{row._id || 'UNKNOWN'}</Badge>
                  <span className="font-mono text-sm text-slate-200">{formatNumber(row.count)}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Highest-risk users" subtitle="From the risk summary" className="xl:col-span-2">
          {loading && !summary ? (
            <LoadingState />
          ) : topUsers.length === 0 ? (
            <p className="text-xs text-slate-500">No user risk data available.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="soc-table">
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Max score</th>
                    <th>Assessments</th>
                    <th>Last seen</th>
                    <th className="text-right">Investigate</th>
                  </tr>
                </thead>
                <tbody>
                  {topUsers.map((row) => (
                    <tr key={row.user_id || 'unknown'}>
                      <td className="font-medium text-slate-200">{row.user_id || '—'}</td>
                      <td className="font-mono text-slate-200">{formatScore(row.max_score, 1)}</td>
                      <td className="text-slate-400">{formatNumber(row.assessments)}</td>
                      <td className="whitespace-nowrap text-slate-400">{row.last_seen ? timeAgo(row.last_seen) : '—'}</td>
                      <td className="text-right">
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
      </div>

      <Panel
        title="Behavioural baselines"
        subtitle={`${profiles.length} EWMA profile${profiles.length === 1 ? '' : 's'} in the current view`}
        bodyClassName="p-0"
      >
        {loading ? (
          <LoadingState />
        ) : profiles.length === 0 ? (
          <EmptyState
            icon={BrainCircuit}
            title="No behaviour profiles yet"
            message="Profiles are created when persisted events are analysed by the behaviour pipeline. Ensure an enrolled agent or SaaS proxy is producing authorised events."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="soc-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Last activity</th>
                  <th>EWMA baseline</th>
                  <th>Updated</th>
                  <th className="text-right">Profile</th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((profile) => (
                  <tr key={profile.user_id}>
                    <td className="font-medium text-slate-200">{profile.user_id}</td>
                    <td className="whitespace-nowrap text-slate-400" title={formatDateTime(profile.last_activity_timestamp)}>
                      {profile.last_activity_timestamp ? timeAgo(profile.last_activity_timestamp) : '—'}
                    </td>
                    <td><EwmaInline ewma={profile.ewma} /></td>
                    <td className="whitespace-nowrap text-slate-500">{formatDateTime(profile.updated_at)}</td>
                    <td className="text-right">
                      <button type="button" className={btnSecondary} onClick={() => openProfile(profile)}>Open</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel
        title="Behavioural findings"
        subtitle={`${anomalies.length} finding${anomalies.length === 1 ? '' : 's'} in the current view`}
        bodyClassName="p-0"
      >
        {loading ? (
          <LoadingState />
        ) : anomalies.length === 0 ? (
          <EmptyState
            icon={Activity}
            title={roleOnly ? 'No role mismatches in this view' : 'No behavioural findings'}
            message={roleOnly ? 'Role mismatches appear when attributed endpoint metadata points to a department category outside the user’s assigned business role.' : 'Findings appear after events are analysed. This page never generates synthetic anomalies.'}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="soc-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>User</th>
                  <th>Business role</th>
                  <th>Type</th>
                  <th>Flag</th>
                  <th>Activity rate</th>
                  <th>Deviation</th>
                  <th>Reason</th>
                  <th className="text-right">Event</th>
                </tr>
              </thead>
              <tbody>
                {anomalies.map((finding) => (
                  <tr key={finding.anomaly_id}>
                    <td className="whitespace-nowrap text-slate-400" title={formatDateTime(finding.timestamp)}>{timeAgo(finding.timestamp)}</td>
                    <td className="font-medium text-slate-200">{finding.user_id}</td>
                    <td><Badge tone={finding.role_mismatch ? 'purple' : 'neutral'}>{finding.business_role || 'GENERAL'}</Badge></td>
                    <td className="font-mono text-[11px] text-slate-400">{finding.anomaly_type}</td>
                    <td>
                      <Badge tone={finding.is_anomaly ? 'red' : 'green'}>
                        {finding.is_anomaly ? 'anomaly' : 'baseline'}
                      </Badge>
                    </td>
                    <td className="font-mono text-slate-300">{formatScore(finding.activity_rate, 2)}</td>
                    <td className="font-mono text-slate-300">{formatScore(finding.deviation, 2)}</td>
                    <td className="max-w-[22rem] text-[11px] text-slate-500">
                      <span className="line-clamp-2" title={finding.reason}>{finding.reason || '—'}</span>
                    </td>
                    <td className="text-right font-mono text-[10px] text-slate-500">
                      {finding.event_id ? (
                        <Link to={`/investigation?event=${encodeURIComponent(finding.event_id)}`} className="text-blue-400 hover:text-blue-300">
                          context →
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

      <Drawer
        open={Boolean(selected)}
        onClose={closeDetail}
        title={selected ? `Behaviour · ${selected.user_id}` : 'Behaviour profile'}
        subtitle="EWMA baseline, recent findings and risk assessments"
        footer={
          selected ? (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Link to={`/investigation?user=${encodeURIComponent(selected.user_id)}`} className="text-xs font-semibold text-blue-400 hover:text-blue-300">
                Open full investigation →
              </Link>
              <button type="button" className={btnSecondary} onClick={closeDetail}>Close</button>
            </div>
          ) : null
        }
      >
        {detailLoading ? (
          <LoadingState label="Loading behavioural profile…" />
        ) : detailError ? (
          <ErrorState message={detailError} onRetry={() => selected && openProfile(selected)} />
        ) : detail ? (
          <div className="space-y-5">
            <section className="grid grid-cols-2 gap-3">
              <KeyValue label="User">{detail.profile?.user_id}</KeyValue>
              <KeyValue label="Last activity">{formatDateTime(detail.profile?.last_activity_timestamp)}</KeyValue>
              <KeyValue label="Profile updated" className="col-span-2">{formatDateTime(detail.profile?.updated_at)}</KeyValue>
            </section>

            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-100">EWMA baseline</h3>
              <EwmaGrid ewma={detail.profile?.ewma} />
            </section>

            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-100">Recent findings ({detail.anomalies.length})</h3>
              {detail.anomalies.length === 0 ? (
                <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-500">No findings recorded for this user.</p>
              ) : (
                <div className="space-y-1.5">
                  {detail.anomalies.map((finding) => (
                    <div key={finding.anomaly_id} className="rounded-md border border-slate-800 bg-slate-900/40 px-3 py-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <Badge tone={finding.is_anomaly ? 'red' : 'green'}>{finding.is_anomaly ? 'anomaly' : 'baseline'}</Badge>
                        <span className="text-[10px] text-slate-500">{formatDateTime(finding.timestamp)}</span>
                      </div>
                      <p className="mt-1 text-[11px] text-slate-400">{finding.reason}</p>
                      <p className="mt-0.5 font-mono text-[10px] text-slate-500">
                        rate {formatScore(finding.activity_rate, 2)} · deviation {formatScore(finding.deviation, 2)} · {finding.anomaly_type}
                      </p>
                      {finding.role_mismatch ? <p className="mt-1 text-[10px] text-purple-300">Role score {formatScore(finding.role_anomaly_score, 0)} · {(finding.observed_resource_categories || []).join(', ')}</p> : null}
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-100">Risk assessments ({detail.risks.length})</h3>
              {detail.risks.length === 0 ? (
                <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-500">No risk assessments stored for this user.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="soc-table">
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Category</th>
                        <th>Score</th>
                        <th>Signals</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.risks.map((risk) => (
                        <tr key={risk.risk_id}>
                          <td className="whitespace-nowrap text-slate-400">{timeAgo(risk.timestamp)}</td>
                          <td><Badge tone={severityTone(risk.risk_category)}>{risk.risk_category}</Badge></td>
                          <td className="font-mono text-slate-200">{formatScore(risk.combined_score, 1)}</td>
                          <td className="text-[10px] text-slate-500">
                            P {formatScore(risk.privacy_score, 0)} · B {formatScore(risk.behavioral_score, 0)} · E {formatScore(risk.endpoint_score, 0)} · A {formatScore(risk.access_score, 0)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}
