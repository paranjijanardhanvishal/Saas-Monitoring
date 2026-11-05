import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  EyeOff,
  FileWarning,
  Loader2,
  ShieldCheck,
  ShieldOff,
  UserRound,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { errorMessage } from '../api';
import { Badge, btnPrimary, btnSecondary, consentTone, formatDateTime, InlineNotice } from '../components/ui';

export default function Consent() {
  const { user, updateConsent, logout } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  if (!user) return null;

  const state = user.monitoring_enabled;
  const isAdmin = user.role === 'ADMIN';

  const apply = async (nextState) => {
    setBusy(nextState);
    setError('');
    setSuccess('');
    try {
      await updateConsent(nextState);
      setSuccess(
        nextState === 'ALLOWED'
          ? 'Consent recorded. Endpoint monitoring may now be collected for your account.'
          : 'Consent recorded. Endpoint monitoring is disabled and any enrolled devices were revoked.',
      );
    } catch (err) {
      setError(errorMessage(err, 'Could not update consent.'));
    } finally {
      setBusy('');
    }
  };

  const signOut = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="min-h-screen bg-[#0b0f19] px-4 py-10">
      <div className="mx-auto max-w-3xl">
        <div className="mb-6 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-500/30 bg-blue-500/10 text-blue-400">
              <ShieldCheck size={21} />
            </span>
            <div>
              <p className="text-sm font-bold text-white">SaaS Security Monitor</p>
              <p className="text-xs text-slate-500">Privacy &amp; monitoring consent</p>
            </div>
          </div>
          <button type="button" onClick={signOut} className={btnSecondary}>
            Sign out
          </button>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-[#111827] p-6 shadow-2xl shadow-black/30 sm:p-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-blue-400">
                Consent required
              </p>
              <h1 className="mt-1 text-2xl font-bold text-white">Choose your monitoring preference</h1>
              <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-400">
                Monitoring is opt-in. The backend will not accept endpoint telemetry for your
                account until you record <span className="font-semibold text-slate-200">ALLOWED</span>.
                You can change or withdraw consent at any time.
              </p>
            </div>
            <div className="shrink-0 rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-center">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Current state
              </p>
              <Badge tone={consentTone(state)} className="mt-1.5">
                {state.replace('_', ' ')}
              </Badge>
            </div>
          </div>

          {error ? (
            <div className="mt-5 rounded-lg border border-red-900/50 bg-red-950/20 p-3 text-xs text-red-200" role="alert">
              {error}
            </div>
          ) : null}
          {success ? (
            <div className="mt-5 flex items-start gap-2 rounded-lg border border-emerald-900/50 bg-emerald-950/20 p-3 text-xs text-emerald-200">
              <CheckCircle2 size={15} className="mt-0.5 shrink-0" />
              {success}
            </div>
          ) : null}

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-bold text-slate-100">
                <Activity size={16} className="text-emerald-400" />
                What may be collected after consent
              </div>
              <ul className="space-y-2 text-xs leading-relaxed text-slate-400">
                <li>Process starts and stops, executable names and durations</li>
                <li>Foreground application changes and usage totals</li>
                <li>Windows session lock, unlock, logon and logoff events</li>
                <li>System start, shutdown, suspend and resume events</li>
                <li>File names and metadata in configured watch folders</li>
                <li>Failed sign-in observations when the Security log is readable</li>
              </ul>
            </section>

            <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-bold text-slate-100">
                <EyeOff size={16} className="text-red-400" />
                What is never collected
              </div>
              <ul className="space-y-2 text-xs leading-relaxed text-slate-400">
                <li>File contents, documents or clipboard data</li>
                <li>Keystrokes, screenshots, camera or microphone</li>
                <li>Browser history, passwords or credential values</li>
                <li>Window titles or full command-line arguments</li>
                <li>Data from devices you have not enrolled</li>
              </ul>
            </section>
          </div>

          <div className="mt-4 flex items-start gap-2 rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-[11px] leading-relaxed text-slate-500">
            <FileWarning size={14} className="mt-0.5 shrink-0" />
            <span>
              Withdrawing consent or declining takes effect server-side immediately. Existing device
              enrollments are revoked, and the agent stops sending events until you allow monitoring
              and re-enroll the device.
            </span>
          </div>

          {isAdmin ? (
            <InlineNotice tone="info" className="mt-4">
              You are signed in as an administrator. Consent still applies to any endpoint associated
              with your own account; administrative access does not bypass it.
            </InlineNotice>
          ) : null}

          <div className="mt-6 flex flex-col gap-3 border-t border-slate-800 pt-5 sm:flex-row sm:flex-wrap">
            {state !== 'ALLOWED' ? (
              <button
                type="button"
                className={btnPrimary}
                disabled={Boolean(busy)}
                onClick={() => apply('ALLOWED')}
              >
                {busy === 'ALLOWED' ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
                {state === 'REVOKED' ? 'Allow monitoring again' : 'Allow monitoring'}
              </button>
            ) : null}

            {state === 'NOT_ASKED' ? (
              <button
                type="button"
                className={btnSecondary}
                disabled={Boolean(busy)}
                onClick={() => apply('DECLINED')}
              >
                {busy === 'DECLINED' ? <Loader2 size={16} className="animate-spin" /> : <ShieldOff size={16} />}
                Decline monitoring
              </button>
            ) : null}

            {state === 'ALLOWED' ? (
              <button
                type="button"
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-red-800/60 bg-red-950/40 px-4 py-2 text-sm font-semibold text-red-300 transition hover:bg-red-900/50 disabled:opacity-50"
                disabled={Boolean(busy)}
                onClick={() => apply('REVOKED')}
              >
                {busy === 'REVOKED' ? <Loader2 size={16} className="animate-spin" /> : <ShieldOff size={16} />}
                Withdraw consent &amp; revoke devices
              </button>
            ) : null}

            {state === 'DECLINED' ? (
              <button
                type="button"
                className={btnSecondary}
                disabled={Boolean(busy)}
                onClick={() => apply('REVOKED')}
              >
                Mark as revoked
              </button>
            ) : null}

            <button
              type="button"
              className={`${btnSecondary} sm:ml-auto`}
              onClick={() => navigate('/dashboard')}
            >
              Continue to dashboard
              <ArrowRight size={15} />
            </button>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-slate-600">
            <span className="inline-flex items-center gap-1">
              <UserRound size={11} /> {user.user_id}
            </span>
            <span>Last consent update: {formatDateTime(user.consent_updated_at)}</span>
            {user.enforcement_status === 'RESTRICTED' ? (
              <span className="text-red-400">Account enforcement: restricted</span>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
