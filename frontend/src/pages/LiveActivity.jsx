import React, { useState, useEffect } from 'react';
import { getEvents } from '../api';
import { Activity, Search, Filter } from 'lucide-react';

const LiveActivity = () => {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const res = await getEvents(0, 100);
        setEvents(res.items || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchEvents();
  }, []);

  return (
    <div className="max-w-7xl mx-auto">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Live Activity</h1>
          <p className="text-gray-400">Enterprise SaaS Event Stream</p>
        </div>
        <div className="flex gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={16} />
            <input 
              type="text" 
              placeholder="Search events..." 
              className="bg-[#121212] border border-[#333] text-sm text-white rounded-lg pl-9 pr-4 py-2 focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>
          <button className="flex items-center gap-2 bg-[#121212] hover:bg-[#1e1e1e] border border-[#333] text-gray-300 px-4 py-2 rounded-lg transition-colors text-sm">
            <Filter size={16} />
            Filters
          </button>
        </div>
      </div>

      <div className="bg-[#121212] border border-[#262626] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="soc-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>SaaS Application</th>
                <th>User</th>
                <th>Action</th>
                <th>Resource</th>
                <th>Device/IP</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e, i) => (
                <tr key={i}>
                  <td className="text-gray-500 font-mono text-xs">{new Date(e.timestamp).toLocaleString()}</td>
                  <td className="text-emerald-400 font-medium">{e.saas_app}</td>
                  <td className="text-gray-300">{e.user_id}</td>
                  <td>
                    <span className="bg-[#1e1e1e] border border-[#333] px-2 py-1 rounded text-xs text-gray-300">
                      {e.action}
                    </span>
                  </td>
                  <td className="text-gray-400 text-sm truncate max-w-[200px]" title={e.resource_id}>{e.resource_id || '-'}</td>
                  <td className="text-gray-500 font-mono text-xs">{e.device_info?.ip_address || '-'}</td>
                </tr>
              ))}
              {events.length === 0 && !loading && (
                <tr><td colSpan="6" className="p-8 text-center text-gray-500">No recent activity detected.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default LiveActivity;
