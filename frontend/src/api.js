import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api',
});

export const getEvents = async (skip = 0, limit = 50) => {
  const response = await api.get(`/events?skip=${skip}&limit=${limit}`);
  return response.data;
};

export const getPrivacyFindings = async (skip = 0, limit = 50) => {
  const response = await api.get(`/privacy/findings?skip=${skip}&limit=${limit}`);
  return response.data;
};

export const getBehaviorAnomalies = async (skip = 0, limit = 50) => {
  const response = await api.get(`/behavior/anomalies?skip=${skip}&limit=${limit}`);
  return response.data;
};

export const getRiskAssessments = async (skip = 0, limit = 50) => {
  const response = await api.get(`/risk/assessments?skip=${skip}&limit=${limit}`);
  return response.data;
};

export const getEnforcementResponses = async (skip = 0, limit = 50) => {
  const response = await api.get(`/enforcement/responses?skip=${skip}&limit=${limit}`);
  return response.data;
};

export const getAlerts = async (skip = 0, limit = 50) => {
  const response = await api.get(`/alerts?skip=${skip}&limit=${limit}`);
  return response.data;
};

export const updateAlertStatus = async (alertId, status) => {
  const response = await api.patch(`/alerts/${alertId}/status?status=${status}`);
  return response.data;
};

export const getIncidents = async (skip = 0, limit = 50) => {
  const response = await api.get(`/incidents?skip=${skip}&limit=${limit}`);
  return response.data;
};

export const updateIncidentStatus = async (incidentId, status) => {
  const response = await api.patch(`/incidents/${incidentId}/status?status=${status}`);
  return response.data;
};

export const getHealth = async () => {
  // Use the health endpoint from root or /health depending on backend structure
  const response = await axios.get((import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace('/api', '') + '/health');
  return response.data;
};

export default api;
