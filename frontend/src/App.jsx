import React, { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation, Link } from 'react-router-dom';
import { Loader2, ShieldX } from 'lucide-react';
import DashboardLayout from './layouts/DashboardLayout';
import { AuthProvider, useAuth } from './context/AuthContext';
import ErrorBoundary from './components/ErrorBoundary';
import { btnPrimary } from './components/ui';

const Login = lazy(() => import('./pages/Login'));
const ResetPassword = lazy(() => import('./pages/ResetPassword'));
const Consent = lazy(() => import('./pages/Consent'));
const Landing = lazy(() => import('./pages/Landing'));
const Overview = lazy(() => import('./pages/Overview'));
const LiveActivity = lazy(() => import('./pages/LiveActivity'));
const Alerts = lazy(() => import('./pages/Alerts'));
const Incidents = lazy(() => import('./pages/Incidents'));
const Users = lazy(() => import('./pages/Users'));
const Ueba = lazy(() => import('./pages/Ueba'));
const SensitiveFiles = lazy(() => import('./pages/SensitiveFiles'));
const RiskPosture = lazy(() => import('./pages/RiskPosture'));
const Investigation = lazy(() => import('./pages/Investigation'));
const Enforcement = lazy(() => import('./pages/Enforcement'));
const SystemHealth = lazy(() => import('./pages/SystemHealth'));

function FullPageLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0b0f19] text-slate-400">
      <Loader2 size={22} className="mr-3 animate-spin text-blue-400" />
      Restoring session…
    </div>
  );
}

function RouteLoader() {
  return (
    <div className="flex min-h-[55vh] items-center justify-center text-slate-400" role="status" aria-live="polite">
      <Loader2 size={20} className="mr-3 animate-spin text-blue-400" />
      Loading view…
    </div>
  );
}

function ProtectedRoute({ children, allowConsentPage = false }) {
  const { user, loading, consentRequired } = useAuth();
  const location = useLocation();

  if (loading) return <FullPageLoader />;
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (consentRequired && !allowConsentPage) {
    return <Navigate to="/consent" replace />;
  }
  return children;
}

function AdminOnly({ children }) {
  const { isAdmin } = useAuth();
  if (!isAdmin) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="max-w-md rounded-xl border border-slate-800 bg-[#111827] p-6 text-center">
          <span className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-red-900/60 bg-red-950/40 text-red-400">
            <ShieldX size={22} />
          </span>
          <h1 className="text-lg font-bold text-white">Administrator access required</h1>
          <p className="mt-2 text-sm text-slate-400">
            This area is restricted to SOC administrators. Your account does not have permission to
            view it.
          </p>
          <Link to="/dashboard" className="mt-5 inline-flex">
            <span className={btnPrimary}>Return to dashboard</span>
          </Link>
        </div>
      </div>
    );
  }
  return children;
}

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, [pathname]);
  return null;
}

function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0b0f19] p-6">
      <div className="max-w-md rounded-xl border border-slate-800 bg-[#111827] p-6 text-center">
        <h1 className="text-4xl font-bold text-white">404</h1>
        <p className="mt-2 text-sm text-slate-400">The page you requested does not exist.</p>
        <Link to="/dashboard" className="mt-5 inline-flex">
          <span className={btnPrimary}>Go to dashboard</span>
        </Link>
      </div>
    </div>
  );
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route
        path="/consent"
        element={
          <ProtectedRoute allowConsentPage>
            <Consent />
          </ProtectedRoute>
        }
      />

      <Route
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<Overview />} />
        <Route path="/risk-posture" element={<RiskPosture />} />
        <Route
          path="/live-activity"
          element={
            <AdminOnly>
              <LiveActivity />
            </AdminOnly>
          }
        />
        <Route path="/sensitive-files" element={<SensitiveFiles />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/incidents" element={<Incidents />} />
        <Route path="/ueba" element={<Ueba />} />
        <Route path="/users" element={<Users />} />
        <Route path="/investigation" element={<Investigation />} />
        <Route path="/enforcement" element={<Enforcement />} />
        <Route
          path="/system-health"
          element={
            <AdminOnly>
              <SystemHealth />
            </AdminOnly>
          }
        />
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <ScrollToTop />
          <Suspense fallback={<RouteLoader />}>
            <AppRoutes />
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}
