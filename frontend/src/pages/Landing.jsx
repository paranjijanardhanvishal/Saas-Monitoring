import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, Target, Activity, AlertTriangle, Users, FileLock2, Search } from 'lucide-react';

const Landing = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-800 flex flex-col relative overflow-hidden">
      {/* Background Gradient & Grid */}
      <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-[0.03] z-0"></div>
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[800px] bg-blue-400/20 rounded-full blur-[120px] z-0 pointer-events-none"></div>

      {/* Header */}
      <header className="relative z-10 flex justify-between items-center p-6 lg:px-12">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center border border-blue-100">
            <ShieldCheck className="text-blue-600" size={20} />
          </div>
          <span className="font-bold text-lg text-slate-900 tracking-tight">SaaS Security Monitor</span>
        </div>
        <a href="https://github.com" target="_blank" rel="noreferrer" className="text-sm font-medium text-slate-500 hover:text-slate-800 flex items-center gap-1">
          github.com ↗
        </a>
      </header>

      {/* Hero Section */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-4 -mt-16">
        
        <div className="mb-6 flex flex-col items-center">
          <div className="w-16 h-16 bg-blue-50 border border-blue-100 rounded-2xl flex items-center justify-center mb-6 shadow-sm">
            <ShieldCheck className="text-blue-600" size={32} />
          </div>
          <div className="bg-blue-100 text-blue-700 text-[11px] font-bold px-3 py-1 rounded-full uppercase tracking-widest mb-6">
            Live Interactive Demo
          </div>
        </div>

        <h1 className="text-5xl md:text-6xl font-extrabold text-center tracking-tight text-slate-900 mb-4 max-w-4xl leading-tight">
          Enterprise SOC Platform <br className="hidden md:block"/>
          <span className="text-blue-600">powered by AI</span>
        </h1>
        
        <p className="text-slate-500 text-center max-w-2xl text-lg mb-10">
          Full-stack SaaS security operations — API Monitoring, UEBA, Privacy Posture, Incident Response, and Enforcement in one platform.
        </p>

        <button 
          onClick={() => navigate('/dashboard')}
          className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3.5 rounded-lg font-semibold shadow-lg shadow-blue-600/30 transition-all hover:-translate-y-0.5 flex items-center gap-2"
        >
          <Search size={18} />
          Launch Live Demo
        </button>
        <p className="text-slate-400 text-xs mt-4">No sign-up required · Live data sandbox</p>

        {/* Top Stat Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-16 max-w-4xl w-full">
          {[
            { value: '50+', label: 'Detection Engines' },
            { value: '14', label: 'SOAR Playbooks' },
            { value: '128', label: 'Monitored SaaS APIs' },
            { value: 'Real-time', label: 'Log Ingestion' },
          ].map((stat, i) => (
            <div key={i} className="bg-white border border-slate-200 rounded-xl p-5 text-center shadow-sm">
              <h3 className="text-2xl font-bold text-blue-600 mb-1">{stat.value}</h3>
              <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">{stat.label}</p>
            </div>
          ))}
        </div>

        {/* Feature Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4 max-w-4xl w-full">
          {[
            { title: 'AI Threat Detection', desc: 'ML-powered anomaly engine', icon: Target },
            { title: 'SIEM / Alert Triage', desc: 'Real-time alert correlation', icon: AlertTriangle },
            { title: 'SOAR Playbooks', desc: 'Automated response actions', icon: ShieldCheck },
            { title: 'UEBA & Insider Threat', desc: 'Behavioral baselining (EWMA)', icon: Users },
            { title: 'Privacy Posture', desc: 'Contextual PII scanning', icon: FileLock2 },
            { title: 'Live Activity Feed', desc: 'Deep traffic inspection', icon: Activity },
          ].map((feat, i) => (
            <div key={i} className="bg-white border border-slate-200 rounded-xl p-5 flex items-start gap-4 shadow-sm hover:border-blue-200 transition-colors cursor-default">
              <div className="w-10 h-10 bg-blue-50 text-blue-600 rounded-lg flex items-center justify-center shrink-0 border border-blue-100">
                <feat.icon size={20} />
              </div>
              <div>
                <h4 className="font-bold text-slate-800 text-sm mb-0.5">{feat.title}</h4>
                <p className="text-xs text-slate-500">{feat.desc}</p>
              </div>
            </div>
          ))}
        </div>

      </main>
    </div>
  );
};

export default Landing;
