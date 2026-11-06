import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowRight, CheckCircle2, Eye, EyeOff, Loader2, LockKeyhole, ShieldCheck } from 'lucide-react';
import { errorMessage, resetPassword } from '../api';
import { btnPrimary, inputClass, labelClass } from '../components/ui';

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const navigate = useNavigate();

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!token) {
      setError('Missing reset token. Please request a new password reset link.');
      return;
    }
    if (password.length < 12) {
      setError('Password must be at least 12 characters.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      const result = await resetPassword(token, password);
      setSuccess(result.message || 'Password reset successfully. Redirecting to sign in…');
      setTimeout(() => {
        navigate('/login', { replace: true });
      }, 2500);
    } catch (err) {
      setError(errorMessage(err, 'Failed to reset password. The link may have expired or already been used.'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#0b0f19] px-4 py-10">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-40 left-1/2 h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-blue-600/10 blur-[120px]" />
      </div>

      <div className="relative z-20 w-full max-w-md rounded-2xl border border-slate-800 bg-[#0d1320] p-8 shadow-2xl shadow-black/40">
        <div className="mb-6 text-center">
          <Link to="/" className="inline-flex items-center gap-2 text-sm font-bold text-white">
            <ShieldCheck size={22} className="text-blue-400" />
            SaaS Security Monitor
          </Link>
          <h1 className="mt-3 text-xl font-bold text-white">Set a new password</h1>
          <p className="mt-1 text-xs text-slate-400">
            Choose a strong password of at least 12 characters.
          </p>
        </div>

        {error ? (
          <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs leading-relaxed text-red-300">
            {error}
          </div>
        ) : null}

        {success ? (
          <div className="mb-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-300 flex items-center gap-2">
            <CheckCircle2 size={16} className="shrink-0 text-emerald-400" />
            <span>{success}</span>
          </div>
        ) : null}

        {!token ? (
          <div className="space-y-4 text-center">
            <p className="text-xs text-amber-300">
              No reset token found in the URL. Please use the link sent to your email or request a new reset.
            </p>
            <Link to="/login" className="inline-block text-xs font-semibold text-blue-400 hover:text-blue-300">
              Return to login →
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="new-password" className={labelClass}>New Password (min 12 chars)</label>
              <div className="relative">
                <input
                  id="new-password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  minLength={12}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={`${inputClass} pr-11`}
                  placeholder="••••••••••••"
                  disabled={submitting || Boolean(success)}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-2 text-slate-500 hover:bg-slate-800 hover:text-slate-300"
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            <div>
              <label htmlFor="confirm-password" className={labelClass}>Confirm New Password</label>
              <input
                id="confirm-password"
                type="password"
                required
                minLength={12}
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={inputClass}
                placeholder="••••••••••••"
                disabled={submitting || Boolean(success)}
              />
            </div>

            <button
              type="submit"
              disabled={submitting || !password || !confirmPassword || Boolean(success)}
              className={`${btnPrimary} w-full mt-2`}
            >
              {submitting ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Updating password…
                </>
              ) : (
                <>
                  Update password
                  <ArrowRight size={16} />
                </>
              )}
            </button>

            <div className="text-center pt-2">
              <Link to="/login" className="text-xs font-medium text-slate-400 hover:text-white">
                Back to sign in
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

