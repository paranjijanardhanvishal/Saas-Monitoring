import React, { useEffect, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { ArrowRight, Eye, EyeOff, Loader2, LockKeyhole, ShieldCheck, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { errorMessage, forgotPassword } from '../api';
import { btnPrimary, btnSecondary, inputClass, labelClass } from '../components/ui';

export default function Login() {
  const { login, signup, user, loading, sessionMessage, clearSessionMessage } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [mode, setMode] = useState('signin'); // 'signin' | 'signup'

  // Sign In state
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Sign Up state
  const [signupEmail, setSignupEmail] = useState('');
  const [signupPassword, setSignupPassword] = useState('');
  const [signupConfirmPassword, setSignupConfirmPassword] = useState('');
  const [showSignupPassword, setShowSignupPassword] = useState(false);
  const [showSignupConfirmPassword, setShowSignupConfirmPassword] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [coldStartProgress, setColdStartProgress] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let timer;
    if (submitting) {
      timer = setTimeout(() => {
        setColdStartProgress(true);
      }, 4000);
    } else {
      setColdStartProgress(false);
    }
    return () => clearTimeout(timer);
  }, [submitting]);

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
    if (submitting) return;
    setError('');
    clearSessionMessage?.();
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

  const handleSignupSubmit = async (event) => {
    event.preventDefault();
    if (submitting) return;
    setError('');
    clearSessionMessage?.();
    if (signupPassword !== signupConfirmPassword) {
      setError('Passwords do not match. Please re-enter your password.');
      return;
    }
    if (signupPassword.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }
    setSubmitting(true);
    try {
      const account = await signup(signupEmail, signupPassword, signupConfirmPassword);
      navigate(destinationFor(account), { replace: true });
    } catch (err) {
      setError(errorMessage(err, 'Sign-up failed. Please verify your details.'));
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

          <div className="mb-6 flex rounded-lg border border-slate-800 bg-slate-900/60 p-1">
            <button
              type="button"
              onClick={() => {
                setMode('signin');
                setError('');
              }}
              className={`flex-1 rounded-md py-2 text-xs font-semibold transition ${
                mode === 'signin'
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setMode('signup');
                setError('');
              }}
              className={`flex-1 rounded-md py-2 text-xs font-semibold transition ${
                mode === 'signup'
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Sign Up (New User)
            </button>
          </div>

          <div className="mb-7">
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-blue-400">
              {mode === 'signin' ? 'Secure sign-in' : 'New User Registration'}
            </p>
            <h2 className="mt-1 text-2xl font-bold text-white">
              {mode === 'signin' ? 'Access the SOC console' : 'Create your account'}
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              {mode === 'signin'
                ? 'Sign in with your email address or user ID (all email domains supported).'
                : 'Enter your email, password, and confirm password to sign up.'}
            </p>
          </div>

          {sessionMessage ? (
            <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-200">
              {sessionMessage}
            </div>
          ) : null}

          {error ? (
            <div
              role="alert"
              className="mb-5 rounded-lg border border-red-200 bg-red-50 p-3 text-xs leading-relaxed text-red-800 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-200"
            >
              {error}
            </div>
          ) : null}

          {mode === 'signin' ? (
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
                  onChange={(event) => {
                    setIdentifier(event.target.value);
                    clearSessionMessage?.();
                    if (error) setError('');
                  }}
                  className={inputClass}
                  placeholder="user@user.com or admin@admin.com"
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
                    onChange={(event) => {
                      setPassword(event.target.value);
                      clearSessionMessage?.();
                      if (error) setError('');
                    }}
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

              {coldStartProgress ? (
                <div className="flex items-center gap-2 rounded-lg border border-blue-500/30 bg-blue-500/10 p-2.5 text-xs text-blue-300">
                  <Loader2 size={14} className="animate-spin text-blue-400 shrink-0" />
                  <span>Connecting to backend (waking up cloud server instance, please wait)...</span>
                </div>
              ) : null}

              <button
                type="submit"
                disabled={submitting}
                className="mt-2 w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
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

              <div className="pt-2 text-center text-xs text-slate-400">
                New user?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setMode('signup');
                    setError('');
                  }}
                  className="font-semibold text-blue-400 hover:text-blue-300"
                >
                  Create an account
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={handleSignupSubmit} className="space-y-4" autoComplete="on">
              <div>
                <label htmlFor="signup-email" className={labelClass}>
                  Enter your email
                </label>
                <input
                  id="signup-email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={signupEmail}
                  onChange={(event) => {
                    setSignupEmail(event.target.value);
                    clearSessionMessage?.();
                    if (error) setError('');
                  }}
                  className={inputClass}
                  placeholder="user@user.com or you@example.com"
                  disabled={submitting}
                />
                <p className="mt-1 text-[11px] text-slate-500">
                  All email domains (@user.com, @visitor.com, @admin.com, etc.) are accepted.
                </p>
              </div>

              <div>
                <label htmlFor="signup-password" className={labelClass}>
                  Password
                </label>
                <div className="relative">
                  <input
                    id="signup-password"
                    name="password"
                    type={showSignupPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    required
                    value={signupPassword}
                    onChange={(event) => {
                      setSignupPassword(event.target.value);
                      clearSessionMessage?.();
                      if (error) setError('');
                    }}
                    className={`${inputClass} pr-11`}
                    placeholder="Enter password (min 6 characters)"
                    disabled={submitting}
                  />
                  <button
                    type="button"
                    onClick={() => setShowSignupPassword((visible) => !visible)}
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-2 text-slate-500 hover:bg-slate-800 hover:text-slate-300"
                    aria-label={showSignupPassword ? 'Hide password' : 'Show password'}
                  >
                    {showSignupPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>

              <div>
                <label htmlFor="signup-confirm-password" className={labelClass}>
                  Re-enter password
                </label>
                <div className="relative">
                  <input
                    id="signup-confirm-password"
                    name="confirm_password"
                    type={showSignupConfirmPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    required
                    value={signupConfirmPassword}
                    onChange={(event) => {
                      setSignupConfirmPassword(event.target.value);
                      clearSessionMessage?.();
                      if (error) setError('');
                    }}
                    className={`${inputClass} pr-11`}
                    placeholder="Confirm your password"
                    disabled={submitting}
                  />
                  <button
                    type="button"
                    onClick={() => setShowSignupConfirmPassword((visible) => !visible)}
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-2 text-slate-500 hover:bg-slate-800 hover:text-slate-300"
                    aria-label={showSignupConfirmPassword ? 'Hide password' : 'Show password'}
                  >
                    {showSignupConfirmPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>

              {coldStartProgress ? (
                <div className="flex items-center gap-2 rounded-lg border border-blue-500/30 bg-blue-500/10 p-2.5 text-xs text-blue-300">
                  <Loader2 size={14} className="animate-spin text-blue-400 shrink-0" />
                  <span>Connecting to backend (waking up cloud server instance, please wait)...</span>
                </div>
              ) : null}

              <button
                type="submit"
                disabled={submitting}
                className="mt-2 w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <span className="inline-flex items-center justify-center gap-2">
                  {submitting ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Creating account…
                    </>
                  ) : (
                    <>
                      Sign up
                      <ArrowRight size={16} />
                    </>
                  )}
                </span>
              </button>

              <div className="pt-2 text-center text-xs text-slate-400">
                Already have an account?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setMode('signin');
                    setError('');
                  }}
                  className="font-semibold text-blue-400 hover:text-blue-300"
                >
                  Sign in
                </button>
              </div>
            </form>
          )}

          <div className="mt-6 flex items-start gap-2 rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-[11px] leading-relaxed text-slate-500">
            <LockKeyhole size={14} className="mt-0.5 shrink-0 text-slate-500" />
            <span>
              Sessions use HttpOnly cookies with CSRF protection. Users with any email domain (@user.com, @visitor.com, @admin.com, etc.) can sign in or register above.
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
