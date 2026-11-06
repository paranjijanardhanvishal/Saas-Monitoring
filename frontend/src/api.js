import axios from 'axios';

/**
 * API client for the SaaS Security Monitor.
 *
 * Authentication uses an HttpOnly `access_token` cookie. The SPA only reads the
 * non-HttpOnly `csrf_token` cookie and echoes it in `X-CSRF-Token` for unsafe
 * methods. No bearer token is ever persisted in localStorage.
 */

export const API_BASE_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/+$/, '');
export const AUTH_EXPIRED_EVENT = 'auth:unauthorized';

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function readCookie(name) {
  if (typeof document === 'undefined') return null;
  const match = document.cookie
    .split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`));
  if (!match) return null;
  return decodeURIComponent(match.slice(name.length + 1));
}

let memoryToken = null;

export function setAuthToken(token) {
  memoryToken = token;
}

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  timeout: 30000,
  headers: { Accept: 'application/json' },
});

api.interceptors.request.use((config) => {
  if (memoryToken && !config.headers?.['Authorization']) {
    config.headers = config.headers || {};
    config.headers['Authorization'] = `Bearer ${memoryToken}`;
  }
  const method = (config.method || 'get').toUpperCase();
  if (UNSAFE_METHODS.has(method)) {
    const csrf = readCookie('csrf_token');
    if (csrf) {
      config.headers = config.headers || {};
      config.headers['X-CSRF-Token'] = csrf;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const url = error?.config?.url || '';
    const isSessionProbe = url.includes('/auth/login') || url.includes('/auth/me');
    if (status === 401 && !isSessionProbe && typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
    }
    return Promise.reject(error);
  },
);

export function errorMessage(error, fallback = 'Request failed. Please try again.') {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || item?.message || JSON.stringify(item))
      .filter(Boolean)
      .join('; ');
  }
  if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
    return detail.message;
  }
  if (error?.code === 'ERR_NETWORK') {
    return 'Cannot reach the backend API. Check that the server is running and the API URL is correct.';
  }
  if (error?.code === 'ECONNABORTED') {
    return 'The backend did not respond in time.';
  }
  return error?.message || fallback;
}

function cleanParams(params = {}) {
  const output = {};
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    output[key] = value;
  });
  return output;
}

const get = async (url, params, config = {}) => {
  const response = await api.get(url, { params: cleanParams(params), ...config });
  return response.data;
};

const post = async (url, body, config = {}) => {
  const response = await api.post(url, body, config);
  return response.data;
};

const patch = async (url, body, config = {}) => {
  const response = await api.patch(url, body, config);
  return response.data;
};

/* ------------------------------------------------------------------ auth */

export async function login(identifier, password) {
  const body = new URLSearchParams();
  body.append('username', identifier);
  body.append('password', password);
  const data = await post('/auth/login', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  if (data?.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

export async function logout() {
  setAuthToken(null);
  return post('/auth/logout', {});
}

export async function getMe() {
  const response = await api.get('/auth/me');
  return response.data;
}

export async function updateConsent(monitoringEnabled) {
  return post('/auth/consent', { monitoring_enabled: monitoringEnabled });
}

export async function changePassword(currentPassword, newPassword) {
  return post('/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export async function forgotPassword(email) {
  return post('/auth/forgot-password', { email });
}

export async function resetPassword(token, newPassword) {
  return post('/auth/reset-password', {
    token,
    new_password: newPassword,
  });
}

/* ------------------------------------------------------------- dashboard */

export const getDashboardOverview = () => get('/dashboard/overview');

/* ---------------------------------------------------------------- events */

export const getEvents = (params) => get('/events', params);
export const getEvent = (eventId) => get(`/events/${encodeURIComponent(eventId)}`);

/* ----------------------------------------------------------------- users */

export const getUsers = (params) => get('/users', params);
export const getUser = (userId) => get(`/users/${encodeURIComponent(userId)}`);
export const getUserSummary = (userId) =>
  get(`/users/${encodeURIComponent(userId)}/summary`);
export const getUserDevices = (userId) =>
  get(`/users/${encodeURIComponent(userId)}/devices`);
export const createUser = (payload) => post('/users', payload);
export const updateUser = (userId, payload) =>
  patch(`/users/${encodeURIComponent(userId)}`, payload);
export const deleteUser = (userId) =>
  api.delete(`/users/${encodeURIComponent(userId)}`).then((r) => r.data);
export const updateUserBusinessRole = (userId, businessRole) =>
  patch(`/users/${encodeURIComponent(userId)}/business-role`, {
    business_role: businessRole,
  });

/* ----------------------------------------------------------------- agent */

export const getAgentDevices = (params) => get('/agent/devices', params);

export async function createEnrollmentToken(userId) {
  const response = await api.post('/agent/enrollment-token', null, {
    params: cleanParams({ user_id: userId }),
  });
  return response.data;
}

export async function revokeAgentDevice(deviceId, reason) {
  const response = await api.post(
    `/agent/devices/${encodeURIComponent(deviceId)}/revoke`,
    null,
    { params: { reason } },
  );
  return response.data;
}

/* ---------------------------------------------------------------- alerts */

export const getAlerts = (params) => get('/alerts', params);
export const getAlert = (alertId) => get(`/alerts/${encodeURIComponent(alertId)}`);
export const updateAlertStatus = (alertId, status, note) =>
  patch(`/alerts/${encodeURIComponent(alertId)}/status`, cleanParams({ status, note }));
export const addAlertNote = (alertId, note) =>
  post(`/alerts/${encodeURIComponent(alertId)}/notes`, { note });

/* ------------------------------------------------------------- incidents */

export const getIncidents = (params) => get('/incidents', params);
export const getIncident = (incidentId) =>
  get(`/incidents/${encodeURIComponent(incidentId)}`);
export const createIncident = (payload) => post('/incidents', payload);
export const updateIncidentStatus = (incidentId, status, note) =>
  patch(`/incidents/${encodeURIComponent(incidentId)}/status`, cleanParams({ status, note }));
export const assignIncident = (incidentId, assignedTo) =>
  patch(`/incidents/${encodeURIComponent(incidentId)}/assign`, {
    assigned_to: assignedTo,
  });
export const addIncidentNote = (incidentId, note) =>
  post(`/incidents/${encodeURIComponent(incidentId)}/notes`, { note });

/* --------------------------------------------------------------- privacy */

export const getPrivacyFindings = (params) => get('/privacy/findings', params);
export const getPrivacyFinding = (findingId) =>
  get(`/privacy/findings/${encodeURIComponent(findingId)}`);

export async function analyzeText(text, { fileId, eventId, targetUserId } = {}) {
  const response = await api.post(
    '/privacy/analyze',
    cleanParams({ text, file_id: fileId, event_id: eventId }),
    { params: cleanParams({ target_user_id: targetUserId }) },
  );
  return response.data;
}

export async function scanOcrDocument(file) {
  const body = new FormData();
  body.append('upload', file);
  const response = await api.post('/privacy/scan-ocr', body, { timeout: 360000 });
  return response.data;
}

export const getOcrStatus = () => get('/privacy/ocr-status');

/* ----------------------------------------------------------------- files */

export const getFiles = (params) => get('/files', params);
export const getFile = (fileId) => get(`/files/${encodeURIComponent(fileId)}`);
export const getFilePiiFindings = (fileId) =>
  get(`/files/${encodeURIComponent(fileId)}/pii-findings`);

/* -------------------------------------------------------------- behavior */

export const getBehaviorProfiles = (params) => get('/behavior/profiles', params);
export const getBehaviorAnomalies = (params) => get('/behavior/anomalies', params);
export const getUserBehaviorProfile = (userId) =>
  get(`/behavior/users/${encodeURIComponent(userId)}`);

/* ------------------------------------------------------------------ risk */

export const getRiskAssessments = (params) => get('/risk/assessments', params);
export const getRiskAssessment = (riskId) =>
  get(`/risk/assessments/${encodeURIComponent(riskId)}`);
export const getUserRiskAssessments = (userId, params) =>
  get(`/risk/users/${encodeURIComponent(userId)}`, params);
export const getRiskSummary = () => get('/risk/summary');

/* ----------------------------------------------------------- enforcement */

export const getEnforcementResponses = (params) =>
  get('/enforcement/responses', params);
export const getEnforcementResponse = (responseId) =>
  get(`/enforcement/responses/${encodeURIComponent(responseId)}`);
export const getEnforcementRecommendation = (riskId) =>
  get(`/enforcement/recommendation/${encodeURIComponent(riskId)}`);
export const respondToRisk = (payload) => post('/enforcement/respond', payload);
export const rollbackEnforcement = (responseId, reason) =>
  post(`/enforcement/responses/${encodeURIComponent(responseId)}/rollback`, { reason });

/* ------------------------------------------------------------ investigation */

export const searchUsers = (q, limit = 20) =>
  get('/investigation/search', { q, limit });
export const investigateUser = (userId, eventLimit = 50) =>
  get(`/investigation/users/${encodeURIComponent(userId)}`, { event_limit: eventLimit });
export const investigateEvent = (eventId) =>
  get(`/investigation/events/${encodeURIComponent(eventId)}/context`);

/* ----------------------------------------------------------------- system */

export const getSystemHealth = () => get('/system/health');
export const getAuditLogs = (params) => get('/system/audit-logs', params);
export const getConsentHistory = (params) => get('/system/consent-history', params);

/* --------------------------------------------------------------- demo mode */

export const getDemoStatus = () => get('/demo/status');
export const generateDemoRun = () => post('/demo/generate', {});
export async function resetDemoRuns() {
  const response = await api.delete('/demo/reset');
  return response.data;
}

/* ------------------------------------------------------------- public health */

export async function getPublicHealth() {
  const base = API_BASE_URL.replace(/\/api$/, '');
  const response = await axios.get(`${base}/health`, { timeout: 10000 });
  return response.data;
}

export default api;
