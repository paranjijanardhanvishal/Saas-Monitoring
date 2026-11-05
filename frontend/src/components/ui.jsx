import React, { useEffect, useId, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, Loader2, Search, X } from 'lucide-react';

export const cx = (...classes) => classes.filter(Boolean).join(' ');

export const inputClass =
  'w-full rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 outline-none transition focus:border-blue-500 focus:ring-1 focus:ring-blue-500/40 disabled:cursor-not-allowed disabled:opacity-50';

export const selectClass =
  'w-full rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-blue-500 focus:ring-1 focus:ring-blue-500/40 disabled:cursor-not-allowed disabled:opacity-50';

export const labelClass =
  'mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-slate-400';

export const btnPrimary =
  'inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 disabled:cursor-not-allowed disabled:opacity-50';

export const btnSecondary =
  'inline-flex items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-800/60 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-600 hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-500/40 disabled:cursor-not-allowed disabled:opacity-50';

export const btnDanger =
  'inline-flex items-center justify-center gap-2 rounded-lg border border-red-800/60 bg-red-950/40 px-4 py-2 text-sm font-semibold text-red-300 transition hover:bg-red-900/50 focus:outline-none focus:ring-2 focus:ring-red-500/40 disabled:cursor-not-allowed disabled:opacity-50';

export const btnGhost =
  'inline-flex items-center justify-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-300 transition hover:bg-slate-800 hover:text-white focus:outline-none focus:ring-2 focus:ring-slate-500/40 disabled:cursor-not-allowed disabled:opacity-50';

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
  neutral: 'border-slate-700 bg-slate-800/60 text-slate-300',
  blue: 'border-blue-800/60 bg-blue-950/40 text-blue-300',
  green: 'border-emerald-800/60 bg-emerald-950/40 text-emerald-300',
  amber: 'border-amber-800/60 bg-amber-950/40 text-amber-300',
  orange: 'border-orange-800/60 bg-orange-950/40 text-orange-300',
  red: 'border-red-800/60 bg-red-950/40 text-red-300',
  purple: 'border-purple-800/60 bg-purple-950/40 text-purple-300',
  cyan: 'border-cyan-800/60 bg-cyan-950/40 text-cyan-300',
};

export function Badge({ children, tone = 'neutral', className = '' }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
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
          <p className="mb-1 text-[11px] font-bold uppercase tracking-[0.18em] text-blue-400">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="text-2xl font-bold tracking-tight text-white">{title}</h1>
        {subtitle ? <p className="mt-1 max-w-3xl text-sm text-slate-400">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function Panel({ title, subtitle, actions, children, className = '', bodyClassName = '' }) {
  return (
    <section
      className={cx(
        'overflow-hidden rounded-xl border border-slate-800 bg-[#111827]/80 shadow-lg shadow-black/10',
        className,
      )}
    >
      {title || actions ? (
        <div className="flex flex-col gap-2 border-b border-slate-800 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            {title ? <h2 className="text-sm font-bold text-slate-100">{title}</h2> : null}
            {subtitle ? <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p> : null}
          </div>
          {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
        </div>
      ) : null}
      <div className={cx('p-4', bodyClassName)}>{children}</div>
    </section>
  );
}

export function StatCard({ label, value, hint, icon: Icon, tone = 'blue', loading = false }) {
  const iconTones = {
    blue: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    green: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    amber: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    red: 'bg-red-500/10 text-red-400 border-red-500/20',
    purple: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    neutral: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
  };
  return (
    <div className="rounded-xl border border-slate-800 bg-[#111827]/80 p-4 shadow-lg shadow-black/10">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-bold tabular-nums text-white">
            {loading ? <span className="inline-block h-7 w-14 animate-pulse rounded bg-slate-800" /> : value}
          </p>
          {hint ? <p className="mt-1 text-[11px] text-slate-500">{hint}</p> : null}
        </div>
        {Icon ? (
          <span className={cx('rounded-lg border p-2', iconTones[tone] || iconTones.blue)}>
            <Icon size={18} />
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
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
      <div className={cx('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

/* ------------------------------------------------------------------ states */

export function LoadingState({ label = 'Loading data…', className = '' }) {
  return (
    <div className={cx('flex items-center justify-center gap-3 py-14 text-sm text-slate-400', className)}>
      <Loader2 size={18} className="animate-spin text-blue-400" />
      {label}
    </div>
  );
}

export function EmptyState({ icon: Icon = Info, title, message, action, className = '' }) {
  return (
    <div className={cx('flex flex-col items-center justify-center px-4 py-14 text-center', className)}>
      <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-slate-800 bg-slate-900 text-slate-500">
        <Icon size={22} />
      </span>
      <h3 className="text-sm font-bold text-slate-200">{title}</h3>
      {message ? <p className="mt-1 max-w-md text-xs leading-relaxed text-slate-500">{message}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ message, onRetry, className = '' }) {
  return (
    <div
      className={cx(
        'flex flex-col items-start gap-3 rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-200',
        className,
      )}
      role="alert"
    >
      <div className="flex items-start gap-2">
        <AlertTriangle size={17} className="mt-0.5 shrink-0 text-red-400" />
        <div>
          <p className="font-semibold text-red-200">Request failed</p>
          <p className="mt-0.5 text-xs leading-relaxed text-red-300/80">{message}</p>
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
    info: 'border-blue-900/50 bg-blue-950/20 text-blue-200',
    success: 'border-emerald-900/50 bg-emerald-950/20 text-emerald-200',
    warning: 'border-amber-900/50 bg-amber-950/20 text-amber-200',
    danger: 'border-red-900/50 bg-red-950/20 text-red-200',
  }[tone];
  const Icon = tone === 'success' ? CheckCircle2 : tone === 'info' ? Info : AlertTriangle;
  return (
    <div className={cx('flex items-start gap-2 rounded-lg border p-3 text-xs leading-relaxed', toneClass, className)}>
      <Icon size={15} className="mt-0.5 shrink-0" />
      <div>{children}</div>
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
        className="absolute inset-0 cursor-default bg-black/60 backdrop-blur-[1px]"
      />
      <aside
        className={cx(
          'relative flex h-full w-full flex-col border-l border-slate-800 bg-[#0d1320] shadow-2xl',
          width,
        )}
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === 'string' ? title : 'Details'}
      >
        <header className="flex items-start justify-between gap-4 border-b border-slate-800 px-5 py-4">
          <div>
            <h2 className="text-base font-bold text-white">{title}</h2>
            {subtitle ? <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p> : null}
          </div>
          <button type="button" onClick={onClose} className={btnGhost} aria-label="Close">
            <X size={16} />
          </button>
        </header>
        <div className="custom-scrollbar flex-1 overflow-y-auto p-5">{children}</div>
        {footer ? <footer className="border-t border-slate-800 p-4">{footer}</footer> : null}
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
        className="absolute inset-0 cursor-default bg-black/70"
      />
      <div className="relative w-full max-w-md rounded-xl border border-slate-800 bg-[#111827] p-5 shadow-2xl">
        <h2 className="text-base font-bold text-white">{title}</h2>
        <div className="mt-2 text-sm leading-relaxed text-slate-400">{message}</div>
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
        {error ? <p className="mt-3 text-xs text-red-300">{error}</p> : null}
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
    <div className="flex flex-col gap-2 border-t border-slate-800 px-4 py-3 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
      <span>
        Showing <span className="font-semibold text-slate-300">{start}</span>–
        <span className="font-semibold text-slate-300">{end}</span>
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
      <dt className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</dt>
      <dd className="mt-1 break-words text-sm text-slate-200">{children ?? '—'}</dd>
    </div>
  );
}
