import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Ban,
  Gavel,
  Laptop,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Target,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  errorMessage,
  getEnforcementRecommendation,
  getEnforcementResponse,
  getEnforcementResponses,
  getRiskAssessments,
  respondToRisk,
  rollbackEnforcement,
} from '../api';
import {
  Badge,
  btnDanger,
  btnPrimary,
  btnSecondary,
  ConfirmDialog,
  Drawer,
  EmptyState,
  ErrorState,
  formatDateTime,
  formatNumber,
  formatScore,
  InlineNotice,
  KeyValue,
  labelClass,
  LoadingState,
  PageHeader,
  Panel,
  selectClass,
  severityTone,
  StatCard,
  statusTone,
  timeAgo,
} from '../components/ui';

const LIMIT = 100;
const CATEGORIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

const ACTION_META = {
  LOG: {
    label: 'Log only',
    tone: 'neutral',
    destructive: false,
    description: 'Record the administrative decision. No account or device state changes.',
  },
  ALERT: {
    label: 'Create alert',
    tone: 'blue',
    destructive: false,
    description: 'Create a medium-severity alert linked to the risk assessment.',
  },
  WARN: {
    label: 'Raise warning',
    tone: 'amber',
    destructive: false,
    description: 'Create a high-severity warning alert linked to the risk assessment.',
  },
  RESTRICT_USER: {
    label: 'Restrict account + revoke devices',
    tone: 'red',
    destructive: true,
    description:
      'Set the account enforcement status to RESTRICTED and revoke every active device. This is an active response and requires confirmation.',
  },
  REVOKE_DEVICES: {
    label: 'Revoke all active devices',
    tone: 'red',
    destructive: true,
    description:
      'Revoke every active endpoint enrollment for this user. Devices must re-enroll with a new one-time token. Requires confirmation.',
  },
};

function actionLabel(action) {
  return ACTION_META[action]?.label || action || '—';
}

function actionTone(action) {
  return ACTION_META[action]?.tone || 'neutral';
}

export default function Enforcement() {
  const { isAdmin, isEditor, isVisitor } = useAuth();
  const canEnforce = isAdmin || isEditor;

  const [risks, setRisks] = useState([]);
  const [responses, setResponses] = useState([]);
  const [category, setCategory] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const [selectedRisk, setSelectedRisk] = useState(null);
  const [recommendation, setRecommendation] = useState(null);
  const [existingResponse, setExistingResponse] = useState(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState('');
  const [actionDraft, setActionDraft] = useState('');
  const [message, setMessage] = useState('');
  const [messageTone, setMessageTone] = useState('success');

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [confirmError, setConfirmError] = useState('');

  const [rollbackTarget, setRollbackTarget] = useState(null);
  const [rollbackBusy, setRollbackBusy] = useState(false);
  const [rollbackError, setRollbackError] = useState('');

  const load = useCallback(
    async ({ silent = false } = {}) => {
      if (silent) setRefreshing(true);
      else setLoading(true);
      setError('');
      try {
        const [riskResult, responseResult] = await Promise.all([
          getRiskAssessments({ limit: LIMIT, category: category || undefined }),
          getEnforcementResponses({ limit: LIMIT, action: actionFilter || undefined }),
        ]);
        setRisks(Array.isArray(riskResult) ? riskResult : []);
        setResponses(Array.isArray(responseResult) ? responseResult : []);
      } catch (err) {
        setError(errorMessage(err, 'Could not load enforcement data.'));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [category, actionFilter],
  );

  useEffect(() => {
    load();
  }, [load]);

  const openReview = useCallback(async (risk) => {
    setSelectedRisk(risk);
    setRecommendation(null);
    setExistingResponse(null);
    setReviewError('');
    setMessage('');
    setConfirmError('');
    setReviewLoading(true);
    try {
      const rec = await getEnforcementRecommendation(risk.risk_id);
      setRecommendation(rec);
      setActionDraft(rec.recommended_action || 'LOG');
      if (rec.existing_response_id) {
        try {
          const existing = await getEnforcementResponse(rec.existing_response_id);
          setExistingResponse(existing);
        } catch {
          setExistingResponse(null);
        }
      }
    } catch (err) {
      setReviewError(errorMessage(err, 'Could not load the enforcement recommendation.'));
    } finally {
      setReviewLoading(false);
    }
  }, []);

  const closeReview = () => {
    setSelectedRisk(null);
    setRecommendation(null);
    setExistingResponse(null);
    setReviewError('');
    setMessage('');
    setConfirmOpen(false);
    setConfirmError('');
  };

  const responseByRisk = useMemo(() => {
    const map = {};
    responses.forEach((item) => {
      map[item.risk_id] = item;
    });
    return map;
  }, [responses]);

  const stats = useMemo(() => {
    const active = responses.filter(
      (item) => ['RESTRICT_USER', 'REVOKE_DEVICES'].includes(item.action_taken) && item.response_status === 'EXECUTED',
    );
    const revoked = responses
      .filter((item) => item.response_status === 'EXECUTED')
      .reduce((total, item) => total + (Number(item.revoked_devices) || 0), 0);
    const rolledBack = responses.filter((item) => item.response_status === 'ROLLED_BACK').length;
    return { active: active.length, revoked, rolledBack };
  }, [responses]);

  const selectedMeta = ACTION_META[actionDraft] || ACTION_META.LOG;
  const alreadyHandled = Boolean(recommendation?.existing_response_id || existingResponse);

  const execute = async (reason) => {
    if (!selectedRisk) return;
    setConfirmBusy(true);
    setConfirmError('');
    try {
      const result = await respondToRisk({
        risk_id: selectedRisk.risk_id,
        action: actionDraft,
        confirm: selectedMeta.destructive,
        reason,
      });
      setExistingResponse(result);
      setConfirmOpen(false);
      setMessage(
        result.response_status === 'ALREADY_HANDLED'
          ? 'This risk assessment already has an enforcement response. No new action was executed.'
          : `Recorded ${result.action_taken} with status ${result.response_status}.`,
      );
      setMessageTone(result.response_status === 'EXECUTED' ? 'success' : 'warning');
      setRecommendation((current) =>
        current ? { ...current, existing_response_id: result.response_id } : current,
      );
      await load({ silent: true });
    } catch (err) {
      setConfirmError(errorMessage(err, 'Could not execute the enforcement response.'));
    } finally {
      setConfirmBusy(false);
    }
  };

  const handleRollback = async (reason) => {
    if (!rollbackTarget) return;
    setRollbackBusy(true);
    setRollbackError('');
    try {
      const updated = await rollbackEnforcement(rollbackTarget.response_id, reason);
      setResponses((items) =>
        items.map((item) => (item.response_id === updated.response_id ? updated : item)),
      );
      if (existingResponse?.response_id === updated.response_id) setExistingResponse(updated);
      setMessage(`Response ${updated.response_id} rolled back.`);
      setMessageTone('success');
      setRollbackTarget(null);
    } catch (err) {
      setRollbackError(errorMessage(err, 'Could not roll back the response.'));
    } finally {
      setRollbackBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Response"
        title="Enforcement"
        subtitle="Review advisory recommendations, execute an administrator-confirmed response, and reverse active restrictions. State changes are written to MongoDB and the audit trail; nothing is described as blocked unless the mutation succeeded."
        actions={
          <button type="button" onClick={() => load({ silent: true })} className={btnSecondary} disabled={refreshing}>
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <StatCard label="Responses loaded" value={formatNumber(responses.length)} hint="Current view" icon={Gavel} tone="blue" loading={loading} />
        <StatCard label="Active restrictions" value={formatNumber(stats.active)} hint="Executed account/device actions" icon={Ban} tone="red" loading={loading} />
        <StatCard label="Devices revoked" value={formatNumber(stats.revoked)} hint="Sum on executed responses" icon={Laptop} tone="orange" loading={loading} />
        <StatCard label="Rolled back" value={formatNumber(stats.rolledBack)} hint="Responses reversed by an admin" icon={RotateCcw} tone="purple" loading={loading} />
      </div>

      <Panel title="Filters" subtitle="Risk queue and response history filters" bodyClassName="p-4">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <select value={category} onChange={(event) => setCategory(event.target.value)} className={selectClass}>
            <option value="">All risk categories</option>
            {CATEGORIES.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={actionFilter} onChange={(event) => setActionFilter(event.target.value)} className={selectClass}>
            <option value="">All response actions</option>
            {Object.keys(ACTION_META).map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <button
            type="button"
            className={btnSecondary}
            onClick={() => { setCategory(''); setActionFilter(''); }}
          >
            Clear filters
          </button>
          <p className="self-center text-[11px] leading-relaxed text-slate-500">
            Recommendations are advisory. An administrator selects and confirms the executed action.
          </p>
        </div>
      </Panel>

      <Panel
        title="Risk assessment queue"
        subtitle="Select an assessment to review the policy recommendation and execute a confirmed response"
        bodyClassName="p-0"
      >
        {loading ? (
          <LoadingState />
        ) : risks.length === 0 ? (
          <EmptyState
            icon={Target}
            title="No risk assessments in this view"
            message="Enforcement can only act on a persisted risk assessment. Adjust the category filter or wait for the risk pipeline to analyse authorised events."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="soc-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>User</th>
                  <th>Category</th>
                  <th>Combined</th>
                  <th>Event</th>
                  <th>Existing response</th>
                  <th className="text-right">Review</th>
                </tr>
              </thead>
              <tbody>
                {risks.map((risk) => {
                  const existing = responseByRisk[risk.risk_id];
                  return (
                    <tr key={risk.risk_id}>
                      <td className="whitespace-nowrap text-slate-400" title={formatDateTime(risk.timestamp)}>{timeAgo(risk.timestamp)}</td>
                      <td className="font-medium text-slate-200">{risk.user_id || '—'}</td>
                      <td><Badge tone={severityTone(risk.risk_category)}>{risk.risk_category}</Badge></td>
                      <td className="font-mono text-slate-200">{formatScore(risk.combined_score, 1)}</td>
                      <td className="max-w-[14rem] truncate font-mono text-[10px] text-slate-500" title={risk.event_id || ''}>{risk.event_id || '—'}</td>
                      <td>
                        {existing ? (
                          <div className="flex flex-wrap items-center gap-1.5">
                            <Badge tone={actionTone(existing.action_taken)}>{existing.action_taken}</Badge>
                            <Badge tone={statusTone(existing.response_status)}>{existing.response_status}</Badge>
                          </div>
                        ) : <span className="text-slate-600">None</span>}
                      </td>
                      <td className="text-right">
                        <button type="button" className={btnSecondary} onClick={() => openReview(risk)}>Review</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel
        title="Response history"
        subtitle={`${responses.length} response${responses.length === 1 ? '' : 's'} in the current view`}
        bodyClassName="p-0"
      >
        {loading ? (
          <LoadingState />
        ) : responses.length === 0 ? (
          <EmptyState
            icon={ShieldCheck}
            title="No enforcement responses yet"
            message="Confirmed actions appear here with their real result. No simulated block events are recorded."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="soc-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>User</th>
                  <th>Risk</th>
                  <th>Action</th>
                  <th>Status</th>
                  <th>Revoked</th>
                  <th>Actor</th>
                  <th>Reason</th>
                  <th className="text-right">Rollback</th>
                </tr>
              </thead>
              <tbody>
                {responses.map((response) => {
                  const canRollback =
                    ['RESTRICT_USER', 'REVOKE_DEVICES'].includes(response.action_taken) &&
                    response.response_status === 'EXECUTED';
                  return (
                    <tr key={response.response_id}>
                      <td className="whitespace-nowrap text-slate-400" title={formatDateTime(response.timestamp)}>{timeAgo(response.timestamp)}</td>
                      <td className="font-medium text-slate-200">{response.user_id}</td>
                      <td><Badge tone={severityTone(response.risk_category)}>{response.risk_category}</Badge></td>
                      <td><Badge tone={actionTone(response.action_taken)}>{response.action_taken}</Badge></td>
                      <td><Badge tone={statusTone(response.response_status)}>{response.response_status}</Badge></td>
                      <td className="font-mono text-slate-300">{formatNumber(response.revoked_devices)}</td>
                      <td className="text-slate-400">{response.actor_id}</td>
                      <td className="max-w-[20rem] text-[11px] text-slate-500">
                        <span className="line-clamp-2" title={response.reason}>{response.reason}</span>
                        {response.rollback_reason ? (
                          <span className="mt-0.5 block text-[10px] text-blue-300/80">
                            Rolled back by {response.rollback_by}: {response.rollback_reason}
                          </span>
                        ) : null}
                      </td>
                      <td className="text-right">
                        {canRollback ? (
                          <button type="button" className={btnDanger} onClick={() => { setRollbackError(''); setRollbackTarget(response); }}>
                            Roll back
                          </button>
                        ) : (
                          <span className="text-[10px] text-slate-600">
                            {response.response_status === 'ROLLED_BACK' ? formatDateTime(response.rolled_back_at) : '—'}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Drawer
        open={Boolean(selectedRisk)}
        onClose={closeReview}
        title="Enforcement review"
        subtitle={selectedRisk ? `${selectedRisk.user_id} · ${selectedRisk.risk_category}` : ''}
        footer={
          selectedRisk ? (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <button type="button" className={btnSecondary} onClick={closeReview}>Close</button>
              {canEnforce ? (
                <button
                  type="button"
                  className={selectedMeta.destructive ? btnDanger : btnPrimary}
                  onClick={() => { setConfirmError(''); setConfirmOpen(true); }}
                  disabled={reviewLoading || reviewError || !recommendation || alreadyHandled}
                >
                  {selectedMeta.destructive ? <Ban size={15} /> : <Gavel size={15} />}
                  Execute response
                </button>
              ) : null}
            </div>
          ) : null
        }
      >
        {reviewLoading ? (
          <LoadingState label="Loading advisory recommendation…" />
        ) : reviewError ? (
          <ErrorState message={reviewError} onRetry={() => selectedRisk && openReview(selectedRisk)} />
        ) : selectedRisk && recommendation ? (
          <div className="space-y-5">
            {message ? <InlineNotice tone={messageTone}>{message}</InlineNotice> : null}

            <section className="grid grid-cols-2 gap-3">
              <KeyValue label="Risk ID" className="col-span-2">{selectedRisk.risk_id}</KeyValue>
              <KeyValue label="User">{selectedRisk.user_id}</KeyValue>
              <KeyValue label="Category"><Badge tone={severityTone(selectedRisk.risk_category)}>{selectedRisk.risk_category}</Badge></KeyValue>
              <KeyValue label="Combined score">{formatScore(selectedRisk.combined_score, 1)}</KeyValue>
              <KeyValue label="Event">{selectedRisk.event_id || '—'}</KeyValue>
              <KeyValue label="Current account status">{recommendation.current_enforcement_status || '—'}</KeyValue>
              <KeyValue label="Active devices">{formatNumber(recommendation.active_devices)}</KeyValue>
              <KeyValue label="Recommended action">
                <Badge tone={actionTone(recommendation.recommended_action)}>{recommendation.recommended_action}</Badge>
              </KeyValue>
              <KeyValue label="Confirmation required">{recommendation.requires_confirmation ? 'Yes' : 'No'}</KeyValue>
            </section>

            <InlineNotice tone="info">
              The recommendation comes from documented server-side policy and is advisory. You choose the
              executed action below; active account/device changes require explicit confirmation and are
              audited.
            </InlineNotice>

            {alreadyHandled ? (
              <InlineNotice tone="warning">
                This risk assessment already has an enforcement response
                {existingResponse ? ` (${existingResponse.action_taken}, ${existingResponse.response_status})` : ''}.
                The backend will not execute a second action for the same assessment.
              </InlineNotice>
            ) : null}

            {existingResponse ? (
              <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
                <h3 className="mb-2 text-sm font-bold text-slate-100">Existing response</h3>
                <div className="grid grid-cols-2 gap-3">
                  <KeyValue label="Response ID" className="col-span-2">{existingResponse.response_id}</KeyValue>
                  <KeyValue label="Action">{existingResponse.action_taken}</KeyValue>
                  <KeyValue label="Status">{existingResponse.response_status}</KeyValue>
                  <KeyValue label="Actor">{existingResponse.actor_id}</KeyValue>
                  <KeyValue label="Time">{formatDateTime(existingResponse.timestamp)}</KeyValue>
                  <KeyValue label="Devices revoked">{formatNumber(existingResponse.revoked_devices)}</KeyValue>
                  <KeyValue label="Reason" className="col-span-2">{existingResponse.reason}</KeyValue>
                  {existingResponse.rollback_reason ? (
                    <KeyValue label="Rollback" className="col-span-2">
                      {existingResponse.rollback_by} · {existingResponse.rollback_reason} · {formatDateTime(existingResponse.rolled_back_at)}
                    </KeyValue>
                  ) : null}
                </div>
              </section>
            ) : null}

            <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
              <label className={labelClass} htmlFor="enforcement-action">Response action</label>
              <select
                id="enforcement-action"
                value={actionDraft}
                onChange={(event) => setActionDraft(event.target.value)}
                className={selectClass}
                disabled={alreadyHandled}
              >
                {Object.entries(ACTION_META).map(([key, meta]) => (
                  <option key={key} value={key}>{meta.label}</option>
                ))}
              </select>
              <p className="mt-2 text-[11px] leading-relaxed text-slate-400">{selectedMeta.description}</p>
              {recommendation.requires_confirmation && actionDraft === recommendation.recommended_action ? (
                <p className="mt-2 flex items-center gap-1.5 text-[11px] text-amber-300">
                  <ShieldAlert size={13} /> The policy recommendation is an active response.
                </p>
              ) : null}
            </section>

            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-100">Why this assessment scored this way</h3>
              <ul className="list-disc space-y-1 pl-5 text-[11px] leading-relaxed text-slate-400">
                {(selectedRisk.explanation || selectedRisk.risk_factors || []).length > 0 ? (
                  (selectedRisk.explanation || selectedRisk.risk_factors).map((item, index) => <li key={index}>{item}</li>)
                ) : (
                  <li>No explanation stored for this assessment.</li>
                )}
              </ul>
            </section>
          </div>
        ) : null}
      </Drawer>

      <ConfirmDialog
        open={confirmOpen}
        title={selectedMeta.destructive ? 'Confirm active enforcement' : 'Confirm response'}
        message={
          <span>
            <strong className="text-slate-200">{actionLabel(actionDraft)}</strong> will be executed for{' '}
            <strong className="text-slate-200">{selectedRisk?.user_id}</strong>.
            {selectedMeta.destructive
              ? ' This changes the account or endpoint state immediately and revokes active device credentials.'
              : ' This records an administrative response and may create an alert.'}{' '}
            The action and reason are written to the audit trail.
          </span>
        }
        confirmLabel={selectedMeta.destructive ? 'Execute active response' : 'Execute response'}
        tone={selectedMeta.destructive ? 'danger' : 'primary'}
        requireReason
        busy={confirmBusy}
        error={confirmError}
        onClose={() => { if (!confirmBusy) { setConfirmOpen(false); setConfirmError(''); } }}
        onConfirm={execute}
      />

      <ConfirmDialog
        open={Boolean(rollbackTarget)}
        title="Roll back this response?"
        message={
          <span>
            The restriction created by <strong className="text-slate-200">{rollbackTarget?.action_taken}</strong> for{' '}
            <strong className="text-slate-200">{rollbackTarget?.user_id}</strong> will be reversed where applicable.
            Revoked devices must enroll again with a new one-time token.
          </span>
        }
        confirmLabel="Roll back response"
        tone="primary"
        requireReason
        busy={rollbackBusy}
        error={rollbackError}
        onClose={() => { if (!rollbackBusy) { setRollbackTarget(null); setRollbackError(''); } }}
        onConfirm={handleRollback}
      />
    </div>
  );
}
