import React, { useState, useEffect } from 'react';
import { getRiskAssessments } from '../api';
import { Users as UsersIcon, ShieldAlert } from 'lucide-react';

const Users = () => {
  const [risks, setRisks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchRisks = async () => {
      try {
        const res = await getRiskAssessments(0, 100);
        setRisks(res.items || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchRisks();
  }, []);

  // Group risks by user to create a pseudo UEBA view
  const userMap = {};
  risks.forEach(r => {
    if (!userMap[r.user_id]) {
      userMap[r.user_id] = {
        userId: r.user_id,
        highestRiskCategory: r.risk_category,
        maxScore: r.combined_score,
        assessments: 1,
        lastActive: r.timestamp
      };
    } else {
      userMap[r.user_id].assessments += 1;
      if (r.combined_score > userMap[r.user_id].maxScore) {
        userMap[r.user_id].maxScore = r.combined_score;
        userMap[r.user_id].highestRiskCategory = r.risk_category;
      }
      if (new Date(r.timestamp) > new Date(userMap[r.user_id].lastActive)) {
        userMap[r.user_id].lastActive = r.timestamp;
      }
    }
  });

  const users = Object.values(userMap);

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">User Entity Behavior Analytics</h1>
        <p className="text-gray-400">Monitor user behavior baselines and anomalies</p>
      </div>

      <div className="bg-[#121212] border border-[#262626] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="soc-table">
            <thead>
              <tr>
                <th>User ID</th>
                <th>Highest Risk Category</th>
                <th>Max Risk Score</th>
                <th>Total Assessments</th>
                <th>Last Active</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u, i) => (
                <tr key={i}>
                  <td className="text-gray-300 font-medium">{u.userId}</td>
                  <td>
                    <span className={`px-2 py-1 rounded text-xs font-bold ${u.highestRiskCategory === 'CRITICAL' ? 'bg-red-500/10 text-red-400' : u.highestRiskCategory === 'HIGH' ? 'bg-orange-500/10 text-orange-400' : 'bg-gray-800 text-gray-400'}`}>
                      {u.highestRiskCategory}
                    </span>
                  </td>
                  <td className="font-mono text-gray-400">{u.maxScore.toFixed(2)}</td>
                  <td className="text-gray-400">{u.assessments}</td>
                  <td className="text-gray-500 text-xs">{new Date(u.lastActive).toLocaleString()}</td>
                </tr>
              ))}
              {users.length === 0 && !loading && (
                <tr><td colSpan="5" className="p-8 text-center text-gray-500">No user data available.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Users;
