/**
 * PresetMatrix Component
 * Grid selector for quality (low/medium/high/ultra) × resolution (720p/1080p/1440p/2160p)
 */

import { useMemo } from 'react';

// Constants matching preset-manager/core/constants.py
export const QUALITY_LEVELS = ['low', 'medium', 'high', 'ultra'] as const;
export const RESOLUTIONS = ['720p', '1080p', '1440p', '2160p'] as const;

export type QualityLevel = typeof QUALITY_LEVELS[number];
export type Resolution = typeof RESOLUTIONS[number];

export interface PresetAvailability {
  [quality: string]: Resolution[];
}

interface PresetMatrixProps {
  gameName: string;
  availablePresets: PresetAvailability;
  sutMaxResolution?: Resolution;
  selectedQuality: QualityLevel | null;
  selectedResolution: Resolution | null;
  onSelect: (quality: QualityLevel, resolution: Resolution) => void;
  disabled?: boolean;
}

const RESOLUTION_INFO: Record<Resolution, { width: number; height: number; name: string }> = {
  '720p': { width: 1280, height: 720, name: 'HD' },
  '1080p': { width: 1920, height: 1080, name: 'Full HD' },
  '1440p': { width: 2560, height: 1440, name: '2K QHD' },
  '2160p': { width: 3840, height: 2160, name: '4K UHD' },
};

const QUALITY_COLORS: Record<QualityLevel, { bg: string; hover: string; selected: string; text: string }> = {
  low: {
    bg: 'bg-gray-100',
    hover: 'hover:bg-gray-200',
    selected: 'bg-gray-500 text-white',
    text: 'text-gray-700',
  },
  medium: {
    bg: 'bg-blue-50',
    hover: 'hover:bg-blue-100',
    selected: 'bg-blue-500 text-white',
    text: 'text-blue-700',
  },
  high: {
    bg: 'bg-green-50',
    hover: 'hover:bg-green-100',
    selected: 'bg-green-500 text-white',
    text: 'text-green-700',
  },
  ultra: {
    bg: 'bg-purple-50',
    hover: 'hover:bg-purple-100',
    selected: 'bg-purple-500 text-white',
    text: 'text-purple-700',
  },
};

function getResolutionOrder(res: Resolution): number {
  return RESOLUTIONS.indexOf(res);
}

export function PresetMatrix({
  gameName,
  availablePresets,
  sutMaxResolution,
  selectedQuality,
  selectedResolution,
  onSelect,
  disabled = false,
}: PresetMatrixProps) {
  // Determine which cells are available vs placeholder
  const cellStates = useMemo(() => {
    const states: Record<string, 'available' | 'placeholder' | 'exceeds_max' | 'unavailable'> = {};

    const maxResOrder = sutMaxResolution ? getResolutionOrder(sutMaxResolution) : 3;

    for (const quality of QUALITY_LEVELS) {
      for (const resolution of RESOLUTIONS) {
        const key = `${quality}-${resolution}`;
        const resOrder = getResolutionOrder(resolution);

        if (resOrder > maxResOrder) {
          states[key] = 'exceeds_max';
        } else if (availablePresets[quality]?.includes(resolution)) {
          states[key] = 'available';
        } else {
          states[key] = 'placeholder';
        }
      }
    }

    return states;
  }, [availablePresets, sutMaxResolution]);

  const isSelected = (quality: QualityLevel, resolution: Resolution) =>
    selectedQuality === quality && selectedResolution === resolution;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">Preset Selection</h3>
        <span className="text-sm text-gray-500">{gameName}</span>
      </div>

      {/* Legend */}
      <div className="mb-4 flex flex-wrap gap-4 text-xs">
        <div className="flex items-center gap-1.5">
          <div className="h-3 w-3 rounded border-2 border-green-500 bg-green-100" />
          <span>Available</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-3 w-3 rounded border border-dashed border-gray-300 bg-gray-50" />
          <span>Placeholder</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-3 w-3 rounded bg-red-100">
            <div className="flex h-full items-center justify-center text-red-400">×</div>
          </div>
          <span>Exceeds SUT</span>
        </div>
      </div>

      {/* Matrix Grid */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[400px]">
          <thead>
            <tr>
              <th className="pb-2 pr-2 text-left text-xs font-medium text-gray-500">Quality</th>
              {RESOLUTIONS.map((res) => (
                <th key={res} className="pb-2 text-center text-xs font-medium text-gray-500">
                  <div>{res}</div>
                  <div className="text-[10px] font-normal text-gray-400">
                    {RESOLUTION_INFO[res].width}×{RESOLUTION_INFO[res].height}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {QUALITY_LEVELS.map((quality) => (
              <tr key={quality}>
                <td className="py-1 pr-2">
                  <span className={`text-sm font-medium capitalize ${QUALITY_COLORS[quality].text}`}>
                    {quality}
                  </span>
                </td>
                {RESOLUTIONS.map((resolution) => {
                  const key = `${quality}-${resolution}`;
                  const state = cellStates[key];
                  const selected = isSelected(quality, resolution);
                  const isClickable = state === 'available' && !disabled;

                  let cellClass = 'h-10 w-full rounded transition-all ';

                  if (selected) {
                    cellClass += QUALITY_COLORS[quality].selected + ' ring-2 ring-offset-1 ring-blue-400';
                  } else if (state === 'available') {
                    cellClass += `border-2 border-green-400 ${QUALITY_COLORS[quality].bg} ${!disabled ? QUALITY_COLORS[quality].hover : ''} ${!disabled ? 'cursor-pointer' : 'cursor-not-allowed opacity-50'}`;
                  } else if (state === 'placeholder') {
                    cellClass += 'border border-dashed border-gray-300 bg-gray-50 cursor-not-allowed';
                  } else if (state === 'exceeds_max') {
                    cellClass += 'bg-red-50 cursor-not-allowed';
                  }

                  return (
                    <td key={key} className="p-1">
                      <button
                        className={cellClass}
                        onClick={() => isClickable && onSelect(quality, resolution)}
                        disabled={!isClickable}
                        title={
                          state === 'available'
                            ? `Select ${quality} @ ${resolution}`
                            : state === 'placeholder'
                            ? 'Preset not yet configured'
                            : state === 'exceeds_max'
                            ? `Resolution exceeds SUT max (${sutMaxResolution})`
                            : 'Unavailable'
                        }
                      >
                        {selected && (
                          <svg className="mx-auto h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                        )}
                        {state === 'exceeds_max' && !selected && (
                          <span className="text-xs text-red-400">×</span>
                        )}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Selected Info */}
      {selectedQuality && selectedResolution && (
        <div className="mt-4 rounded bg-blue-50 p-3 text-sm">
          <div className="font-medium text-blue-900">
            Selected: <span className="capitalize">{selectedQuality}</span> @ {selectedResolution}
          </div>
          <div className="text-blue-700">
            {RESOLUTION_INFO[selectedResolution].width} × {RESOLUTION_INFO[selectedResolution].height} ({RESOLUTION_INFO[selectedResolution].name})
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Compact version for inline use
 */
interface PresetSelectorProps {
  availablePresets: PresetAvailability;
  selectedQuality: QualityLevel | null;
  selectedResolution: Resolution | null;
  onQualityChange: (quality: QualityLevel) => void;
  onResolutionChange: (resolution: Resolution) => void;
  sutMaxResolution?: Resolution;
  disabled?: boolean;
}

export function PresetSelector({
  availablePresets,
  selectedQuality,
  selectedResolution,
  onQualityChange,
  onResolutionChange,
  sutMaxResolution,
  disabled = false,
}: PresetSelectorProps) {
  const maxResOrder = sutMaxResolution ? getResolutionOrder(sutMaxResolution) : 3;

  // Get available resolutions for selected quality
  const availableResolutions = selectedQuality
    ? (availablePresets[selectedQuality] || []).filter(
        (res) => getResolutionOrder(res) <= maxResOrder
      )
    : [];

  return (
    <div className="flex gap-4">
      {/* Quality Selector */}
      <div className="flex-1">
        <label className="mb-1 block text-xs font-medium text-gray-500">Quality</label>
        <select
          className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
          value={selectedQuality || ''}
          onChange={(e) => onQualityChange(e.target.value as QualityLevel)}
          disabled={disabled}
        >
          <option value="">Select quality...</option>
          {QUALITY_LEVELS.map((quality) => {
            const hasPresets = Object.keys(availablePresets).includes(quality);
            return (
              <option key={quality} value={quality} disabled={!hasPresets}>
                {quality.charAt(0).toUpperCase() + quality.slice(1)}
                {!hasPresets && ' (no presets)'}
              </option>
            );
          })}
        </select>
      </div>

      {/* Resolution Selector */}
      <div className="flex-1">
        <label className="mb-1 block text-xs font-medium text-gray-500">Resolution</label>
        <select
          className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
          value={selectedResolution || ''}
          onChange={(e) => onResolutionChange(e.target.value as Resolution)}
          disabled={disabled || !selectedQuality}
        >
          <option value="">Select resolution...</option>
          {RESOLUTIONS.map((res) => {
            const isAvailable = availableResolutions.includes(res);
            const exceedsMax = getResolutionOrder(res) > maxResOrder;
            return (
              <option key={res} value={res} disabled={!isAvailable || exceedsMax}>
                {res} ({RESOLUTION_INFO[res].width}×{RESOLUTION_INFO[res].height})
                {exceedsMax && ' - exceeds SUT'}
                {!isAvailable && !exceedsMax && ' - no preset'}
              </option>
            );
          })}
        </select>
      </div>
    </div>
  );
}
