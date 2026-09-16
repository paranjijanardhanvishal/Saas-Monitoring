import React, { useState, useEffect } from 'react';
import { getIncidents, updateIncidentStatus } from '../api';
import { ShieldAlert } from 'lucide-react';

const Incidents = () => {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchIncidents = async () => {
    try {
      const res = await getIncidents(0, 50);
      setIncidents(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, []);

  const handleStatusChange = async (id, status) => {
    try {
      await updateIncidentStatus(id, status);
      fetchIncidents();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Incident Management</h1>
        <p className="text-gray-400">Track and respond to security incidents</p>
      </div>

      <div className="bg-[#121212] border border-[#262626] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="soc-table">
            <thead>
              <tr>
                <th>Incident ID</th>
                <th>Severity</th>
                <th>Title / Reason</th>
                <th>User / SaaS</th>
                <th>Resource</th>
                <th>Risk Score</th>
                <th>Status</th>
                <th>Created</th>
                <th>Analyst</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((inc, i) => (
                <tr key={i}>
                  <td className="text-gray-500 font-mono text-xs">{inc.id}</td>
                  <td>
                    <span className={`px-2 py-1 rounded text-xs font-bold ${inc.severity === 'CRITICAL' ? 'bg-red-500/10 text-red-400' : 'bg-orange-500/10 text-orange-400'}`}>
                      {inc.severity}
                    </span>
                  </td>
                  <td>
                    <p className="text-gray-200 text-sm font-medium">{inc.title}</p>
                    <p className="text-gray-500 text-xs truncate max-w-[200px]">{inc.reason}</p>
                  </td>
                  <td>
                    <p className="text-gray-300 text-sm">{inc.user_id}</p>
                    <p className="text-emerald-400 text-xs">{inc.saas_app}</p>
                  </td>
                  <td>
                    <p className="text-gray-300 text-xs truncate max-w-[150px]" title={inc.resource}>{inc.resource || 'N/A'}</p>
                  </td>
                  <td className="font-mono text-gray-400">{inc.risk_score?.toFixed(2) || 'N/A'}</td>
                  <td>
                    <span className="bg-[#1e1e1e] border border-[#333] px-2 py-1 rounded text-xs text-gray-300 font-medium">
                      {inc.status}
                    </span>
                  </td>
                  <td className="text-gray-500 text-xs">{new Date(inc.created_time).toLocaleString()}</td>
                  <td className="text-gray-400 text-xs">{inc.analyst || 'Unassigned'}</td>
                  <td>
                    <select 
                      className="bg-[#1e1e1e] text-xs text-gray-300 border border-[#333] rounded px-2 py-1 focus:outline-none focus:border-emerald-500"
                      value={inc.status}
                      onChange={(e) => handleStatusChange(inc.id, e.target.value)}
                    >
                      <option value="OPEN">Open</option>
                      <option value="INVESTIGATING">Investigate</option>
                      <option value="CONTAINED">Contain</option>
                      <option value="RESOLVED">Resolve</option>
                      <option value="DISMISSED">Dismiss</option>
                    </select>
                  </td>
                </tr>
              ))}
              {incidents.length === 0 && !loading && (
                <tr><td colSpan="10" className="p-8 text-center text-gray-500">No active incidents.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Incidents;
