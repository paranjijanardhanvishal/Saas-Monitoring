import React, { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { ArrowRight, Eye, EyeOff, Loader2, LockKeyhole, ShieldCheck, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { errorMessage, forgotPassword } from '../api';
import { btnPrimary, btnSecondary, inputClass, labelClass } from '../components/ui';

export default function Login() {
  const { login, user, loading, sessionMessage } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const [forgotOpen, setForgotOpen] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotBusy, setForgotBusy] = useState(false);
  const [forgotMessage, setForgotMessage] = useState('');
  const [forgotError, setForgotError] = useState('');
  const [devResetLink, setDevResetLink] = useState('');

  const destinationFor = (account) => {
    if (!account) return '/dashboard';
    if (account.role === 'USER' && account.monitoring_enabled === 'NOT_ASKED') {
      return '/consent';
    }
    const requested = location.state?.from;
    if (requested && requested !== '/login' && !requested.startsWith('/consent')) {
      return requested;
    }
    return '/dashboard';
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0b0f19] text-slate-400">
        <Loader2 size={22} className="mr-3 animate-spin text-blue-400" />
        Checking session…
      </div>
    );
  }

  if (user) return <Navigate to={destinationFor(user)} replace />;

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const account = await login(identifier, password);
      navigate(destinationFor(account), { replace: true });
    } catch (err) {
      setError(errorMessage(err, 'Sign-in failed. Please check your credentials.'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleForgotSubmit = async (e) => {
    e.preventDefault();
    setForgotBusy(true);
    setForgotError('');
    setForgotMessage('');
    setDevResetLink('');
    try {
      const res = await forgotPassword(forgotEmail.trim());
      setForgotMessage(res.message || 'If an account exists with that email address, a password reset link has been dispatched.');
      if (res.dev_reset_link) {
        setDevResetLink(res.dev_reset_link);
      }
    } catch (err) {
      setForgotError(errorMessage(err, 'Failed to send password reset link.'));
    } finally {
      setForgotBusy(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#0b0f19] px-4 py-10 pb-28 sm:pb-16">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-40 left-1/2 h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-blue-600/10 blur-[120px]" />
        <div className="absolute bottom-0 right-0 h-[360px] w-[360px] rounded-full bg-emerald-500/5 blur-[100px]" />
      </div>

      <div className="relative z-20 grid w-full max-w-5xl overflow-hidden rounded-2xl border border-slate-800 bg-[#0d1320] shadow-2xl shadow-black/40 lg:grid-cols-2">
        <div className="hidden flex-col justify-between border-r border-slate-800 bg-[#0a0f1a] p-10 lg:flex">
          <div>
            <Link to="/" className="inline-flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-500/30 bg-blue-500/10 text-blue-400">
                <ShieldCheck size={22} />
              </span>
              <span className="text-sm font-bold tracking-tight text-white">
                SaaS Security Monitor
              </span>
            </Link>

            <h1 className="mt-14 text-3xl font-bold leading-tight tracking-tight text-white">
              Security operations for
              <span className="text-blue-400"> SaaS data and endpoints</span>
            </h1>
            <p className="mt-4 max-w-md text-sm leading-relaxed text-slate-400">
              Correlate endpoint telemetry, sensitive-data findings and behavioural baselines into
              explainable risk assessments for authorised SOC investigation.
            </p>

            <ul className="mt-8 space-y-3 text-sm text-slate-400">
              {[
                'Consent-gated endpoint monitoring',
                'PII detection with derived-only storage',
                'EWMA behaviour analytics and four-signal risk scoring',
                'Administrator-confirmed, auditable response actions',
              ].map((item) => (
                <li key={item} className="flex items-start gap-2.5">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <p className="text-[11px] leading-relaxed text-slate-600">
            Accounts are provisioned by an administrator. Access is logged. Monitoring is only
            active after the monitored user grants consent.
          </p>
        </div>

        <div className="p-7 sm:p-10">
          <div className="mb-8 lg:hidden">
            <Link to="/" className="inline-flex items-center gap-2 text-sm font-bold text-white">
              <ShieldCheck size={20} className="text-blue-400" />
              SaaS Security Monitor
            </Link>
          </div>

          <div className="mb-7">
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-blue-400">
              Secure sign-in
            </p>
            <h2 className="mt-1 text-2xl font-bold text-white">Access the SOC console</h2>
            <p className="mt-1 text-sm text-slate-500">
              Use the email address or user ID assigned by your administrator.
            </p>
          </div>

          {sessionMessage ? (
            <div className="mb-5 rounded-lg border border-amber-900/50 bg-amber-950/20 p-3 text-xs text-amber-200">
              {sessionMessage}
            </div>
          ) : null}

          {error ? (
            <div
              role="alert"
              className="mb-5 rounded-lg border border-red-900/50 bg-red-950/20 p-3 text-xs leading-relaxed text-red-200"
            >
              {error}
            </div>
          ) : null}

          <form onSubmit={handleSubmit} className="space-y-4" autoComplete="on">
            <div>
              <label htmlFor="identifier" className={labelClass}>
                Email or user ID
              </label>
              <input
                id="identifier"
                name="username"
                type="text"
                autoComplete="username"
                required
                value={identifier}
                onChange={(event) => setIdentifier(event.target.value)}
                className={inputClass}
                placeholder="analyst@example.com"
                disabled={submitting}
              />
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label htmlFor="password" className={labelClass}>
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => {
                    setForgotOpen(true);
                    setForgotEmail(identifier.includes('@') ? identifier : '');
                    setForgotMessage('');
                    setForgotError('');
                    setDevResetLink('');
                  }}
                  className="mb-1 text-[11px] font-semibold text-blue-400 hover:text-blue-300"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className={`${inputClass} pr-11`}
                  placeholder="Enter your password"
                  disabled={submitting}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-2 text-slate-500 hover:bg-slate-800 hover:text-slate-300"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            <button type="submit" disabled={submitting} className="mt-2 w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60">
              <span className="inline-flex items-center justify-center gap-2">
                {submitting ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Signing in…
                  </>
                ) : (
                  <>
                    Sign in
                    <ArrowRight size={16} />
                  </>
                )}
              </span>
            </button>
          </form>

          <div className="mt-6 flex items-start gap-2 rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-[11px] leading-relaxed text-slate-500">
            <LockKeyhole size={14} className="mt-0.5 shrink-0 text-slate-500" />
            <span>
              Sessions use an HttpOnly cookie with CSRF protection. There is no public sign-up;
              contact an administrator if you need an account.
            </span>
          </div>
        </div>
      </div>

      {forgotOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-black/75 backdrop-blur-sm"
            onClick={() => setForgotOpen(false)}
          />
          <div className="relative w-full max-w-md rounded-2xl border border-slate-800 bg-[#0d1320] p-6 shadow-2xl">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-base font-bold text-white">Reset Password</h3>
                <p className="mt-1 text-xs text-slate-400">
                  Enter your registered account email address. We will generate a secure single-use reset link.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setForgotOpen(false)}
                className="rounded-md p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleForgotSubmit} className="mt-5 space-y-4">
              {forgotMessage ? (
                <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-300">
                  <p>{forgotMessage}</p>
                  {devResetLink ? (
                    <div className="mt-2.5 rounded bg-slate-900/90 p-2 font-mono text-[11px] text-blue-300 break-all border border-blue-500/30">
                      <span className="font-semibold text-slate-400">Local Dev Link: </span>
                      <a href={devResetLink} className="underline text-blue-400 hover:text-blue-300">{devResetLink}</a>
                    </div>
                  ) : null}
                </div>
              ) : null}
              {forgotError ? (
                <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300">
                  {forgotError}
                </div>
              ) : null}

              <div>
                <label htmlFor="forgot-email" className={labelClass}>Registered Email Address</label>
                <input
                  id="forgot-email"
                  type="email"
                  required
                  value={forgotEmail}
                  onChange={(e) => setForgotEmail(e.target.value)}
                  className={inputClass}
                  placeholder="analyst@example.com"
                  disabled={forgotBusy}
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  className={btnSecondary}
                  onClick={() => setForgotOpen(false)}
                  disabled={forgotBusy}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={btnPrimary}
                  disabled={forgotBusy || !forgotEmail}
                >
                  {forgotBusy ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      Sending…
                    </>
                  ) : (
                    'Send Reset Link'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
