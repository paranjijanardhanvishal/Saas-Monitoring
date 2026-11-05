import React from 'react';
import { AlertTriangle } from 'lucide-react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Log only the message and component stack; never credentials or payloads.
    console.error('Unhandled UI error:', error?.message);
    if (info?.componentStack) console.error(info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-[#0b0f19] p-6">
          <div className="w-full max-w-lg rounded-xl border border-red-900/50 bg-[#111827] p-6 text-center shadow-2xl">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full border border-red-900/60 bg-red-950/40 text-red-400">
              <AlertTriangle size={22} />
            </div>
            <h1 className="text-lg font-bold text-white">The interface encountered an error</h1>
            <p className="mt-2 text-sm text-slate-400">
              The page could not be rendered. Reload to try again. If it persists, check the browser
              console and backend logs.
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-5 inline-flex items-center justify-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500"
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
