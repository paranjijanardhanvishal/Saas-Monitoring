import React from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  FileSearch,
  Gavel,
  Server,
  ShieldCheck,
  Users,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const CAPABILITIES = [
  {
    icon: Activity,
    title: 'Live activity',
    body: 'Consent-gated endpoint and SaaS proxy events, correlated with user, device and session context.',
  },
  {
    icon: FileSearch,
    title: 'Sensitive data findings',
    body: 'PII detection with Presidio when installed and a labelled regex fallback. Only derived findings are stored.',
  },
  {
    icon: BrainCircuit,
    title: 'Behaviour analytics',
    body: 'EWMA baselines per user with deviation findings kept separate from the user directory.',
  },
  {
    icon: AlertTriangle,
    title: 'Alerts and incidents',
    body: 'Administrator triage, status transitions, notes, evidence history and incident creation from alerts.',
  },
  {
    icon: Users,
    title: 'Risk and investigation',
    body: 'Explainable four-signal risk assessments plus a correlated per-user and per-event investigation view.',
  },
  {
    icon: Gavel,
    title: 'Auditable enforcement',
    body: 'Administrator-confirmed restriction and device revocation with reason capture and rollback.',
  },
];

const SCOPE = [
  'Windows process, foreground-application, session, usage and file-event telemetry from an enrolled device agent.',
  'Optional cloud file metadata and PII findings supplied through the authenticated API.',
  'Administrator-only investigation, enforcement, user management and system-health visibility.',
  'Server-side consent enforcement: withdrawal stops ingestion and revokes the user’s devices.',
];

const LIMITATIONS = [
  'The endpoint agent does not capture file contents, keystrokes, screenshots, browser history or clipboard data.',
  'Global file access and upload visibility is not claimed; the agent reports the events its collectors support.',
  'Offline analysis inspects file names only, never file contents.',
  'Windows failed-login monitoring may be unavailable without elevated access to the Security log; the collector then disables itself and reports the reason.',
  'SaaS proxy ingestion requires a configured ingestion key; events are stored without a verified identity when the proxy cannot attest one.',
];

export default function Landing() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen overflow-hidden bg-[#0b0f19] text-slate-200">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-48 left-1/2 h-[560px] w-[760px] -translate-x-1/2 rounded-full bg-blue-600/10 blur-[130px]" />
        <div className="absolute bottom-0 right-0 h-[360px] w-[360px] rounded-full bg-emerald-500/5 blur-[110px]" />
      </div>

      <header className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-blue-500/30 bg-blue-500/10 text-blue-400">
            <ShieldCheck size={20} />
          </span>
          <span className="text-sm font-bold tracking-tight text-white">SaaS Security Monitor</span>
        </div>
        <Link
          to={user ? '/dashboard' : '/login'}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-slate-600 hover:text-white"
        >
          {user ? 'Open console' : 'Sign in'}
          <ArrowRight size={15} />
        </Link>
      </header>

      <main className="relative z-10 mx-auto max-w-6xl px-6 pb-20">
        <section className="pt-14 pb-16 sm:pt-20">
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/60 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-blue-400">
            Security operations console
          </div>
          <h1 className="mt-6 max-w-3xl text-4xl font-extrabold leading-tight tracking-tight text-white sm:text-5xl">
            SaaS API monitoring for data leakage and access anomalies
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-slate-400">
            A capstone SOC platform that correlates consent-gated Windows endpoint telemetry with SaaS
            access events, sensitive-data findings and behavioural baselines to produce explainable risk
            assessments and auditable response actions.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              to={user ? '/dashboard' : '/login'}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-blue-500"
            >
              {user ? 'Open the SOC console' : 'Sign in to the SOC console'}
              <ArrowRight size={16} />
            </Link>
            <span className="text-xs text-slate-500">
              Accounts are provisioned by an administrator. There is no public sign-up.
            </span>
          </div>
        </section>

        <section aria-labelledby="capabilities-heading">
          <h2 id="capabilities-heading" className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">
            What the console does
          </h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {CAPABILITIES.map((capability) => (
              <div
                key={capability.title}
                className="rounded-xl border border-slate-800 bg-[#0d1320] p-5"
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-blue-500/20 bg-blue-500/10 text-blue-400">
                  <capability.icon size={19} />
                </span>
                <h3 className="mt-4 text-sm font-bold text-white">{capability.title}</h3>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-400">{capability.body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-10 grid gap-4 lg:grid-cols-2" aria-label="Scope and limitations">
          <div className="rounded-xl border border-slate-800 bg-[#0d1320] p-6">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-emerald-400">
              <Server size={15} />
              Monitored scope
            </div>
            <ul className="mt-4 space-y-3 text-xs leading-relaxed text-slate-400">
              {SCOPE.map((item) => (
                <li key={item} className="flex items-start gap-2.5">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-xl border border-amber-900/40 bg-amber-950/10 p-6">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-amber-300">
              <AlertTriangle size={15} />
              Documented limitations
            </div>
            <ul className="mt-4 space-y-3 text-xs leading-relaxed text-amber-100/70">
              {LIMITATIONS.map((item) => (
                <li key={item} className="flex items-start gap-2.5">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <footer className="mt-12 flex flex-col gap-2 border-t border-slate-800 pt-6 text-[11px] text-slate-600 sm:flex-row sm:items-center sm:justify-between">
          <p>Monitoring is consent-gated and administrator access is logged.</p>
          <p>Capstone demonstration build. No production SLA or compliance certification is claimed.</p>
        </footer>
      </main>
    </div>
  );
}
