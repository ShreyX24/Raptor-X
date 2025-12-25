interface StatusBadgeProps {
  status: 'online' | 'offline' | 'error' | 'unknown' | boolean;
  label?: string;
  size?: 'sm' | 'md';
}

export function StatusBadge({ status, label, size = 'md' }: StatusBadgeProps) {
  const isOnline = status === 'online' || status === true;
  const isOffline = status === 'offline' || status === false;
  const isError = status === 'error';

  const colors = isOnline
    ? 'bg-green-100 text-green-700'
    : isOffline
    ? 'bg-gray-100 text-gray-600'
    : isError
    ? 'bg-red-100 text-red-700'
    : 'bg-yellow-100 text-yellow-700';

  const dotColor = isOnline
    ? 'bg-green-500'
    : isOffline
    ? 'bg-gray-400'
    : isError
    ? 'bg-red-500'
    : 'bg-yellow-500';

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm';

  const statusText = typeof status === 'boolean'
    ? status ? 'Online' : 'Offline'
    : status.charAt(0).toUpperCase() + status.slice(1);

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-medium ${colors} ${sizeClasses}`}>
      <span className={`h-2 w-2 rounded-full ${dotColor}`} />
      {label || statusText}
    </span>
  );
}
