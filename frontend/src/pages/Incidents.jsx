import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  CheckCircle2,
  ClipboardList,
  Loader2,
  Plus,
  RefreshCw,
  ShieldAlert,
  UserCog,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  addIncidentNote,
  assignIncident,
  createIncident,
  errorMessage,
  getIncident,
  getIncidents,
  updateIncidentStatus,
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
const STATUSES = ['OPEN', 'INVESTIGATING', 'CONTAINED', 'RESOLVED', 'DISMISSED'];

const emptyForm = {
  title: '',
  severity: 'HIGH',
  user_id: '',
  saas_app: '',
  resource_id: '',
  reason: '',
  risk_score: '',
  assigned_to: '',
  related_alerts: '',
  related_events: '',
};

function splitIds(value) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function Incidents() {
  const { isAdmin, isEditor, isVisitor } = useAuth();
  const canTriage = isAdmin || isEditor;

  const [incidents, setIncidents] = useState([]);
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
  const [assignee, setAssignee] = useState('');
  const [noteInput, setNoteInput] = useState('');
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState('');
  const [actionMessage, setActionMessage] = useState('');

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState(emptyForm);
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState('');
  const [createSuccess, setCreateSuccess] = useState('');

  const load = useCallback(
    async ({ silent = false, nextSkip = skip } = {}) => {
      if (silent) setRefreshing(true);
      else setLoading(true);
      setError('');
      try {
        const result = await getIncidents({
          limit: LIMIT,
          skip: nextSkip,
          severity: severity || undefined,
          status: status || undefined,
          q: appliedQuery || undefined,
          user_id: (isAdmin || isEditor || isVisitor) ? appliedUserId || undefined : undefined,
        });
        setIncidents(Array.isArray(result) ? result : []);
      } catch (err) {
        setError(errorMessage(err, 'Could not load incidents.'));
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

  const openIncident = useCallback(async (incident) => {
    setSelectedId(incident.id);
    setSelected(incident);
    setDetailError('');
    setActionError('');
    setActionMessage('');
    setStatusDraft(incident.status);
    setStatusNote('');
    setAssignee(incident.assigned_to || '');
    setNoteInput('');
    setDetailLoading(true);
    try {
      const fresh = await getIncident(incident.id);
      setSelected(fresh);
      setStatusDraft(fresh.status);
      setAssignee(fresh.assigned_to || '');
    } catch (err) {
      setDetailError(errorMessage(err, 'Could not load incident details.'));
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
  };

  const replaceIncident = (updated) => {
    if (!updated) return;
    setIncidents((items) => items.map((item) => (item.id === updated.id ? updated : item)));
    if (selectedId && updated.id === selectedId) {
      setSelected(updated);
      setStatusDraft(updated.status);
      setAssignee(updated.assigned_to || '');
    }
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

  const handleStatus = async () => {
    if (!selected) return;
    setActionBusy(true);
    setActionError('');
    setActionMessage('');
    try {
      const updated = await updateIncidentStatus(selected.id, statusDraft, statusNote.trim() || undefined);
      replaceIncident(updated);
      setStatusNote('');
      setActionMessage(`Incident status updated to ${updated.status}.`);
    } catch (err) {
      setActionError(errorMessage(err, 'Could not update the incident status.'));
    } finally {
      setActionBusy(false);
    }
  };

  const handleAssign = async () => {
    if (!selected || assignee.trim().length === 0) return;
    setActionBusy(true);
    setActionError('');
    setActionMessage('');
    try {
      const updated = await assignIncident(selected.id, assignee.trim());
      replaceIncident(updated);
      setActionMessage(`Incident assigned to ${updated.assigned_to}.`);
    } catch (err) {
      setActionError(errorMessage(err, 'Could not assign the incident.'));
    } finally {
      setActionBusy(false);
    }
  };

  const handleNote = async () => {
    if (!selected || noteInput.trim().length === 0) return;
    setActionBusy(true);
    setActionError('');
    setActionMessage('');
    try {
      const updated = await addIncidentNote(selected.id, noteInput.trim());
      replaceIncident(updated);
      setNoteInput('');
      setActionMessage('Note appended to the incident history.');
    } catch (err) {
      setActionError(errorMessage(err, 'Could not add the note.'));
    } finally {
      setActionBusy(false);
    }
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    setCreateError('');
    setCreateSuccess('');
    if (createForm.reason.trim().length === 0) {
      setCreateError('A reason is required.');
      return;
    }
    setCreateBusy(true);
    try {
      const payload = {
        title: createForm.title.trim(),
        severity: createForm.severity,
        status: 'OPEN',
        user_id: createForm.user_id.trim() || null,
        saas_app: createForm.saas_app.trim() || null,
        resource_id: createForm.resource_id.trim() || null,
        reason: createForm.reason.trim(),
        risk_score: createForm.risk_score === '' ? null : Number(createForm.risk_score),
        related_alerts: splitIds(createForm.related_alerts),
        related_events: splitIds(createForm.related_events),
        assigned_to: createForm.assigned_to.trim() || null,
        evidence: [],
        notes: [],
      };
      const created = await createIncident(payload);
      setCreateSuccess(`Created incident ${created.id}.`);
      setCreateForm(emptyForm);
      load({ silent: true, nextSkip: 0 });
    } catch (err) {
      setCreateError(errorMessage(err, 'Could not create the incident.'));
    } finally {
      setCreateBusy(false);
    }
  };

  const pageCounts = useMemo(() => {
    const counts = { total: incidents.length, open: 0, contained: 0, critical: 0 };
    incidents.forEach((item) => {
      if (['OPEN', 'INVESTIGATING'].includes(item.status)) counts.open += 1;
      if (item.status === 'CONTAINED') counts.contained += 1;
      if (item.severity === 'CRITICAL') counts.critical += 1;
    });
    return counts;
  }, [incidents]);

  const history = selected?.history || [];
  const notes = selected?.notes || [];
  const responseHistory = selected?.response_history || [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Response"
        title="Incidents"
        subtitle="Correlated investigations created from alerts, administrative review or confirmed response actions. Status, assignment and notes are admin-only and audited."
        actions={
          <>
            <button type="button" onClick={() => load({ silent: true })} className={btnSecondary} disabled={refreshing}>
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
              Refresh
            </button>
            {canTriage ? (
              <button type="button" className={btnPrimary} onClick={() => { setCreateOpen(true); setCreateError(''); setCreateSuccess(''); }}>
                <Plus size={15} />
                New incident
              </button>
            ) : null}
          </>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <StatCard label="Incidents in page" value={formatNumber(pageCounts.total)} hint="Current page only" icon={ShieldAlert} tone="blue" loading={loading} />
        <StatCard label="Open / investigating" value={formatNumber(pageCounts.open)} hint="Current page only" icon={ShieldAlert} tone="red" loading={loading} />
        <StatCard label="Contained" value={formatNumber(pageCounts.contained)} hint="Current page only" icon={CheckCircle2} tone="purple" loading={loading} />
        <StatCard label="Critical" value={formatNumber(pageCounts.critical)} hint="Current page only" icon={ShieldAlert} tone="orange" loading={loading} />
      </div>

      <Panel title="Filters" subtitle="Filters are applied by the backend within your authorised scope." bodyClassName="p-4">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-6">
          <SearchInput value={query} onChange={setQuery} onSubmit={applyFilters} placeholder="Search title, reason or assignee" className="xl:col-span-2" />
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

      <Panel title="Incident queue" subtitle={`${incidents.length} incident${incidents.length === 1 ? '' : 's'} in the current page`} bodyClassName="p-0">
        {loading ? (
          <LoadingState />
        ) : incidents.length === 0 ? (
          <EmptyState
            icon={ShieldAlert}
            title="No incidents match this view"
            message="Create an incident manually, or promote an alert from the Alerts page. Incidents are never generated as placeholder data."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="soc-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Incident</th>
                  <th>User / app</th>
                  <th>Risk</th>
                  <th>Status</th>
                  <th>Assignee</th>
                  <th>Created</th>
                  <th className="text-right">Details</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((incident) => (
                  <tr key={incident.id}>
                    <td><Badge tone={severityTone(incident.severity)}>{incident.severity}</Badge></td>
                    <td className="max-w-[22rem]">
                      <p className="truncate font-semibold text-slate-100" title={incident.title}>{incident.title}</p>
                      <p className="truncate text-[11px] text-slate-500" title={incident.reason}>{incident.reason}</p>
                      <p className="truncate font-mono text-[10px] text-slate-600">{incident.id}</p>
                    </td>
                    <td>
                      <p className="text-slate-300">{incident.user_id || '—'}</p>
                      <p className="text-[11px] text-slate-500">{incident.saas_app || '—'}</p>
                    </td>
                    <td className="font-mono text-slate-300">{formatScore(incident.risk_score, 1)}</td>
                    <td><Badge tone={statusTone(incident.status)}>{incident.status}</Badge></td>
                    <td className="text-slate-400">{incident.assigned_to || <span className="text-slate-600">Unassigned</span>}</td>
                    <td className="whitespace-nowrap text-slate-400" title={formatDateTime(incident.created_time)}>{timeAgo(incident.created_time)}</td>
                    <td className="text-right">
                      <button type="button" className={btnSecondary} onClick={() => openIncident(incident)}>Open</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination skip={skip} limit={LIMIT} count={incidents.length} loading={loading} onPrevious={() => setSkip((value) => Math.max(0, value - LIMIT))} onNext={() => setSkip((value) => value + LIMIT)} />
      </Panel>

      <Drawer
        open={Boolean(selected)}
        onClose={closeDetail}
        title={selected?.title || 'Incident details'}
        subtitle={selected ? `${selected.severity} · ${selected.id}` : ''}
        footer={
          selected ? (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap gap-2">
                <Badge tone={severityTone(selected.severity)}>{selected.severity}</Badge>
                <Badge tone={statusTone(selected.status)}>{selected.status}</Badge>
                {selected.assigned_to ? <Badge tone="blue">{selected.assigned_to}</Badge> : null}
              </div>
              <button type="button" className={btnSecondary} onClick={closeDetail}>Close</button>
            </div>
          ) : null
        }
      >
        {detailLoading ? (
          <LoadingState label="Loading incident record…" />
        ) : detailError ? (
          <ErrorState message={detailError} onRetry={() => selected && openIncident(selected)} />
        ) : selected ? (
          <div className="space-y-5">
            <section className="grid grid-cols-2 gap-3">
              <KeyValue label="Incident ID" className="col-span-2">{selected.id}</KeyValue>
              <KeyValue label="User">{selected.user_id || '—'}</KeyValue>
              <KeyValue label="Application">{selected.saas_app || '—'}</KeyValue>
              <KeyValue label="Resource">{selected.resource_id || '—'}</KeyValue>
              <KeyValue label="Risk score">{formatScore(selected.risk_score, 1)}</KeyValue>
              <KeyValue label="Created">{formatDateTime(selected.created_time)}</KeyValue>
              <KeyValue label="Updated">{formatDateTime(selected.updated_at)}</KeyValue>
              <KeyValue label="Related alerts" className="col-span-2">
                {(selected.related_alerts || []).length > 0 ? (selected.related_alerts || []).join(', ') : '—'}
              </KeyValue>
              <KeyValue label="Related events" className="col-span-2">
                {(selected.related_events || []).length > 0 ? (selected.related_events || []).join(', ') : '—'}
              </KeyValue>
            </section>

            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-100">Reason</h3>
              <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs leading-relaxed text-slate-300">{selected.reason}</p>
            </section>

            {actionMessage ? <InlineNotice tone="success">{actionMessage}</InlineNotice> : null}
            {actionError ? <InlineNotice tone="danger">{actionError}</InlineNotice> : null}

            {canTriage ? (
              <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
                <h3 className="text-sm font-bold text-slate-100">Triage</h3>
                <p className="mt-0.5 text-[11px] text-slate-500">All changes are recorded in the audit trail.</p>

                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <div>
                    <label className={labelClass} htmlFor="incident-status">Status</label>
                    <select id="incident-status" value={statusDraft} onChange={(event) => setStatusDraft(event.target.value)} className={selectClass}>
                      {STATUSES.map((item) => <option key={item} value={item}>{item}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className={labelClass} htmlFor="incident-status-note">Status note (optional)</label>
                    <input id="incident-status-note" value={statusNote} onChange={(event) => setStatusNote(event.target.value)} maxLength={2000} placeholder="Context for the status change" className={inputClass} />
                  </div>
                </div>
                <div className="mt-2 flex justify-end">
                  <button type="button" className={btnPrimary} onClick={handleStatus} disabled={actionBusy || statusDraft === selected.status}>
                    {actionBusy ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
                    Update status
                  </button>
                </div>

                <div className="mt-4 border-t border-slate-800 pt-3">
                  <label className={labelClass} htmlFor="incident-assignee">Assign to (user ID or analyst name)</label>
                  <div className="flex gap-2">
                    <input id="incident-assignee" value={assignee} onChange={(event) => setAssignee(event.target.value)} maxLength={64} placeholder="e.g. alice.analyst" className={inputClass} />
                    <button type="button" className={btnSecondary} onClick={handleAssign} disabled={actionBusy || assignee.trim().length === 0}>
                      {actionBusy ? <Loader2 size={15} className="animate-spin" /> : <UserCog size={15} />}
                      Assign
                    </button>
                  </div>
                </div>

                <div className="mt-4 border-t border-slate-800 pt-3">
                  <label className={labelClass} htmlFor="incident-note">Append note</label>
                  <textarea id="incident-note" rows={2} value={noteInput} onChange={(event) => setNoteInput(event.target.value)} maxLength={4000} placeholder="Add investigative context" className={inputClass} />
                  <div className="mt-2 flex justify-end">
                    <button type="button" className={btnSecondary} onClick={handleNote} disabled={actionBusy || noteInput.trim().length === 0}>
                      {actionBusy ? <Loader2 size={15} className="animate-spin" /> : <ClipboardList size={15} />}
                      Add note
                    </button>
                  </div>
                </div>
              </section>
            ) : null}

            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-100">Analyst notes ({notes.length})</h3>
              {notes.length === 0 ? (
                <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-500">No analyst notes yet.</p>
              ) : (
                <div className="space-y-1.5">
                  {[...notes].reverse().map((entry, index) => (
                    <div key={`${entry.timestamp || 'note'}-${index}`} className="rounded-md border border-slate-800 bg-slate-900/40 px-3 py-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-[11px] font-semibold text-slate-200">{entry.author || 'analyst'}</span>
                        <span className="text-[10px] text-slate-500">{formatDateTime(entry.timestamp)}</span>
                      </div>
                      <p className="mt-1 whitespace-pre-wrap text-[11px] leading-relaxed text-slate-400">{entry.note}</p>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-100">History</h3>
              {history.length === 0 && responseHistory.length === 0 ? (
                <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-500">No history entries yet.</p>
              ) : (
                <div className="space-y-1.5">
                  {[...history].reverse().map((entry, index) => (
                    <div key={`${entry.timestamp || 'history'}-${index}`} className="rounded-md border border-slate-800 bg-slate-900/40 px-3 py-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-[11px] font-semibold text-slate-200">{entry.action || 'update'}</span>
                        <span className="text-[10px] text-slate-500">{formatDateTime(entry.timestamp)}</span>
                      </div>
                      <p className="mt-0.5 text-[10px] text-slate-500">by {entry.actor || 'system'}</p>
                      {entry.detail ? <p className="mt-1 text-[11px] leading-relaxed text-slate-400">{entry.detail}</p> : null}
                    </div>
                  ))}
                  {[...responseHistory].reverse().map((line, index) => (
                    <div key={`response-${index}`} className="rounded-md border border-slate-800 bg-slate-950/40 px-3 py-2 text-[11px] text-slate-400">
                      {line}
                    </div>
                  ))}
                </div>
              )}
            </section>

            {(selected.evidence || []).length > 0 ? (
              <section>
                <h3 className="mb-2 text-sm font-bold text-slate-100">Evidence</h3>
                <pre className="custom-scrollbar max-h-64 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-[10px] leading-relaxed text-slate-400">{JSON.stringify(selected.evidence, null, 2)}</pre>
              </section>
            ) : null}
          </div>
        ) : null}
      </Drawer>

      <Drawer
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create an incident"
        subtitle="Administrative case creation. Nothing is auto-filled from placeholder data."
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className={labelClass} htmlFor="incident-title">Title</label>
            <input id="incident-title" className={inputClass} value={createForm.title} onChange={(event) => setCreateForm({ ...createForm, title: event.target.value })} maxLength={200} required placeholder="Short incident title" />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className={labelClass} htmlFor="incident-severity">Severity</label>
              <select id="incident-severity" className={selectClass} value={createForm.severity} onChange={(event) => setCreateForm({ ...createForm, severity: event.target.value })}>
                {SEVERITIES.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </div>
            <div>
              <label className={labelClass} htmlFor="incident-risk">Risk score (optional)</label>
              <input id="incident-risk" type="number" min="0" max="100" step="0.1" className={inputClass} value={createForm.risk_score} onChange={(event) => setCreateForm({ ...createForm, risk_score: event.target.value })} placeholder="0–100" />
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className={labelClass} htmlFor="incident-user">User ID (optional)</label>
              <input id="incident-user" className={inputClass} value={createForm.user_id} onChange={(event) => setCreateForm({ ...createForm, user_id: event.target.value })} maxLength={64} placeholder="e.g. bob" />
            </div>
            <div>
              <label className={labelClass} htmlFor="incident-assignee-new">Assignee (optional)</label>
              <input id="incident-assignee-new" className={inputClass} value={createForm.assigned_to} onChange={(event) => setCreateForm({ ...createForm, assigned_to: event.target.value })} maxLength={64} placeholder="e.g. alice.analyst" />
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className={labelClass} htmlFor="incident-app">SaaS application (optional)</label>
              <input id="incident-app" className={inputClass} value={createForm.saas_app} onChange={(event) => setCreateForm({ ...createForm, saas_app: event.target.value })} maxLength={64} placeholder="e.g. google_drive" />
            </div>
            <div>
              <label className={labelClass} htmlFor="incident-resource">Resource ID (optional)</label>
              <input id="incident-resource" className={inputClass} value={createForm.resource_id} onChange={(event) => setCreateForm({ ...createForm, resource_id: event.target.value })} maxLength={256} />
            </div>
          </div>
          <div>
            <label className={labelClass} htmlFor="incident-reason">Reason</label>
            <textarea id="incident-reason" rows={4} className={inputClass} value={createForm.reason} onChange={(event) => setCreateForm({ ...createForm, reason: event.target.value })} maxLength={4000} required placeholder="What happened and why is this an incident?" />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className={labelClass} htmlFor="incident-alerts">Related alert IDs (comma separated)</label>
              <input id="incident-alerts" className={inputClass} value={createForm.related_alerts} onChange={(event) => setCreateForm({ ...createForm, related_alerts: event.target.value })} placeholder="alert-id-1, alert-id-2" />
            </div>
            <div>
              <label className={labelClass} htmlFor="incident-events">Related event IDs (comma separated)</label>
              <input id="incident-events" className={inputClass} value={createForm.related_events} onChange={(event) => setCreateForm({ ...createForm, related_events: event.target.value })} placeholder="event-id-1, event-id-2" />
            </div>
          </div>

          {createError ? <InlineNotice tone="danger">{createError}</InlineNotice> : null}
          {createSuccess ? <InlineNotice tone="success">{createSuccess}</InlineNotice> : null}

          <div className="flex justify-end gap-2 border-t border-slate-800 pt-4">
            <button type="button" className={btnSecondary} onClick={() => setCreateOpen(false)}>Close</button>
            <button type="submit" className={btnPrimary} disabled={createBusy}>
              {createBusy ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
              Create incident
            </button>
          </div>
        </form>
      </Drawer>
    </div>
  );
}
