import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Check,
  Copy,
  KeyRound,
  Laptop,
  Loader2,
  Plus,
  RefreshCw,
  ShieldCheck,
  ShieldOff,
  UserPlus,
  Users as UsersIcon,
} from 'lucide-react';
import {
  createEnrollmentToken,
  createUser,
  deleteUser,
  errorMessage,
  getUsers,
  getUserDevices,
  getUserSummary,
  revokeAgentDevice,
  updateUser,
  updateUserBusinessRole,
} from '../api';
import { useAuth } from '../context/AuthContext';
import {
  Badge,
  btnDanger,
  btnPrimary,
  btnSecondary,
  ConfirmDialog,
  consentTone,
  Drawer,
  EmptyState,
  ErrorState,
  formatDateTime,
  formatNumber,
  formatScore,
  inputClass,
  InlineNotice,
  KeyValue,
  labelClass,
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

const LIMIT = 25;

const emptyCreateForm = {
  user_id: '',
  email: '',
  display_name: '',
  password: '',
  role: 'USER',
  business_role: 'GENERAL',
};

export default function Users() {
  const { isAdmin, isEditor, isVisitor } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [skip, setSkip] = useState(0);
  const [query, setQuery] = useState('');
  const [appliedQuery, setAppliedQuery] = useState('');
  const [consent, setConsent] = useState('');
  const [role, setRole] = useState('');
  const [businessRole, setBusinessRole] = useState('');

  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState(emptyCreateForm);
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState('');
  const [createSuccess, setCreateSuccess] = useState('');

  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  const [tokenBusy, setTokenBusy] = useState(false);
  const [tokenData, setTokenData] = useState(null);
  const [tokenError, setTokenError] = useState('');
  const [copied, setCopied] = useState(false);

  const [revokeTarget, setRevokeTarget] = useState(null);
  const [revokeBusy, setRevokeBusy] = useState(false);
  const [revokeError, setRevokeError] = useState('');
  const [businessRoleDraft, setBusinessRoleDraft] = useState('GENERAL');
  const [businessRoleBusy, setBusinessRoleBusy] = useState(false);
  const [businessRoleNotice, setBusinessRoleNotice] = useState('');

  const load = useCallback(
    async ({ silent = false, nextSkip = skip } = {}) => {
      if (silent) setRefreshing(true);
      else setLoading(true);
      setError('');
      try {
        const result = await getUsers({
          limit: LIMIT,
          skip: nextSkip,
          q: appliedQuery || undefined,
          consent: consent || undefined,
          role: role || undefined,
          business_role: businessRole || undefined,
          include_pending: true,
        });
        setUsers(Array.isArray(result) ? result : []);
      } catch (err) {
        setError(errorMessage(err, 'Could not load the user directory.'));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [skip, appliedQuery, consent, role, businessRole],
  );

  useEffect(() => {
    load();
  }, [load]);

  const openDetail = useCallback(async (user) => {
    setSelected(user);
    setDetail(null);
    setDetailError('');
    setDetailLoading(true);
    try {
      const [summary, devices] = await Promise.all([
        getUserSummary(user.user_id),
        getUserDevices(user.user_id),
      ]);
      setDetail({ summary, devices: Array.isArray(devices) ? devices : [] });
      setBusinessRoleDraft(summary?.user?.business_role || user.business_role || 'GENERAL');
      setBusinessRoleNotice('');
    } catch (err) {
      setDetailError(errorMessage(err, 'Could not load user details.'));
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const closeDetail = () => {
    setSelected(null);
    setDetail(null);
    setDetailError('');
    setTokenData(null);
    setTokenError('');
  };

  const handleSearch = () => {
    setSkip(0);
    setAppliedQuery(query.trim());
    if (skip === 0) load({ nextSkip: 0 });
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    setCreateError('');
    setCreateSuccess('');
    if (createForm.password.length < 12) {
      setCreateError('Password must be at least 12 characters.');
      return;
    }
    setCreateBusy(true);
    try {
      const created = await createUser({
        user_id: createForm.user_id.trim(),
        email: createForm.email.trim(),
        display_name: createForm.display_name.trim() || null,
        password: createForm.password,
        role: createForm.role,
        business_role: createForm.business_role,
      });
      setCreateSuccess(`Created ${created.user_id}. The password was not stored in the browser.`);
      setCreateForm(emptyCreateForm);
      load({ silent: true, nextSkip: 0 });
    } catch (err) {
      setCreateError(errorMessage(err, 'Could not create the user.'));
    } finally {
      setCreateBusy(false);
    }
  };

  const handleToken = async () => {
    if (!selected) return;
    setTokenBusy(true);
    setTokenError('');
    setTokenData(null);
    try {
      const result = await createEnrollmentToken(selected.user_id);
      setTokenData(result);
    } catch (err) {
      setTokenError(errorMessage(err, 'Could not issue an enrollment token.'));
    } finally {
      setTokenBusy(false);
    }
  };

  const copyToken = async () => {
    if (!tokenData?.enrollment_token) return;
    try {
      await navigator.clipboard.writeText(tokenData.enrollment_token);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setTokenError('Clipboard access was denied. Select and copy the token manually.');
    }
  };

  const handleRevoke = async (reason) => {
    if (!revokeTarget) return;
    setRevokeBusy(true);
    setRevokeError('');
    try {
      await revokeAgentDevice(revokeTarget.device_id, reason);
      setRevokeTarget(null);
      if (selected) await openDetail(selected);
    } catch (err) {
      setRevokeError(errorMessage(err, 'Could not revoke the device.'));
    } finally {
      setRevokeBusy(false);
    }
  };

  const handleDeleteUser = async () => {
    if (!deleteTarget) return;
    setDeleteBusy(true);
    setDeleteError('');
    try {
      await deleteUser(deleteTarget.user_id);
      setDeleteTarget(null);
      if (selected?.user_id === deleteTarget.user_id) {
        closeDetail();
      }
      load({ silent: true });
    } catch (err) {
      setDeleteError(errorMessage(err, 'Could not delete user.'));
    } finally {
      setDeleteBusy(false);
    }
  };

  const handleBusinessRoleUpdate = async () => {
    if (!selected) return;
    setBusinessRoleBusy(true);
    setBusinessRoleNotice('');
    setDetailError('');
    try {
      const updated = await updateUserBusinessRole(selected.user_id, businessRoleDraft);
      setSelected(updated);
      setBusinessRoleDraft(updated.business_role || 'GENERAL');
      setDetail((current) => current ? {
        ...current,
        summary: { ...current.summary, user: updated },
      } : current);
      setBusinessRoleNotice('Business role updated. New activity will use this profile.');
      await load({ silent: true, nextSkip: skip });
    } catch (err) {
      setDetailError(errorMessage(err, 'Could not update the business role.'));
    } finally {
      setBusinessRoleBusy(false);
    }
  };

  const summary = detail?.summary;
  const devices = detail?.devices || [];
  const canEnroll =
    selected &&
    selected.is_active &&
    selected.enforcement_status === 'ACTIVE' &&
    selected.monitoring_enabled === 'ALLOWED';

  const consentCounts = useMemo(() => {
    const counts = { ALLOWED: 0, NOT_ASKED: 0, DECLINED: 0, REVOKED: 0 };
    users.forEach((item) => {
      if (counts[item.monitoring_enabled] != null) counts[item.monitoring_enabled] += 1;
    });
    return counts;
  }, [users]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="User directory"
        title="Users and endpoint enrollment"
        subtitle="Administrative view of accounts, consent state, enforcement status and enrolled devices. Device credentials are issued as one-time enrollment tokens; only a hash is stored server-side."
        actions={
          <>
            <button type="button" onClick={() => load({ silent: true, nextSkip: skip })} className={btnSecondary} disabled={refreshing}>
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
              Refresh
            </button>
            {isAdmin ? (
              <button type="button" onClick={() => { setCreateOpen(true); setCreateError(''); setCreateSuccess(''); }} className={btnPrimary}>
                <UserPlus size={15} />
                Create user
              </button>
            ) : null}
          </>
        }
      />

      {isVisitor ? (
        <InlineNotice
          tone="neutral"
          message="Visitor mode: You have read-only access to the user directory with sanitized contact details. User provisioning, role assignment, and endpoint management are restricted to SOC administrators."
        />
      ) : null}

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          { label: 'Users in view', value: users.length, tone: 'blue' },
          { label: 'Consented', value: consentCounts.ALLOWED, tone: 'green' },
          { label: 'Awaiting consent', value: consentCounts.NOT_ASKED, tone: 'amber' },
          { label: 'Declined / revoked', value: consentCounts.DECLINED + consentCounts.REVOKED, tone: 'red' },
        ].map((item) => (
          <div key={item.label} className="rounded-xl border border-slate-800 bg-[#111827]/80 p-4">
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{item.label}</p>
            <p className="mt-1 text-2xl font-bold tabular-nums text-white">{formatNumber(item.value)}</p>
          </div>
        ))}
      </div>

      <Panel title="Directory" subtitle="Consent is enforced by the backend, not just hidden in the UI." bodyClassName="p-0">
        <div className="flex flex-col gap-2 border-b border-slate-800 p-4 lg:flex-row lg:items-center">
          <SearchInput value={query} onChange={setQuery} onSubmit={handleSearch} placeholder="Search user ID, email or display name" className="lg:w-80" />
          <select value={consent} onChange={(event) => { setConsent(event.target.value); setSkip(0); }} className={`${selectClass} lg:w-44`}>
            <option value="">All consent states</option>
            <option value="ALLOWED">ALLOWED</option>
            <option value="NOT_ASKED">NOT_ASKED</option>
            <option value="DECLINED">DECLINED</option>
            <option value="REVOKED">REVOKED</option>
          </select>
          <select value={role} onChange={(event) => { setRole(event.target.value); setSkip(0); }} className={`${selectClass} lg:w-36`}>
            <option value="">All access roles</option>
            <option value="ADMIN">ADMIN</option>
            <option value="EDITOR">EDITOR</option>
            <option value="VISITOR">VISITOR</option>
            <option value="USER">USER</option>
          </select>
          <select value={businessRole} onChange={(event) => { setBusinessRole(event.target.value); setSkip(0); }} className={`${selectClass} lg:w-44`}>
            <option value="">All business roles</option>
            <option value="GENERAL">GENERAL</option>
            <option value="DEVELOPER">DEVELOPER</option>
            <option value="HR">HR</option>
            <option value="FINANCE">FINANCE</option>
          </select>
          <button type="button" onClick={handleSearch} className={btnSecondary}>Apply</button>
        </div>

        {loading ? (
          <LoadingState />
        ) : users.length === 0 ? (
          <EmptyState
            icon={UsersIcon}
            title="No users match this view"
            message="Adjust the filters or create a user. New users begin in NOT_ASKED consent and cannot be monitored until they allow it."
            action={<button type="button" className={btnPrimary} onClick={() => setCreateOpen(true)}><Plus size={15} />Create user</button>}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="soc-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Access role</th>
                  <th>Business role</th>
                  <th>Consent</th>
                  <th>Enforcement</th>
                  <th>Active</th>
                  <th>Last login</th>
                  <th>Created</th>
                  <th className="text-right">Details</th>
                </tr>
              </thead>
              <tbody>
                {users.map((item) => (
                  <tr key={item.user_id}>
                    <td>
                      <p className="font-semibold text-slate-100">{item.display_name || item.user_id}</p>
                      <p className="text-[11px] text-slate-500">{item.user_id}{item.email ? ` · ${item.email}` : ''}</p>
                    </td>
                    <td><Badge tone={item.role === 'ADMIN' ? 'blue' : 'neutral'}>{item.role}</Badge></td>
                    <td><Badge tone={item.business_role === 'GENERAL' ? 'neutral' : 'purple'}>{item.business_role || 'GENERAL'}</Badge></td>
                    <td><Badge tone={consentTone(item.monitoring_enabled)}>{item.monitoring_enabled.replace('_', ' ')}</Badge></td>
                    <td><Badge tone={statusTone(item.enforcement_status)}>{item.enforcement_status}</Badge></td>
                    <td>{item.is_active ? <span className="text-emerald-400">Yes</span> : <span className="text-red-400">No</span>}</td>
                    <td className="whitespace-nowrap text-slate-400">{item.last_login_at ? timeAgo(item.last_login_at) : 'Never'}</td>
                    <td className="whitespace-nowrap text-slate-500">{formatDateTime(item.created_at)}</td>
                    <td className="text-right">
                      <button type="button" className={btnSecondary} onClick={() => openDetail(item)}>Open</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <Pagination
          skip={skip}
          limit={LIMIT}
          count={users.length}
          loading={loading}
          onPrevious={() => setSkip((value) => Math.max(0, value - LIMIT))}
          onNext={() => setSkip((value) => value + LIMIT)}
        />
      </Panel>

      <Drawer
        open={Boolean(selected)}
        onClose={closeDetail}
        title={selected?.display_name || selected?.user_id || 'User details'}
        subtitle={selected ? `${selected.user_id}${selected.email ? ` · ${selected.email}` : ''}` : ''}
        footer={
          selected ? (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap gap-2">
                <Badge tone={selected.role === 'ADMIN' ? 'blue' : selected.role === 'EDITOR' ? 'purple' : selected.role === 'VISITOR' ? 'emerald' : 'neutral'}>{selected.role}</Badge>
                <Badge tone={consentTone(selected.monitoring_enabled)}>{selected.monitoring_enabled.replace('_', ' ')}</Badge>
                <Badge tone={statusTone(selected.enforcement_status)}>{selected.enforcement_status}</Badge>
              </div>
              <div className="flex items-center gap-2">
                {isAdmin && selected.user_id !== 'admin' ? (
                  <button
                    type="button"
                    className={btnDanger}
                    onClick={() => {
                      setDeleteError('');
                      setDeleteTarget(selected);
                    }}
                  >
                    Delete account
                  </button>
                ) : null}
                <button type="button" className={btnSecondary} onClick={closeDetail}>Close</button>
              </div>
            </div>
          ) : null
        }
      >
        {detailError ? <ErrorState message={detailError} onRetry={() => selected && openDetail(selected)} /> : null}
        {detailLoading ? (
          <LoadingState label="Loading correlated user summary…" />
        ) : summary ? (
          <div className="space-y-5">
            <section className="grid grid-cols-2 gap-3">
              <KeyValue label="Events · 24h">{formatNumber(summary.activity?.events_last_24h)}</KeyValue>
              <KeyValue label="Events · 7d">{formatNumber(summary.activity?.events_last_7d)}</KeyValue>
              <KeyValue label="Last event">{summary.activity?.last_event_at ? formatDateTime(summary.activity.last_event_at) : 'None'}</KeyValue>
              <KeyValue label="Open alerts">{formatNumber(summary.risk?.open_alerts)}</KeyValue>
              <KeyValue label="Latest risk">
                {summary.risk?.latest ? (
                  <span className="inline-flex items-center gap-2">
                    <Badge tone={severityTone(summary.risk.latest.risk_category)}>{summary.risk.latest.risk_category}</Badge>
                    <span className="font-mono">{formatScore(summary.risk.latest.combined_score, 1)}</span>
                  </span>
                ) : 'No assessment'}
              </KeyValue>
              <KeyValue label="Consent updated">{formatDateTime(summary.user?.consent_updated_at)}</KeyValue>
            </section>

            <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div className="flex-1">
                  <label className={labelClass} htmlFor="business-role">Business role</label>
                  <select
                    id="business-role"
                    className={selectClass}
                    value={businessRoleDraft}
                    onChange={(event) => setBusinessRoleDraft(event.target.value)}
                    disabled={businessRoleBusy || isVisitor || (isEditor && selected.role === 'ADMIN')}
                  >
                    <option value="GENERAL">GENERAL — no department profile</option>
                    <option value="DEVELOPER">DEVELOPER</option>
                    <option value="HR">HR</option>
                    <option value="FINANCE">FINANCE</option>
                  </select>
                </div>
                {!isVisitor && !(isEditor && selected.role === 'ADMIN') ? (
                  <button type="button" className={btnSecondary} onClick={handleBusinessRoleUpdate} disabled={businessRoleBusy || businessRoleDraft === (selected.business_role || 'GENERAL')}>
                    {businessRoleBusy ? <Loader2 size={14} className="animate-spin" /> : null}
                    Save business role
                  </button>
                ) : null}
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
                Role analytics use department-category signals from attributed endpoint events. A role change applies to new events.
              </p>
              {businessRoleNotice ? <p className="mt-2 text-xs text-emerald-300">{businessRoleNotice}</p> : null}
            </section>

            {isAdmin ? (
              <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-bold text-slate-100">Endpoint enrollment</h3>
                    <p className="mt-0.5 text-[11px] text-slate-500">
                      Issue a one-time token, then run the agent enrollment command on the device.
                    </p>
                  </div>
                  <button type="button" className={btnPrimary} onClick={handleToken} disabled={!canEnroll || tokenBusy}>
                    {tokenBusy ? <Loader2 size={15} className="animate-spin" /> : <KeyRound size={15} />}
                    Issue token
                  </button>
                </div>
                {!canEnroll ? (
                  <p className="mt-2 text-[11px] leading-relaxed text-amber-300/90">
                    The user must be active, not restricted and have ALLOWED consent before a device can
                    be enrolled.
                  </p>
                ) : null}
                {tokenError ? <p className="mt-2 text-xs text-red-300">{tokenError}</p> : null}
                {tokenData ? (
                  <div className="mt-3 rounded-lg border border-emerald-900/50 bg-emerald-950/20 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-300">One-time enrollment token</p>
                    <div className="mt-1.5 flex items-start gap-2">
                      <code className="min-w-0 flex-1 break-all rounded-md border border-slate-800 bg-slate-950 p-2 font-mono text-[11px] text-emerald-200">
                        {tokenData.enrollment_token}
                      </code>
                      <button type="button" className={btnSecondary} onClick={copyToken} aria-label="Copy token">
                        {copied ? <Check size={14} /> : <Copy size={14} />}
                      </button>
                    </div>
                    <p className="mt-1.5 text-[10px] text-emerald-300/70">
                      Expires {formatDateTime(tokenData.expires_at)}. It is shown once and is not stored in
                      plaintext.
                    </p>
                    <pre className="mt-2 overflow-x-auto rounded-md border border-slate-800 bg-slate-950 p-2 text-[10px] leading-relaxed text-slate-400">{`python -m agent enroll --token <TOKEN> --backend-url http://localhost:8000/api
python -m agent run`}</pre>
                  </div>
                ) : null}
              </section>
            ) : null}

            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-100">Devices ({devices.length})</h3>
              {devices.length === 0 ? (
                <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-500">
                  No endpoints enrolled for this user.
                </p>
              ) : (
                <div className="space-y-2">
                  {devices.map((device) => (
                    <div key={device.device_id} className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="flex items-center gap-2 text-xs font-semibold text-slate-200">
                            <Laptop size={13} /> {device.hostname || device.device_id}
                          </p>
                          <p className="mt-0.5 truncate text-[10px] text-slate-500">{device.device_id}</p>
                          <p className="mt-1 text-[10px] text-slate-500">
                            {device.os_version || 'OS unknown'} · agent {device.agent_version || '—'}
                          </p>
                          <p className="mt-0.5 text-[10px] text-slate-500">
                            Enrolled {formatDateTime(device.enrolled_at)} · heartbeat{' '}
                            {device.last_heartbeat ? timeAgo(device.last_heartbeat) : 'never'}
                          </p>
                          {device.revoked_reason ? (
                            <p className="mt-1 text-[10px] text-red-300">Revoked: {device.revoked_reason}</p>
                          ) : null}
                        </div>
                        <div className="flex shrink-0 flex-col items-end gap-1.5">
                          <Badge tone={statusTone(device.status)}>{device.status}</Badge>
                          {device.status === 'ACTIVE' && isAdmin ? (
                            <button type="button" className={btnDanger} onClick={() => { setRevokeError(''); setRevokeTarget(device); }}>
                              Revoke
                            </button>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        ) : null}
      </Drawer>

      <Drawer
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create a user account"
        subtitle="Administrative provisioning only. There is no public registration endpoint."
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className={labelClass} htmlFor="new-user-id">User ID</label>
            <input id="new-user-id" className={inputClass} value={createForm.user_id} onChange={(event) => setCreateForm({ ...createForm, user_id: event.target.value })} placeholder="e.g. alice.analyst" required minLength={2} maxLength={64} />
            <p className="mt-1 text-[10px] text-slate-500">Letters, digits, hyphen, underscore and dot only.</p>
          </div>
          <div>
            <label className={labelClass} htmlFor="new-email">Email</label>
            <input id="new-email" type="email" className={inputClass} value={createForm.email} onChange={(event) => setCreateForm({ ...createForm, email: event.target.value })} placeholder="alice@example.com" required />
          </div>
          <div>
            <label className={labelClass} htmlFor="new-display-name">Display name (optional)</label>
            <input id="new-display-name" className={inputClass} value={createForm.display_name} onChange={(event) => setCreateForm({ ...createForm, display_name: event.target.value })} placeholder="Alice Analyst" maxLength={120} />
          </div>
          <div>
            <label className={labelClass} htmlFor="new-password">Initial password</label>
            <input id="new-password" type="password" className={inputClass} value={createForm.password} onChange={(event) => setCreateForm({ ...createForm, password: event.target.value })} placeholder="At least 12 characters" required minLength={12} maxLength={72} autoComplete="new-password" />
            <p className="mt-1 text-[10px] text-slate-500">The password is sent once and is never stored in this interface.</p>
          </div>
          <div>
            <label className={labelClass} htmlFor="new-role">Application access role</label>
            <select id="new-role" className={selectClass} value={createForm.role} onChange={(event) => setCreateForm({ ...createForm, role: event.target.value })}>
              <option value="USER">USER — monitored employee account</option>
              <option value="EDITOR">EDITOR — SOC operator (operational triage)</option>
              <option value="VISITOR">VISITOR — Demonstration viewer (read-only)</option>
              <option value="ADMIN">ADMIN — Full SOC administrator</option>
            </select>
          </div>
          <div>
            <label className={labelClass} htmlFor="new-business-role">Business role</label>
            <select id="new-business-role" className={selectClass} value={createForm.business_role} onChange={(event) => setCreateForm({ ...createForm, business_role: event.target.value })}>
              <option value="GENERAL">GENERAL — no department profile</option>
              <option value="DEVELOPER">DEVELOPER</option>
              <option value="HR">HR</option>
              <option value="FINANCE">FINANCE</option>
            </select>
            <p className="mt-1 text-[10px] text-slate-500">Used for role-aware behavior analysis, separate from ADMIN/USER permissions.</p>
          </div>

          {createError ? <p className="rounded-lg border border-red-900/50 bg-red-950/20 p-3 text-xs text-red-200">{createError}</p> : null}
          {createSuccess ? <InlineNotice tone="success">{createSuccess}</InlineNotice> : null}

          <div className="flex justify-end gap-2 border-t border-slate-800 pt-4">
            <button type="button" className={btnSecondary} onClick={() => setCreateOpen(false)}>Close</button>
            <button type="submit" className={btnPrimary} disabled={createBusy}>
              {createBusy ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />}
              Create account
            </button>
          </div>
          <p className="flex items-center gap-1.5 text-[10px] text-slate-500">
            <ShieldOff size={12} /> New accounts start with NOT_ASKED consent unless they allow monitoring.
          </p>
        </form>
      </Drawer>

      <ConfirmDialog
        open={Boolean(revokeTarget)}
        title="Revoke this device?"
        message={
          <span>
            The agent credential for <strong className="text-slate-200">{revokeTarget?.hostname || revokeTarget?.device_id}</strong>{' '}
            will stop working immediately. The device must complete enrollment again with a new
            one-time token.
          </span>
        }
        confirmLabel="Revoke device"
        requireReason
        busy={revokeBusy}
        error={revokeError}
        onClose={() => { if (!revokeBusy) { setRevokeTarget(null); setRevokeError(''); } }}
        onConfirm={handleRevoke}
      />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title={`Delete account ${deleteTarget?.user_id}?`}
        message={
          <span>
            Are you sure you want to delete user <strong className="text-slate-200">{deleteTarget?.user_id}</strong>?
            This will permanently remove the account from the directory.
          </span>
        }
        confirmLabel="Delete User"
        tone="danger"
        busy={deleteBusy}
        error={deleteError}
        onClose={() => { if (!deleteBusy) { setDeleteTarget(null); setDeleteError(''); } }}
        onConfirm={handleDeleteUser}
      />
    </div>
  );
}
