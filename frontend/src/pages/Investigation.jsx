import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Activity,
  BrainCircuit,
  FileText,
  Laptop,
  Loader2,
  RefreshCw,
  Search,
  ShieldAlert,
  Target,
  Users,
} from 'lucide-react';
import { errorMessage, investigateEvent, investigateUser, searchUsers } from '../api';
import {
  Badge,
  btnPrimary,
  btnSecondary,
  consentTone,
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
  SearchInput,
  severityTone,
  StatCard,
  statusTone,
  timeAgo,
} from '../components/ui';

function countOf(items) {
  return Array.isArray(items) ? items.length : 0;
}

export default function Investigation() {
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [searched, setSearched] = useState(false);

  const [investigatedId, setInvestigatedId] = useState('');
  const [investigation, setInvestigation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [eventOpen, setEventOpen] = useState(false);
  const [eventContext, setEventContext] = useState(null);
  const [eventLoading, setEventLoading] = useState(false);
  const [eventError, setEventError] = useState('');
  const [eventId, setEventId] = useState('');

  const runSearch = useCallback(async (value) => {
    const term = (value || '').trim();
    if (term.length < 2) {
      setSearchError('Enter at least 2 characters to search the user directory.');
      setResults([]);
      return;
    }
    setSearchLoading(true);
    setSearchError('');
    setSearched(true);
    try {
      const found = await searchUsers(term, 25);
      setResults(Array.isArray(found) ? found : []);
    } catch (err) {
      setSearchError(errorMessage(err, 'Could not search the user directory.'));
    } finally {
      setSearchLoading(false);
    }
  }, []);

  const runInvestigation = useCallback(async (userId) => {
    if (!userId) return;
    setInvestigatedId(userId);
    setLoading(true);
    setError('');
    setInvestigation(null);
    try {
      const data = await investigateUser(userId, 50);
      setInvestigation(data);
    } catch (err) {
      setError(errorMessage(err, 'Could not build the investigation view.'));
    } finally {
      setLoading(false);
    }
  }, []);

  const openEventContext = useCallback(async (id) => {
    if (!id) return;
    setEventId(id);
    setEventOpen(true);
    setEventContext(null);
    setEventError('');
    setEventLoading(true);
    try {
      const data = await investigateEvent(id);
      setEventContext(data);
    } catch (err) {
      setEventError(errorMessage(err, 'Could not load event context.'));
    } finally {
      setEventLoading(false);
    }
  }, []);

  useEffect(() => {
    const userParam = searchParams.get('user');
    const eventParam = searchParams.get('event');
    if (userParam) runInvestigation(userParam);
    if (eventParam) openEventContext(eventParam);
    // Only bootstrap from the URL on first mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearchSubmit = () => {
    runSearch(query);
  };

  const user = investigation?.user;
  const devices = investigation?.devices || [];
  const events = investigation?.events || [];
  const alerts = investigation?.alerts || [];
  const incidents = investigation?.incidents || [];
  const risks = investigation?.risk_assessments || [];
  const anomalies = investigation?.anomalies || [];
  const findings = investigation?.pii_findings || [];

  const counts = useMemo(
    () => ({
      events: countOf(events),
      alerts: countOf(alerts),
      incidents: countOf(incidents),
      risks: countOf(risks),
      anomalies: countOf(anomalies.filter((item) => item.is_anomaly)),
      findings: countOf(findings),
    }),
    [events, alerts, incidents, risks, anomalies, findings],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Investigation"
        title="Correlated user and event investigation"
        subtitle="Administrator-only correlation of a user's account, enrolled devices, activity, alerts, incidents, risk assessments, behavioural findings and PII metadata. Every lookup stays inside the live database."
        actions={
          investigatedId ? (
            <button type="button" className={btnSecondary} onClick={() => runInvestigation(investigatedId)} disabled={loading}>
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>
          ) : null
        }
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title="User directory search" subtitle="Search by user ID, email or display name">
          <div className="flex gap-2">
            <SearchInput value={query} onChange={setQuery} onSubmit={handleSearchSubmit} placeholder="At least 2 characters" className="flex-1" />
            <button type="button" className={btnPrimary} onClick={handleSearchSubmit} disabled={searchLoading}>
              {searchLoading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
              Search
            </button>
          </div>
          {searchError ? <p className="mt-2 text-xs text-red-300">{searchError}</p> : null}

          <div className="mt-3">
            {searchLoading ? (
              <LoadingState label="Searching users…" />
            ) : results.length === 0 ? (
              <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-500">
                {searched ? 'No users matched that search.' : 'Search to select a user and correlate their records.'}
              </p>
            ) : (
              <div className="max-h-72 space-y-1.5 overflow-y-auto pr-1">
                {results.map((item) => (
                  <button
                    key={item.user_id}
                    type="button"
                    onClick={() => runInvestigation(item.user_id)}
                    className="flex w-full items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-2 text-left transition hover:border-slate-700 hover:bg-slate-900"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold text-slate-200">{item.display_name || item.user_id}</p>
                      <p className="truncate text-[10px] text-slate-500">{item.user_id}{item.email ? ` · ${item.email}` : ''}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      <Badge tone={consentTone(item.monitoring_enabled)}>{item.monitoring_enabled.replace('_', ' ')}</Badge>
                      <Badge tone="neutral">{formatNumber(item.active_devices)} devices</Badge>
                      <Badge tone={item.open_alerts > 0 ? 'red' : 'green'}>{formatNumber(item.open_alerts)} alerts</Badge>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </Panel>

        <Panel title="Event lookup" subtitle="Open an event and its correlated risk, alert, anomaly and PII records">
          <div className="flex gap-2">
            <input
              value={eventId}
              onChange={(event) => setEventId(event.target.value)}
              onKeyDown={(event) => { if (event.key === 'Enter') openEventContext(eventId.trim()); }}
              placeholder="Paste an event ID"
              className={inputClass}
            />
            <button type="button" className={btnSecondary} onClick={() => openEventContext(eventId.trim())} disabled={eventLoading || eventId.trim().length === 0}>
              {eventLoading ? <Loader2 size={15} className="animate-spin" /> : <ShieldAlert size={15} />}
              Open
            </button>
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
            Event lookup is authorised by the owning user or administrator role. Raw event metadata is
            shown only when the event was persisted by the ingestion pipeline.
          </p>
          {eventError && !eventOpen ? <p className="mt-2 text-xs text-red-300">{eventError}</p> : null}
        </Panel>
      </div>

      {loading ? (
        <LoadingState label="Correlating account, devices and security records…" />
      ) : error ? (
        <ErrorState message={error} onRetry={() => investigatedId && runInvestigation(investigatedId)} />
      ) : investigation ? (
        <>
          <Panel
            title={user?.display_name || user?.user_id || 'User'}
            subtitle={user ? `${user.user_id}${user.email ? ` · ${user.email}` : ''}` : ''}
            actions={
              <div className="flex flex-wrap gap-2">
                <Badge tone={user?.role === 'ADMIN' ? 'blue' : 'neutral'}>{user?.role}</Badge>
                <Badge tone={consentTone(user?.monitoring_enabled)}>{(user?.monitoring_enabled || '').replace('_', ' ')}</Badge>
                <Badge tone={statusTone(user?.enforcement_status)}>{user?.enforcement_status}</Badge>
              </div>
            }
          >
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
              <KeyValue label="Created">{formatDateTime(user?.created_at)}</KeyValue>
              <KeyValue label="Consent updated">{formatDateTime(user?.consent_updated_at)}</KeyValue>
              <KeyValue label="Last login">{user?.last_login_at ? formatDateTime(user.last_login_at) : 'Never'}</KeyValue>
              <KeyValue label="Account active">{user?.is_active ? 'Yes' : 'No'}</KeyValue>
              <KeyValue label="Source">{user?.source || '—'}</KeyValue>
              <KeyValue label="Generated">{formatDateTime(investigation.generated_at)}</KeyValue>
            </div>
          </Panel>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <StatCard label="Events" value={formatNumber(counts.events)} hint="Returned window" icon={Activity} tone="blue" />
            <StatCard label="Alerts" value={formatNumber(counts.alerts)} hint="Returned window" icon={ShieldAlert} tone="red" />
            <StatCard label="Incidents" value={formatNumber(counts.incidents)} hint="Returned window" icon={ShieldAlert} tone="orange" />
            <StatCard label="Risk assessments" value={formatNumber(counts.risks)} hint="Returned window" icon={Target} tone="purple" />
            <StatCard label="Anomalies" value={formatNumber(counts.anomalies)} hint="is_anomaly = true" icon={BrainCircuit} tone="amber" />
            <StatCard label="PII findings" value={formatNumber(counts.findings)} hint="Derived metadata" icon={FileText} tone="cyan" />
          </div>

          <Panel title={`Devices (${devices.length})`} subtitle="Enrolled endpoint credentials; token hashes are never returned" bodyClassName="p-0">
            {devices.length === 0 ? (
              <EmptyState icon={Laptop} title="No enrolled devices" message="This user has no endpoint devices. Enrollment requires ALLOWED consent and an active, unrestricted account." />
            ) : (
              <div className="overflow-x-auto">
                <table className="soc-table">
                  <thead>
                    <tr>
                      <th>Hostname</th>
                      <th>Device ID</th>
                      <th>OS</th>
                      <th>Agent</th>
                      <th>Status</th>
                      <th>Enrolled</th>
                      <th>Heartbeat</th>
                    </tr>
                  </thead>
                  <tbody>
                    {devices.map((device) => (
                      <tr key={device.device_id}>
                        <td className="font-medium text-slate-200">{device.hostname || '—'}</td>
                        <td className="max-w-[16rem] truncate font-mono text-[10px] text-slate-500" title={device.device_id}>{device.device_id}</td>
                        <td className="text-slate-400">{device.os_version || '—'}</td>
                        <td className="text-slate-400">{device.agent_version || '—'}</td>
                        <td><Badge tone={statusTone(device.status)}>{device.status}</Badge></td>
                        <td className="whitespace-nowrap text-slate-400">{formatDateTime(device.enrolled_at)}</td>
                        <td className="whitespace-nowrap text-slate-400">{device.last_heartbeat ? timeAgo(device.last_heartbeat) : 'Never'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Panel title={`Alerts (${alerts.length})`} bodyClassName="p-0">
              {alerts.length === 0 ? (
                <p className="p-4 text-xs text-slate-500">No alerts for this user.</p>
              ) : (
                <div className="max-h-80 overflow-y-auto">
                  {alerts.map((alert) => (
                    <div key={alert._id || alert.id} className="border-b border-slate-800/70 px-4 py-3 last:border-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={severityTone(alert.severity)}>{alert.severity}</Badge>
                        <Badge tone={statusTone(alert.status)}>{alert.status}</Badge>
                        <span className="ml-auto text-[10px] text-slate-500">{timeAgo(alert.timestamp)}</span>
                      </div>
                      <p className="mt-1 text-xs font-semibold text-slate-200">{alert.title}</p>
                      <p className="mt-0.5 text-[11px] text-slate-500">{alert.reason}</p>
                    </div>
                  ))}
                </div>
              )}
            </Panel>

            <Panel title={`Incidents (${incidents.length})`} bodyClassName="p-0">
              {incidents.length === 0 ? (
                <p className="p-4 text-xs text-slate-500">No incidents for this user.</p>
              ) : (
                <div className="max-h-80 overflow-y-auto">
                  {incidents.map((incident) => (
                    <div key={incident._id || incident.id} className="border-b border-slate-800/70 px-4 py-3 last:border-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={severityTone(incident.severity)}>{incident.severity}</Badge>
                        <Badge tone={statusTone(incident.status)}>{incident.status}</Badge>
                        <span className="ml-auto text-[10px] text-slate-500">{timeAgo(incident.created_time)}</span>
                      </div>
                      <p className="mt-1 text-xs font-semibold text-slate-200">{incident.title}</p>
                      <p className="mt-0.5 text-[11px] text-slate-500">{incident.reason}</p>
                      {incident.assigned_to ? <p className="mt-0.5 text-[10px] text-slate-600">Assigned to {incident.assigned_to}</p> : null}
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          </div>

          <Panel title={`Risk assessments (${risks.length})`} bodyClassName="p-0">
            {risks.length === 0 ? (
              <p className="p-4 text-xs text-slate-500">No risk assessments for this user.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="soc-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Category</th>
                      <th>Combined</th>
                      <th>Privacy</th>
                      <th>Behaviour</th>
                      <th>Endpoint</th>
                      <th>Access</th>
                      <th>Explanation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {risks.map((risk) => (
                      <tr key={risk.risk_id}>
                        <td className="whitespace-nowrap text-slate-400" title={formatDateTime(risk.timestamp)}>{timeAgo(risk.timestamp)}</td>
                        <td><Badge tone={severityTone(risk.risk_category)}>{risk.risk_category}</Badge></td>
                        <td className="font-mono text-slate-100">{formatScore(risk.combined_score, 1)}</td>
                        <td className="font-mono text-slate-400">{formatScore(risk.privacy_score, 1)}</td>
                        <td className="font-mono text-slate-400">{formatScore(risk.behavioral_score, 1)}</td>
                        <td className="font-mono text-slate-400">{formatScore(risk.endpoint_score, 1)}</td>
                        <td className="font-mono text-slate-400">{formatScore(risk.access_score, 1)}</td>
                        <td className="max-w-[22rem] text-[11px] text-slate-500">
                          <span className="line-clamp-2" title={(risk.explanation || []).join(' ')}>
                            {(risk.explanation || risk.risk_factors || []).join(' ') || '—'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Panel title={`Behavioural findings (${anomalies.length})`} bodyClassName="p-0">
              {anomalies.length === 0 ? (
                <p className="p-4 text-xs text-slate-500">No behavioural findings for this user.</p>
              ) : (
                <div className="max-h-80 overflow-y-auto">
                  {anomalies.map((finding) => (
                    <div key={finding.anomaly_id} className="border-b border-slate-800/70 px-4 py-3 last:border-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={finding.is_anomaly ? 'red' : 'green'}>{finding.is_anomaly ? 'anomaly' : 'baseline'}</Badge>
                        <span className="font-mono text-[10px] text-slate-500">{finding.anomaly_type}</span>
                        <span className="ml-auto text-[10px] text-slate-500">{timeAgo(finding.timestamp)}</span>
                      </div>
                      <p className="mt-1 text-[11px] text-slate-400">{finding.reason}</p>
                      <p className="mt-0.5 font-mono text-[10px] text-slate-500">rate {formatScore(finding.activity_rate, 2)} · deviation {formatScore(finding.deviation, 2)}</p>
                    </div>
                  ))}
                </div>
              )}
            </Panel>

            <Panel title={`PII findings (${findings.length})`} subtitle="Derived metadata only; raw analysed text is never stored" bodyClassName="p-0">
              {findings.length === 0 ? (
                <p className="p-4 text-xs text-slate-500">No PII findings for this user.</p>
              ) : (
                <div className="max-h-80 overflow-y-auto">
                  {findings.map((finding) => (
                    <div key={finding.finding_id} className="border-b border-slate-800/70 px-4 py-3 last:border-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={finding.category === 'HIGH_RISK' ? 'red' : finding.category === 'SENSITIVE' ? 'amber' : 'green'}>{finding.category}</Badge>
                        <span className="font-mono text-[10px] text-slate-400">score {finding.sensitivity_score}</span>
                        <span className="ml-auto text-[10px] text-slate-500">{timeAgo(finding.timestamp)}</span>
                      </div>
                      <p className="mt-1 text-[11px] text-slate-400">
                        {(finding.entities || []).map((entity) => `${entity.entity_type} ×${entity.count}`).join(', ') || 'No entities'}
                      </p>
                      <p className="mt-0.5 text-[10px] text-slate-600">engine {finding.engine}{finding.file_id ? ` · file ${finding.file_id}` : ''}</p>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          </div>

          <Panel title={`Recent events (${events.length})`} bodyClassName="p-0">
            {events.length === 0 ? (
              <p className="p-4 text-xs text-slate-500">No events for this user.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="soc-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Event type</th>
                      <th>Action</th>
                      <th>Source</th>
                      <th>Application</th>
                      <th>Resource</th>
                      <th className="text-right">Context</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((event) => (
                      <tr key={event.event_id}>
                        <td className="whitespace-nowrap text-slate-400" title={formatDateTime(event.timestamp)}>{timeAgo(event.timestamp)}</td>
                        <td className="font-mono text-[11px] text-slate-300">{event.event_type}</td>
                        <td><Badge tone="neutral">{event.action}</Badge></td>
                        <td><Badge tone={event.source === 'endpoint_agent' ? 'cyan' : event.source === 'saas_proxy' ? 'purple' : 'neutral'}>{event.source}</Badge></td>
                        <td className="text-slate-400">{event.saas_app || '—'}</td>
                        <td className="max-w-[18rem] truncate text-slate-400" title={event.resource_name || event.resource_id || ''}>{event.resource_name || event.resource_id || '—'}</td>
                        <td className="text-right">
                          <button type="button" className={btnSecondary} onClick={() => openEventContext(event.event_id)}>Open</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </>
      ) : (
        <EmptyState
          icon={Users}
          title="No investigation selected"
          message="Search the directory or open a profile from UEBA or Risk Posture. The investigation view is built from live records only."
        />
      )}

      <Drawer
        open={eventOpen}
        onClose={() => setEventOpen(false)}
        title="Event context"
        subtitle={eventId}
      >
        {eventLoading ? (
          <LoadingState label="Correlating event records…" />
        ) : eventError ? (
          <ErrorState message={eventError} onRetry={() => openEventContext(eventId)} />
        ) : eventContext ? (
          <div className="space-y-5">
            <section className="grid grid-cols-2 gap-3">
              <KeyValue label="Event type">{eventContext.event?.event_type}</KeyValue>
              <KeyValue label="Action">{eventContext.event?.action}</KeyValue>
              <KeyValue label="Source">{eventContext.event?.source}</KeyValue>
              <KeyValue label="Timestamp">{formatDateTime(eventContext.event?.timestamp)}</KeyValue>
              <KeyValue label="User">{eventContext.event?.user_id || 'Unverified / none'}</KeyValue>
              <KeyValue label="Device">{eventContext.event?.device_info?.hostname || eventContext.event?.device_id || '—'}</KeyValue>
              <KeyValue label="Application">{eventContext.event?.saas_app || '—'}</KeyValue>
              <KeyValue label="Resource">{eventContext.event?.resource_name || eventContext.event?.resource_id || '—'}</KeyValue>
              <KeyValue label="Correlation ID" className="col-span-2">{eventContext.correlation_id}</KeyValue>
            </section>

            {eventContext.risk_assessment ? (
              <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-100">Risk assessment</h3>
                  <Badge tone={severityTone(eventContext.risk_assessment.risk_category)}>{eventContext.risk_assessment.risk_category}</Badge>
                </div>
                <p className="mt-2 font-mono text-2xl font-bold text-white">
                  {formatScore(eventContext.risk_assessment.combined_score, 1)}
                  <span className="ml-1 text-xs font-normal text-slate-500">/ 100</span>
                </p>
                {(eventContext.risk_assessment.explanation || []).length > 0 ? (
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-[11px] leading-relaxed text-slate-400">
                    {eventContext.risk_assessment.explanation.map((item, index) => <li key={index}>{item}</li>)}
                  </ul>
                ) : null}
              </section>
            ) : null}

            <div className="grid gap-4 sm:grid-cols-2">
              <section>
                <h3 className="mb-2 text-sm font-bold text-slate-100">Alerts ({eventContext.alerts?.length || 0})</h3>
                {(eventContext.alerts || []).length === 0 ? (
                  <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-500">No alerts linked to this event.</p>
                ) : (
                  <div className="space-y-1.5">
                    {eventContext.alerts.map((alert) => (
                      <div key={alert._id || alert.id} className="rounded-md border border-slate-800 bg-slate-900/40 p-3">
                        <div className="flex flex-wrap gap-2">
                          <Badge tone={severityTone(alert.severity)}>{alert.severity}</Badge>
                          <Badge tone={statusTone(alert.status)}>{alert.status}</Badge>
                        </div>
                        <p className="mt-1 text-xs font-semibold text-slate-200">{alert.title}</p>
                        <p className="mt-0.5 text-[11px] text-slate-500">{alert.reason}</p>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section>
                <h3 className="mb-2 text-sm font-bold text-slate-100">Signals</h3>
                <div className="space-y-2">
                  <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Behaviour</p>
                    {eventContext.anomaly ? (
                      <>
                        <p className="mt-1 text-xs text-slate-200">{eventContext.anomaly.is_anomaly ? 'Anomalous activity' : 'Within baseline'}</p>
                        <p className="mt-0.5 text-[11px] text-slate-500">{eventContext.anomaly.reason}</p>
                      </>
                    ) : <p className="mt-1 text-[11px] text-slate-500">No behaviour finding linked.</p>}
                  </div>
                  <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Privacy</p>
                    {eventContext.pii_finding ? (
                      <>
                        <p className="mt-1 text-xs text-slate-200">{eventContext.pii_finding.category} · score {eventContext.pii_finding.sensitivity_score}</p>
                        <p className="mt-0.5 text-[11px] text-slate-500">
                          {(eventContext.pii_finding.entities || []).map((entity) => `${entity.entity_type} ×${entity.count}`).join(', ') || 'No entities'}
                        </p>
                      </>
                    ) : <p className="mt-1 text-[11px] text-slate-500">No PII finding linked.</p>}
                  </div>
                </div>
              </section>
            </div>

            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-100">Related events ({eventContext.related_events?.length || 0})</h3>
              {(eventContext.related_events || []).length === 0 ? (
                <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-500">No related events share this correlation ID.</p>
              ) : (
                <div className="space-y-1.5">
                  {eventContext.related_events.map((event) => (
                    <div key={event.event_id} className="flex items-start justify-between gap-2 rounded-md border border-slate-800 bg-slate-900/30 px-3 py-2">
                      <div className="min-w-0">
                        <p className="truncate font-mono text-[11px] text-slate-300">{event.event_type} · {event.action}</p>
                        <p className="text-[10px] text-slate-500">{formatDateTime(event.timestamp)}</p>
                      </div>
                      <Badge tone={event.event_id === eventContext.event?.event_id ? 'blue' : 'neutral'}>
                        {event.event_id === eventContext.event?.event_id ? 'current' : event.source}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {eventContext.event?.metadata ? (
              <section>
                <h3 className="mb-2 text-sm font-bold text-slate-100">Event metadata</h3>
                <pre className="custom-scrollbar max-h-64 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-[10px] leading-relaxed text-slate-400">{JSON.stringify(eventContext.event.metadata, null, 2)}</pre>
              </section>
            ) : null}
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}
