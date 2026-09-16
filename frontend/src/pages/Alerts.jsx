import React, { useState, useEffect } from 'react';
import { getAlerts, updateAlertStatus } from '../api';
import { AlertTriangle, ShieldAlert, CheckCircle, Clock } from 'lucide-react';

const Alerts = () => {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAlerts = async () => {
    try {
      const res = await getAlerts(0, 50);
      setAlerts(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, []);

  const handleStatusChange = async (id, status) => {
    try {
      await updateAlertStatus(id, status);
      fetchAlerts();
    } catch (err) {
      console.error(err);
    }
  };

  const getStatusIcon = (status) => {
    switch(status) {
      case 'OPEN': return <AlertTriangle size={14} className="text-red-400" />;
      case 'INVESTIGATING': return <Clock size={14} className="text-yellow-400" />;
      case 'RESOLVED': return <CheckCircle size={14} className="text-emerald-400" />;
      default: return <ShieldAlert size={14} className="text-gray-400" />;
    }
  };

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Alert Center</h1>
        <p className="text-gray-400">Manage and investigate security alerts</p>
      </div>

      <div className="bg-[#121212] border border-[#262626] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="soc-table">
            <thead>
              <tr>
                <th>Alert ID</th>
                <th>Severity</th>
                <th>Title / Reason</th>
                <th>User / SaaS</th>
                <th>Resource</th>
                <th>Signals</th>
                <th>Status</th>
                <th>Time</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((a, i) => (
                <tr key={i}>
                  <td className="text-gray-500 font-mono text-xs">{a.id}</td>
                  <td>
                    <span className={`px-2 py-1 rounded text-xs font-bold ${a.severity === 'CRITICAL' ? 'bg-red-500/10 text-red-400' : 'bg-orange-500/10 text-orange-400'}`}>
                      {a.severity}
                    </span>
                  </td>
                  <td>
                    <p className="text-gray-200 text-sm font-medium">{a.title}</p>
                    <p className="text-gray-500 text-xs truncate max-w-[200px]">{a.reason}</p>
                  </td>
                  <td>
                    <p className="text-gray-300 text-sm">{a.user_id}</p>
                    <p className="text-emerald-400 text-xs">{a.saas_app}</p>
                  </td>
                  <td>
                    <p className="text-gray-300 text-xs truncate max-w-[150px]" title={a.resource_id || 'N/A'}>{a.resource_id || 'N/A'}</p>
                  </td>
                  <td>
                    <div className="flex flex-col gap-1 text-xs text-gray-400 font-mono">
                      <span>Risk: {a.risk_score?.toFixed(2) || 'N/A'}</span>
                      <span>Priv: {a.privacy_signal?.toFixed(2) || 'N/A'}</span>
                      <span>Behav: {a.behavior_signal?.toFixed(2) || 'N/A'}</span>
                    </div>
                  </td>
                  <td>
                    <div className="flex items-center gap-2 bg-[#1e1e1e] border border-[#333] px-2 py-1 rounded w-max">
                      {getStatusIcon(a.status)}
                      <span className="text-xs text-gray-300 font-medium">{a.status}</span>
                    </div>
                  </td>
                  <td className="text-gray-500 text-xs">{new Date(a.timestamp).toLocaleString()}</td>
                  <td>
                    <select 
                      className="bg-[#1e1e1e] text-xs text-gray-300 border border-[#333] rounded px-2 py-1 focus:outline-none focus:border-emerald-500"
                      value={a.status}
                      onChange={(e) => handleStatusChange(a.id, e.target.value)}
                    >
                      <option value="OPEN">Open</option>
                      <option value="INVESTIGATING">Investigate</option>
                      <option value="RESOLVED">Resolve</option>
                      <option value="DISMISSED">Dismiss</option>
                    </select>
                  </td>
                </tr>
              ))}
              {alerts.length === 0 && !loading && (
                <tr><td colSpan="9" className="p-8 text-center text-gray-500">No alerts found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Alerts;
