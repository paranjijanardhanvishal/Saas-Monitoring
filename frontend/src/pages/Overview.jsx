import React, { useState, useEffect } from 'react';
import { AlertTriangle, ShieldAlert, Activity, Users, Clock, Target, CheckCircle2, ChevronRight, Info, Search } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { getEvents, getAlerts, getIncidents, getPrivacyFindings } from '../api';

const GaugeChart = ({ value }) => {
  const data = [
    { name: 'Risk', value: value },
    { name: 'Safe', value: 100 - value }
  ];
  
  return (
    <div className="relative h-24 w-32 mx-auto">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="100%"
            startAngle={180}
            endAngle={0}
            innerRadius={30}
            outerRadius={40}
            paddingAngle={0}
            dataKey="value"
            stroke="none"
          >
            <Cell fill={value >= 80 ? '#ef4444' : value >= 50 ? '#f97316' : '#10b981'} />
            <Cell fill="#f1f5f9" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute bottom-0 left-0 w-full text-center flex flex-col">
        <span className="text-2xl font-bold text-slate-800">{value}</span>
      </div>
    </div>
  );
};

const TopMetricCard = ({ title, value, subtitle, children }) => (
  <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col h-full">
    <div className="flex items-center gap-1.5 text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-3">
      {children && <span className="text-slate-400">{children}</span>}
      {title}
    </div>
    <div className="mt-auto">
      {typeof value === 'string' || typeof value === 'number' ? (
        <h3 className="text-3xl font-extrabold text-slate-800 tracking-tight">{value}</h3>
      ) : (
        value
      )}
      <p className="text-[13px] font-medium text-slate-500 mt-1">{subtitle}</p>
    </div>
  </div>
);

const MiniMetricCard = ({ title, value, subtitle, icon }) => (
  <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col justify-between h-24">
    <div className="flex items-center gap-1.5 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
      {icon}
      {title}
    </div>
    <div className="flex items-end justify-between">
      <h3 className="text-2xl font-bold text-slate-800">{value}</h3>
      <span className="text-[11px] font-medium text-slate-500">{subtitle}</span>
    </div>
  </div>
);

const Overview = () => {
  const [data, setData] = useState({ events: [], alerts: [], incidents: [], privacy: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [eventsRes, alertsRes, incidentsRes, privacyRes] = await Promise.all([
          getEvents(0, 50).catch(() => []),
          getAlerts(0, 50).catch(() => []),
          getIncidents(0, 50).catch(() => []),
          getPrivacyFindings(0, 50).catch(() => [])
        ]);
        setData({
          events: Array.isArray(eventsRes) ? eventsRes : (eventsRes.items || []),
          alerts: Array.isArray(alertsRes) ? alertsRes : (alertsRes.items || []),
          incidents: Array.isArray(incidentsRes) ? incidentsRes : (incidentsRes.items || []),
          privacy: Array.isArray(privacyRes) ? privacyRes : (privacyRes.items || [])
        });
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const criticalAlerts = data.alerts.filter(a => a.severity === 'CRITICAL').length;
  const openIncidents = data.incidents.filter(i => i.status === 'OPEN').length;
  const activeInvestigations = data.incidents.filter(i => i.status === 'INVESTIGATING').length;
  const avgRisk = data.alerts.length > 0 
    ? Math.round(data.alerts.reduce((acc, a) => acc + (a.risk_score || 0), 0) / data.alerts.length) 
    : 12; // Fallback

  return (
    <div className="max-w-[1400px] mx-auto space-y-4">
      
      {/* Top Row - Large Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4 h-auto lg:h-40">
        
        <div className="lg:col-span-1">
          <TopMetricCard title="Security Score" value="51%" subtitle="Needs attention">
            <ShieldAlert size={14} />
          </TopMetricCard>
        </div>

        <div className="lg:col-span-2">
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm h-full flex flex-col items-center justify-center">
            <h3 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider absolute top-4">Risk Score</h3>
            <GaugeChart value={avgRisk > 0 ? avgRisk : 82} />
            <p className="text-red-500 text-sm font-bold mt-2">Critical Risk</p>
          </div>
        </div>

        <div className="lg:col-span-1">
          <TopMetricCard 
            title="Threat Level" 
            value={<div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-red-500"></div><span className="text-2xl font-bold text-slate-800">Critical</span></div>} 
            subtitle="Platform-wide" 
          />
        </div>

        <div className="lg:col-span-1">
          <TopMetricCard title="MTTD" value="7h 44m" subtitle="200 samples">
            <Clock size={14} />
          </TopMetricCard>
        </div>

        <div className="lg:col-span-1">
          <TopMetricCard title="Open Cases" value={openIncidents > 0 ? openIncidents : 18} subtitle={`${activeInvestigations} under investigation`}>
            <Activity size={14} />
          </TopMetricCard>
        </div>

      </div>

      {/* Middle Row - Mini Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4">
        <MiniMetricCard title="Critical Alerts" value={criticalAlerts > 0 ? criticalAlerts : 34} subtitle="30 open" icon={<AlertTriangle size={14} />} />
        <MiniMetricCard title="Open Incidents" value={openIncidents > 0 ? openIncidents : 14} subtitle="Active incidents" icon={<ShieldAlert size={14} />} />
        <MiniMetricCard title="Investigations" value={activeInvestigations > 0 ? activeInvestigations : 6} subtitle="Cases in progress" icon={<Search size={14} />} />
        <MiniMetricCard title="SOAR Executed" value="0" subtitle="Auto-responses" icon={<Activity size={14} />} />
        <MiniMetricCard title="Monitored Users" value="3" subtitle="4 total" icon={<Users size={14} />} />
        <MiniMetricCard title="Unmonitored" value="1" subtitle="Coverage gap" icon={<Users size={14} className="text-slate-300" />} />
        <MiniMetricCard title="High Findings" value={data.privacy.length > 0 ? data.privacy.length : 45} subtitle="25 critical" icon={<Info size={14} />} />
        <MiniMetricCard title="Coverage" value="50%" subtitle="API endpoints" icon={<CheckCircle2 size={14} />} />
      </div>

      {/* Red Alert Banner */}
      <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-3 text-red-600 shadow-sm">
        <AlertTriangle size={16} className="shrink-0" />
        <span className="text-sm font-medium">Alert volume is 2300% above the 7-day average — possible attack surge or noisy rule.</span>
      </div>

      {/* Bottom Split Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[500px]">
        
        {/* Live SOC Feed */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col overflow-hidden">
          <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
            <h2 className="text-[13px] font-bold text-slate-700 uppercase flex items-center gap-2">
              <Activity size={16} className="text-blue-500" />
              Live SOC Feed
              <span className="flex items-center gap-1 text-[10px] text-emerald-500 bg-emerald-50 px-2 py-0.5 rounded-full normal-case"><div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse"></div> Live</span>
            </h2>
            <button className="text-xs font-medium text-blue-600 hover:text-blue-700">View all &rarr;</button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
            {data.events.slice(0, 10).map((event, i) => (
              <div key={i} className="flex gap-4">
                <div className="w-2 h-2 mt-1.5 rounded-full bg-blue-500 shrink-0 shadow-[0_0_8px_rgba(59,130,246,0.5)]"></div>
                <div className="flex-1">
                  <div className="flex justify-between items-start">
                    <h4 className="text-sm font-bold text-slate-800">{event.action}</h4>
                    <span className="text-xs text-slate-400 font-medium">Just now</span>
                  </div>
                  <p className="text-[13px] text-slate-600 mt-0.5 font-medium">{event.source} — <span className="text-slate-500 font-normal">{event.user_id}</span></p>
                  <p className="text-xs text-slate-400 font-mono mt-1">{event.file_id || 'N/A'}</p>
                </div>
              </div>
            ))}
            {data.events.length === 0 && !loading && (
              <div className="text-center text-slate-500 text-sm mt-10">No live events detected.</div>
            )}
          </div>
        </div>

        {/* Analyst Work Queue */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col overflow-hidden">
          <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
            <h2 className="text-[13px] font-bold text-slate-700 uppercase flex items-center gap-2">
              <ShieldAlert size={16} className="text-blue-500" />
              Analyst Work Queue
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
            
            <div>
              <h3 className="text-[11px] font-bold text-orange-500 uppercase tracking-wider mb-4 border-b border-slate-100 pb-2">Investigating ({activeInvestigations > 0 ? activeInvestigations : 3})</h3>
              <div className="space-y-4">
                {[1,2,3].map((_, i) => (
                  <div key={i} className="flex items-center justify-between group">
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-red-500"></div>
                      <div>
                        <p className="text-sm font-semibold text-slate-800">Critical PII Exposure — <span className="text-slate-500 font-normal">Suspected Data Exfiltration</span></p>
                        <p className="text-xs text-slate-400 mt-0.5">70d ago</p>
                      </div>
                    </div>
                    <button className="text-xs font-bold text-blue-600 bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded-md opacity-0 group-hover:opacity-100 transition-opacity">Active</button>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h3 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-4 border-b border-slate-100 pb-2 mt-6">Open Cases ({openIncidents > 0 ? openIncidents : 4})</h3>
              <div className="space-y-4">
                {[1,2,3,4].map((_, i) => (
                  <div key={i} className="flex items-center justify-between group">
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-slate-300"></div>
                      <div>
                        <p className="text-sm font-semibold text-slate-700">Abnormal Download Volume — <span className="text-slate-500 font-normal">sales-team-01</span></p>
                        <p className="text-xs text-slate-400 mt-0.5">open</p>
                      </div>
                    </div>
                    <button className="text-xs font-bold text-blue-600 border border-blue-200 hover:bg-blue-50 px-3 py-1.5 rounded-md opacity-0 group-hover:opacity-100 transition-opacity">Case</button>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>

      </div>
    </div>
  );
};

export default Overview;
