import type { GameConfig } from '../types';

interface GameCardProps {
  game: GameConfig;
  onSelect?: (game: GameConfig) => void;
  onRun?: (gameName: string) => void;
  isSelected?: boolean;
  disabled?: boolean;
}

export function GameCard({ game, onSelect, onRun, isSelected, disabled }: GameCardProps) {
  return (
    <div
      className={`rounded-lg border p-4 transition-all ${
        disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:shadow-md'
      } ${isSelected ? 'border-blue-500 bg-blue-50' : 'border-gray-200 bg-white'}`}
      onClick={() => !disabled && onSelect?.(game)}
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">
            {game.display_name || game.name}
          </h3>
          <p className="text-sm text-gray-500 truncate max-w-[200px]">
            {game.process_name}
          </p>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 text-white font-bold">
          {(game.display_name || game.name).charAt(0).toUpperCase()}
        </div>
      </div>

      <div className="mt-4 text-sm text-gray-600">
        <div className="flex items-center gap-2">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <span>{game.automation_steps?.length || 0} automation steps</span>
        </div>
        <div className="mt-1 flex items-center gap-2">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{game.launch_delay}s launch delay</span>
        </div>
      </div>

      {game.presets && game.presets.length > 0 && (
        <div className="mt-3">
          <p className="text-xs text-gray-500 mb-1">Presets:</p>
          <div className="flex flex-wrap gap-1">
            {game.presets.slice(0, 3).map((preset) => (
              <span
                key={preset.id}
                className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
              >
                {preset.name}
              </span>
            ))}
            {game.presets.length > 3 && (
              <span className="text-xs text-gray-400">+{game.presets.length - 3} more</span>
            )}
          </div>
        </div>
      )}

      <button
        onClick={(e) => {
          e.stopPropagation();
          onRun?.(game.name);
        }}
        disabled={disabled}
        className="mt-4 w-full rounded bg-green-500 px-3 py-2 text-sm font-medium text-white hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
      >
        Run Automation
      </button>
    </div>
  );
}
