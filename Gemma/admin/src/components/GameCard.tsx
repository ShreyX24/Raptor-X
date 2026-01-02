import { useState, useEffect } from 'react';
import { checkGameAvailability, type GameAvailabilityResult } from '../api';
import type { GameConfig } from '../types';

interface GameCardProps {
  game: GameConfig;
  onSelect?: (game: GameConfig) => void;
  onRun?: (gameName: string) => void;
  isSelected?: boolean;
  disabled?: boolean;
  sutIp?: string;  // Optional SUT IP to check availability
  // Campaign selection mode
  campaignMode?: boolean;
  isCampaignSelected?: boolean;
  onCampaignToggle?: (gameName: string, selected: boolean) => void;
}

export function GameCard({ game, onSelect, onRun, isSelected, disabled, sutIp, campaignMode, isCampaignSelected, onCampaignToggle }: GameCardProps) {
  const [availability, setAvailability] = useState<GameAvailabilityResult | null>(null);
  const [checking, setChecking] = useState(false);

  // Check availability when sutIp is provided
  useEffect(() => {
    if (!sutIp) {
      setAvailability(null);
      return;
    }

    const check = async () => {
      setChecking(true);
      try {
        const result = await checkGameAvailability(game.name, sutIp);
        setAvailability(result);
      } catch (err) {
        setAvailability({
          available: false,
          game_name: game.name,
          steam_app_id: null,
          sut_ip: sutIp,
          match_method: null,
          error: err instanceof Error ? err.message : 'Check failed'
        });
      } finally {
        setChecking(false);
      }
    };

    check();
  }, [sutIp, game.name]);

  // Determine border color based on availability
  const getBorderClass = () => {
    if (campaignMode && isCampaignSelected) return 'border-purple-500 ring-2 ring-purple-200 bg-purple-50';
    if (isSelected) return 'border-blue-500 bg-blue-50';
    if (!sutIp) return 'border-gray-200 bg-white';
    if (checking) return 'border-gray-300 bg-gray-50';
    if (availability?.available) return 'border-green-400 bg-green-50/50';
    return 'border-red-300 bg-red-50/30';
  };

  // Handle card click in campaign mode
  const handleCardClick = () => {
    if (disabled) return;
    if (campaignMode) {
      onCampaignToggle?.(game.name, !isCampaignSelected);
    } else {
      onSelect?.(game);
    }
  };

  return (
    <div
      className={`rounded-lg border p-4 transition-all ${
        disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:shadow-md'
      } ${getBorderClass()}`}
      onClick={handleCardClick}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          {/* Campaign Mode Checkbox */}
          {campaignMode && (
            <div className="flex-shrink-0 pt-0.5">
              <input
                type="checkbox"
                checked={isCampaignSelected}
                onChange={(e) => {
                  e.stopPropagation();
                  onCampaignToggle?.(game.name, e.target.checked);
                }}
                className="h-5 w-5 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
              />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">
              {game.display_name || game.name}
            </h3>
            <p className="text-sm text-gray-500 truncate">
              {game.process_name}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 text-white font-bold">
            {(game.display_name || game.name).charAt(0).toUpperCase()}
          </div>
          {/* Availability badge */}
          {sutIp && (
            <div className="mt-1">
              {checking ? (
                <span className="inline-flex items-center px-2 py-0.5 text-xs bg-gray-100 text-gray-500 rounded-full">
                  <svg className="animate-spin h-3 w-3 mr-1" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Checking
                </span>
              ) : availability?.available ? (
                <span className="inline-flex items-center px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded-full">
                  <svg className="h-3 w-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                  Installed
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 text-xs bg-red-100 text-red-700 rounded-full">
                  <svg className="h-3 w-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                  Not Found
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* SUT Availability Details */}
      {sutIp && availability && !checking && (
        <div className={`mt-3 p-2 rounded-lg text-xs ${
          availability.available ? 'bg-green-100/50' : 'bg-red-100/50'
        }`}>
          {availability.available ? (
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-gray-500">Match:</span>
                <span className="font-medium text-green-700">
                  {availability.match_method === 'steam_app_id' ? 'Steam App ID' : 'Name'}
                </span>
                {availability.steam_app_id && (
                  <span className="text-gray-400">({availability.steam_app_id})</span>
                )}
              </div>
              {availability.install_path && (
                <div className="truncate" title={availability.install_path}>
                  <span className="text-gray-500">Path:</span>{' '}
                  <span className="font-mono text-green-700">{availability.install_path}</span>
                </div>
              )}
            </div>
          ) : (
            <div className="text-red-600">
              {availability.error || 'Game not installed on selected SUT'}
            </div>
          )}
        </div>
      )}

      <div className="mt-3 text-sm text-gray-600">
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

      {campaignMode ? (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onCampaignToggle?.(game.name, !isCampaignSelected);
          }}
          className={`mt-4 w-full rounded px-3 py-2 text-sm font-medium transition-colors ${
            isCampaignSelected
              ? 'bg-purple-500 text-white hover:bg-purple-600'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-300'
          }`}
        >
          {isCampaignSelected ? '✓ Added to Campaign' : 'Add to Campaign'}
        </button>
      ) : (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRun?.(game.name);
          }}
          disabled={disabled || (!!sutIp && !availability?.available)}
          className="mt-4 w-full rounded bg-green-500 px-3 py-2 text-sm font-medium text-white hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
        >
          Run Automation
        </button>
      )}
    </div>
  );
}
