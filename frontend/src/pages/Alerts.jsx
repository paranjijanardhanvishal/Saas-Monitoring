import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  ClipboardList,
  Clock,
  Loader2,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  addAlertNote,
  createIncident,
  errorMessage,
  getAlert,
  getAlerts,
  updateAlertStatus,
} from '../api';
import {
  Badge,
  btnPrimary,
  btnSecondary,
  Drawer,
  EmptyState,
  ErrorState,
  formatDateTime,
  formatNumber,
  formatScore,
  InlineNotice,
  inputClass,
  KeyValue,
  labelClass,
  LoadingState,
  PageHeader,
  Pagination,
  Panel,
  SearchInput,
  selectClass,
  severityTone,
  StatCard,
  statusTone,
  timeAgo,
} from '../components/ui';

const LIMIT = 25;
const SEVERITIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
const STATUSES = ['OPEN', 'ACKNOWLEDGED', 'INVESTIGATING', 'RESOLVED', 'DISMISSED'];

function SignalCard({ label, value, weight }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold text-slate-100">{formatScore(value, 1)}</p>
      {weight != null ? <p className="text-[10px] text-slate-600">weight {formatScore(weight, 2)}</p> : null}
    </div>
  );
}

export default function Alerts() {
  const { isAdmin, isEditor, isVisitor } = useAuth();
  const canTriage = isAdmin || isEditor;

  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [skip, setSkip] = useState(0);
  const [query, setQuery] = useState('');
  const [appliedQuery, setAppliedQuery] = useState('');
  const [severity, setSeverity] = useState('');
  const [status, setStatus] = useState('');
  const [userId, setUserId] = useState('');
  const [appliedUserId, setAppliedUserId] = useState('');

  const [selectedId, setSelectedId] = useState('');
  const [selected, setSelected] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');

  const [statusDraft, setStatusDraft] = useState('');
  const [statusNote, setStatusNote] = useState('');
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState('');
  const [actionMessage, setActionMessage] = useState('');

  const [noteInput, setNoteInput] = useState('');
  const [incidentBusy, setIncidentBusy] = useState(false);
  const [incidentMessage, setIncidentMessage] = useState('');

  const load = useCallback(
    async ({ silent = false, nextSkip = skip } = {}) => {
      if (silent) setRefreshing(true);
      else setLoading(true);
      setError('');
      try {
        const result = await getAlerts({
          limit: LIMIT,
          skip: nextSkip,
          severity: severity || undefined,
          status: status || undefined,
          q: appliedQuery || undefined,
          user_id: (isAdmin || isEditor || isVisitor) ? appliedUserId || undefined : undefined,
        });
        setAlerts(Array.isArray(result) ? result : []);
      } catch (err) {
        setError(errorMessage(err, 'Could not load alerts.'));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [skip, severity, status, appliedQuery, appliedUserId, isAdmin, isEditor, isVisitor],
  );

  useEffect(() => {
    load();
  }, [load]);

  const openAlert = useCallback(async (alert) => {
    setSelectedId(alert.id);
    setSelected(alert);
    setDetailError('');
    setActionError('');
    setActionMessage('');
    setIncidentMessage('');
    setStatusDraft(alert.status);
    setStatusNote('');
    setNoteInput('');
    setDetailLoading(true);
    try {
      const fresh = await getAlert(alert.id);
      setSelected(fresh);
      setStatusDraft(fresh.status);
    } catch (err) {
      setDetailError(errorMessage(err, 'Could not load alert details.'));
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const closeDetail = () => {
    setSelectedId('');
    setSelected(null);
    setDetailError('');
    setActionError('');
    setActionMessage('');
    setIncidentMessage('');
  };

  const applyFilters = () => {
    setSkip(0);
    setAppliedQuery(query.trim());
    setAppliedUserId(userId.trim());
    if (skip === 0) load({ nextSkip: 0 });
  };

  const resetFilters = () => {
    setQuery('');
    setAppliedQuery('');
    setSeverity('');
    setStatus('');
    setUserId('');
    setAppliedUserId('');
    setSkip(0);
  };

  const replaceAlert = (updated) => {
    if (!updated) return;
    setAlerts((items) =>
      items.map((item) => (item.id === updated.id ? updated : item)),
    );
    if (selectedId && updated.id === selectedId) {
      setSelected(updated);
      setStatusDraft(updated.status);
    }
  };

  const handleStatusUpdate = async () => {
    if (!selected || !statusDraft) return;
    setActionBusy(true);
    setActionError('');
    setActionMessage('');
    try {
      const updated = await updateAlertStatus(selected.id, statusDraft, statusNote.trim() || undefined);
      replaceAlert(updated);
      setStatusNote('');
      setActionMessage(`Status updated to ${updated.status}.`);
    } catch (err) {
      setActionError(errorMessage(err, 'Could not update the alert status.'));
    } finally {
      setActionBusy(false);
    }
  };

  const handleAddNote = async () => {
    if (!selected || noteInput.trim().length === 0) return;
    setActionBusy(true);
    setActionError('');
    setActionMessage('');
    try {
      const updated = await addAlertNote(selected.id, noteInput.trim());
      replaceAlert(updated);
      setNoteInput('');
      setActionMessage('Note appended to the alert history.');
    } catch (err) {
      setActionError(errorMessage(err, 'Could not add the note.'));
    } finally {
      setActionBusy(false);
    }
  };

  const handleCreateIncident = async () => {
    if (!selected) return;
    setIncidentBusy(true);
    setActionError('');
    setIncidentMessage('');
    try {
      const created = await createIncident({
        title: selected.title,
        severity: selected.severity,
        status: 'OPEN',
        user_id: selected.user_id || null,
        saas_app: selected.saas_app || null,
        resource_id: selected.resource_id || null,
        reason: selected.reason,
        risk_score: selected.risk_score ?? null,
        related_alerts: [selected.id],
        related_events: selected.event_id ? [selected.event_id] : [],
        assigned_to: null,
        evidence: selected.evidence || [],
        notes: [],
      });
      setIncidentMessage(`Incident ${created.id} created from this alert.`);
    } catch (err) {
      setActionError(errorMessage(err, 'Could not create an incident from this alert.'));
    } finally {
      setIncidentBusy(false);
    }
  };

  const pageCounts = useMemo(() => {
    const counts = { total: alerts.length, critical: 0, high: 0, open: 0 };
    alerts.forEach((item) => {
      if (item.severity === 'CRITICAL') counts.critical += 1;
      if (item.severity === 'HIGH') counts.high += 1;
      if (!['RESOLVED', 'DISMISSED'].includes(item.status)) counts.open += 1;
    });
    return counts;
  }, [alerts]);

  const activeAlerts = alerts;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Response"
        title="Alerts"
        subtitle="Alerts produced by the server-side risk pipeline, manual triage or a confirmed enforcement action. Status changes and notes are administrator actions and are written to the audit trail."
        actions={
          <button type="button" onClick={() => load({ silent: true })} className={btnSecondary} disabled={refreshing}>
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <StatCard label="Alerts in page" value={formatNumber(pageCounts.total)} hint="Current page only" icon={Bell} tone="blue" loading={loading} />
        <StatCard label="Critical" value={formatNumber(pageCounts.critical)} hint="Current page only" icon={AlertTriangle} tone="red" loading={loading} />
        <StatCard label="High" value={formatNumber(pageCounts.high)} hint="Current page only" icon={ShieldAlert} tone="orange" loading={loading} />
        <StatCard label="Unresolved" value={formatNumber(pageCounts.open)} hint="Not resolved or dismissed in page" icon={Clock} tone="amber" loading={loading} />
      </div>

      <Panel title="Filters" subtitle="Filters are applied by the backend within your authorised scope." bodyClassName="p-4">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-6">
          <SearchInput value={query} onChange={setQuery} onSubmit={applyFilters} placeholder="Search title or reason" className="xl:col-span-2" />
          <select value={severity} onChange={(event) => { setSeverity(event.target.value); setSkip(0); }} className={selectClass}>
            <option value="">All severities</option>
            {SEVERITIES.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={status} onChange={(event) => { setStatus(event.target.value); setSkip(0); }} className={selectClass}>
            <option value="">All statuses</option>
            {STATUSES.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          {(isAdmin || isEditor || isVisitor) ? (
            <input value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="Filter by user ID" className={inputClass} />
          ) : <div className="hidden xl:block" />}
          <div className="flex items-center gap-2">
            <button type="button" className={btnSecondary} onClick={applyFilters}>Apply</button>
            <button type="button" className="text-xs font-semibold text-slate-500 hover:text-slate-300" onClick={resetFilters}>Reset</button>
          </div>
        </div>
      </Panel>

      <Panel title="Alert queue" subtitle={`${activeAlerts.length} alert${activeAlerts.length === 1 ? '' : 's'} in the current page`} bodyClassName="p-0">
        {loading ? (
          <LoadingState />
        ) : activeAlerts.length === 0 ? (
          <EmptyState
            icon={Bell}
            title="No alerts match this view"
            message="Alerts are created only from real analysed events or explicit administrative actions. Adjust the filters, or ingest authorised activity from an enrolled agent."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="soc-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Alert</th>
                  <th>User</th>
                  <th>Application</th>
                  <th>Risk</th>
                  <th>Status</th>
                  <th>Time</th>
                  <th className="text-right">Details</th>
                </tr>
              </thead>
              <tbody>
                {activeAlerts.map((alert) => (
                  <tr key={alert.id}>
                    <td><Badge tone={severityTone(alert.severity)}>{alert.severity}</Badge></td>
                    <td className="max-w-[20rem]">
                      <p className="truncate font-semibold text-slate-100" title={alert.title}>{alert.title}</p>
                      <p className="truncate text-[11px] text-slate-500" title={alert.reason}>{alert.reason}</p>
                    </td>
                    <td className="text-slate-300">{alert.user_id || <span className="text-amber-400">unverified</span>}</td>
                    <td className="text-slate-400">{alert.saas_app || '—'}</td>
                    <td className="font-mono text-slate-300">{formatScore(alert.risk_score, 1)}</td>
                    <td><Badge tone={statusTone(alert.status)}>{alert.status}</Badge></td>
                    <td className="whitespace-nowrap text-slate-400" title={formatDateTime(alert.timestamp)}>{timeAgo(alert.timestamp)}</td>
                    <td className="text-right">
                      <button type="button" className={btnSecondary} onClick={() => openAlert(alert)}>Open</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination skip={skip} limit={LIMIT} count={activeAlerts.length} loading={loading} onPrevious={() => setSkip((value) => Math.max(0, value - LIMIT))} onNext={() => setSkip((value) => value + LIMIT)} />
      </Panel>

      <Drawer
        open={Boolean(selected)}
        onClose={closeDetail}
        title={selected?.title || 'Alert details'}
        subtitle={selected ? `${selected.severity} · ${selected.id}` : ''}
        footer={
          selected ? (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap gap-2">
                <Badge tone={severityTone(selected.severity)}>{selected.severity}</Badge>
                <Badge tone={statusTone(selected.status)}>{selected.status}</Badge>
                <Badge tone="neutral">{selected.source}</Badge>
              </div>
              <button type="button" className={btnSecondary} onClick={closeDetail}>Close</button>
            </div>
          ) : null
        }
      >
        {detailLoading ? (
          <LoadingState label="Loading alert record…" />
        ) : detailError ? (
          <ErrorState message={detailError} onRetry={() => selected && openAlert(selected)} />
        ) : selected ? (
          <div className="space-y-5">
            <section className="grid grid-cols-2 gap-3">
              <KeyValue label="Alert ID" className="col-span-2">{selected.id}</KeyValue>
              <KeyValue label="User">{selected.user_id || 'Unverified / none'}</KeyValue>
              <KeyValue label="Device">{selected.device_id || '—'}</KeyValue>
              <KeyValue label="Application">{selected.saas_app || '—'}</KeyValue>
              <KeyValue label="Resource">{selected.resource_id || '—'}</KeyValue>
              <KeyValue label="Event">{selected.event_id || '—'}</KeyValue>
              <KeyValue label="Risk assessment">{selected.risk_id || '—'}</KeyValue>
              <KeyValue label="Created">{formatDateTime(selected.timestamp)}</KeyValue>
              <KeyValue label="Updated">{formatDateTime(selected.updated_at)}</KeyValue>
              {selected.acknowledged_by ? (
                <KeyValue label="Acknowledged by" className="col-span-2">
                  {selected.acknowledged_by} · {formatDateTime(selected.acknowledged_at)}
                </KeyValue>
              ) : null}
            </section>

            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-100">Reason</h3>
              <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs leading-relaxed text-slate-300">{selected.reason}</p>
            </section>

            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-100">Signals</h3>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <SignalCard label="Privacy" value={selected.privacy_signal} />
                <SignalCard label="Behaviour" value={selected.behavior_signal} />
                <SignalCard label="Endpoint" value={selected.endpoint_signal} />
                <SignalCard label="Risk score" value={selected.risk_score} />
              </div>
            </section>

            {actionMessage ? <InlineNotice tone="success">{actionMessage}</InlineNotice> : null}
            {actionError ? <InlineNotice tone="danger">{actionError}</InlineNotice> : null}

            {canTriage ? (
              <>
                <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
                  <h3 className="text-sm font-bold text-slate-100">Triage</h3>
                  <p className="mt-0.5 text-[11px] text-slate-500">
                    SOC operators can change alert status or append notes. Every change is
                    recorded in the audit trail.
                  </p>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <div>
                      <label className={labelClass} htmlFor="alert-status">Status</label>
                      <select id="alert-status" value={statusDraft} onChange={(event) => setStatusDraft(event.target.value)} className={selectClass}>
                        {STATUSES.map((item) => <option key={item} value={item}>{item}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className={labelClass} htmlFor="alert-status-note">Status note (optional)</label>
                      <input id="alert-status-note" value={statusNote} onChange={(event) => setStatusNote(event.target.value)} maxLength={1000} placeholder="Why is the status changing?" className={inputClass} />
                    </div>
                  </div>
                  <div className="mt-2 flex justify-end">
                    <button type="button" className={btnPrimary} onClick={handleStatusUpdate} disabled={actionBusy || statusDraft === selected.status}>
                      {actionBusy ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
                      Update status
                    </button>
                  </div>

                  <div className="mt-4 border-t border-slate-800 pt-3">
                    <label className={labelClass} htmlFor="alert-note">Append note</label>
                    <textarea id="alert-note" rows={2} value={noteInput} onChange={(event) => setNoteInput(event.target.value)} maxLength={2000} placeholder="Add analyst context to the alert history" className={inputClass} />
                    <div className="mt-2 flex justify-end">
                      <button type="button" className={btnSecondary} onClick={handleAddNote} disabled={actionBusy || noteInput.trim().length === 0}>
                        {actionBusy ? <Loader2 size={15} className="animate-spin" /> : <ClipboardList size={15} />}
                        Add note
                      </button>
                    </div>
                  </div>

                  <div className="mt-4 border-t border-slate-800 pt-3">
                    <p className="text-[11px] leading-relaxed text-slate-500">
                      Create an incident that references this alert. The incident starts as OPEN and
                      can be assigned and tracked on the Incidents page.
                    </p>
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <button type="button" className={btnPrimary} onClick={handleCreateIncident} disabled={incidentBusy}>
                        {incidentBusy ? <Loader2 size={15} className="animate-spin" /> : <ShieldAlert size={15} />}
                        Create incident
                      </button>
                      <Link to="/incidents" className="text-xs font-semibold text-blue-400 hover:text-blue-300">Open incidents →</Link>
                    </div>
                    {incidentMessage ? <InlineNotice tone="success" className="mt-2">{incidentMessage}</InlineNotice> : null}
                  </div>
                </section>
              </>
            ) : (
              <InlineNotice tone="info">
                This is a read-only view. Alert triage is restricted to SOC administrators.
              </InlineNotice>
            )}

            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-100">Evidence ({selected.evidence?.length || 0})</h3>
              {(selected.evidence || []).length === 0 ? (
                <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-500">No structured evidence attached.</p>
              ) : (
                <pre className="custom-scrollbar max-h-64 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-[10px] leading-relaxed text-slate-400">{JSON.stringify(selected.evidence, null, 2)}</pre>
              )}
            </section>

            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-100">History ({selected.history?.length || 0})</h3>
              {(selected.history || []).length === 0 ? (
                <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-500">No history entries yet.</p>
              ) : (
                <div className="space-y-1.5">
                  {[...(selected.history || [])].reverse().map((entry, index) => (
                    <div key={`${entry.timestamp || 'entry'}-${index}`} className="rounded-md border border-slate-800 bg-slate-900/40 px-3 py-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-[11px] font-semibold text-slate-200">{entry.action || 'update'}</span>
                        <span className="text-[10px] text-slate-500">{formatDateTime(entry.timestamp)}</span>
                      </div>
                      <p className="mt-0.5 text-[10px] text-slate-500">by {entry.actor || 'system'}</p>
                      {entry.detail ? <p className="mt-1 text-[11px] leading-relaxed text-slate-400">{entry.detail}</p> : null}
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}
