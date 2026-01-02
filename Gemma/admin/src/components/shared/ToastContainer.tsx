/**
 * ToastContainer - Displays toast notifications
 */

import { useToast } from '../../contexts/ToastContext';
import type { ToastMessage } from '../../types/admin';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';

const TOAST_ICONS: Record<ToastMessage['type'], React.ReactNode> = {
  success: <CheckCircle className="w-5 h-5 text-success" />,
  error: <XCircle className="w-5 h-5 text-danger" />,
  warning: <AlertTriangle className="w-5 h-5 text-warning" />,
  info: <Info className="w-5 h-5 text-primary" />,
};

const TOAST_STYLES: Record<ToastMessage['type'], string> = {
  success: 'border-success/30 bg-success/10',
  error: 'border-danger/30 bg-danger/10',
  warning: 'border-warning/30 bg-warning/10',
  info: 'border-primary/30 bg-primary/10',
};

interface ToastProps {
  toast: ToastMessage;
  onDismiss: () => void;
}

function Toast({ toast, onDismiss }: ToastProps) {
  return (
    <div
      className={`
        flex items-start gap-3 p-4 rounded-lg border shadow-lg
        backdrop-blur-sm animate-slide-in-right
        ${TOAST_STYLES[toast.type]}
      `}
      role="alert"
    >
      <div className="flex-shrink-0 mt-0.5">{TOAST_ICONS[toast.type]}</div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-text-primary">{toast.title}</p>
        {toast.message && (
          <p className="mt-1 text-xs text-text-secondary">{toast.message}</p>
        )}
      </div>
      <button
        onClick={onDismiss}
        className="flex-shrink-0 p-1 rounded hover:bg-surface-hover transition-colors text-text-muted hover:text-text-primary"
        aria-label="Dismiss"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

export function ToastContainer() {
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) {
    return null;
  }

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none"
      aria-live="polite"
      aria-atomic="true"
    >
      {toasts.map(toast => (
        <div key={toast.id} className="pointer-events-auto">
          <Toast toast={toast} onDismiss={() => removeToast(toast.id)} />
        </div>
      ))}
    </div>
  );
}

export default ToastContainer;
