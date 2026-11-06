import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import {
  AUTH_EXPIRED_EVENT,
  errorMessage,
  getMe,
  login as apiLogin,
  logout as apiLogout,
  updateConsent as apiUpdateConsent,
} from '../api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionMessage, setSessionMessage] = useState('');
  const mounted = useRef(true);

  const bootstrap = useCallback(async () => {
    try {
      const current = await getMe();
      if (mounted.current) {
        setUser(current);
        setSessionMessage('');
      }
    } catch (error) {
      if (!mounted.current) return;
      setUser(null);
      // A 401 here simply means there is no active session. Surface anything else.
      if (error?.response?.status !== 401) {
        setSessionMessage(errorMessage(error, 'Could not restore your session.'));
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    bootstrap();

    const onExpired = () => {
      if (!mounted.current) return;
      setUser(null);
      setSessionMessage('Your session expired. Please sign in again.');
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => {
      mounted.current = false;
      window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
    };
  }, [bootstrap]);

  const login = useCallback(async (identifier, password) => {
    await apiLogin(identifier.trim(), password);
    const current = await getMe();
    setUser(current);
    setSessionMessage('');
    return current;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      // The local session is cleared even if the server session already expired.
    } finally {
      setUser(null);
    }
  }, []);

  const updateConsent = useCallback(async (state) => {
    const updated = await apiUpdateConsent(state);
    setUser(updated);
    return updated;
  }, []);

  const refreshUser = useCallback(async () => {
    const current = await getMe();
    setUser(current);
    return current;
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      sessionMessage,
      clearSessionMessage: () => setSessionMessage(''),
      isAuthenticated: Boolean(user),
      isAdmin: user?.role === 'ADMIN',
      isEditor: user?.role === 'EDITOR',
      isVisitor: user?.role === 'VISITOR',
      canEdit: user?.role === 'ADMIN' || user?.role === 'EDITOR',
      consentRequired: user?.role === 'USER' && user?.monitoring_enabled === 'NOT_ASKED',
      login,
      logout,
      updateConsent,
      refreshUser,
    }),
    [user, loading, sessionMessage, login, logout, updateConsent, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside an AuthProvider');
  return context;
}
