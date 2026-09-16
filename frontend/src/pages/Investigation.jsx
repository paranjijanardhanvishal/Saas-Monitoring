import React, { useState } from 'react';
import { Search, AlertTriangle, ShieldAlert, Activity, User, FileText, CheckCircle, Clock } from 'lucide-react';
import {
  getEvents,
  getAlerts,
  getIncidents,
  getPrivacyFindings,
  getBehaviorAnomalies,
  getEnforcementResponses
} from '../api';

const Investigation = () => {
  const [query, setQuery] = useState('');
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    
    setLoading(true);
    setError('');
    setHasSearched(true);
    setTimeline([]);

    try {
      // Fetch data from multiple sources
      const limit = 500;
      const [events, alerts, incidents, privacy, behavior, enforcements] = await Promise.all([
        getEvents(0, limit).catch(() => []),
        getAlerts(0, limit).catch(() => []),
        getIncidents(0, limit).catch(() => []),
        getPrivacyFindings(0, limit).catch(() => []),
        getBehaviorAnomalies(0, limit).catch(() => []),
        getEnforcementResponses(0, limit).catch(() => [])
      ]);

      const q = query.toLowerCase();
      const match = (item) => JSON.stringify(item).toLowerCase().includes(q);

      const combined = [];

      // Process Events
      events.filter(match).forEach(item => {
        combined.push({
          id: item.event_id,
          timestamp: new Date(item.timestamp),
          type: 'Event',
          title: `${item.action} on ${item.source}`,
          user: item.user_id,
          resource: item.file_id,
          severity: 'LOW',
          icon: <Activity className="w-5 h-5 text-blue-400" />,
          data: item
        });
      });

      // Process Alerts
      alerts.filter(match).forEach(item => {
        combined.push({
          id: item.id || item._id,
          timestamp: new Date(item.timestamp),
          type: 'Alert',
          title: item.title,
          user: item.user_id,
          resource: item.resource_id,
          severity: item.severity,
          icon: <AlertTriangle className="w-5 h-5 text-amber-400" />,
          data: item
        });
      });

      // Process Incidents
      incidents.filter(match).forEach(item => {
        combined.push({
          id: item.id || item._id,
          timestamp: new Date(item.created_time),
          type: 'Incident',
          title: item.title,
          user: item.user,
          resource: item.resource,
          severity: item.severity,
          icon: <ShieldAlert className="w-5 h-5 text-rose-500" />,
          data: item
        });
      });

      // Process Privacy Findings
      privacy.filter(match).forEach(item => {
        combined.push({
          id: item.id || item._id,
          timestamp: new Date(item.timestamp || Date.now()), // fallback
          type: 'Privacy Finding',
          title: `PII Detected: ${item.sensitivity_category || 'Unknown'}`,
          user: item.user_id,
          resource: item.file_id,
          severity: item.score >= 60 ? 'HIGH' : item.score >= 20 ? 'MEDIUM' : 'LOW',
          icon: <FileText className="w-5 h-5 text-purple-400" />,
          data: item
        });
      });

      // Process Behavior Anomalies
      behavior.filter(match).forEach(item => {
        combined.push({
          id: item.id || item._id,
          timestamp: new Date(item.timestamp || Date.now()),
          type: 'Behavior Anomaly',
          title: `Anomaly Detected for User`,
          user: item.user_id,
          resource: 'N/A',
          severity: item.risk_level || 'MEDIUM',
          icon: <User className="w-5 h-5 text-orange-400" />,
          data: item
        });
      });

      // Process Enforcement Responses
      enforcements.filter(match).forEach(item => {
        combined.push({
          id: item.id || item._id,
          timestamp: new Date(item.timestamp || Date.now()),
          type: 'Enforcement Action',
          title: item.action_taken || 'Action Taken',
          user: item.user_id,
          resource: 'N/A',
          severity: 'CRITICAL',
          icon: <CheckCircle className="w-5 h-5 text-emerald-400" />,
          data: item
        });
      });

      // Sort chronological descending
      combined.sort((a, b) => b.timestamp - a.timestamp);
      
      setTimeline(combined);
    } catch (err) {
      console.error(err);
      setError('An error occurred during investigation search.');
    } finally {
      setLoading(false);
    }
  };

  const getSeverityBadge = (severity) => {
    switch (severity?.toUpperCase()) {
      case 'CRITICAL': return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
      case 'HIGH': return 'bg-orange-500/10 text-orange-400 border-orange-500/20';
      case 'MEDIUM': return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      default: return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Investigation Center</h1>
          <p className="text-gray-400">Search across users, files, alerts, and incidents to trace the security timeline.</p>
        </div>
      </div>

      <div className="bg-[#121212] border border-[#262626] rounded-xl p-6">
        <form onSubmit={handleSearch} className="flex gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input 
              type="text" 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter User ID, File ID, or Alert ID..." 
              className="w-full bg-[#1e1e1e] border border-[#333] text-white rounded-lg pl-12 pr-4 py-3 focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>
          <button 
            type="submit" 
            disabled={loading || !query.trim()}
            className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium px-8 py-3 rounded-lg transition-colors"
          >
            {loading ? 'Searching...' : 'Investigate'}
          </button>
        </form>
      </div>

      {error && (
        <div className="bg-rose-500/10 border border-rose-500/20 text-rose-400 p-4 rounded-lg">
          {error}
        </div>
      )}

      {hasSearched && !loading && timeline.length === 0 && (
        <div className="bg-[#121212] border border-[#262626] rounded-xl p-12 text-center">
          <Clock className="w-12 h-12 text-gray-500 mx-auto mb-4" />
          <h3 className="text-xl font-medium text-white mb-2">No related events found</h3>
          <p className="text-gray-400">Try searching for a different user, file, or incident ID.</p>
        </div>
      )}

      {timeline.length > 0 && (
        <div className="bg-[#121212] border border-[#262626] rounded-xl p-6">
          <h2 className="text-xl font-semibold text-white mb-6">Investigation Timeline: {query}</h2>
          
          <div className="relative border-l border-[#333] ml-4 space-y-8">
            {timeline.map((item, index) => (
              <div key={`${item.id}-${index}`} className="relative pl-8">
                <div className="absolute -left-4 top-1 bg-[#121212] border border-[#333] rounded-full p-1.5">
                  {item.icon}
                </div>
                
                <div className="bg-[#1e1e1e] border border-[#333] rounded-lg p-5 hover:border-[#444] transition-colors">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <div className="flex items-center gap-3 mb-1">
                        <span className="text-emerald-400 font-medium text-sm">{item.type}</span>
                        <span className="text-gray-500 text-sm">•</span>
                        <span className="text-gray-400 text-sm">{item.timestamp.toLocaleString()}</span>
                      </div>
                      <h3 className="text-lg font-medium text-white">{item.title}</h3>
                    </div>
                    <span className={`px-2.5 py-1 text-xs font-semibold rounded-md border ${getSeverityBadge(item.severity)}`}>
                      {item.severity}
                    </span>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4 mt-4 p-4 bg-[#121212] rounded-md border border-[#262626]">
                    <div>
                      <span className="text-gray-500 text-xs uppercase tracking-wider block mb-1">User</span>
                      <span className="text-gray-200 text-sm">{item.user || 'System'}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 text-xs uppercase tracking-wider block mb-1">Resource</span>
                      <span className="text-gray-200 text-sm truncate block" title={item.resource}>{item.resource || 'N/A'}</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default Investigation;
