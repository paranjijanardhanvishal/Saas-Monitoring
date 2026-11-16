import React, { useEffect, useId, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, Loader2, Search, X } from 'lucide-react';

export const cx = (...classes) => classes.filter(Boolean).join(' ');

export const inputClass =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-blue-600 focus:ring-1 focus:ring-blue-600/40 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-100 dark:placeholder-slate-500 dark:focus:border-blue-500';

export const selectClass =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-blue-600 focus:ring-1 focus:ring-blue-600/40 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-100 dark:focus:border-blue-500';

export const labelClass =
  'mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400';

export const btnPrimary =
  'inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-xs transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-600/40 disabled:cursor-not-allowed disabled:opacity-50';

export const btnSecondary =
  'inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-xs transition hover:border-slate-400 hover:bg-slate-50 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-600/40 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-800 dark:hover:text-white';

export const btnDanger =
  'inline-flex items-center justify-center gap-2 rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm font-semibold text-red-700 shadow-xs transition hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-500/40 disabled:cursor-not-allowed disabled:opacity-50 dark:border-red-800/60 dark:bg-red-950/40 dark:text-red-300 dark:hover:bg-red-900/50';

export const btnGhost =
  'inline-flex items-center justify-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-400/40 disabled:cursor-not-allowed disabled:opacity-50 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white';

export function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function formatTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

export function timeAgo(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return `${Math.max(seconds, 0)}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function formatNumber(value) {
  if (value === null || value === undefined) return '—';
  const number = Number(value);
  if (Number.isNaN(number)) return '—';
  return number.toLocaleString();
}

export function formatScore(value, digits = 0) {
  if (value === null || value === undefined) return '—';
  const number = Number(value);
  if (Number.isNaN(number)) return '—';
  return number.toFixed(digits);
}

export function formatPercent(value, digits = 0) {
  if (value === null || value === undefined) return '—';
  const number = Number(value);
  if (Number.isNaN(number)) return '—';
  return `${(number * 100).toFixed(digits)}%`;
}

/* ------------------------------------------------------------------ tones */

const TONES = {
  neutral:
    'border-slate-200 bg-[#F1F5F9] text-[#475569] dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-300',
  blue:
    'border-[#BFDBFE] bg-[#EFF6FF] text-[#1D4ED8] dark:border-blue-800/60 dark:bg-blue-950/40 dark:text-blue-300',
  green:
    'border-[#A7F3D0] bg-[#ECFDF5] text-[#059669] dark:border-emerald-800/60 dark:bg-emerald-950/40 dark:text-emerald-300',
  emerald:
    'border-[#A7F3D0] bg-[#ECFDF5] text-[#059669] dark:border-emerald-800/60 dark:bg-emerald-950/40 dark:text-emerald-300',
  amber:
    'border-[#FDE68A] bg-[#FFFBEB] text-[#B45309] dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-300',
  orange:
    'border-[#FED7AA] bg-[#FFF7ED] text-[#C2410C] dark:border-orange-800/60 dark:bg-orange-950/40 dark:text-orange-300',
  red:
    'border-[#FECACA] bg-[#FEF2F2] text-[#DC2626] dark:border-red-800/60 dark:bg-red-950/40 dark:text-red-300',
  purple:
    'border-[#E9D5FF] bg-[#FAF5FF] text-[#6B21A8] dark:border-purple-800/60 dark:bg-purple-950/40 dark:text-purple-300',
  cyan:
    'border-[#A5F3FC] bg-[#ECFEFF] text-[#0E7490] dark:border-cyan-800/60 dark:bg-cyan-950/40 dark:text-cyan-300',
};

export function Badge({ children, tone = 'neutral', className = '' }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider transition-colors',
        TONES[tone] || TONES.neutral,
        className,
      )}
    >
      {children}
    </span>
  );
}

export const severityTone = (severity) =>
  ({
    CRITICAL: 'red',
    HIGH: 'orange',
    MEDIUM: 'amber',
    LOW: 'green',
  })[severity] || 'neutral';

export const statusTone = (status) =>
  ({
    OPEN: 'red',
    ACKNOWLEDGED: 'blue',
    INVESTIGATING: 'amber',
    CONTAINED: 'purple',
    RESOLVED: 'green',
    DISMISSED: 'neutral',
    EXECUTED: 'green',
    FAILED: 'red',
    ALREADY_HANDLED: 'amber',
    ROLLED_BACK: 'blue',
    ACTIVE: 'green',
    REVOKED: 'red',
    RESTRICTED: 'red',
  })[status] || 'neutral';

export const consentTone = (state) =>
  ({
    ALLOWED: 'green',
    NOT_ASKED: 'amber',
    DECLINED: 'orange',
    REVOKED: 'red',
  })[state] || 'neutral';

/* ----------------------------------------------------------------- layout */

export function PageHeader({ title, subtitle, actions, eyebrow }) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow ? (
          <p className="mb-1 text-[11px] font-bold uppercase tracking-[0.18em] text-blue-600 dark:text-blue-400">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">{title}</h1>
        {subtitle ? <p className="mt-1 max-w-3xl text-sm text-slate-600 dark:text-slate-400">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function Panel({ title, subtitle, actions, children, className = '', bodyClassName = '' }) {
  return (
    <section
      className={cx(
        'overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs dark:border-slate-800 dark:bg-[#111827] dark:shadow-lg dark:shadow-black/10',
        className,
      )}
    >
      {title || actions ? (
        <div className="flex flex-col gap-2 border-b border-slate-200 px-5 py-3.5 sm:flex-row sm:items-center sm:justify-between dark:border-slate-800">
          <div>
            {title ? <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">{title}</h2> : null}
            {subtitle ? <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{subtitle}</p> : null}
          </div>
          {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
        </div>
      ) : null}
      <div className={cx('p-5', bodyClassName)}>{children}</div>
    </section>
  );
}

export function StatCard({ label, value, hint, icon: Icon, tone = 'blue', loading = false }) {
  const iconTones = {
    blue: 'bg-blue-50 text-blue-600 border-blue-200 dark:bg-blue-500/10 dark:text-blue-400 dark:border-blue-500/20',
    green: 'bg-emerald-50 text-emerald-600 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/20',
    amber: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/20',
    red: 'bg-red-50 text-red-600 border-red-200 dark:bg-red-500/10 dark:text-red-400 dark:border-red-500/20',
    purple: 'bg-purple-50 text-purple-600 border-purple-200 dark:bg-purple-500/10 dark:text-purple-400 dark:border-purple-500/20',
    neutral: 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-500/10 dark:text-slate-400 dark:border-slate-500/20',
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition hover:border-slate-300 dark:border-slate-800 dark:bg-[#111827] dark:shadow-lg dark:shadow-black/10 dark:hover:border-slate-700">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">{label}</p>
          <p className="mt-2 text-2xl font-bold tabular-nums text-slate-900 dark:text-white">
            {loading ? <span className="inline-block h-7 w-14 animate-pulse rounded bg-slate-200 dark:bg-slate-800" /> : value}
          </p>
          {hint ? <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{hint}</p> : null}
        </div>
        {Icon ? (
          <span className={cx('rounded-lg border p-2.5', iconTones[tone] || iconTones.blue)}>
            <Icon size={19} />
          </span>
        ) : null}
      </div>
    </div>
  );
}

export function ProgressBar({ value, max = 100, tone }) {
  const pct = Math.max(0, Math.min(100, ((Number(value) || 0) / (max || 100)) * 100));
  const color = tone || (pct >= 75 ? 'bg-red-500' : pct >= 45 ? 'bg-amber-500' : 'bg-emerald-500');
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
      <div className={cx('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

/* ------------------------------------------------------------------ states */

export function LoadingState({ label = 'Loading data…', className = '' }) {
  return (
    <div className={cx('flex items-center justify-center gap-3 py-14 text-sm text-slate-500 dark:text-slate-400', className)}>
      <Loader2 size={18} className="animate-spin text-blue-600 dark:text-blue-400" />
      {label}
    </div>
  );
}

export function EmptyState({ icon: Icon = Info, title, message, action, className = '' }) {
  return (
    <div className={cx('flex flex-col items-center justify-center px-4 py-14 text-center', className)}>
      <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
        <Icon size={22} />
      </span>
      <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200">{title}</h3>
      {message ? <p className="mt-1 max-w-md text-xs leading-relaxed text-slate-500 dark:text-slate-400">{message}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ message, onRetry, className = '' }) {
  return (
    <div
      className={cx(
        'flex flex-col items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-200',
        className,
      )}
      role="alert"
    >
      <div className="flex items-start gap-2">
        <AlertTriangle size={17} className="mt-0.5 shrink-0 text-red-600 dark:text-red-400" />
        <div>
          <p className="font-semibold text-red-900 dark:text-red-200">Request failed</p>
          <p className="mt-0.5 text-xs leading-relaxed text-red-700 dark:text-red-300/80">{message}</p>
        </div>
      </div>
      {onRetry ? (
        <button type="button" onClick={onRetry} className={btnSecondary}>
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function InlineNotice({ tone = 'info', children, className = '' }) {
  const toneClass = {
    info: 'border-blue-200 bg-blue-50/90 text-blue-900 dark:border-blue-900/50 dark:bg-blue-950/30 dark:text-blue-200',
    success: 'border-emerald-200 bg-emerald-50/90 text-emerald-900 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-200',
    warning: 'border-amber-200 bg-amber-50/90 text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200',
    danger: 'border-red-200 bg-red-50/90 text-red-900 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-200',
    neutral: 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-300',
  }[tone] || 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-300';
  const Icon = tone === 'success' ? CheckCircle2 : tone === 'info' ? Info : AlertTriangle;
  return (
    <div className={cx('flex items-start gap-2.5 rounded-lg border p-3.5 text-xs leading-relaxed', toneClass, className)}>
      <Icon size={16} className="mt-0.5 shrink-0" />
      <div className="flex-1">{children}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ search */

export function SearchInput({ value, onChange, placeholder = 'Search…', onSubmit, className = '' }) {
  const id = useId();
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (onSubmit) onSubmit();
      }}
      className={cx('relative', className)}
    >
      <label htmlFor={id} className="sr-only">
        {placeholder}
      </label>
      <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
      <input
        id={id}
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className={cx(inputClass, 'pl-9')}
      />
    </form>
  );
}

/* ------------------------------------------------------------------ drawer */

export function Drawer({ open, title, subtitle, onClose, children, footer, width = 'max-w-2xl' }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        aria-label="Close details"
        onClick={onClose}
        className="absolute inset-0 cursor-default bg-slate-900/60 backdrop-blur-xs"
      />
      <aside
        className={cx(
          'relative flex h-full w-full flex-col border-l border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-[#0d1320]',
          width,
        )}
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === 'string' ? title : 'Details'}
      >
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-4 dark:border-slate-800">
          <div>
            <h2 className="text-base font-bold text-slate-900 dark:text-white">{title}</h2>
            {subtitle ? <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{subtitle}</p> : null}
          </div>
          <button type="button" onClick={onClose} className={btnGhost} aria-label="Close">
            <X size={16} />
          </button>
        </header>
        <div className="custom-scrollbar flex-1 overflow-y-auto p-6">{children}</div>
        {footer ? <footer className="border-t border-slate-200 p-4 dark:border-slate-800">{footer}</footer> : null}
      </aside>
    </div>
  );
}

/* ------------------------------------------------------------------ dialog */

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  tone = 'danger',
  requireReason = false,
  busy = false,
  error = '',
  onConfirm,
  onClose,
}) {
  const [reason, setReason] = useState('');
  useEffect(() => {
    if (!open) setReason('');
  }, [open]);
  if (!open) return null;
  const disabled = busy || (requireReason && reason.trim().length < 3);
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Cancel"
        onClick={busy ? undefined : onClose}
        className="absolute inset-0 cursor-default bg-slate-900/60 backdrop-blur-xs"
      />
      <div className="relative w-full max-w-md rounded-xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-[#111827]">
        <h2 className="text-base font-bold text-slate-900 dark:text-white">{title}</h2>
        <div className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">{message}</div>
        {requireReason ? (
          <div className="mt-4">
            <label className={labelClass} htmlFor="confirm-reason">
              Reason (required, min 3 characters)
            </label>
            <textarea
              id="confirm-reason"
              rows={3}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              className={inputClass}
              placeholder="Explain why this action is being taken"
            />
          </div>
        ) : null}
        {error ? <p className="mt-3 text-xs text-red-600 dark:text-red-300">{error}</p> : null}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className={btnSecondary} onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            type="button"
            className={tone === 'danger' ? btnDanger : btnPrimary}
            disabled={disabled}
            onClick={() => onConfirm(requireReason ? reason.trim() : undefined)}
          >
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- pagination */

export function Pagination({ skip, limit, count, onPrevious, onNext, loading = false }) {
  const start = count === 0 ? 0 : skip + 1;
  const end = skip + count;
  return (
    <div className="flex flex-col gap-2 border-t border-slate-200 px-5 py-3.5 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between dark:border-slate-800 dark:text-slate-400">
      <span>
        Showing <span className="font-semibold text-slate-700 dark:text-slate-300">{start}</span>–
        <span className="font-semibold text-slate-700 dark:text-slate-300">{end}</span>
        {count > 0 ? ' of the current result set' : ''}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          className={btnSecondary}
          disabled={skip === 0 || loading}
          onClick={onPrevious}
        >
          Previous
        </button>
        <button
          type="button"
          className={btnSecondary}
          disabled={count < limit || loading}
          onClick={onNext}
        >
          Next
        </button>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------- misc */

export function KeyValue({ label, children, className = '' }) {
  return (
    <div className={className}>
      <dt className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="mt-1 break-words text-sm font-medium text-slate-800 dark:text-slate-200">{children ?? '—'}</dd>
    </div>
  );
}
