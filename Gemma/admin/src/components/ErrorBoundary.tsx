import { Component, ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[ErrorBoundary] Caught error:', error);
    console.error('[ErrorBoundary] Component stack:', errorInfo.componentStack);
    this.setState({ errorInfo });
  }

  handleReload = () => {
    window.location.reload();
  };

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen bg-background flex items-center justify-center p-4">
          <div className="max-w-2xl w-full bg-surface rounded-xl border border-danger/50 p-6 shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="h-12 w-12 rounded-xl bg-danger/20 flex items-center justify-center">
                <svg className="h-7 w-7 text-danger" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold text-text-primary">Something went wrong</h1>
                <p className="text-sm text-text-muted">An error occurred in the application</p>
              </div>
            </div>

            <div className="bg-surface-elevated rounded-lg p-4 mb-4 border border-border">
              <p className="text-danger font-mono text-sm mb-2">
                {this.state.error?.message || 'Unknown error'}
              </p>
              {this.state.error?.stack && (
                <details className="mt-2">
                  <summary className="text-text-muted text-xs cursor-pointer hover:text-text-secondary transition-colors">
                    Stack trace
                  </summary>
                  <pre className="mt-2 text-xs text-text-muted overflow-x-auto whitespace-pre-wrap font-mono">
                    {this.state.error.stack}
                  </pre>
                </details>
              )}
              {this.state.errorInfo?.componentStack && (
                <details className="mt-2">
                  <summary className="text-text-muted text-xs cursor-pointer hover:text-text-secondary transition-colors">
                    Component stack
                  </summary>
                  <pre className="mt-2 text-xs text-text-muted overflow-x-auto whitespace-pre-wrap font-mono">
                    {this.state.errorInfo.componentStack}
                  </pre>
                </details>
              )}
            </div>

            <div className="flex gap-3">
              <button
                onClick={this.handleReset}
                className="flex-1 btn btn-secondary"
              >
                Try Again
              </button>
              <button
                onClick={this.handleReload}
                className="flex-1 btn btn-primary"
              >
                Reload Page
              </button>
            </div>

            <div className="mt-4 pt-4 border-t border-border">
              <p className="text-xs text-text-muted">
                If this problem persists, check the browser console for more details or contact support.
              </p>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * Global error handler setup - call this in main.tsx
 */
export function setupGlobalErrorHandlers() {
  // Handle unhandled promise rejections
  window.addEventListener('unhandledrejection', (event) => {
    console.error('[Global] Unhandled Promise Rejection:', event.reason);
    // Optionally show a toast notification here
  });

  // Handle global errors
  window.addEventListener('error', (event) => {
    console.error('[Global] Uncaught Error:', event.error);
  });

  // Handle network errors gracefully
  window.addEventListener('offline', () => {
    console.warn('[Global] Network connection lost');
  });

  window.addEventListener('online', () => {
    console.log('[Global] Network connection restored');
  });
}
