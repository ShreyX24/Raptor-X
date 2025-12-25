import { useRef, useEffect } from 'react';
import type { LogEntry } from '../types';

interface LogViewerProps {
  logs: LogEntry[];
  maxHeight?: string;
  autoScroll?: boolean;
}

export function LogViewer({ logs, maxHeight = '300px', autoScroll = true }: LogViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const levelColors: Record<string, string> = {
    info: 'text-blue-400',
    warning: 'text-yellow-400',
    error: 'text-red-400',
    debug: 'text-gray-500',
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { hour12: false });
  };

  if (logs.length === 0) {
    return (
      <div
        className="rounded-lg bg-gray-900 p-4 font-mono text-sm text-gray-400"
        style={{ maxHeight }}
      >
        No logs available
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="rounded-lg bg-gray-900 p-4 font-mono text-sm overflow-y-auto"
      style={{ maxHeight }}
    >
      {logs.map((log, index) => (
        <div key={index} className="flex gap-2 hover:bg-gray-800 px-1 -mx-1 rounded">
          <span className="text-gray-500 flex-shrink-0">
            {formatTime(log.timestamp)}
          </span>
          <span className={`flex-shrink-0 uppercase w-14 ${levelColors[log.level] || 'text-gray-400'}`}>
            [{log.level}]
          </span>
          <span className="text-gray-300 break-all">{log.message}</span>
        </div>
      ))}
    </div>
  );
}
