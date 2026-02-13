/**
 * BrandingSettings - Banner color customization tab
 * Port of the Service Manager BannerColorTab to the React frontend
 */

import { useState, useEffect } from 'react';
import { getBranding, updateBranding } from '../../api';
import { useToast } from '../../contexts/ToastContext';
import { Save, RotateCcw, Loader2 } from 'lucide-react';

interface BrandingSettingsProps {
  onUnsavedChange: () => void;
  onSaved: () => void;
}

// Same presets as service_manager/settings.py
const BANNER_PRESETS: Record<string, number[]> = {
  'Purple White': [93, 135, 141, 183, 189, 231],
  'Cyan White': [51, 87, 123, 159, 195, 231],
  'Red Yellow': [196, 202, 208, 214, 220, 226],
  'Green Cyan': [46, 48, 50, 51, 87, 123],
  'Blue Purple': [21, 57, 93, 129, 165, 201],
  'Orange Yellow': [208, 214, 220, 226, 227, 231],
  'Pink White': [199, 205, 211, 217, 223, 231],
  'Fire': [196, 202, 208, 214, 220, 226],
  'Ocean': [17, 18, 19, 20, 21, 27],
  'Forest': [22, 28, 34, 40, 46, 82],
  'Neon': [201, 165, 129, 93, 57, 21],
  'Rainbow': [196, 208, 226, 46, 51, 201],
};

const DEFAULT_GRADIENT = [93, 135, 141, 183, 189, 231];

// RAPTOR X banner lines (Unicode block characters)
const BANNER_LINES = [
  '\u2588\u2588\u2588\u2588\u2588\u2588\u2557  \u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2557     \u2588\u2588\u2557  \u2588\u2588\u2557',
  '\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u255a\u2550\u2550\u2588\u2588\u2554\u2550\u2550\u255d\u2588\u2588\u2554\u2550\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557    \u255a\u2588\u2588\u2557\u2588\u2588\u2554\u255d',
  '\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d   \u2588\u2588\u2551   \u2588\u2588\u2551   \u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d     \u255a\u2588\u2588\u2588\u2554\u255d',
  '\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u2550\u255d    \u2588\u2588\u2551   \u2588\u2588\u2551   \u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557     \u2588\u2588\u2554\u2588\u2588\u2557',
  '\u2588\u2588\u2551  \u2588\u2588\u2551\u2588\u2588\u2551  \u2588\u2588\u2551\u2588\u2588\u2551        \u2588\u2588\u2551   \u255a\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2551  \u2588\u2588\u2551    \u2588\u2588\u2554\u255d \u2588\u2588\u2557',
  '\u255a\u2550\u255d  \u255a\u2550\u255d\u255a\u2550\u255d  \u255a\u2550\u255d\u255a\u2550\u255d        \u255a\u2550\u255d    \u255a\u2550\u2550\u2550\u2550\u2550\u255d \u255a\u2550\u255d  \u255a\u2550\u255d    \u255a\u2550\u255d  \u255a\u2550\u255d',
];

/**
 * Convert ANSI 256-color code to hex RGB string.
 */
function ansi256ToHex(code: number): string {
  let r: number, g: number, b: number;

  if (code < 16) {
    const basic = [
      [0, 0, 0], [128, 0, 0], [0, 128, 0], [128, 128, 0],
      [0, 0, 128], [128, 0, 128], [0, 128, 128], [192, 192, 192],
      [128, 128, 128], [255, 0, 0], [0, 255, 0], [255, 255, 0],
      [0, 0, 255], [255, 0, 255], [0, 255, 255], [255, 255, 255],
    ];
    [r, g, b] = basic[code];
  } else if (code < 232) {
    const idx = code - 16;
    r = Math.floor(idx / 36) * 51;
    g = Math.floor((idx % 36) / 6) * 51;
    b = (idx % 6) * 51;
  } else {
    const v = 8 + (code - 232) * 10;
    r = g = b = v;
  }

  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}

/**
 * Convert hex RGB string to nearest ANSI 256-color code.
 */
function hexToAnsi256(hex: string): number {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);

  // Check 216-color cube (16-231)
  const ri = Math.round(r / 51);
  const gi = Math.round(g / 51);
  const bi = Math.round(b / 51);
  const cubeCode = 16 + 36 * ri + 6 * gi + bi;
  const cr = ri * 51, cg = gi * 51, cb = bi * 51;
  let bestDist = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2;
  let bestCode = cubeCode;

  // Check grayscale ramp (232-255)
  const grayAvg = Math.floor((r + g + b) / 3);
  const grayIdx = Math.max(0, Math.min(23, Math.round((grayAvg - 8) / 10)));
  const grayCode = 232 + grayIdx;
  const gv = 8 + grayIdx * 10;
  const grayDist = (r - gv) ** 2 + (g - gv) ** 2 + (b - gv) ** 2;
  if (grayDist < bestDist) {
    bestCode = grayCode;
  }

  return bestCode;
}

export function BrandingSettings({ onUnsavedChange, onSaved }: BrandingSettingsProps) {
  const [gradient, setGradient] = useState<number[]>(DEFAULT_GRADIENT);
  const [originalGradient, setOriginalGradient] = useState<number[]>(DEFAULT_GRADIENT);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  // Fetch current branding on mount
  useEffect(() => {
    async function load() {
      try {
        const data = await getBranding();
        setGradient(data.banner_gradient);
        setOriginalGradient(data.banner_gradient);
      } catch {
        // Use default if fetch fails
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const isDirty = JSON.stringify(gradient) !== JSON.stringify(originalGradient);

  useEffect(() => {
    if (isDirty) onUnsavedChange();
  }, [isDirty, onUnsavedChange]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateBranding(gradient);
      setOriginalGradient([...gradient]);
      toast.success('Saved', 'Banner colors saved. SUTs will update on next connection.');
      onSaved();
    } catch (err) {
      toast.error('Save Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSaving(false);
    }
  };

  const handlePreset = (colors: number[]) => {
    setGradient([...colors]);
  };

  const handleColorChange = (index: number, hex: string) => {
    const newGradient = [...gradient];
    newGradient[index] = hexToAnsi256(hex);
    setGradient(newGradient);
  };

  const handleReset = () => {
    setGradient([...DEFAULT_GRADIENT]);
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-text-muted" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      {/* Header with Save/Reset */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">Banner Colors</h2>
          <p className="text-sm text-text-muted">Customize the RAPTOR X banner gradient for all SUT consoles</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleReset}
            className="flex items-center gap-2 px-3 py-2 text-sm bg-surface-elevated hover:bg-surface-hover border border-border rounded-lg transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            Reset
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !isDirty}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-primary hover:bg-primary/90 text-white rounded-lg transition-colors disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Presets + Per-row pickers */}
        <div className="space-y-6">
          {/* Presets */}
          <div>
            <h3 className="text-sm font-semibold text-text-secondary mb-3">Preset Gradients</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {Object.entries(BANNER_PRESETS).map(([name, colors]) => {
                const isActive = JSON.stringify(colors) === JSON.stringify(gradient);
                return (
                  <button
                    key={name}
                    onClick={() => handlePreset(colors)}
                    className={`
                      flex flex-col items-center gap-1.5 p-2 rounded-lg border transition-all text-xs
                      ${isActive
                        ? 'border-primary bg-primary/10 ring-1 ring-primary'
                        : 'border-border hover:border-text-muted bg-surface-elevated hover:bg-surface-hover'
                      }
                    `}
                  >
                    {/* Color bar */}
                    <div className="flex w-full h-4 rounded overflow-hidden">
                      {colors.map((c, i) => (
                        <div
                          key={i}
                          className="flex-1"
                          style={{ backgroundColor: ansi256ToHex(c) }}
                        />
                      ))}
                    </div>
                    <span className="text-text-secondary">{name}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Per-row color pickers */}
          <div>
            <h3 className="text-sm font-semibold text-text-secondary mb-3">Per-Row Colors</h3>
            <div className="space-y-2">
              {gradient.map((code, i) => (
                <div key={i} className="flex items-center gap-3 bg-surface-elevated rounded-lg px-3 py-2">
                  <span className="text-xs text-text-muted w-12">Row {i + 1}</span>
                  <input
                    type="color"
                    value={ansi256ToHex(code)}
                    onChange={(e) => handleColorChange(i, e.target.value)}
                    className="w-8 h-8 rounded border border-border cursor-pointer bg-transparent"
                  />
                  <div
                    className="flex-1 h-6 rounded"
                    style={{ backgroundColor: ansi256ToHex(code) }}
                  />
                  <span className="text-xs text-text-muted font-mono w-8 text-right">{code}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Live preview */}
        <div>
          <h3 className="text-sm font-semibold text-text-secondary mb-3">Live Preview</h3>
          <div className="bg-[#1e1e1e] rounded-lg p-6 font-mono text-[11px] leading-snug select-none">
            {BANNER_LINES.map((line, i) => (
              <div
                key={i}
                style={{ color: ansi256ToHex(gradient[i] ?? 231), whiteSpace: 'pre' }}
              >
                {line}
              </div>
            ))}
            <div className="mt-3" style={{ color: '#ffffff' }}>
              <div className="text-center text-xs">SUT Client v0.3.0</div>
            </div>
          </div>
          <p className="text-xs text-text-muted mt-2">
            Changes apply to all connected SUTs on their next WebSocket reconnect.
          </p>
        </div>
      </div>
    </div>
  );
}

export default BrandingSettings;
