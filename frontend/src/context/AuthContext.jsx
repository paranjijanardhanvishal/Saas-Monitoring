import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import {
  AUTH_EXPIRED_EVENT,
  errorMessage,
  getMe,
  login as apiLogin,
  logout as apiLogout,
  signup as apiSignup,
  updateConsent as apiUpdateConsent,
} from '../api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionMessage, setSessionMessage] = useState('');
  const mounted = useRef(true);
  const userRef = useRef(null);

  useEffect(() => {
    userRef.current = user;
  }, [user]);

  const bootstrap = useCallback(async () => {
    try {
      const current = await getMe();
      if (mounted.current) {
        setUser(current);
        setSessionMessage('');
      }
    } catch {
      if (!mounted.current) return;
      setUser(null);
      // Silently treat failure during initial bootstrap as no active session.
      // An unauthenticated visitor opening the app should never see "session expired"
      // or "backend did not respond in time" before attempting to log in.
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    bootstrap();

    const onExpired = () => {
      if (!mounted.current) return;
      // Only show "Your session expired" if the user was previously authenticated
      if (userRef.current) {
        setUser(null);
        setSessionMessage('Your session expired. Please sign in again.');
      } else {
        setUser(null);
      }
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => {
      mounted.current = false;
      window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
    };
  }, [bootstrap]);

  const login = useCallback(async (identifier, password) => {
    const data = await apiLogin(identifier.trim(), password);
    // Use user returned in token response directly to avoid a redundant second network call
    const current = data?.user || (await getMe());
    setUser(current);
    setSessionMessage('');
    return current;
  }, []);

  const signup = useCallback(async (email, password, confirmPassword) => {
    const data = await apiSignup({ email, password, confirmPassword });
    const current = data?.user || (await getMe());
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
      setSessionMessage('');
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
      signup,
      logout,
      updateConsent,
      refreshUser,
    }),
    [user, loading, sessionMessage, login, signup, logout, updateConsent, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside an AuthProvider');
  return context;
}
