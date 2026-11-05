import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, RefreshCw } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { errorMessage, getEvents, investigateEvent } from '../api';
import {
  Badge,
  btnSecondary,
  Drawer,
  EmptyState,
  ErrorState,
  formatDateTime,
  inputClass,
  KeyValue,
  LoadingState,
  PageHeader,
  Pagination,
  Panel,
  SearchInput,
  selectClass,
  severityTone,
  statusTone,
  timeAgo,
} from '../components/ui';

const LIMIT = 50;
const ACTIONS = ['', 'ACCESS', 'DOWNLOAD', 'UPLOAD', 'MODIFY', 'DELETE', 'SHARE', 'PERMISSION_CHANGE', 'EXECUTE', 'SESSION', 'SYSTEM'];
const SOURCES = ['', 'endpoint_agent', 'saas_proxy', 'offline_analysis'];

export default function LiveActivity() {
  const { isAdmin } = useAuth();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [skip, setSkip] = useState(0);
  const [query, setQuery] = useState('');
  const [appliedQuery, setAppliedQuery] = useState('');
  const [source, setSource] = useState('');
  const [action, setAction] = useState('');
  const [userId, setUserId] = useState('');
  const [appliedUserId, setAppliedUserId] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(true);

  const [selected, setSelected] = useState(null);
  const [context, setContext] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const mounted = useRef(true);

  const load = useCallback(
    async ({ silent = false, nextSkip = skip } = {}) => {
      if (silent) setRefreshing(true);
      else setLoading(true);
      setError('');
      try {
        const result = await getEvents({
          limit: LIMIT,
          skip: nextSkip,
          q: appliedQuery || undefined,
          source: source || undefined,
          action: action || undefined,
          user_id: isAdmin ? appliedUserId || undefined : undefined,
        });
        if (mounted.current) setEvents(Array.isArray(result) ? result : []);
      } catch (err) {
        if (mounted.current) setError(errorMessage(err, 'Could not load activity events.'));
      } finally {
        if (mounted.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [skip, appliedQuery, source, action, appliedUserId, isAdmin],
  );

  useEffect(() => {
    mounted.current = true;
    load();
    return () => {
      mounted.current = false;
    };
  }, [load]);

  useEffect(() => {
    if (!autoRefresh) return undefined;
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') load({ silent: true, nextSkip: skip });
    }, 10000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, load, skip]);

  const applyFilters = () => {
    setSkip(0);
    setAppliedQuery(query.trim());
    setAppliedUserId(userId.trim());
    if (skip === 0) load({ nextSkip: 0 });
  };

  const openEvent = async (event) => {
    setSelected(event);
    setContext(null);
    setDetailError('');
    setDetailLoading(true);
    try {
      const result = await investigateEvent(event.event_id);
      setContext(result);
    } catch (err) {
      setDetailError(errorMessage(err, 'Could not load correlated event context.'));
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetail = () => {
    setSelected(null);
    setContext(null);
    setDetailError('');
  };

  const resetFilters = () => {
    setQuery('');
    setAppliedQuery('');
    setSource('');
    setAction('');
    setUserId('');
    setAppliedUserId('');
    setSkip(0);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Telemetry"
        title="Live activity"
        subtitle="Endpoint and SaaS events from your authorised scope. Endpoint identity is derived from the enrolled device; proxy events are explicitly marked identity-unverified."
        actions={
          <>
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-xs font-medium text-slate-300">
              <input type="checkbox" checked={autoRefresh} onChange={(event) => setAutoRefresh(event.target.checked)} className="h-3.5 w-3.5 accent-blue-500" />
              Auto-refresh 10s
            </label>
            <button type="button" className={btnSecondary} onClick={() => load({ silent: true })} disabled={refreshing}>
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
              Refresh
            </button>
          </>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      <Panel title="Filters" bodyClassName="p-4">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-6">
          <SearchInput value={query} onChange={setQuery} onSubmit={applyFilters} placeholder="Search resource or app" className="xl:col-span-2" />
          <select value={source} onChange={(event) => { setSource(event.target.value); setSkip(0); }} className={selectClass}>
            <option value="">All sources</option>
            {SOURCES.filter(Boolean).map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={action} onChange={(event) => { setAction(event.target.value); setSkip(0); }} className={selectClass}>
            <option value="">All actions</option>
            {ACTIONS.filter(Boolean).map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          {isAdmin ? (
            <input value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="Filter by user ID" className={inputClass} />
          ) : <div className="hidden xl:block" />}
          <div className="flex gap-2">
            <button type="button" className={btnSecondary} onClick={applyFilters}>Apply</button>
            <button type="button" className="text-xs font-semibold text-slate-500 hover:text-slate-300" onClick={resetFilters}>Reset</button>
          </div>
        </div>
      </Panel>

      <Panel title="Event stream" subtitle={`${events.length} event${events.length === 1 ? '' : 's'} in the current page`} bodyClassName="p-0">
        {loading ? (
          <LoadingState />
        ) : events.length === 0 ? (
          <EmptyState
            icon={Activity}
            title="No events match this view"
            message="Events require an enrolled endpoint agent with ALLOWED consent, or a SaaS proxy configured with the server-side ingestion key. Events are never fabricated by the frontend."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="soc-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Type</th>
                  <th>Action</th>
                  <th>Source</th>
                  <th>User</th>
                  <th>Application</th>
                  <th>Resource</th>
                  <th>Device</th>
                  <th className="text-right">Context</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.event_id} className="cursor-pointer">
                    <td className="whitespace-nowrap text-slate-400" title={formatDateTime(event.timestamp)}>{timeAgo(event.timestamp)}</td>
                    <td className="font-mono text-[11px] text-slate-300">{event.event_type}</td>
                    <td><Badge tone="neutral">{event.action}</Badge></td>
                    <td><Badge tone={event.source === 'endpoint_agent' ? 'cyan' : event.source === 'saas_proxy' ? 'purple' : 'neutral'}>{event.source}</Badge></td>
                    <td className="text-slate-300">{event.user_id || <span className="text-amber-400">unverified</span>}</td>
                    <td className="text-slate-400">{event.saas_app || '—'}</td>
                    <td className="max-w-[16rem] truncate text-slate-400" title={event.resource_name || event.resource_id || ''}>{event.resource_name || event.resource_id || '—'}</td>
                    <td className="max-w-[10rem] truncate text-[11px] text-slate-500" title={event.device_id || ''}>{event.device_info?.hostname || event.device_id || '—'}</td>
                    <td className="text-right">
                      <button type="button" className={btnSecondary} onClick={() => openEvent(event)}>Open</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination skip={skip} limit={LIMIT} count={events.length} loading={loading} onPrevious={() => setSkip((value) => Math.max(0, value - LIMIT))} onNext={() => setSkip((value) => value + LIMIT)} />
      </Panel>

      <Drawer open={Boolean(selected)} onClose={closeDetail} title="Event context" subtitle={selected?.event_id}>
        {detailLoading ? (
          <LoadingState label="Correlating related events, alerts and risk…" />
        ) : detailError ? (
          <ErrorState message={detailError} onRetry={() => selected && openEvent(selected)} />
        ) : context ? (
          <div className="space-y-5">
            <section className="grid grid-cols-2 gap-3">
              <KeyValue label="Event type">{context.event?.event_type}</KeyValue>
              <KeyValue label="Action">{context.event?.action}</KeyValue>
              <KeyValue label="Source">{context.event?.source}</KeyValue>
              <KeyValue label="Timestamp">{formatDateTime(context.event?.timestamp)}</KeyValue>
              <KeyValue label="User">{context.event?.user_id || <span className="text-amber-300">Unverified proxy identity</span>}</KeyValue>
              <KeyValue label="Device">{context.event?.device_info?.hostname || context.event?.device_id || '—'}</KeyValue>
              <KeyValue label="Application">{context.event?.saas_app || '—'}</KeyValue>
              <KeyValue label="Resource">{context.event?.resource_name || context.event?.resource_id || '—'}</KeyValue>
              <KeyValue label="Correlation ID" className="col-span-2">{context.correlation_id}</KeyValue>
            </section>

            {context.risk_assessment ? (
              <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-100">Risk assessment</h3>
                  <Badge tone={severityTone(context.risk_assessment.risk_category)}>{context.risk_assessment.risk_category}</Badge>
                </div>
                <p className="mt-2 font-mono text-2xl font-bold text-white">{Number(context.risk_assessment.combined_score).toFixed(1)}<span className="ml-1 text-xs font-normal text-slate-500">/ 100</span></p>
                <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] sm:grid-cols-4">
                  {[['Privacy', context.risk_assessment.privacy_score], ['Behaviour', context.risk_assessment.behavioral_score], ['Endpoint', context.risk_assessment.endpoint_score], ['Access', context.risk_assessment.access_score]].map(([label, value]) => (
                    <div key={label} className="rounded-md border border-slate-800 bg-slate-950/40 p-2">
                      <p className="text-slate-500">{label}</p>
                      <p className="font-mono text-slate-200">{Number(value || 0).toFixed(1)}</p>
                    </div>
                  ))}
                </div>
                {(context.risk_assessment.explanation || []).length > 0 ? (
                  <ul className="mt-3 list-disc space-y-1 pl-5 text-[11px] leading-relaxed text-slate-400">
                    {context.risk_assessment.explanation.map((item, index) => <li key={index}>{item}</li>)}
                  </ul>
                ) : null}
              </section>
            ) : null}

            <div className="grid gap-4 sm:grid-cols-2">
              <section>
                <h3 className="mb-2 text-sm font-bold text-slate-100">Alerts ({context.alerts?.length || 0})</h3>
                {(context.alerts || []).length === 0 ? (
                  <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-500">No alerts linked to this event.</p>
                ) : (
                  <div className="space-y-2">
                    {context.alerts.map((alert) => (
                      <div key={alert._id || alert.id} className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={severityTone(alert.severity)}>{alert.severity}</Badge>
                          <Badge tone={statusTone(alert.status)}>{alert.status}</Badge>
                        </div>
                        <p className="mt-1.5 text-xs font-semibold text-slate-200">{alert.title}</p>
                        <p className="mt-0.5 text-[11px] text-slate-500">{alert.reason}</p>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section>
                <h3 className="mb-2 text-sm font-bold text-slate-100">Anomaly &amp; PII signal</h3>
                <div className="space-y-2">
                  <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Behaviour</p>
                    {context.anomaly ? (
                      <>
                        <p className="mt-1 text-xs text-slate-200">{context.anomaly.is_anomaly ? 'Anomalous activity' : 'Within baseline'}</p>
                        <p className="mt-0.5 text-[11px] text-slate-500">{context.anomaly.reason}</p>
                        <p className="mt-1 text-[10px] text-slate-500">Deviation {Number(context.anomaly.deviation || 0).toFixed(2)} · rate {Number(context.anomaly.activity_rate || 0).toFixed(2)}</p>
                      </>
                    ) : (
                      <p className="mt-1 text-[11px] text-slate-500">No behaviour finding linked.</p>
                    )}
                  </div>
                  <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Privacy</p>
                    {context.pii_finding ? (
                      <>
                        <p className="mt-1 text-xs text-slate-200">{context.pii_finding.category} · score {context.pii_finding.sensitivity_score}</p>
                        <p className="mt-0.5 text-[11px] text-slate-500">
                          {(context.pii_finding.entities || []).map((entity) => `${entity.entity_type} ×${entity.count}`).join(', ') || 'No entities'}
                        </p>
                        <p className="mt-1 text-[10px] text-slate-500">Engine: {context.pii_finding.engine}</p>
                      </>
                    ) : (
                      <p className="mt-1 text-[11px] text-slate-500">No PII finding linked.</p>
                    )}
                  </div>
                </div>
              </section>
            </div>

            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-100">Related events ({context.related_events?.length || 0})</h3>
              {(context.related_events || []).length === 0 ? (
                <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-500">No related events share this correlation ID.</p>
              ) : (
                <div className="space-y-1.5">
                  {context.related_events.map((event) => (
                    <div key={event.event_id} className="flex items-start justify-between gap-2 rounded-md border border-slate-800 bg-slate-900/30 px-3 py-2">
                      <div className="min-w-0">
                        <p className="truncate font-mono text-[11px] text-slate-300">{event.event_type} · {event.action}</p>
                        <p className="text-[10px] text-slate-500">{formatDateTime(event.timestamp)}</p>
                      </div>
                      <Badge tone={event.event_id === context.event?.event_id ? 'blue' : 'neutral'}>{event.event_id === context.event?.event_id ? 'current' : event.source}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {context.event?.metadata ? (
              <section>
                <h3 className="mb-2 text-sm font-bold text-slate-100">Event metadata</h3>
                <pre className="custom-scrollbar max-h-64 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-[10px] leading-relaxed text-slate-400">{JSON.stringify(context.event.metadata, null, 2)}</pre>
              </section>
            ) : null}
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}
