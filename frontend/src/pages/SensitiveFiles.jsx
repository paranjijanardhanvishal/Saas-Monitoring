import React, { useState, useEffect } from 'react';
import { getPrivacyFindings } from '../api';
import { FileLock2 } from 'lucide-react';

const SensitiveFiles = () => {
  const [findings, setFindings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchFindings = async () => {
      try {
        const res = await getPrivacyFindings(0, 100);
        setFindings(res.items || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchFindings();
  }, []);

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Sensitive Files</h1>
        <p className="text-gray-400">Discover and manage files containing PII</p>
      </div>

      <div className="bg-[#121212] border border-[#262626] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="soc-table">
            <thead>
              <tr>
                <th>Event ID / File Ref</th>
                <th>PII Entities</th>
                <th>Sensitivity Score</th>
                <th>Detection Time</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f, i) => (
                <tr key={i}>
                  <td className="text-gray-300 font-mono text-xs">{f.event_id}</td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      {f.entities.map((ent, idx) => (
                        <span key={idx} className="bg-purple-500/10 text-purple-400 border border-purple-500/20 px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider">
                          {ent.entity_type}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="font-mono text-gray-400">{f.sensitivity_score.toFixed(2)}</td>
                  <td className="text-gray-500 text-xs">{new Date(f.timestamp).toLocaleString()}</td>
                </tr>
              ))}
              {findings.length === 0 && !loading && (
                <tr><td colSpan="4" className="p-8 text-center text-gray-500">No sensitive files discovered yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default SensitiveFiles;
