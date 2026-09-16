import React, { useState, useEffect } from 'react';
import { getHealth } from '../api';
import { ActivitySquare, CheckCircle, XCircle } from 'lucide-react';

const SystemHealth = () => {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await getHealth();
        setHealth(res);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchHealth();
  }, []);

  const StatusIcon = ({ status }) => {
    return status === 'healthy' || status === 'connected' ? 
      <CheckCircle size={18} className="text-emerald-500" /> : 
      <XCircle size={18} className="text-red-500" />;
  };

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">System Health</h1>
        <p className="text-gray-400">Component status and integrations</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Core Services */}
        <div className="bg-[#121212] border border-[#262626] rounded-xl p-6">
          <h2 className="text-lg font-bold text-white mb-6 border-b border-[#262626] pb-4">Core Services</h2>
          <div className="space-y-4">
            <div className="flex justify-between items-center p-3 bg-[#1e1e1e] rounded-lg border border-[#333]">
              <span className="text-gray-300 font-medium">FastAPI Backend</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400 uppercase font-bold">{health ? health.status : 'UNAVAILABLE'}</span>
                {health ? <StatusIcon status={health.status} /> : <XCircle size={18} className="text-red-500" />}
              </div>
            </div>
            
            <div className="flex justify-between items-center p-3 bg-[#1e1e1e] rounded-lg border border-[#333]">
              <span className="text-gray-300 font-medium">MongoDB Database</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400 uppercase font-bold">{health?.database?.status || 'UNAVAILABLE'}</span>
                {health?.database ? <StatusIcon status={health.database.status} /> : <XCircle size={18} className="text-red-500" />}
              </div>
            </div>
          </div>
        </div>

        {/* Security Engines */}
        <div className="bg-[#121212] border border-[#262626] rounded-xl p-6">
          <h2 className="text-lg font-bold text-white mb-6 border-b border-[#262626] pb-4">Security Engines</h2>
          <div className="space-y-4">
            <div className="flex justify-between items-center p-3 bg-[#1e1e1e] rounded-lg border border-[#333]">
              <span className="text-gray-300 font-medium">Microsoft Presidio (PII)</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-emerald-400 uppercase font-bold">IMPLEMENTED</span>
                <CheckCircle size={18} className="text-emerald-500" />
              </div>
            </div>
            
            <div className="flex justify-between items-center p-3 bg-[#1e1e1e] rounded-lg border border-[#333]">
              <span className="text-gray-300 font-medium">EWMA Behavioral Analytics</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-emerald-400 uppercase font-bold">IMPLEMENTED</span>
                <CheckCircle size={18} className="text-emerald-500" />
              </div>
            </div>

            <div className="flex justify-between items-center p-3 bg-[#1e1e1e] rounded-lg border border-[#333]">
              <span className="text-gray-300 font-medium">Local TF / Cosine Semantic</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-emerald-400 uppercase font-bold">IMPLEMENTED</span>
                <CheckCircle size={18} className="text-emerald-500" />
              </div>
            </div>
          </div>
        </div>
        
        {/* Integrations */}
        <div className="bg-[#121212] border border-[#262626] rounded-xl p-6 md:col-span-2">
          <h2 className="text-lg font-bold text-white mb-6 border-b border-[#262626] pb-4">Integrations</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex justify-between items-center p-3 bg-[#1e1e1e] rounded-lg border border-[#333]">
              <span className="text-gray-300 font-medium">Slack Alerting</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 uppercase font-bold">MOCK / NOT CONFIGURED</span>
              </div>
            </div>
            
            <div className="flex justify-between items-center p-3 bg-[#1e1e1e] rounded-lg border border-[#333]">
              <span className="text-gray-300 font-medium">Jira Ticketing</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 uppercase font-bold">MOCK / NOT CONFIGURED</span>
              </div>
            </div>
          </div>
        </div>

        {/* Future Enhancements */}
        <div className="bg-[#121212] border border-[#262626] rounded-xl p-6 md:col-span-2 opacity-70">
          <h2 className="text-lg font-bold text-gray-400 mb-6 border-b border-[#262626] pb-4">Future Enhancements (Not Implemented)</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-3 bg-[#1e1e1e] rounded-lg border border-[#333] text-center">
              <span className="text-gray-500 font-medium text-sm">OCR Multimodal PII</span>
            </div>
            <div className="p-3 bg-[#1e1e1e] rounded-lg border border-[#333] text-center">
              <span className="text-gray-500 font-medium text-sm">Deep-Learning UEBA</span>
            </div>
            <div className="p-3 bg-[#1e1e1e] rounded-lg border border-[#333] text-center">
              <span className="text-gray-500 font-medium text-sm">Pinecone Cloud Vector</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

export default SystemHealth;
