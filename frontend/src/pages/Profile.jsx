import React, { useCallback, useEffect, useState } from 'react';
import { Activity, AlertTriangle, Pencil, RefreshCw, ShieldCheck, UserRound } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { errorMessage, getPersonalDashboard, getUserBehaviorProfile, updateMyProfile } from '../api';
import { Badge, btnPrimary, btnSecondary, ErrorState, formatDateTime, formatScore, LoadingState, PageHeader, Panel, ProgressBar, severityTone, StatCard, statusTone } from '../components/ui';

export default function Profile() {
  const { user, refreshUser } = useAuth();
  const [dashboard, setDashboard] = useState(null);
  const [behavior, setBehavior] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const [form, setForm] = useState({ display_name: user?.display_name || '', full_name: user?.full_name || '', profile_information: user?.profile_information || '' });

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [personal, profile] = await Promise.all([
        getPersonalDashboard(), getUserBehaviorProfile(user.user_id).catch(() => null),
      ]);
      setDashboard(personal); setBehavior(profile);
    } catch (err) { setError(errorMessage(err, 'Could not load your personal security data.')); }
    finally { setLoading(false); }
  }, [user?.user_id]);

  useEffect(() => { if (user?.user_id) load(); }, [load, user?.user_id]);

  const save = async (event) => {
    event.preventDefault(); setSaving(true); setNotice('');
    try {
      await updateMyProfile(form); await refreshUser(); setEditing(false); setNotice('Profile saved.');
    } catch (err) { setError(errorMessage(err, 'Could not save profile.')); }
    finally { setSaving(false); }
  };

  if (loading) return <LoadingState label="Loading your security profile…" />;
  if (error && !dashboard) return <ErrorState title="Profile unavailable" message={error} onRetry={load} />;
  const latestRisk = dashboard?.risk?.latest;
  const baseline = behavior?.baseline || behavior?.profile?.baseline || {};
  const recentAlerts = dashboard?.alerts?.recent || [];

  return <div className="space-y-6">
    <PageHeader eyebrow="Personal security" title="My Profile & Security Dashboard" subtitle="Your account, live activity and role-aware behavioural baseline. This view is always scoped to your own account." actions={<button className={btnSecondary} onClick={load}><RefreshCw size={15} /> Refresh</button>} />
    {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">{error}</div> : null}
    {notice ? <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300">{notice}</div> : null}
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard label="Personal risk" value={formatScore(latestRisk?.risk_score)} hint={latestRisk?.risk_category || 'No scored activity'} icon={ShieldCheck} tone={latestRisk?.risk_score >= 70 ? 'red' : latestRisk?.risk_score >= 40 ? 'amber' : 'green'} />
      <StatCard label="Open alerts" value={dashboard?.alerts?.open ?? 0} hint="Your unresolved detections" icon={AlertTriangle} tone="amber" />
      <StatCard label="Events / 24h" value={dashboard?.events?.last_24h ?? 0} hint={`Last activity: ${formatDateTime(dashboard?.events?.last_event_at)}`} icon={Activity} tone="blue" />
      <StatCard label="Managed devices" value={dashboard?.devices?.active ?? 0} hint={`${dashboard?.devices?.stale ?? 0} stale`} icon={UserRound} tone="purple" />
    </div>
    <div className="grid gap-6 xl:grid-cols-[1.1fr_.9fr]">
      <Panel title="Account information" subtitle="Identity and access controls are protected; only personal display fields can be changed here." actions={<button className={btnSecondary} onClick={() => setEditing((value) => !value)}><Pencil size={14} /> {editing ? 'Cancel' : 'Edit profile'}</button>}>
        {editing ? <form onSubmit={save} className="space-y-4">
          <Field label="Display name" value={form.display_name} onChange={(display_name) => setForm({ ...form, display_name })} required />
          <Field label="Full name" value={form.full_name} onChange={(full_name) => setForm({ ...form, full_name })} />
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Profile information<textarea value={form.profile_information} maxLength={500} rows={3} onChange={(e) => setForm({ ...form, profile_information: e.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" /></label>
          <button disabled={saving} className={btnPrimary}>{saving ? 'Saving…' : 'Save profile'}</button>
        </form> : <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2 text-sm">
          <Info label="Display name" value={user?.display_name || user?.user_id} /><Info label="Full name" value={user?.full_name || 'Not provided'} />
          <Info label="Email" value={user?.email || 'Not available'} /><Info label="User ID" value={user?.user_id} />
          <Info label="Access role" value={<Badge tone="blue">{user?.role}</Badge>} /><Info label="Business role" value={<Badge tone="purple">{user?.business_role}</Badge>} />
          <Info label="Account status" value={<Badge tone={user?.is_active ? 'green' : 'red'}>{user?.is_active ? 'Active' : 'Disabled'}</Badge>} /><Info label="Monitoring consent" value={<Badge tone={user?.monitoring_enabled === 'ALLOWED' ? 'green' : 'amber'}>{user?.monitoring_enabled}</Badge>} />
        </dl>}
        <p className="mt-5 text-xs text-slate-500 dark:text-slate-400">Email and role changes require administrator approval and an identity-verification workflow; they cannot be changed from this screen.</p>
      </Panel>
      <Panel title="UEBA baseline" subtitle="Live per-user baseline calculated by the detection engine.">
        {Object.keys(baseline).length ? <div className="space-y-4">{Object.entries(baseline).slice(0, 5).map(([key, value]) => <div key={key}><div className="mb-1 flex justify-between gap-3 text-xs"><span className="font-medium text-slate-700 dark:text-slate-300">{key.replaceAll('_', ' ')}</span><span className="text-slate-500">{typeof value === 'number' ? formatScore(value, 2) : String(value)}</span></div>{typeof value === 'number' ? <ProgressBar value={Math.min(value, 100)} /> : null}</div>)}</div> : <p className="text-sm text-slate-500">A personal baseline will appear after monitored activity is analysed.</p>}
      </Panel>
    </div>
    <Panel title="Recent personal alerts" subtitle="Only alerts associated with your account are shown.">
      {recentAlerts.length ? <div className="divide-y divide-slate-200 dark:divide-slate-800">{recentAlerts.map((alert) => <div key={alert.alert_id || alert._id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm"><div><p className="font-semibold text-slate-800 dark:text-slate-200">{alert.title || alert.description || alert.alert_type || 'Security alert'}</p><p className="mt-0.5 text-xs text-slate-500">{formatDateTime(alert.timestamp)}</p></div><div className="flex gap-2"><Badge tone={severityTone(alert.severity)}>{alert.severity || 'LOW'}</Badge><Badge tone={statusTone(alert.status)}>{alert.status || 'OPEN'}</Badge></div></div>)}</div> : <p className="text-sm text-slate-500 dark:text-slate-400">No personal alerts have been generated. New monitoring events update this view automatically when refreshed.</p>}
    </Panel>
  </div>;
}

function Field({ label, value, onChange, required = false }) { return <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">{label}<input value={value || ''} required={required} onChange={(e) => onChange(e.target.value)} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" /></label>; }
function Info({ label, value }) { return <div><dt className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</dt><dd className="mt-1 text-slate-800 dark:text-slate-200">{value}</dd></div>; }
