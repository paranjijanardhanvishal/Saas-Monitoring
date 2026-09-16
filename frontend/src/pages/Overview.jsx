import React, { useState, useEffect } from 'react';
import { ShieldAlert, Activity, Lock, AlertTriangle, RefreshCw } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, LineChart, Line } from 'recharts';
import { getEvents, getPrivacyFindings, getBehaviorAnomalies, getRiskAssessments, getEnforcementResponses } from '../api';

const StatCard = ({ title, value, icon, trend }) => (
  <div className="bg-[#121212] p-6 rounded-xl border border-[#262626] relative overflow-hidden group">
    <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-[#262626]/50 to-transparent rounded-full -mr-16 -mt-16 transition-transform group-hover:scale-110" />
    <div className="flex justify-between items-start mb-4 relative z-10">
      <div className="p-3 bg-[#1e1e1e] rounded-lg border border-[#333]">
        {icon}
      </div>
      {trend && (
        <span className={`text-xs font-bold px-2 py-1 rounded-md ${trend > 0 ? 'bg-red-500/10 text-red-400' : 'bg-emerald-500/10 text-emerald-400'}`}>
          {trend > 0 ? '+' : ''}{trend}%
        </span>
      )}
    </div>
    <div className="relative z-10">
      <p className="text-sm font-medium text-gray-400 mb-1">{title}</p>
      <h3 className="text-3xl font-bold text-white tracking-tight">{value}</h3>
    </div>
  </div>
);

const RiskBadge = ({ category }) => {
  const styles = {
    CRITICAL: 'bg-red-500/10 text-red-400 border-red-500/20 shadow-[0_0_10px_rgba(239,68,68,0.2)]',
    HIGH: 'bg-orange-500/10 text-orange-400 border-orange-500/20 shadow-[0_0_10px_rgba(249,115,22,0.2)]',
    MEDIUM: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20 shadow-[0_0_10px_rgba(234,179,8,0.2)]',
    LOW: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.2)]',
  };
  
  return (
    <span className={`px-2.5 py-1 rounded border text-[10px] font-bold uppercase tracking-wider ${styles[category] || 'bg-gray-800 text-gray-300 border-gray-700'}`}>
      {category}
    </span>
  );
};

const Overview = () => {
  const [data, setData] = useState({ events: [], privacy: [], behavior: [], risk: [], enforcement: [] });
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [eventsRes, privacyRes, behaviorRes, riskRes, enforcementRes] = await Promise.all([
        getEvents(0, 100), getPrivacyFindings(0, 50), getBehaviorAnomalies(0, 50), getRiskAssessments(0, 100), getEnforcementResponses(0, 20)
      ]);
      setData({
        events: eventsRes.items || [], privacy: privacyRes.items || [], behavior: behaviorRes.items || [], risk: riskRes.items || [], enforcement: enforcementRes.items || []
      });
    } catch (err) {
      console.error("Failed to load dashboard data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading && data.events.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center">
          <RefreshCw className="animate-spin text-emerald-500 mb-4" size={32} />
          <p className="text-gray-400">Loading SOC Overview...</p>
        </div>
      </div>
    );
  }

  const criticalRisks = data.risk.filter(r => r.risk_category === 'CRITICAL').length;
  const highRisks = data.risk.filter(r => r.risk_category === 'HIGH').length;

  const riskCounts = data.risk.reduce((acc, curr) => {
    acc[curr.risk_category] = (acc[curr.risk_category] || 0) + 1;
    return acc;
  }, { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 });

  const chartData = [
    { name: 'LOW', count: riskCounts.LOW, color: '#10b981' },
    { name: 'MEDIUM', count: riskCounts.MEDIUM, color: '#eab308' },
    { name: 'HIGH', count: riskCounts.HIGH, color: '#f97316' },
    { name: 'CRITICAL', count: riskCounts.CRITICAL, color: '#ef4444' },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">SOC Overview</h1>
          <p className="text-gray-400">Enterprise SaaS Security Posture</p>
        </div>
        <button onClick={fetchData} className="flex items-center gap-2 bg-[#1e1e1e] hover:bg-[#2a2a2a] text-gray-300 px-4 py-2 rounded-lg border border-[#333] transition-colors">
          <RefreshCw size={16} className={loading ? "animate-spin text-emerald-500" : "text-emerald-500"} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard title="Total Monitored Events" value={data.events.length} icon={<Activity className="text-blue-400" size={24} />} trend={+12} />
        <StatCard title="Privacy Findings" value={data.privacy.length} icon={<Lock className="text-purple-400" size={24} />} trend={-5} />
        <StatCard title="Behavior Anomalies" value={data.behavior.filter(b => b.is_anomaly).length} icon={<AlertTriangle className="text-orange-400" size={24} />} trend={+2} />
        <StatCard title="High/Critical Risks" value={highRisks + criticalRisks} icon={<ShieldAlert className="text-red-400" size={24} />} trend={0} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
        {/* Risk Chart */}
        <div className="lg:col-span-1 bg-[#121212] p-6 rounded-xl border border-[#262626]">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-6">Risk Distribution</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#262626" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#9ca3af', fontSize: 12}} />
                <YAxis axisLine={false} tickLine={false} tick={{fill: '#9ca3af', fontSize: 12}} />
                <Tooltip 
                  cursor={{fill: '#1a1a1a'}} 
                  contentStyle={{backgroundColor: '#121212', border: '1px solid #333', borderRadius: '8px', color: '#fff'}}
                  itemStyle={{color: '#fff'}}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent Risks Table */}
        <div className="lg:col-span-2 bg-[#121212] rounded-xl border border-[#262626] overflow-hidden flex flex-col">
          <div className="p-6 border-b border-[#262626]">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Latest Risk Assessments</h2>
          </div>
          <div className="overflow-x-auto flex-1">
            <table className="soc-table">
              <thead>
                <tr>
                  <th>User ID</th>
                  <th>Category</th>
                  <th>Score</th>
                  <th>Risk Factors</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {data.risk.slice(0, 6).map((r, i) => (
                  <tr key={i}>
                    <td className="text-gray-300 font-medium truncate max-w-[120px]">{r.user_id}</td>
                    <td><RiskBadge category={r.risk_category} /></td>
                    <td className="font-mono text-gray-400">{r.combined_score.toFixed(2)}</td>
                    <td className="text-gray-500 text-xs truncate max-w-[250px]">{r.risk_factors.join(', ') || 'None'}</td>
                    <td className="text-gray-500 text-xs">{new Date(r.timestamp).toLocaleTimeString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Overview;
