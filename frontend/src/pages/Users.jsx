import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Check,
  Clock,
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
  getUserDirectory,
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
  StatCard,
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
  const { user, isAdmin, isEditor, isVisitor } = useAuth();
  const canViewDetails = isAdmin || isEditor;

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

  const [accessRoleDraft, setAccessRoleDraft] = useState('USER');
  const [accessRoleBusy, setAccessRoleBusy] = useState(false);
  const [accessRoleNotice, setAccessRoleNotice] = useState('');

  const [businessRoleDraft, setBusinessRoleDraft] = useState('GENERAL');
  const [businessRoleBusy, setBusinessRoleBusy] = useState(false);
  const [businessRoleNotice, setBusinessRoleNotice] = useState('');

  const load = useCallback(
    async ({ silent = false, nextSkip = skip } = {}) => {
      if (silent) setRefreshing(true);
      else setLoading(true);
      setError('');
      try {
        const result = isVisitor
          ? await getUserDirectory({
              limit: LIMIT,
              skip: nextSkip,
              q: appliedQuery || undefined,
              role: role || undefined,
              business_role: businessRole || undefined,
            })
          : await getUsers({
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
    [skip, appliedQuery, consent, role, businessRole, isVisitor],
  );

  useEffect(() => {
    load();
  }, [load]);

  const openDetail = useCallback(async (targetUser) => {
    if (!canViewDetails) return;
    setSelected(targetUser);
    setDetail(null);
    setDetailError('');
    setDetailLoading(true);
    setAccessRoleDraft(targetUser.role || 'USER');
    setAccessRoleNotice('');
    setBusinessRoleDraft(targetUser.business_role || 'GENERAL');
    setBusinessRoleNotice('');
    try {
      const [summary, devices] = await Promise.all([
        getUserSummary(targetUser.user_id),
        getUserDevices(targetUser.user_id),
      ]);
      setDetail({ summary, devices: Array.isArray(devices) ? devices : [] });
      setAccessRoleDraft(summary?.user?.role || targetUser.role || 'USER');
      setBusinessRoleDraft(summary?.user?.business_role || targetUser.business_role || 'GENERAL');
    } catch (err) {
      setDetailError(errorMessage(err, 'Could not load correlated user details.'));
    } finally {
      setDetailLoading(false);
    }
  }, [canViewDetails]);

  const closeDetail = () => {
    setSelected(null);
    setDetail(null);
    setTokenData(null);
    setTokenError('');
    setAccessRoleNotice('');
    setBusinessRoleNotice('');
  };

  const handleSearch = (event) => {
    event?.preventDefault();
    setSkip(0);
    setAppliedQuery(query.trim());
  };

  const handleCreateChange = (event) => {
    const { name, value } = event.target;
    setCreateForm((current) => ({ ...current, [name]: value }));
  };

  const handleCreateSubmit = async (event) => {
    event.preventDefault();
    setCreateBusy(true);
    setCreateError('');
    setCreateSuccess('');
    try {
      const created = await createUser({
        user_id: createForm.user_id.trim(),
        email: createForm.email.trim(),
        display_name: createForm.display_name.trim() || undefined,
        password: createForm.password,
        role: createForm.role,
        business_role: createForm.business_role,
      });
      setCreateSuccess(`Account created for ${created.user_id}.`);
      setCreateForm(emptyCreateForm);
      await load({ silent: true, nextSkip: 0 });
      setSkip(0);
      setTimeout(() => {
        setCreateOpen(false);
        setCreateSuccess('');
      }, 1200);
    } catch (err) {
      setCreateError(errorMessage(err, 'Failed to create user.'));
    } finally {
      setCreateBusy(false);
    }
  };

  const handleToken = async () => {
    if (!selected) return;
    setTokenBusy(true);
    setTokenError('');
    try {
      const response = await createEnrollmentToken(selected.user_id);
      setTokenData(response);
      setCopied(false);
    } catch (err) {
      setTokenError(errorMessage(err, 'Could not generate enrollment token.'));
    } finally {
      setTokenBusy(false);
    }
  };

  const copyToken = async () => {
    if (!tokenData?.enrollment_token) return;
    try {
      await navigator.clipboard.writeText(tokenData.enrollment_token);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setTokenError('Clipboard write failed.');
    }
  };

  const handleRevoke = async () => {
    if (!revokeTarget) return;
    setRevokeBusy(true);
    setRevokeError('');
    try {
      await revokeAgentDevice(revokeTarget.device_id, 'Revoked by administrator from User Directory');
      setRevokeTarget(null);
      if (selected) {
        const devices = await getUserDevices(selected.user_id);
        setDetail((current) => (current ? { ...current, devices: Array.isArray(devices) ? devices : [] } : current));
      }
      load({ silent: true });
    } catch (err) {
      setRevokeError(errorMessage(err, 'Could not revoke device.'));
    } finally {
      setRevokeBusy(false);
    }
  };

  const handleDelete = async () => {
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

  const handleAccessRoleUpdate = async () => {
    if (!selected || selected.user_id === 'admin') return;
    setAccessRoleBusy(true);
    setAccessRoleNotice('');
    setDetailError('');
    try {
      const updated = await updateUser(selected.user_id, { role: accessRoleDraft });
      setSelected(updated);
      setAccessRoleDraft(updated.role);
      setDetail((current) => (current ? {
        ...current,
        summary: { ...current.summary, user: updated },
      } : current));
      setAccessRoleNotice('System access role updated successfully.');
      await load({ silent: true, nextSkip: skip });
    } catch (err) {
      setDetailError(errorMessage(err, 'Could not update system access role.'));
    } finally {
      setAccessRoleBusy(false);
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
      setDetail((current) => (current ? {
        ...current,
        summary: { ...current.summary, user: updated },
      } : current));
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

  // VISITOR MODE: restricted 4-column directory
  if (isVisitor) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="User directory"
          title="Users"
          subtitle="Restricted directory view. Only display names, masked email addresses, access roles, and business roles are shown."
          actions={
            <button
              type="button"
              onClick={() => load({ silent: true, nextSkip: skip })}
              className={btnSecondary}
              disabled={refreshing}
            >
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} /> Refresh
            </button>
          }
        />

        <InlineNotice tone="neutral">
          Visitor mode: You have restricted, read-only directory access. Contact details are masked, and account lifecycle controls are restricted to administrators.
        </InlineNotice>

        {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

        <Panel
          title="Directory"
          subtitle={`${users.length} account${users.length === 1 ? '' : 's'} on this page`}
          bodyClassName="p-0"
        >
          <div className="flex flex-col gap-2.5 border-b border-slate-200 p-4 lg:flex-row lg:items-center dark:border-slate-800">
            <SearchInput
              value={query}
              onChange={setQuery}
              onSubmit={handleSearch}
              placeholder="Search user ID or display name"
              className="lg:w-80"
            />
            <select
              value={role}
              onChange={(event) => { setRole(event.target.value); setSkip(0); }}
              className={`${selectClass} lg:w-36`}
            >
              <option value="">All access roles</option>
              <option value="ADMIN">ADMIN</option>
              <option value="EDITOR">EDITOR</option>
              <option value="VISITOR">VISITOR</option>
              <option value="USER">USER</option>
            </select>
            <select
              value={businessRole}
              onChange={(event) => { setBusinessRole(event.target.value); setSkip(0); }}
              className={`${selectClass} lg:w-44`}
            >
              <option value="">All business roles</option>
              <option value="GENERAL">GENERAL</option>
              <option value="DEVELOPER">DEVELOPER</option>
              <option value="HR">HR</option>
              <option value="FINANCE">FINANCE</option>
            </select>
            <button type="button" onClick={handleSearch} className={btnSecondary}>
              Apply
            </button>
          </div>

          {loading ? (
            <LoadingState />
          ) : users.length === 0 ? (
            <EmptyState
              icon={UsersIcon}
              title="No directory entries"
              message="No users match the current filter in this directory view."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="soc-table">
                <thead>
                  <tr>
                    <th>Display Name</th>
                    <th>Email</th>
                    <th>Access role</th>
                    <th>Business role</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((item) => (
                    <tr key={item.user_id}>
                      <td className="font-semibold text-slate-900 dark:text-slate-100">
                        {item.display_name || item.user_id}
                      </td>
                      <td className="font-mono text-xs text-slate-600 dark:text-slate-400">
                        {item.email || '—'}
                      </td>
                      <td>
                        <Badge tone={item.role === 'ADMIN' ? 'blue' : item.role === 'EDITOR' ? 'purple' : item.role === 'VISITOR' ? 'emerald' : 'neutral'}>
                          {item.role}
                        </Badge>
                      </td>
                      <td>
                        <Badge tone={item.business_role === 'GENERAL' ? 'neutral' : 'purple'}>
                          {item.business_role || 'GENERAL'}
                        </Badge>
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
      </div>
    );
  }

  // ADMIN, EDITOR, and USER MODES
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="User directory"
        title={isAdmin ? 'Users and endpoint enrollment' : 'Users'}
        subtitle={
          isAdmin
            ? 'Administrative view of accounts, consent state, enforcement status and enrolled devices. Device credentials are issued as one-time enrollment tokens; only a hash is stored server-side.'
            : 'Directory view of users, access roles, business roles, consent and enforcement status.'
        }
        actions={
          <>
            <button
              type="button"
              onClick={() => load({ silent: true, nextSkip: skip })}
              className={btnSecondary}
              disabled={refreshing}
            >
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
              Refresh
            </button>
            {isAdmin ? (
              <button
                type="button"
                onClick={() => {
                  setCreateOpen(true);
                  setCreateError('');
                  setCreateSuccess('');
                }}
                className={btnPrimary}
              >
                <UserPlus size={15} />
                Create user
              </button>
            ) : null}
          </>
        }
      />

      {user?.role === 'USER' ? (
        <InlineNotice tone="neutral">
          You have read-only access to the user directory. User provisioning, role assignment, and endpoint management are restricted to SOC administrators.
        </InlineNotice>
      ) : null}

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Users in view"
          value={formatNumber(users.length)}
          hint="Filtered directory subset"
          icon={UsersIcon}
          tone="blue"
          loading={loading}
        />
        <StatCard
          label="Consented"
          value={formatNumber(consentCounts.ALLOWED)}
          hint="Monitoring active"
          icon={ShieldCheck}
          tone="green"
          loading={loading}
        />
        <StatCard
          label="Awaiting consent"
          value={formatNumber(consentCounts.NOT_ASKED)}
          hint="Pending user authorization"
          icon={Clock}
          tone="amber"
          loading={loading}
        />
        <StatCard
          label="Declined / revoked"
          value={formatNumber(consentCounts.DECLINED + consentCounts.REVOKED)}
          hint="Monitoring paused"
          icon={ShieldOff}
          tone="red"
          loading={loading}
        />
      </div>

      <Panel title="Directory" subtitle="Consent is enforced by the backend, not just hidden in the UI." bodyClassName="p-0">
        <div className="flex flex-col gap-2.5 border-b border-slate-200 p-4 lg:flex-row lg:items-center dark:border-slate-800">
          <SearchInput
            value={query}
            onChange={setQuery}
            onSubmit={handleSearch}
            placeholder="Search user ID, email or display name"
            className="lg:w-80"
          />
          <select
            value={consent}
            onChange={(event) => { setConsent(event.target.value); setSkip(0); }}
            className={`${selectClass} lg:w-44`}
          >
            <option value="">All consent states</option>
            <option value="ALLOWED">ALLOWED</option>
            <option value="NOT_ASKED">NOT_ASKED</option>
            <option value="DECLINED">DECLINED</option>
            <option value="REVOKED">REVOKED</option>
          </select>
          <select
            value={role}
            onChange={(event) => { setRole(event.target.value); setSkip(0); }}
            className={`${selectClass} lg:w-36`}
          >
            <option value="">All access roles</option>
            <option value="ADMIN">ADMIN</option>
            <option value="EDITOR">EDITOR</option>
            <option value="VISITOR">VISITOR</option>
            <option value="USER">USER</option>
          </select>
          <select
            value={businessRole}
            onChange={(event) => { setBusinessRole(event.target.value); setSkip(0); }}
            className={`${selectClass} lg:w-44`}
          >
            <option value="">All business roles</option>
            <option value="GENERAL">GENERAL</option>
            <option value="DEVELOPER">DEVELOPER</option>
            <option value="HR">HR</option>
            <option value="FINANCE">FINANCE</option>
          </select>
          <button type="button" onClick={handleSearch} className={btnSecondary}>
            Apply
          </button>
        </div>

        {loading ? (
          <LoadingState />
        ) : users.length === 0 ? (
          <EmptyState
            icon={UsersIcon}
            title="No users match this view"
            message="Adjust the filters or create a user. New users begin in NOT_ASKED consent and cannot be monitored until they allow it."
            action={
              isAdmin ? (
                <button type="button" className={btnPrimary} onClick={() => setCreateOpen(true)}>
                  <Plus size={15} />
                  Create user
                </button>
              ) : null
            }
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
                  {canViewDetails ? <th className="text-right">Details</th> : null}
                </tr>
              </thead>
              <tbody>
                {users.map((item) => (
                  <tr key={item.user_id}>
                    <td>
                      <p className="font-semibold text-slate-900 dark:text-slate-100">{item.display_name || item.user_id}</p>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400">
                        {item.user_id}
                        {item.email ? ` · ${item.email}` : ''}
                      </p>
                    </td>
                    <td>
                      <Badge tone={item.role === 'ADMIN' ? 'blue' : item.role === 'EDITOR' ? 'purple' : item.role === 'VISITOR' ? 'emerald' : 'neutral'}>
                        {item.role}
                      </Badge>
                    </td>
                    <td>
                      <Badge tone={item.business_role === 'GENERAL' ? 'neutral' : 'purple'}>
                        {item.business_role || 'GENERAL'}
                      </Badge>
                    </td>
                    <td>
                      <Badge tone={consentTone(item.monitoring_enabled)}>
                        {item.monitoring_enabled.replace('_', ' ')}
                      </Badge>
                    </td>
                    <td>
                      <Badge tone={statusTone(item.enforcement_status)}>
                        {item.enforcement_status}
                      </Badge>
                    </td>
                    <td>
                      {item.is_active ? <Badge tone="green">Active</Badge> : <Badge tone="red">Inactive</Badge>}
                    </td>
                    <td className="whitespace-nowrap text-slate-600 dark:text-slate-400">
                      {item.last_login_at ? timeAgo(item.last_login_at) : 'Never'}
                    </td>
                    <td className="whitespace-nowrap text-slate-500 dark:text-slate-400">
                      {formatDateTime(item.created_at)}
                    </td>
                    {canViewDetails ? (
                      <td className="text-right">
                        <button type="button" className={btnSecondary} onClick={() => openDetail(item)}>
                          Open
                        </button>
                      </td>
                    ) : null}
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

      {/* DETAIL DRAWER — Restricted to authorized operators (ADMIN & EDITOR) */}
      {canViewDetails ? (
        <Drawer
          open={Boolean(selected)}
          onClose={closeDetail}
          title={selected?.display_name || selected?.user_id || 'User details'}
          subtitle={selected ? `${selected.user_id}${selected.email ? ` · ${selected.email}` : ''}` : ''}
          footer={
            selected ? (
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap gap-2">
                  <Badge tone={selected.role === 'ADMIN' ? 'blue' : selected.role === 'EDITOR' ? 'purple' : selected.role === 'VISITOR' ? 'emerald' : 'neutral'}>
                    {selected.role}
                  </Badge>
                  <Badge tone={consentTone(selected.monitoring_enabled)}>
                    {selected.monitoring_enabled.replace('_', ' ')}
                  </Badge>
                  <Badge tone={statusTone(selected.enforcement_status)}>
                    {selected.enforcement_status}
                  </Badge>
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
                  <button type="button" className={btnSecondary} onClick={closeDetail}>
                    Close
                  </button>
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
                      <Badge tone={severityTone(summary.risk.latest.risk_category)}>
                        {summary.risk.latest.risk_category}
                      </Badge>
                      <span className="font-mono">{formatScore(summary.risk.latest.combined_score, 1)}</span>
                    </span>
                  ) : 'No assessment'}
                </KeyValue>
                <KeyValue label="Consent updated">{formatDateTime(summary.user?.consent_updated_at)}</KeyValue>
              </section>

              {isAdmin ? (
                <section className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 dark:border-slate-800 dark:bg-slate-900/40">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                    <div className="flex-1">
                      <label className={labelClass} htmlFor="access-role">System access role</label>
                      <select
                        id="access-role"
                        className={selectClass}
                        value={accessRoleDraft}
                        onChange={(event) => setAccessRoleDraft(event.target.value)}
                        disabled={accessRoleBusy || selected.user_id === 'admin'}
                      >
                        <option value="USER">USER — monitored user with read-only directory</option>
                        <option value="ADMIN">ADMIN — complete platform control</option>
                        <option value="EDITOR">EDITOR — operational triage & user directory</option>
                        <option value="VISITOR">VISITOR — restricted demonstration viewer</option>
                      </select>
                    </div>
                    {selected.user_id !== 'admin' ? (
                      <button
                        type="button"
                        className={btnSecondary}
                        onClick={handleAccessRoleUpdate}
                        disabled={accessRoleBusy || accessRoleDraft === selected.role}
                      >
                        {accessRoleBusy ? <Loader2 size={14} className="animate-spin" /> : null}
                        Save access role
                      </button>
                    ) : null}
                  </div>
                  {selected.user_id === 'admin' ? (
                    <p className="mt-2 text-[11px] font-medium text-amber-700 dark:text-amber-400">Primary administrator access role is protected.</p>
                  ) : (
                    <p className="mt-2 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
                      Controls platform authorization and management capabilities.
                    </p>
                  )}
                  {accessRoleNotice ? <p className="mt-2 text-xs text-emerald-600 dark:text-emerald-300">{accessRoleNotice}</p> : null}
                </section>
              ) : null}

              <section className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 dark:border-slate-800 dark:bg-slate-900/40">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                  <div className="flex-1">
                    <label className={labelClass} htmlFor="business-role">Business role</label>
                    <select
                      id="business-role"
                      className={selectClass}
                      value={businessRoleDraft}
                      onChange={(event) => setBusinessRoleDraft(event.target.value)}
                      disabled={businessRoleBusy || (isEditor && selected.role === 'ADMIN')}
                    >
                      <option value="GENERAL">GENERAL — no department profile</option>
                      <option value="DEVELOPER">DEVELOPER</option>
                      <option value="HR">HR</option>
                      <option value="FINANCE">FINANCE</option>
                    </select>
                  </div>
                  {!(isEditor && selected.role === 'ADMIN') ? (
                    <button
                      type="button"
                      className={btnSecondary}
                      onClick={handleBusinessRoleUpdate}
                      disabled={businessRoleBusy || businessRoleDraft === (selected.business_role || 'GENERAL')}
                    >
                      {businessRoleBusy ? <Loader2 size={14} className="animate-spin" /> : null}
                      Save business role
                    </button>
                  ) : null}
                </div>
                <p className="mt-2 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
                  Role analytics use department-category signals from attributed endpoint events. A role change applies to new events.
                </p>
                {businessRoleNotice ? <p className="mt-2 text-xs text-emerald-600 dark:text-emerald-300">{businessRoleNotice}</p> : null}
              </section>

              {isAdmin ? (
                <section className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 dark:border-slate-800 dark:bg-slate-900/40">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Endpoint enrollment</h3>
                      <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
                        Issue a one-time token, then run the agent enrollment command on the device.
                      </p>
                    </div>
                    <button
                      type="button"
                      className={btnPrimary}
                      onClick={handleToken}
                      disabled={!canEnroll || tokenBusy}
                    >
                      {tokenBusy ? <Loader2 size={15} className="animate-spin" /> : <KeyRound size={15} />}
                      Issue token
                    </button>
                  </div>
                  {!canEnroll ? (
                    <p className="mt-2 text-[11px] leading-relaxed font-medium text-amber-700 dark:text-amber-300">
                      The user must be active, not restricted and have ALLOWED consent before a device can be enrolled.
                    </p>
                  ) : null}
                  {tokenError ? <p className="mt-2 text-xs text-red-600 dark:text-red-300">{tokenError}</p> : null}
                  {tokenData ? (
                    <div className="mt-3 rounded-lg border border-emerald-900/50 bg-emerald-950/20 p-3">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-300">
                        One-time enrollment token
                      </p>
                      <div className="mt-1.5 flex items-start gap-2">
                        <code className="min-w-0 flex-1 break-all rounded-md border border-slate-800 bg-slate-950 p-2 font-mono text-[11px] text-emerald-200">
                          {tokenData.enrollment_token}
                        </code>
                        <button
                          type="button"
                          className={btnSecondary}
                          onClick={copyToken}
                          aria-label="Copy token"
                        >
                          {copied ? <Check size={14} /> : <Copy size={14} />}
                        </button>
                      </div>
                      <p className="mt-1.5 text-[10px] text-emerald-300/70">
                        Expires {formatDateTime(tokenData.expires_at)}. It is shown once and is not stored in plaintext.
                      </p>
                      <pre className="mt-2 overflow-x-auto rounded-md border border-slate-800 bg-slate-950 p-2 text-[10px] leading-relaxed text-slate-400">{`python -m agent enroll --token <TOKEN> --backend-url http://localhost:8000/api\npython -m agent run`}</pre>
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
                      <div
                        key={device.device_id}
                        className="flex flex-col gap-2 rounded-lg border border-slate-800 bg-slate-900/40 p-3 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div className="flex items-start gap-3">
                          <span className="mt-0.5 rounded-md border border-slate-800 bg-slate-800/60 p-2 text-slate-400">
                            <Laptop size={16} />
                          </span>
                          <div>
                            <p className="text-xs font-semibold text-slate-200">
                              {device.hostname || device.device_id}
                            </p>
                            <p className="text-[11px] text-slate-500">
                              {device.os_version || 'OS unknown'} · Agent {device.agent_version || '0.1.0'}
                            </p>
                            <div className="mt-1 flex items-center gap-2">
                              <Badge tone={device.status === 'ACTIVE' ? 'green' : 'red'}>
                                {device.status}
                              </Badge>
                              <span className="text-[10px] text-slate-500">
                                Enrolled {formatDateTime(device.enrolled_at)}
                              </span>
                            </div>
                          </div>
                        </div>

                        {isAdmin && device.status === 'ACTIVE' ? (
                          <button
                            type="button"
                            className={btnDanger}
                            onClick={() => {
                              setRevokeError('');
                              setRevokeTarget(device);
                            }}
                          >
                            <ShieldOff size={14} />
                            Revoke
                          </button>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          ) : null}
        </Drawer>
      ) : null}

      {/* CREATE USER MODAL — ADMIN ONLY */}
      {isAdmin && createOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-slate-900/60 backdrop-blur-xs"
            onClick={() => !createBusy && setCreateOpen(false)}
            aria-label="Close dialog overlay"
          />
          <div className="relative w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-[#0d1320]">
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">Create user account</h2>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Provision an account directly. Initial consent state is NOT_ASKED.
            </p>

            <form onSubmit={handleCreateSubmit} className="mt-4 space-y-3">
              {createError ? (
                <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300">
                  {createError}
                </div>
              ) : null}
              {createSuccess ? (
                <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-300">
                  {createSuccess}
                </div>
              ) : null}

              <div>
                <label htmlFor="create-user-id" className={labelClass}>User ID</label>
                <input
                  id="create-user-id"
                  name="user_id"
                  required
                  value={createForm.user_id}
                  onChange={handleCreateChange}
                  className={inputClass}
                  placeholder="analyst.jones"
                  disabled={createBusy}
                />
              </div>

              <div>
                <label htmlFor="create-email" className={labelClass}>Email address</label>
                <input
                  id="create-email"
                  name="email"
                  type="email"
                  required
                  value={createForm.email}
                  onChange={handleCreateChange}
                  className={inputClass}
                  placeholder="analyst@example.com"
                  disabled={createBusy}
                />
              </div>

              <div>
                <label htmlFor="create-display-name" className={labelClass}>Display name (optional)</label>
                <input
                  id="create-display-name"
                  name="display_name"
                  value={createForm.display_name}
                  onChange={handleCreateChange}
                  className={inputClass}
                  placeholder="Analyst Jones"
                  disabled={createBusy}
                />
              </div>

              <div>
                <label htmlFor="create-password" className={labelClass}>Initial password</label>
                <input
                  id="create-password"
                  name="password"
                  type="password"
                  required
                  value={createForm.password}
                  onChange={handleCreateChange}
                  className={inputClass}
                  placeholder="Minimum 6 characters"
                  disabled={createBusy}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="create-role" className={labelClass}>Access role</label>
                  <select
                    id="create-role"
                    name="role"
                    value={createForm.role}
                    onChange={handleCreateChange}
                    className={selectClass}
                    disabled={createBusy}
                  >
                    <option value="USER">USER</option>
                    <option value="ADMIN">ADMIN</option>
                    <option value="EDITOR">EDITOR</option>
                    <option value="VISITOR">VISITOR</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="create-business-role" className={labelClass}>Business role</label>
                  <select
                    id="create-business-role"
                    name="business_role"
                    value={createForm.business_role}
                    onChange={handleCreateChange}
                    className={selectClass}
                    disabled={createBusy}
                  >
                    <option value="GENERAL">GENERAL</option>
                    <option value="DEVELOPER">DEVELOPER</option>
                    <option value="HR">HR</option>
                    <option value="FINANCE">FINANCE</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  className={btnSecondary}
                  onClick={() => setCreateOpen(false)}
                  disabled={createBusy}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={btnPrimary}
                  disabled={createBusy}
                >
                  {createBusy ? <Loader2 size={14} className="animate-spin" /> : null}
                  Create account
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {/* REVOKE DEVICE CONFIRMATION */}
      <ConfirmDialog
        open={Boolean(revokeTarget)}
        title="Revoke device access"
        message={`Are you sure you want to revoke endpoint ${revokeTarget?.hostname || revokeTarget?.device_id}? The device will be disconnected immediately and cannot send telemetry until re-enrolled.`}
        confirmLabel={revokeBusy ? 'Revoking…' : 'Revoke device'}
        tone="red"
        busy={revokeBusy}
        error={revokeError}
        onConfirm={handleRevoke}
        onCancel={() => !revokeBusy && setRevokeTarget(null)}
      />

      {/* DELETE USER CONFIRMATION */}
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete user account"
        message={`Are you sure you want to permanently delete account ${deleteTarget?.user_id}? Associated devices and session records will no longer authenticate.`}
        confirmLabel={deleteBusy ? 'Deleting…' : 'Delete account'}
        tone="red"
        busy={deleteBusy}
        error={deleteError}
        onConfirm={handleDelete}
        onCancel={() => !deleteBusy && setDeleteTarget(null)}
      />
    </div>
  );
}
