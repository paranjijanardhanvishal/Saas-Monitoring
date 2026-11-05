import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  Database,
  History,
  Laptop,
  RefreshCw,
  ScrollText,
  Server,
  ShieldCheck,
  ShieldAlert,
  ShieldOff,
} from 'lucide-react';
import {
  errorMessage,
  getAuditLogs,
  getConsentHistory,
  generateDemoRun,
  getDemoStatus,
  resetDemoRuns,
  getSystemHealth,
} from '../api';
import {
  Badge,
  btnSecondary,
  consentTone,
  cx,
  Drawer,
  EmptyState,
  ErrorState,
  formatDateTime,
  formatNumber,
  InlineNotice,
  inputClass,
  KeyValue,
  LoadingState,
  PageHeader,
  Pagination,
  Panel,
  StatCard,
  statusTone,
  timeAgo,
} from '../components/ui';

const AUDIT_LIMIT = 50;
const CONSENT_LIMIT = 100;

const TABS = [
  { id: 'health', label: 'Operational health', icon: Activity },
  { id: 'audit', label: 'Audit trail', icon: ScrollText },
  { id: 'consent', label: 'Consent history', icon: History },
  { id: 'demo', label: 'Synthetic demo', icon: ShieldAlert },
];

function formatUptime(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value < 0) return '—';
  const days = Math.floor(value / 86400);
  const hours = Math.floor((value % 86400) / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const secs = Math.floor(value % 60);
  if (days > 0) return `${days}d ${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h ${minutes}m ${secs}s`;
  if (minutes > 0) return `${minutes}m ${secs}s`;
  return `${secs}s`;
}

function ConfigBadge({ configured, label }) {
  return (
    <Badge tone={configured ? 'green' : 'neutral'}>
      {configured ? `${label} configured` : `${label} not configured`}
    </Badge>
  );
}

export default function SystemHealth() {
  const [tab, setTab] = useState('health');

  const [health, setHealth] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthRefreshing, setHealthRefreshing] = useState(false);
  const [healthError, setHealthError] = useState('');

  const [auditLogs, setAuditLogs] = useState([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState('');
  const [auditSkip, setAuditSkip] = useState(0);
  const [auditFilters, setAuditFilters] = useState({ actor_id: '', action: '', target_type: '' });
  const [appliedAuditFilters, setAppliedAuditFilters] = useState({ actor_id: '', action: '', target_type: '' });
  const [selectedAudit, setSelectedAudit] = useState(null);

  const [demoStatus, setDemoStatus] = useState(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);
  const [demoError, setDemoError] = useState('');
  const [demoResult, setDemoResult] = useState(null);

  const [consentHistory, setConsentHistory] = useState([]);
  const [consentLoading, setConsentLoading] = useState(false);
  const [consentError, setConsentError] = useState('');
  const [consentUser, setConsentUser] = useState('');
  const [appliedConsentUser, setAppliedConsentUser] = useState('');

  const loadHealth = useCallback(async ({ silent = false } = {}) => {
    if (silent) setHealthRefreshing(true);
    else setHealthLoading(true);
    setHealthError('');
    try {
      const result = await getSystemHealth();
      setHealth(result);
    } catch (err) {
      setHealthError(errorMessage(err, 'Could not load system health.'));
    } finally {
      setHealthLoading(false);
      setHealthRefreshing(false);
    }
  }, []);

  const loadAudit = useCallback(
    async ({ silent = false, nextSkip = auditSkip } = {}) => {
      if (!silent) setAuditLoading(true);
      setAuditError('');
      try {
        const result = await getAuditLogs({
          limit: AUDIT_LIMIT,
          skip: nextSkip,
          actor_id: appliedAuditFilters.actor_id || undefined,
          action: appliedAuditFilters.action || undefined,
          target_type: appliedAuditFilters.target_type || undefined,
        });
        setAuditLogs(Array.isArray(result) ? result : []);
      } catch (err) {
        setAuditError(errorMessage(err, 'Could not load the audit trail.'));
      } finally {
        setAuditLoading(false);
      }
    },
    [auditSkip, appliedAuditFilters],
  );

  const loadConsent = useCallback(async () => {
    setConsentLoading(true);
    setConsentError('');
    try {
      const result = await getConsentHistory({
        limit: CONSENT_LIMIT,
        user_id: appliedConsentUser || undefined,
      });
      setConsentHistory(Array.isArray(result) ? result : []);
    } catch (err) {
      setConsentError(errorMessage(err, 'Could not load consent history.'));
    } finally {
      setConsentLoading(false);
    }
  }, [appliedConsentUser]);

  const loadDemo = useCallback(async () => {
    setDemoLoading(true);
    setDemoError('');
    try {
      setDemoStatus(await getDemoStatus());
    } catch (err) {
      setDemoError(errorMessage(err, 'Could not load synthetic demo status.'));
    } finally {
      setDemoLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHealth();
  }, [loadHealth]);

  useEffect(() => {
    if (tab === 'audit') loadAudit();
  }, [tab, loadAudit]);

  useEffect(() => {
    if (tab === 'consent') loadConsent();
  }, [tab, loadConsent]);

  useEffect(() => {
    if (tab === 'demo') loadDemo();
  }, [tab, loadDemo]);

  const applyAuditFilters = () => {
    setAuditSkip(0);
    setAppliedAuditFilters({
      actor_id: auditFilters.actor_id.trim(),
      action: auditFilters.action.trim(),
      target_type: auditFilters.target_type.trim(),
    });
    if (auditSkip === 0) loadAudit({ nextSkip: 0 });
  };

  const resetAuditFilters = () => {
    const empty = { actor_id: '', action: '', target_type: '' };
    setAuditFilters(empty);
    setAppliedAuditFilters(empty);
    setAuditSkip(0);
    if (auditSkip === 0) loadAudit({ nextSkip: 0 });
  };

  const refreshCurrent = () => {
    if (tab === 'health') loadHealth({ silent: true });
    else if (tab === 'audit') loadAudit({ silent: true });
    else if (tab === 'consent') loadConsent();
    else loadDemo();
  };

  const generateDemo = async () => {
    setDemoBusy(true);
    setDemoError('');
    setDemoResult(null);
    try {
      setDemoResult(await generateDemoRun());
      await Promise.all([loadDemo(), loadHealth({ silent: true })]);
    } catch (err) {
      setDemoError(errorMessage(err, 'Could not generate synthetic demo data.'));
    } finally {
      setDemoBusy(false);
    }
  };

  const resetDemo = async () => {
    setDemoBusy(true);
    setDemoError('');
    try {
      setDemoResult(await resetDemoRuns());
      await Promise.all([loadDemo(), loadHealth({ silent: true })]);
    } catch (err) {
      setDemoError(errorMessage(err, 'Could not reset synthetic demo data.'));
    } finally {
      setDemoBusy(false);
    }
  };

  const databaseConnected = Boolean(health?.database?.connected);
  const collections = health?.database?.collections || {};
  const collectionEntries = useMemo(() => Object.entries(collections), [collections]);
  const totalDocuments = useMemo(
    () =>
      collectionEntries.reduce((total, [, value]) => total + (Number.isFinite(Number(value)) ? Number(value) : 0), 0),
    [collectionEntries],
  );

  const busy = healthRefreshing || auditLoading || consentLoading || demoLoading || demoBusy;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operations"
        title="System health"
        subtitle="Live operational state, append-only audit trail and consent transition history. Unavailable counters are reported as unavailable, not replaced with zero or synthetic values."
        actions={
          <button type="button" onClick={refreshCurrent} className={btnSecondary} disabled={busy}>
            <RefreshCw size={14} className={busy ? 'animate-spin' : ''} />
            Refresh
          </button>
        }
      />

      <div className="flex flex-wrap gap-1 rounded-xl border border-slate-800 bg-[#111827]/80 p-1">
        {TABS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setTab(item.id)}
              className={cx(
                'inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold transition',
                tab === item.id ? 'bg-blue-500/10 text-blue-300 ring-1 ring-inset ring-blue-500/20' : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-100',
              )}
            >
              <Icon size={14} />
              {item.label}
            </button>
          );
        })}
      </div>

      {tab === 'health' ? (
        healthError ? (
          <ErrorState message={healthError} onRetry={() => loadHealth()} />
        ) : healthLoading && !health ? (
          <LoadingState label="Reading live service health…" />
        ) : health ? (
          <>
            <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
              <StatCard
                label="Database"
                value={databaseConnected ? 'Connected' : 'Unavailable'}
                hint={health.database?.name || 'MongoDB'}
                icon={Database}
                tone={databaseConnected ? 'green' : 'red'}
              />
              <StatCard label="Active devices" value={formatNumber(health.devices?.active)} hint={`${formatNumber(health.devices?.stale)} stale`} icon={Laptop} tone="blue" />
              <StatCard label="Documents counted" value={formatNumber(totalDocuments)} hint="Across reported collections" icon={Server} tone="purple" />
              <StatCard label="Uptime" value={formatUptime(health.uptime_seconds)} hint={`Version ${health.version}`} icon={Activity} tone="amber" />
            </div>

            {databaseConnected ? (
              <InlineNotice tone="success">
                The API is serving requests and the MongoDB ping succeeded.
              </InlineNotice>
            ) : (
              <InlineNotice tone="danger">
                MongoDB is not reachable. Data-backed pages will return service-unavailable errors until the
                database connection is restored.
              </InlineNotice>
            )}

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <Panel title="Service" subtitle="Reported by the running API process">
                <div className="grid grid-cols-2 gap-3">
                  <KeyValue label="Version">{health.version}</KeyValue>
                  <KeyValue label="Environment">{health.environment}</KeyValue>
                  <KeyValue label="Server time">{formatDateTime(health.server_time)}</KeyValue>
                  <KeyValue label="Uptime">{formatUptime(health.uptime_seconds)}</KeyValue>
                  <KeyValue label="Database">{health.database?.name || '—'}</KeyValue>
                  <KeyValue label="Risk auto-analysis">{health.risk_engine?.auto_enabled ? 'Enabled' : 'Disabled'}</KeyValue>
                  <KeyValue label="Privacy engine configured">{health.privacy_engine?.configured || '—'}</KeyValue>
                  <KeyValue label="Privacy engine active">{health.privacy_engine?.active || '—'}</KeyValue>
                  <KeyValue label="OCR engine">
                    {health.ocr_engine?.available
                      ? `${health.ocr_engine.engine} ${health.ocr_engine.version || ''}`.trim()
                      : 'Not configured'}
                  </KeyValue>
                  <KeyValue label="Event retention">{formatNumber(health.retention?.events_days)} days</KeyValue>
                  <KeyValue label="Audit retention">{formatNumber(health.retention?.audit_days)} days</KeyValue>
                </div>
              </Panel>

              <Panel title="Device fleet" subtitle="Enrollment state from the devices collection">
                <div className="grid grid-cols-2 gap-3">
                  <KeyValue label="Active">{formatNumber(health.devices?.active)}</KeyValue>
                  <KeyValue label="Revoked">{formatNumber(health.devices?.revoked)}</KeyValue>
                  <KeyValue label="Stale heartbeats">{formatNumber(health.devices?.stale)}</KeyValue>
                  <KeyValue label="Stale after">{formatNumber(health.devices?.stale_after_seconds)} seconds</KeyValue>
                </div>
                <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
                  A device is stale when it is still marked ACTIVE but its last heartbeat is older than the
                  configured threshold. Staleness does not revoke the credential automatically.
                </p>
              </Panel>
            </div>

            <Panel title="Collections" subtitle="Document counts measured from the live database" bodyClassName="p-0">
              {collectionEntries.length === 0 ? (
                <p className="p-4 text-xs text-slate-500">No collection counts were reported.</p>
              ) : (
                <div className="grid grid-cols-2 gap-px bg-slate-800 sm:grid-cols-3 xl:grid-cols-5">
                  {collectionEntries.map(([name, value]) => (
                    <div key={name} className="bg-[#111827] p-4">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{name.replaceAll('_', ' ')}</p>
                      <p className="mt-1 text-xl font-bold tabular-nums text-white">{value == null ? '—' : formatNumber(value)}</p>
                    </div>
                  ))}
                </div>
              )}
            </Panel>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <Panel title="Integrations" subtitle="Only environment-configured integrations are reported">
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2 rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-2">
                    <span className="text-xs text-slate-300">Slack notifications</span>
                    <ConfigBadge configured={Boolean(health.integrations?.slack_configured)} label="Slack" />
                  </div>
                  <div className="flex items-center justify-between gap-2 rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-2">
                    <span className="text-xs text-slate-300">Jira ticketing</span>
                    <ConfigBadge configured={Boolean(health.integrations?.jira_configured)} label="Jira" />
                  </div>
                </div>
                <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
                  This panel reports configuration presence only. It does not perform an outbound delivery
                  test, and no credentials are displayed.
                </p>
              </Panel>

              <Panel title="Runtime" subtitle="Reported by the server process">
                <div className="grid grid-cols-2 gap-3">
                  <KeyValue label="Python">{health.runtime?.python || '—'}</KeyValue>
                  <KeyValue label="Platform" className="col-span-2">{health.runtime?.platform || '—'}</KeyValue>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {databaseConnected ? (
                    <Badge tone="green"><ShieldCheck size={11} className="mr-0.5" /> database reachable</Badge>
                  ) : (
                    <Badge tone="red"><ShieldOff size={11} className="mr-0.5" /> database unavailable</Badge>
                  )}
                  <Badge tone={health.privacy_engine?.active === 'presidio' ? 'green' : 'amber'}>
                    PII engine: {health.privacy_engine?.active || 'unavailable'}
                  </Badge>
                </div>
              </Panel>
            </div>
          </>
        ) : null
      ) : null}

      {tab === 'audit' ? (
        <>
          <Panel title="Audit filters" subtitle="The trail never stores passwords, tokens, raw event payloads or file contents." bodyClassName="p-4">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-5">
              <input
                value={auditFilters.actor_id}
                onChange={(event) => setAuditFilters({ ...auditFilters, actor_id: event.target.value })}
                placeholder="Actor ID"
                className={inputClass}
              />
              <input
                value={auditFilters.action}
                onChange={(event) => setAuditFilters({ ...auditFilters, action: event.target.value })}
                placeholder="Action (e.g. auth.login)"
                className={inputClass}
              />
              <input
                value={auditFilters.target_type}
                onChange={(event) => setAuditFilters({ ...auditFilters, target_type: event.target.value })}
                placeholder="Target type (e.g. user)"
                className={inputClass}
              />
              <button type="button" className={btnSecondary} onClick={applyAuditFilters}>Apply</button>
              <button type="button" className="text-xs font-semibold text-slate-500 hover:text-slate-300" onClick={resetAuditFilters}>Reset</button>
            </div>
          </Panel>

          {auditError ? <ErrorState message={auditError} onRetry={() => loadAudit()} /> : null}

          <Panel title="Append-only audit trail" subtitle={`${auditLogs.length} entr${auditLogs.length === 1 ? 'y' : 'ies'} in the current page`} bodyClassName="p-0">
            {auditLoading ? (
              <LoadingState />
            ) : auditLogs.length === 0 ? (
              <EmptyState
                icon={ScrollText}
                title="No audit entries match this view"
                message="Administrative and authentication actions are recorded here as they occur."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="soc-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Actor</th>
                      <th>Action</th>
                      <th>Target</th>
                      <th>Result</th>
                      <th>Reason</th>
                      <th>Client IP</th>
                      <th className="text-right">Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.map((entry) => (
                      <tr key={entry._id}>
                        <td className="whitespace-nowrap text-slate-400" title={formatDateTime(entry.timestamp)}>{timeAgo(entry.timestamp)}</td>
                        <td>
                          <p className="text-slate-200">{entry.actor_id || 'system'}</p>
                          <p className="text-[10px] text-slate-500">{entry.actor_role || '—'}</p>
                        </td>
                        <td className="font-mono text-[11px] text-slate-300">{entry.action}</td>
                        <td>
                          <p className="text-slate-400">{entry.target_type || '—'}</p>
                          <p className="max-w-[12rem] truncate font-mono text-[10px] text-slate-600" title={entry.target_id || ''}>{entry.target_id || '—'}</p>
                        </td>
                        <td><Badge tone={statusTone(String(entry.result || '').toUpperCase())}>{entry.result || '—'}</Badge></td>
                        <td className="max-w-[18rem] text-[11px] text-slate-500">
                          <span className="line-clamp-2" title={entry.reason || ''}>{entry.reason || '—'}</span>
                        </td>
                        <td className="font-mono text-[10px] text-slate-500">{entry.client_ip || '—'}</td>
                        <td className="text-right">
                          <button type="button" className={btnSecondary} onClick={() => setSelectedAudit(entry)}>Open</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <Pagination
              skip={auditSkip}
              limit={AUDIT_LIMIT}
              count={auditLogs.length}
              loading={auditLoading}
              onPrevious={() => setAuditSkip((value) => Math.max(0, value - AUDIT_LIMIT))}
              onNext={() => setAuditSkip((value) => value + AUDIT_LIMIT)}
            />
          </Panel>
        </>
      ) : null}

      {tab === 'consent' ? (
        <>
          <Panel title="Consent filter" subtitle="Every consent transition is recorded with the previous and new state" bodyClassName="p-4">
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                value={consentUser}
                onChange={(event) => setConsentUser(event.target.value)}
                placeholder="Filter by exact user ID"
                className={inputClass}
              />
              <button
                type="button"
                className={btnSecondary}
                onClick={() => setAppliedConsentUser(consentUser.trim())}
              >
                Apply
              </button>
              <button
                type="button"
                className={btnSecondary}
                onClick={() => { setConsentUser(''); setAppliedConsentUser(''); }}
              >
                Clear
              </button>
            </div>
            <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
              DECLINED or REVOKED consent revokes all active endpoint devices server-side, so ingestion
              stops immediately.
            </p>
          </Panel>

          {consentError ? <ErrorState message={consentError} onRetry={() => loadConsent()} /> : null}

          <Panel
            title="Consent history"
            subtitle={`${consentHistory.length} transition${consentHistory.length === 1 ? '' : 's'} in the current view`}
            bodyClassName="p-0"
          >
            {consentLoading ? (
              <LoadingState />
            ) : consentHistory.length === 0 ? (
              <EmptyState
                icon={History}
                title="No consent transitions recorded"
                message="A transition is written when an account selects ALLOWED, DECLINED or REVOKED."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="soc-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>User</th>
                      <th>Previous</th>
                      <th>New</th>
                      <th>Client IP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {consentHistory.map((entry) => (
                      <tr key={entry._id}>
                        <td className="whitespace-nowrap text-slate-400" title={formatDateTime(entry.timestamp)}>{timeAgo(entry.timestamp)}</td>
                        <td className="font-medium text-slate-200">{entry.user_id}</td>
                        <td><Badge tone={consentTone(entry.previous_state)}>{(entry.previous_state || '—').replace('_', ' ')}</Badge></td>
                        <td><Badge tone={consentTone(entry.new_state)}>{(entry.new_state || '—').replace('_', ' ')}</Badge></td>
                        <td className="font-mono text-[10px] text-slate-500">{entry.client_ip || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </>
      ) : null}

      {tab === 'demo' ? (
        <>
          <InlineNotice tone="warning">
            This mode creates clearly-labelled synthetic users, devices and events. It uses the same PII,
            UEBA, risk, alert and incident services as monitored data. Reset removes only this isolated demo data.
          </InlineNotice>
          {demoError ? <ErrorState message={demoError} onRetry={loadDemo} /> : null}
          {demoLoading ? <LoadingState label="Reading synthetic demo status…" /> : (
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <Panel title="Synthetic demo controls" subtitle="Administrative, isolated from real monitoring data">
                <div className="space-y-3 text-sm text-slate-400">
                  <p>Generate normal endpoint activity for Finance, Developer and HR profiles, then a suspicious HR deletion of a finance export. The generated PII analysis, role mismatch, risk assessment, alert and critical incident are derived by the production services.</p>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={generateDemo} className={btnSecondary} disabled={demoBusy}>
                      <ShieldAlert size={14} /> {demoBusy ? 'Generating…' : 'Generate demo run'}
                    </button>
                    <button type="button" onClick={resetDemo} className="inline-flex items-center justify-center gap-2 rounded-lg border border-red-900/60 bg-red-950/20 px-4 py-2 text-sm font-semibold text-red-200 transition hover:bg-red-950/40 disabled:cursor-not-allowed disabled:opacity-60" disabled={demoBusy}>
                      Reset synthetic data
                    </button>
                  </div>
                </div>
              </Panel>
              <Panel title="Demo status" subtitle="Run records are retained only for synthetic data cleanup">
                {(demoStatus?.runs || []).length === 0 ? (
                  <EmptyState icon={ShieldAlert} title="No synthetic run exists" message="Generate a demo run to populate the dashboard using the real processing pipeline." />
                ) : (
                  <div className="space-y-2">
                    {demoStatus.runs.map((run) => (
                      <div key={run.run_id} className="rounded-lg border border-purple-900/40 bg-purple-950/10 p-3">
                        <p className="font-mono text-xs text-purple-200">{run.run_id}</p>
                        <p className="mt-1 text-[11px] text-slate-500">Created {formatDateTime(run.created_at)} · {run.user_ids?.length || 0} synthetic users</p>
                      </div>
                    ))}
                  </div>
                )}
              </Panel>
            </div>
          )}
          {demoResult ? (
            <Panel title="Last demo operation" subtitle="Server response from the live demo API">
              <pre className="custom-scrollbar max-h-72 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-[11px] leading-relaxed text-slate-300">{JSON.stringify(demoResult, null, 2)}</pre>
            </Panel>
          ) : null}
        </>
      ) : null}

      <Drawer
        open={Boolean(selectedAudit)}
        onClose={() => setSelectedAudit(null)}
        title="Audit entry"
        subtitle={selectedAudit?.action}
      >
        {selectedAudit ? (
          <div className="space-y-5">
            <section className="grid grid-cols-2 gap-3">
              <KeyValue label="Timestamp" className="col-span-2">{formatDateTime(selectedAudit.timestamp)}</KeyValue>
              <KeyValue label="Actor">{selectedAudit.actor_id || 'system'}</KeyValue>
              <KeyValue label="Actor role">{selectedAudit.actor_role || '—'}</KeyValue>
              <KeyValue label="Action" className="col-span-2">{selectedAudit.action}</KeyValue>
              <KeyValue label="Target type">{selectedAudit.target_type || '—'}</KeyValue>
              <KeyValue label="Target ID">{selectedAudit.target_id || '—'}</KeyValue>
              <KeyValue label="Result">{selectedAudit.result || '—'}</KeyValue>
              <KeyValue label="Client IP">{selectedAudit.client_ip || '—'}</KeyValue>
              <KeyValue label="Reason" className="col-span-2">{selectedAudit.reason || '—'}</KeyValue>
            </section>
            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-100">Metadata</h3>
              <pre className="custom-scrollbar max-h-72 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-[10px] leading-relaxed text-slate-400">{JSON.stringify(selectedAudit.metadata || {}, null, 2)}</pre>
            </section>
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}
