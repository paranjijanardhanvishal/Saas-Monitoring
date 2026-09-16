import React, { useState, useEffect } from 'react';
import { getEnforcementResponses } from '../api';
import { ShieldCheck } from 'lucide-react';

const Enforcement = () => {
  const [enforcements, setEnforcements] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEnforcements = async () => {
      try {
        const res = await getEnforcementResponses(0, 100);
        setEnforcements(res.items || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchEnforcements();
  }, []);

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Enforcement & Response</h1>
        <p className="text-gray-400">Automated and manual security interventions</p>
      </div>

      <div className="bg-[#121212] border border-[#262626] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="soc-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>User</th>
                <th>Risk ID</th>
                <th>Action Taken</th>
                <th>Reason</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {enforcements.map((e, i) => (
                <tr key={i}>
                  <td className="text-gray-500 text-xs">{new Date(e.timestamp).toLocaleString()}</td>
                  <td className="text-gray-300 font-medium">{e.user_id}</td>
                  <td className="text-gray-500 font-mono text-xs">{e.risk_assessment_id}</td>
                  <td>
                    <span className="bg-[#1e1e1e] border border-[#333] px-2 py-1 rounded text-xs text-gray-300 font-bold uppercase tracking-wider">
                      {e.action_taken}
                    </span>
                  </td>
                  <td className="text-gray-400 text-sm truncate max-w-[200px]" title={e.reason}>{e.reason}</td>
                  <td>
                    <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider ${e.status === 'SIMULATED' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                      {e.status === 'SIMULATED' ? 'SIMULATED BLOCK' : e.status}
                    </span>
                  </td>
                </tr>
              ))}
              {enforcements.length === 0 && !loading && (
                <tr><td colSpan="6" className="p-8 text-center text-gray-500">No enforcement actions taken yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Enforcement;
