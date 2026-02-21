/**
 * WorkflowBuilder - Visual workflow builder for game automation
 * Replaces the desktop Tkinter workflow_builder.py with a web-based interface
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useDevices, useWorkflowBuilder } from '../hooks';
import { StatusDot, WorkflowLibrary } from '../components';
import type { BoundingBox, WorkflowStep, SUT } from '../types';
import { saveWorkflowYaml, launchGame, killProcess, isProcessRunning } from '../api/workflowBuilder';
import { Play, StopCircle, Camera, Workflow, ArrowLeft } from 'lucide-react';

// OCR configuration for OmniParser
interface OcrConfig {
  use_paddleocr: boolean;
  text_threshold: number;
  box_threshold: number;
}

// Hook configuration for pre/post automation scripts
interface HookConfig {
  path: string;
  args?: string[];
  timeout?: number;
  persistent?: boolean;  // If true, runs throughout automation
  critical?: boolean;    // If true, automation fails if hook fails
}

// Hooks section for game metadata
interface HooksConfig {
  pre?: HookConfig[];
  post?: HookConfig[];
}

// Tracing configuration
interface TracingConfig {
  enabled: boolean;
  agents?: string[];
  output_dir?: string;
}

// Sideload configuration for per-step scripts
interface SideloadConfig {
  path: string;
  args?: string[];
  timeout?: number;
  wait_for_completion?: boolean;
}

// Game metadata interface - matches YAML config structure
interface GameMetadata {
  // Basic Info
  game_name: string;
  preset_id: string;
  steam_app_id: string;
  launch_method: 'steam' | 'exe';
  // Process Info
  path: string;
  process_id: string;
  process_name: string;
  game_process: string; // For launcher-based games
  // Timing
  startup_wait: number;
  benchmark_duration: number;
  benchmark_name: string;
  // Technical
  engine: string;
  graphics_api: string;
  version: string;
  use_ocr_fallback: boolean;
  // OCR Config
  ocr_config: OcrConfig;
  // Tracing Config (SOCWatch, PTAT)
  tracing?: TracingConfig;
  // Hooks Config (pre/post scripts)
  hooks?: HooksConfig;
}

// Action types supported
const ACTION_TYPES = [
  { value: 'find_and_click', label: 'Click Element', description: 'Find element and click' },
  { value: 'double_click', label: 'Double Click', description: 'Double click element' },
  { value: 'right_click', label: 'Right Click', description: 'Right click element' },
  { value: 'key', label: 'Press Key', description: 'Press a single key' },
  { value: 'hotkey', label: 'Hotkey', description: 'Press key combination' },
  { value: 'text', label: 'Type Text', description: 'Type text into field' },
  { value: 'wait', label: 'Wait', description: 'Wait for duration' },
  { value: 'scroll', label: 'Scroll', description: 'Scroll up or down' },
  { value: 'drag', label: 'Drag', description: 'Drag element to position' },
] as const;

// Whimsical loading words shown during AI parsing
const PARSING_WORDS = [
  'Julienning', 'Reticulating', 'Sautéing', 'Caramelizing', 'Deglazing',
  'Marinating', 'Flambéing', 'Blanching', 'Whisking', 'Braising',
  'Fermenting', 'Kneading', 'Tempering', 'Simmering', 'Folding',
  'Reducing', 'Emulsifying', 'Zesting', 'Proofing', 'Garnishing',
  'Mincing', 'Basting', 'Transmogrifying', 'Discombobulating', 'Percolating',
  'Amalgamating', 'Tessellating', 'Crystallizing', 'Synthesizing', 'Harmonizing',
  'Calibrating', 'Interpolating', 'Coalescing', 'Bifurcating', 'Galvanizing',
  'Ionizing', 'Permutating', 'Cogitating', 'Ruminating', 'Pontificating',
  'Defragulating', 'Rasmatizing', 'Syncopating', 'Untangling', 'Refactoring',
  'Decanting', 'Distilling', 'Perambulating', 'Recalibrating', 'Extrapolating',
  'Massaging', 'Churning', 'Steeping', 'Aerating', 'Infusing',
  'Pickling', 'Crunching', 'Wrangling', 'Pixelating', 'Dicing',
  'Broiling', 'Poaching', 'Clarifying', 'Congealing', 'Precipitating',
];

// Key options for key actions
const KEY_OPTIONS = [
  'enter', 'escape', 'tab', 'space', 'backspace', 'delete',
  'up', 'down', 'left', 'right', 'home', 'end', 'pageup', 'pagedown',
  'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
];

// Text match options
const TEXT_MATCH_OPTIONS = [
  { value: 'exact', label: 'Exact Match' },
  { value: 'contains', label: 'Contains' },
  { value: 'startswith', label: 'Starts With' },
  { value: 'endswith', label: 'Ends With' },
];

// Element type in selector
interface ElementSelector {
  type: 'icon' | 'text' | 'any';
  text: string;
  textMatch: 'exact' | 'contains' | 'startswith' | 'endswith';
}

// Draft step being edited
interface DraftStep {
  actionType: string;
  element: ElementSelector | null;
  key?: string;
  hotkey?: string;
  text?: string;
  duration?: number;
  scrollDirection?: 'up' | 'down';
  scrollAmount?: number;
  timeout: number;
  delay: number;
  optional: boolean;
  description: string;
  // Per-step OCR config (overrides workflow-level defaults)
  ocrConfig?: {
    use_paddleocr?: boolean;
    text_threshold?: number;
    box_threshold?: number;
  };
  useCustomOcr: boolean; // Toggle to enable per-step OCR config
  // Sideload script (runs after step action)
  sideload?: SideloadConfig;
  useSideload: boolean; // Toggle to enable sideload for this step
  // Verify success (check expected screen state after action)
  useVerify: boolean;
  verifyElements: Array<{
    type: 'icon' | 'text' | 'any';
    text: string;
    textMatch: string;
    useCustomOcr: boolean;
    ocrConfig?: {
      use_paddleocr?: boolean;
      text_threshold?: number;
      box_threshold?: number;
    };
  }>;
}

// Log entry for console panel
type LogEntry = { ts: number; level: 'info' | 'warn' | 'error' | 'success'; msg: string };

// Screenshot canvas with bounding box overlay - 16:9 aspect ratio, fit-to-container zoom
function ScreenshotCanvas({
  imageUrl,
  elements,
  selectedElement,
  onElementClick,
  zoom,
  onZoomChange,
  isParsing,
}: {
  imageUrl: string | null;
  elements: BoundingBox[];
  selectedElement: BoundingBox | null;
  onElementClick: (element: BoundingBox) => void;
  zoom: number;
  onZoomChange?: (newZoom: number) => void;
  isParsing?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [parsingWord, setParsingWord] = useState('');

  // Rotate loading words while parsing
  useEffect(() => {
    if (!isParsing) { setParsingWord(''); return; }
    const pick = () => setParsingWord(PARSING_WORDS[Math.floor(Math.random() * PARSING_WORDS.length)]);
    pick();
    const id = setInterval(pick, 2000);
    return () => clearInterval(id);
  }, [isParsing]);

  // Inject AI flow animation styles once
  useEffect(() => {
    const id = 'ai-flow-styles';
    if (document.getElementById(id)) return;
    const style = document.createElement('style');
    style.id = id;
    style.textContent = `
      @keyframes ai-flow-up {
        0% { transform: translateY(0); }
        100% { transform: translateY(-50%); }
      }
    `;
    document.head.appendChild(style);
  }, []);

  // Scroll wheel zoom handler - only zoom IN from 100% (fit)
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !onZoomChange) return;

    const handleWheel = (e: WheelEvent) => {
      if (e.ctrlKey || e.metaKey) return;

      e.preventDefault();
      e.stopPropagation();

      const delta = e.deltaY > 0 ? -10 : 10;
      // Min zoom is 100% (fit to container), max is 400%
      const newZoom = Math.min(400, Math.max(100, zoom + delta));
      onZoomChange(newZoom);
    };

    container.addEventListener('wheel', handleWheel, { passive: false });
    return () => container.removeEventListener('wheel', handleWheel);
  }, [zoom, onZoomChange]);

  if (!imageUrl) {
    return (
      <div
        ref={containerRef}
        className="h-full flex items-center justify-center bg-gray-800/50 rounded border border-gray-700"
      >
        <div className="flex items-center justify-center bg-gray-900/50 rounded aspect-video w-full max-w-full">
          <div className="text-center text-gray-500">
            <div className="text-4xl mb-2">[ ]</div>
            <div className="text-sm">No screenshot</div>
            <div className="text-xs mt-1">Select a SUT and capture</div>
          </div>
        </div>
      </div>
    );
  }

  // At 100% zoom, image fits container. Above 100% = zoomed in with scrollbars
  const showScrollbars = zoom > 100;
  const showGlow = !!isParsing && !!imageUrl;

  return (
    <div className="h-full relative min-h-0">
      <div
        ref={containerRef}
        className={`relative h-full bg-gray-900 rounded border border-gray-700 ${showScrollbars ? 'overflow-auto' : 'overflow-hidden'}`}
      >
      <div
        className="relative inline-block origin-top-left"
        style={{
          transform: `scale(${zoom / 100})`,
          transformOrigin: 'top left',
        }}
      >
        <img
          src={imageUrl}
          alt="Screenshot"
          className="block max-w-none"
          style={{
            // At 100% zoom, image should fit container width while maintaining aspect ratio
            width: zoom === 100 ? '100%' : 'auto',
            height: 'auto',
          }}
          draggable={false}
        />
        {/* Bounding boxes - use percentage positioning based on image */}
        {elements.map((element, index) => {
          const isSelected = selectedElement &&
            selectedElement.x === element.x &&
            selectedElement.y === element.y;

          // Position using percentages (assuming 1920x1080 source)
          // This works because the boxes are children of the same container as the image
          const leftPct = (element.x / 1920) * 100;
          const topPct = (element.y / 1080) * 100;
          const widthPct = (element.width / 1920) * 100;
          const heightPct = (element.height / 1080) * 100;

          return (
            <button
              key={index}
              onClick={(e) => {
                e.stopPropagation();
                onElementClick(element);
              }}
              className={`absolute border-2 transition-all cursor-pointer hover:bg-blue-500/30 hover:border-blue-300 ${
                isSelected
                  ? 'border-yellow-400 bg-yellow-400/30 shadow-lg shadow-yellow-400/20 z-10'
                  : element.element_type === 'icon'
                    ? 'border-blue-400 bg-blue-400/10'
                    : 'border-emerald-400 bg-emerald-400/10'
              }`}
              style={{
                left: `${leftPct}%`,
                top: `${topPct}%`,
                width: `${widthPct}%`,
                height: `${heightPct}%`,
              }}
              title={`Click to select: ${element.element_type} - "${element.element_text}"`}
            />
          );
        })}
      </div>
      </div>
      {/* AI processing overlay — rainbow flow bottom→top, on top of screenshot */}
      <div
        className={`absolute inset-0 pointer-events-none z-20 overflow-hidden rounded transition-opacity duration-700 ${showGlow ? 'opacity-100' : 'opacity-0'}`}
      >
        <div
          className="w-full"
          style={{
            height: '200%',
            background: `linear-gradient(
              to top,
              rgba(56, 189, 248, 0.28),
              rgba(99, 102, 241, 0.30) 10%,
              rgba(139, 92, 246, 0.28) 20%,
              rgba(168, 85, 247, 0.30) 30%,
              rgba(236, 72, 153, 0.28) 40%,
              rgba(244, 114, 182, 0.26) 50%,
              rgba(251, 191, 36, 0.28) 60%,
              rgba(245, 158, 11, 0.30) 70%,
              rgba(52, 211, 153, 0.26) 80%,
              rgba(34, 197, 94, 0.28) 90%,
              rgba(56, 189, 248, 0.28)
            )`,
            animation: showGlow ? 'ai-flow-up 1.8s linear infinite' : 'none',
          }}
        />
        {/* Whimsical loading text */}
        {parsingWord && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="px-4 py-2 rounded-lg bg-black/40 backdrop-blur-sm">
              <span className="text-sm font-bold text-white tracking-wide" style={{ fontFamily: "'Intel One Display', 'Intel Clear', 'Segoe UI', system-ui, sans-serif" }}>{parsingWord}...</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Step editor form
function StepEditor({
  draft,
  selectedElement,
  onDraftChange,
  onAddStep,
  onUpdateStep,
  onCancelEdit,
  isEditing,
  editingStepIndex,
  screenshotBlob,
  isParsing,
  onReparseWithOcr,
  lastOcrTestResult,
  verifyPickMode,
  onVerifyPickModeChange,
}: {
  draft: DraftStep;
  selectedElement: BoundingBox | null;
  onDraftChange: (draft: DraftStep) => void;
  onAddStep: () => void;
  onUpdateStep: () => void;
  onCancelEdit: () => void;
  isEditing: boolean;
  editingStepIndex: number | null;
  screenshotBlob: Blob | null;
  isParsing: boolean;
  onReparseWithOcr: () => void;
  lastOcrTestResult: { found: boolean; elementCount: number } | null;
  verifyPickMode: boolean;
  onVerifyPickModeChange: (active: boolean) => void;
}) {
  const needsElement = ['find_and_click', 'double_click', 'right_click', 'drag'].includes(draft.actionType);

  return (
    <div className="space-y-4">
      {/* Action Type */}
      <div>
        <label className="block text-xs text-gray-400 uppercase tracking-wide mb-1">
          Action Type
        </label>
        <select
          value={draft.actionType}
          onChange={(e) => onDraftChange({ ...draft, actionType: e.target.value })}
          className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200"
        >
          {ACTION_TYPES.map((action) => (
            <option key={action.value} value={action.value}>
              {action.label}
            </option>
          ))}
        </select>
        <div className="text-xs text-gray-500 mt-1">
          {ACTION_TYPES.find(a => a.value === draft.actionType)?.description}
        </div>
      </div>

      {/* Element Selector (for click actions) */}
      {needsElement && (
        <div className="p-3 bg-gray-800/50 rounded-lg border border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs text-gray-400 uppercase tracking-wide">
              Target Element
            </label>
            {selectedElement && (
              <button
                onClick={() => {
                  onDraftChange({
                    ...draft,
                    element: {
                      type: selectedElement.element_type,
                      text: selectedElement.element_text,
                      textMatch: 'contains',
                    },
                    description: `Click "${selectedElement.element_text}"`,
                  });
                }}
                className="text-xs text-blue-400 hover:text-blue-300"
              >
                Use Selected
              </button>
            )}
          </div>

          {draft.element ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded text-xs ${
                  draft.element.type === 'icon' ? 'bg-blue-900/50 text-blue-400' : 'bg-emerald-900/50 text-emerald-400'
                }`}>
                  {draft.element.type}
                </span>
                <input
                  type="text"
                  value={draft.element.text}
                  onChange={(e) => onDraftChange({
                    ...draft,
                    element: { ...draft.element!, text: e.target.value },
                  })}
                  className="flex-1 bg-gray-700 border border-gray-600 rounded px-2 py-0.5 text-sm text-gray-200 font-mono min-w-0"
                />
                <button
                  onClick={() => onDraftChange({ ...draft, element: null })}
                  className="text-gray-500 hover:text-gray-400"
                >
                  x
                </button>
              </div>
              <select
                value={draft.element.textMatch}
                onChange={(e) => onDraftChange({
                  ...draft,
                  element: { ...draft.element!, textMatch: e.target.value as ElementSelector['textMatch'] },
                })}
                className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200"
              >
                {TEXT_MATCH_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
          ) : (
            <div className="text-center py-3 text-gray-500 text-xs">
              Click an element in the screenshot to select
            </div>
          )}
        </div>
      )}

      {/* Key input (for key action) */}
      {draft.actionType === 'key' && (
        <div>
          <label className="block text-xs text-gray-400 uppercase tracking-wide mb-1">
            Key
          </label>
          <select
            value={draft.key || ''}
            onChange={(e) => onDraftChange({ ...draft, key: e.target.value })}
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200"
          >
            <option value="">Select key...</option>
            {KEY_OPTIONS.map((key) => (
              <option key={key} value={key}>{key}</option>
            ))}
          </select>
        </div>
      )}

      {/* Hotkey input */}
      {draft.actionType === 'hotkey' && (
        <div>
          <label className="block text-xs text-gray-400 uppercase tracking-wide mb-1">
            Hotkey (e.g., ctrl+s, alt+f4)
          </label>
          <input
            type="text"
            value={draft.hotkey || ''}
            onChange={(e) => onDraftChange({ ...draft, hotkey: e.target.value })}
            placeholder="ctrl+s"
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200"
          />
        </div>
      )}

      {/* Text input */}
      {draft.actionType === 'text' && (
        <div>
          <label className="block text-xs text-gray-400 uppercase tracking-wide mb-1">
            Text to Type
          </label>
          <input
            type="text"
            value={draft.text || ''}
            onChange={(e) => onDraftChange({ ...draft, text: e.target.value })}
            placeholder="Enter text..."
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200"
          />
        </div>
      )}

      {/* Wait duration */}
      {draft.actionType === 'wait' && (
        <div>
          <label className="block text-xs text-gray-400 uppercase tracking-wide mb-1">
            Duration (seconds)
          </label>
          <input
            type="number"
            value={draft.duration || 1}
            onChange={(e) => onDraftChange({ ...draft, duration: Number(e.target.value) })}
            min={0.1}
            step={0.1}
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200"
          />
        </div>
      )}

      {/* Scroll options */}
      {draft.actionType === 'scroll' && (
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-xs text-gray-400 uppercase tracking-wide mb-1">
              Direction
            </label>
            <select
              value={draft.scrollDirection || 'down'}
              onChange={(e) => onDraftChange({ ...draft, scrollDirection: e.target.value as 'up' | 'down' })}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200"
            >
              <option value="down">Down</option>
              <option value="up">Up</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 uppercase tracking-wide mb-1">
              Amount
            </label>
            <input
              type="number"
              value={draft.scrollAmount || 3}
              onChange={(e) => onDraftChange({ ...draft, scrollAmount: Number(e.target.value) })}
              min={1}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200"
            />
          </div>
        </div>
      )}

      {/* Description */}
      <div>
        <label className="block text-xs text-gray-400 uppercase tracking-wide mb-1">
          Step Description
        </label>
        <input
          type="text"
          value={draft.description}
          onChange={(e) => onDraftChange({ ...draft, description: e.target.value })}
          placeholder="Describe this step..."
          className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200"
        />
      </div>

      {/* Timing */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-xs text-gray-400 uppercase tracking-wide mb-1">
            Timeout (sec)
          </label>
          <input
            type="number"
            value={draft.timeout}
            onChange={(e) => onDraftChange({ ...draft, timeout: Number(e.target.value) })}
            min={1}
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 uppercase tracking-wide mb-1">
            Delay After (sec)
          </label>
          <input
            type="number"
            value={draft.delay}
            onChange={(e) => onDraftChange({ ...draft, delay: Number(e.target.value) })}
            min={0}
            step={0.5}
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200"
          />
        </div>
      </div>

      {/* Optional */}
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={draft.optional}
          onChange={(e) => onDraftChange({ ...draft, optional: e.target.checked })}
          className="rounded border-gray-600 bg-gray-700 text-blue-500"
        />
        <span className="text-sm text-gray-300">Optional step (continue if fails)</span>
      </label>

      {/* Verify Success (check expected screen state after action) */}
      <div className="p-2 bg-gray-800/30 rounded border border-gray-700">
        <label className="flex items-center gap-2 cursor-pointer mb-2">
          <input
            type="checkbox"
            checked={draft.useVerify}
            onChange={(e) => {
              if (!e.target.checked) onVerifyPickModeChange(false);
              onDraftChange({
                ...draft,
                useVerify: e.target.checked,
                verifyElements: e.target.checked ? draft.verifyElements : [],
              });
            }}
            className="rounded border-gray-600 bg-gray-700 text-cyan-500"
          />
          <span className="text-xs text-gray-400">Verify after action (check expected screen state)</span>
        </label>

        {draft.useVerify && (
          <div className="space-y-2 pl-4 border-l-2 border-cyan-500/30">
            {draft.verifyElements.map((ve, idx) => (
              <div key={idx} className="space-y-0">
                <div className="flex items-center gap-2 p-1.5 bg-gray-800/50 rounded border border-gray-700">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] flex-shrink-0 ${
                    ve.type === 'icon' ? 'bg-blue-900/50 text-blue-400' : ve.type === 'text' ? 'bg-emerald-900/50 text-emerald-400' : 'bg-gray-700 text-gray-400'
                  }`}>
                    {ve.type}
                  </span>
                  <input
                    type="text"
                    value={ve.text}
                    onChange={(e) => {
                      const updated = [...draft.verifyElements];
                      updated[idx] = { ...updated[idx], text: e.target.value };
                      onDraftChange({ ...draft, verifyElements: updated });
                    }}
                    className="flex-1 bg-gray-700 border border-gray-600 rounded px-2 py-0.5 text-xs text-gray-200 font-mono min-w-0"
                  />
                  <select
                    value={ve.textMatch}
                    onChange={(e) => {
                      const updated = [...draft.verifyElements];
                      updated[idx] = { ...updated[idx], textMatch: e.target.value };
                      onDraftChange({ ...draft, verifyElements: updated });
                    }}
                    className="bg-gray-700 border border-gray-600 rounded px-1 py-0.5 text-[10px] text-gray-200"
                  >
                    {TEXT_MATCH_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                  <button
                    onClick={() => {
                      const updated = [...draft.verifyElements];
                      updated[idx] = { ...updated[idx], useCustomOcr: !ve.useCustomOcr, ocrConfig: !ve.useCustomOcr ? { use_paddleocr: true, text_threshold: 0.1, box_threshold: 0.05 } : undefined };
                      onDraftChange({ ...draft, verifyElements: updated });
                    }}
                    className={`text-xs flex-shrink-0 px-1 py-0.5 rounded transition-colors ${
                      ve.useCustomOcr ? 'bg-cyan-600/30 text-cyan-400 border border-cyan-500/50' : 'text-gray-500 hover:text-cyan-400'
                    }`}
                    title="Per-verify OCR config"
                  >
                    ⚙
                  </button>
                  <button
                    onClick={() => {
                      const updated = draft.verifyElements.filter((_, i) => i !== idx);
                      onDraftChange({ ...draft, verifyElements: updated });
                    }}
                    className="text-red-500 hover:text-red-400 text-xs flex-shrink-0"
                  >
                    x
                  </button>
                </div>
                {ve.useCustomOcr && ve.ocrConfig && (
                  <div className="ml-4 mt-1 p-2 bg-gray-800/60 rounded border border-cyan-500/20 space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[10px] text-gray-500 uppercase tracking-wide mb-0.5">Text Threshold</label>
                        <input
                          type="number"
                          value={ve.ocrConfig.text_threshold ?? 0.1}
                          onChange={(e) => {
                            const updated = [...draft.verifyElements];
                            updated[idx] = { ...updated[idx], ocrConfig: { ...updated[idx].ocrConfig!, text_threshold: Number(e.target.value) } };
                            onDraftChange({ ...draft, verifyElements: updated });
                          }}
                          min={0}
                          max={1}
                          step={0.1}
                          className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] text-gray-500 uppercase tracking-wide mb-0.5">Box Threshold</label>
                        <input
                          type="number"
                          value={ve.ocrConfig.box_threshold ?? 0.05}
                          onChange={(e) => {
                            const updated = [...draft.verifyElements];
                            updated[idx] = { ...updated[idx], ocrConfig: { ...updated[idx].ocrConfig!, box_threshold: Number(e.target.value) } };
                            onDraftChange({ ...draft, verifyElements: updated });
                          }}
                          min={0}
                          max={1}
                          step={0.01}
                          className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200"
                        />
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="radio"
                          name={`verify-ocr-engine-${idx}`}
                          checked={ve.ocrConfig.use_paddleocr !== false}
                          onChange={() => {
                            const updated = [...draft.verifyElements];
                            updated[idx] = { ...updated[idx], ocrConfig: { ...updated[idx].ocrConfig!, use_paddleocr: true } };
                            onDraftChange({ ...draft, verifyElements: updated });
                          }}
                          className="text-cyan-500"
                        />
                        <span className="text-[10px] text-gray-400">PaddleOCR</span>
                      </label>
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="radio"
                          name={`verify-ocr-engine-${idx}`}
                          checked={ve.ocrConfig.use_paddleocr === false}
                          onChange={() => {
                            const updated = [...draft.verifyElements];
                            updated[idx] = { ...updated[idx], ocrConfig: { ...updated[idx].ocrConfig!, use_paddleocr: false } };
                            onDraftChange({ ...draft, verifyElements: updated });
                          }}
                          className="text-cyan-500"
                        />
                        <span className="text-[10px] text-gray-400">EasyOCR</span>
                      </label>
                    </div>
                  </div>
                )}
              </div>
            ))}
            <button
              onClick={() => onVerifyPickModeChange(!verifyPickMode)}
              className={`w-full px-2 py-1 text-xs rounded flex items-center justify-center gap-1 transition-colors ${
                verifyPickMode
                  ? 'bg-cyan-600 text-white border border-cyan-400 animate-pulse'
                  : 'bg-cyan-600/20 hover:bg-cyan-600/30 border border-cyan-500/30 text-cyan-400'
              }`}
            >
              {verifyPickMode ? 'Click an element on the screenshot...' : '+ Pick from Screenshot'}
            </button>
          </div>
        )}
      </div>

      {/* Per-Step OCR Config (only for click actions that need element detection) */}
      {needsElement && (
        <div className="p-2 bg-gray-800/30 rounded border border-gray-700">
          <label className="flex items-center gap-2 cursor-pointer mb-2">
            <input
              type="checkbox"
              checked={draft.useCustomOcr}
              onChange={(e) => onDraftChange({
                ...draft,
                useCustomOcr: e.target.checked,
                ocrConfig: e.target.checked ? { use_paddleocr: true, text_threshold: 0.5, box_threshold: 0.05 } : undefined
              })}
              className="rounded border-gray-600 bg-gray-700 text-purple-500"
            />
            <span className="text-xs text-gray-400">Custom OCR settings for this step</span>
          </label>

          {draft.useCustomOcr && draft.ocrConfig && (
            <div className="space-y-2 pl-4 border-l-2 border-purple-500/30">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] text-gray-500 uppercase tracking-wide mb-0.5">Text Threshold</label>
                  <input
                    type="number"
                    value={draft.ocrConfig.text_threshold ?? 0.5}
                    onChange={(e) => onDraftChange({
                      ...draft,
                      ocrConfig: { ...draft.ocrConfig!, text_threshold: Number(e.target.value) }
                    })}
                    min={0}
                    max={1}
                    step={0.1}
                    className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-gray-500 uppercase tracking-wide mb-0.5">Box Threshold</label>
                  <input
                    type="number"
                    value={draft.ocrConfig.box_threshold ?? 0.05}
                    onChange={(e) => onDraftChange({
                      ...draft,
                      ocrConfig: { ...draft.ocrConfig!, box_threshold: Number(e.target.value) }
                    })}
                    min={0}
                    max={1}
                    step={0.01}
                    className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200"
                  />
                </div>
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={draft.ocrConfig.use_paddleocr ?? true}
                  onChange={(e) => onDraftChange({
                    ...draft,
                    ocrConfig: { ...draft.ocrConfig!, use_paddleocr: e.target.checked }
                  })}
                  className="rounded border-gray-600 bg-gray-700 text-purple-500"
                />
                <span className="text-[10px] text-gray-500">PaddleOCR (uncheck for EasyOCR)</span>
              </label>

              {/* Re-parse with custom OCR settings button */}
              <button
                onClick={onReparseWithOcr}
                disabled={!screenshotBlob || isParsing}
                className="w-full mt-2 px-3 py-1.5 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white text-xs font-medium rounded flex items-center justify-center gap-2 transition-colors"
              >
                {isParsing ? (
                  <>
                    <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Parsing...
                  </>
                ) : (
                  <>
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Re-parse with these settings
                  </>
                )}
              </button>

              {/* OCR test result feedback */}
              {lastOcrTestResult && (
                <div className={`mt-2 text-xs p-2 rounded ${lastOcrTestResult.found ? 'bg-emerald-900/30 text-emerald-300 border border-emerald-500/30' : 'bg-amber-900/30 text-amber-300 border border-amber-500/30'}`}>
                  {lastOcrTestResult.found ? (
                    <>✓ Found "{draft.element?.text}" - {lastOcrTestResult.elementCount} elements detected</>
                  ) : (
                    <>✗ "{draft.element?.text || 'target'}" not found - {lastOcrTestResult.elementCount} elements detected</>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Sideload Script (runs after step action) */}
      <div className="p-2 bg-gray-800/30 rounded border border-gray-700">
        <label className="flex items-center gap-2 cursor-pointer mb-2">
          <input
            type="checkbox"
            checked={draft.useSideload}
            onChange={(e) => onDraftChange({
              ...draft,
              useSideload: e.target.checked,
              sideload: e.target.checked ? { path: '', timeout: 60, wait_for_completion: true } : undefined
            })}
            className="rounded border-gray-600 bg-gray-700 text-amber-500"
          />
          <span className="text-xs text-gray-400">Sideload script (run after this step)</span>
        </label>

        {draft.useSideload && draft.sideload && (
          <div className="space-y-2 pl-4 border-l-2 border-amber-500/30">
            <div>
              <label className="block text-[10px] text-gray-500 uppercase tracking-wide mb-0.5">Script Path</label>
              <input
                type="text"
                value={draft.sideload.path}
                onChange={(e) => onDraftChange({
                  ...draft,
                  sideload: { ...draft.sideload!, path: e.target.value }
                })}
                placeholder="C:\Scripts\monitor.ps1"
                className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[10px] text-gray-500 uppercase tracking-wide mb-0.5">Arguments</label>
                <input
                  type="text"
                  value={draft.sideload.args?.join(' ') ?? ''}
                  onChange={(e) => onDraftChange({
                    ...draft,
                    sideload: { ...draft.sideload!, args: e.target.value ? e.target.value.split(' ') : undefined }
                  })}
                  placeholder="-interval 1"
                  className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200"
                />
              </div>
              <div>
                <label className="block text-[10px] text-gray-500 uppercase tracking-wide mb-0.5">Timeout (sec)</label>
                <input
                  type="number"
                  value={draft.sideload.timeout ?? 60}
                  onChange={(e) => onDraftChange({
                    ...draft,
                    sideload: { ...draft.sideload!, timeout: Number(e.target.value) }
                  })}
                  min={1}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200"
                />
              </div>
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={draft.sideload.wait_for_completion ?? true}
                onChange={(e) => onDraftChange({
                  ...draft,
                  sideload: { ...draft.sideload!, wait_for_completion: e.target.checked }
                })}
                className="rounded border-gray-600 bg-gray-700 text-amber-500"
              />
              <span className="text-[10px] text-gray-500">Wait for script completion</span>
            </label>
          </div>
        )}
      </div>

      {/* Editing indicator */}
      {isEditing && (
        <div className="flex items-center gap-2 px-2 py-1.5 bg-blue-900/30 rounded border border-blue-500/50">
          <span className="text-xs text-blue-300">
            Editing Step {editingStepIndex !== null ? editingStepIndex + 1 : ''}
          </span>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-2">
        {isEditing ? (
          <>
            <button
              onClick={onCancelEdit}
              className="px-3 py-2 bg-gray-600 hover:bg-gray-500 text-white text-sm font-medium rounded transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={onUpdateStep}
              className="flex-1 px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded transition-colors"
            >
              Update Step
            </button>
          </>
        ) : (
          <button
            onClick={onAddStep}
            className="w-full px-3 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded transition-colors"
          >
            Add to Workflow
          </button>
        )}
      </div>
    </div>
  );
}

// Workflow steps list
function StepsList({
  steps,
  selectedIndex,
  onSelect,
  onRemove,
  onMoveUp,
  onMoveDown,
  onTest,
  onRunFlow,
  onClear,
  isTestingStep,
  isRunningFlow,
}: {
  steps: WorkflowStep[];
  selectedIndex: number | null;
  onSelect: (index: number | null) => void;
  onRemove: (index: number) => void;
  onMoveUp: (index: number) => void;
  onMoveDown: (index: number) => void;
  onTest: (index: number) => void;
  onRunFlow: () => void;
  onClear: () => void;
  isTestingStep: number | null;
  isRunningFlow: boolean;
}) {
  return (
    <div className="flex flex-col h-full">
      {/* Header with Flow and Clear buttons */}
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-gray-300">
          Workflow Steps ({steps.length})
        </h3>
        <div className="flex items-center gap-1">
          {steps.length > 0 && (
            <>
              <button
                onClick={onRunFlow}
                disabled={isRunningFlow || steps.length === 0}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium rounded transition-colors"
                title="Run all steps"
              >
                {isRunningFlow ? (
                  <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <Workflow className="w-3 h-3" />
                )}
                Flow
              </button>
              <button
                onClick={onClear}
                className="px-2 py-1 text-xs text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded transition-colors"
              >
                Clear All
              </button>
            </>
          )}
        </div>
      </div>

      {/* Steps list */}
      {steps.length === 0 ? (
        <div className="text-center py-8 text-gray-500 text-sm flex-1">
          No steps added yet
        </div>
      ) : (
        <div className="space-y-2 flex-1 overflow-y-auto">
      {steps.map((step, index) => {
        const isSelected = selectedIndex === index;
        const isTesting = isTestingStep === index;

        return (
          <div
            key={index}
            onClick={() => onSelect(isSelected ? null : index)}
            className={`flex items-center gap-2 p-2 rounded-lg border cursor-pointer transition-colors ${
              isSelected
                ? 'bg-blue-900/30 border-blue-500'
                : 'bg-gray-800/50 border-gray-700 hover:border-gray-600'
            }`}
          >
            <span className={`w-6 h-6 flex items-center justify-center rounded text-xs ${
              isSelected ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-400'
            }`}>
              {index + 1}
            </span>
            <div className="flex-1 min-w-0">
              <div className={`text-sm truncate ${isSelected ? 'text-blue-200' : 'text-gray-200'}`}>
                {step.description || `Step ${index + 1}`}
              </div>
              <div className="text-xs text-gray-500 flex items-center gap-1">
                <span>{step.action_type}</span>
                {step.optional && <span>(optional)</span>}
                {step.find?.text && <span className="truncate">{`→ "${step.find.text}"`}</span>}
                {step.verify_success && step.verify_success.length > 0 && (
                  <span className="px-1 py-0 rounded bg-cyan-900/40 text-cyan-400 text-[10px]" title={`Verify: ${step.verify_success.map(v => v.text).join(', ')}`}>
                    verify
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-0.5" onClick={(e) => e.stopPropagation()}>
              {/* Play button */}
              <button
                onClick={() => onTest(index)}
                disabled={isTesting}
                className="p-1.5 rounded hover:bg-amber-500/20 text-amber-500 hover:text-amber-400 disabled:opacity-50 transition-colors"
                title="Run this step"
              >
                {isTesting ? (
                  <span className="w-4 h-4 border-2 border-amber-500/30 border-t-amber-500 rounded-full animate-spin block" />
                ) : (
                  <Play className="w-4 h-4 fill-current" />
                )}
              </button>
              <button
                onClick={() => onMoveUp(index)}
                disabled={index === 0}
                className="p-1 text-gray-500 hover:text-gray-300 disabled:opacity-30"
                title="Move up"
              >
                ↑
              </button>
              <button
                onClick={() => onMoveDown(index)}
                disabled={index === steps.length - 1}
                className="p-1 text-gray-500 hover:text-gray-300 disabled:opacity-30"
                title="Move down"
              >
                ↓
              </button>
              <button
                onClick={() => onRemove(index)}
                className="p-1 text-red-500 hover:text-red-400"
                title="Remove step"
              >
                ×
              </button>
            </div>
          </div>
        );
      })}
        </div>
      )}
    </div>
  );
}

// Game metadata panel - organized in sections
function MetadataPanel({
  metadata,
  onChange,
}: {
  metadata: GameMetadata;
  onChange: (metadata: GameMetadata) => void;
}) {
  const inputClass = "w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-xs text-gray-200";
  const labelClass = "block text-[10px] text-gray-500 uppercase tracking-wide mb-0.5";

  // Fetch available tracing agents from API
  const [wfTracingAgents, setWfTracingAgents] = useState<{ id: string; label: string }[]>([]);
  useEffect(() => {
    fetch('/api/tracing/config')
      .then(res => res.json())
      .then(data => {
        const agents = data.config?.agents ?? {};
        setWfTracingAgents(Object.entries(agents).map(([id, _agent]: [string, any]) => ({
          id,
          label: id === 'socwatch' ? 'SOCWatch' : id === 'ptat' ? 'Intel PTAT' : id.charAt(0).toUpperCase() + id.slice(1),
        })));
      })
      .catch(() => {
        setWfTracingAgents([
          { id: 'socwatch', label: 'SOCWatch' },
          { id: 'ptat', label: 'Intel PTAT' },
          { id: 'presentmon', label: 'PresentMon' },
        ]);
      });
  }, []);

  return (
    <div className="space-y-4">
      {/* Basic Info */}
      <div className="space-y-2">
        <h4 className="text-xs font-medium text-gray-400 border-b border-gray-700 pb-1">Basic Info</h4>
        <div>
          <label className={labelClass}>Game Name *</label>
          <input
            type="text"
            value={metadata.game_name}
            onChange={(e) => onChange({ ...metadata, game_name: e.target.value })}
            placeholder="e.g., HITMAN 3"
            className={inputClass}
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className={labelClass}>Steam App ID *</label>
            <input
              type="text"
              value={metadata.steam_app_id}
              onChange={(e) => onChange({ ...metadata, steam_app_id: e.target.value })}
              placeholder="e.g., 1847520"
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Preset ID</label>
            <input
              type="text"
              value={metadata.preset_id}
              onChange={(e) => onChange({ ...metadata, preset_id: e.target.value })}
              placeholder="e.g., hitman-3-dubai"
              className={inputClass}
            />
          </div>
        </div>
        <div>
          <label className={labelClass}>Launch Method</label>
          <select
            value={metadata.launch_method}
            onChange={(e) => onChange({ ...metadata, launch_method: e.target.value as 'steam' | 'exe' })}
            className={inputClass}
          >
            <option value="steam">Steam (Default)</option>
            <option value="exe">Direct Executable</option>
          </select>
        </div>
      </div>

      {/* Process Info */}
      <div className="space-y-2">
        <h4 className="text-xs font-medium text-gray-400 border-b border-gray-700 pb-1">Process Info</h4>
        <div>
          <label className={labelClass}>Executable Path</label>
          <input
            type="text"
            value={metadata.path}
            onChange={(e) => onChange({ ...metadata, path: e.target.value })}
            placeholder="e.g., D:\Games\...\Game.exe"
            className={inputClass}
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className={labelClass}>Process ID *</label>
            <input
              type="text"
              value={metadata.process_id}
              onChange={(e) => onChange({ ...metadata, process_id: e.target.value })}
              placeholder="e.g., HITMAN3"
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Process Name</label>
            <input
              type="text"
              value={metadata.process_name}
              onChange={(e) => onChange({ ...metadata, process_name: e.target.value })}
              placeholder="e.g., HITMAN3.exe"
              className={inputClass}
            />
          </div>
        </div>
        <div>
          <label className={labelClass}>Game Process (if launcher)</label>
          <input
            type="text"
            value={metadata.game_process}
            onChange={(e) => onChange({ ...metadata, game_process: e.target.value })}
            placeholder="Actual game process after launcher"
            className={inputClass}
          />
        </div>
      </div>

      {/* Timing */}
      <div className="space-y-2">
        <h4 className="text-xs font-medium text-gray-400 border-b border-gray-700 pb-1">Timing</h4>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className={labelClass}>Startup Wait (sec)</label>
            <input
              type="number"
              value={metadata.startup_wait}
              onChange={(e) => onChange({ ...metadata, startup_wait: Number(e.target.value) })}
              min={0}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Benchmark Duration (sec)</label>
            <input
              type="number"
              value={metadata.benchmark_duration}
              onChange={(e) => onChange({ ...metadata, benchmark_duration: Number(e.target.value) })}
              min={0}
              className={inputClass}
            />
          </div>
        </div>
        <div>
          <label className={labelClass}>Benchmark Name</label>
          <input
            type="text"
            value={metadata.benchmark_name}
            onChange={(e) => onChange({ ...metadata, benchmark_name: e.target.value })}
            placeholder="e.g., Built-in Benchmark - Dubai"
            className={inputClass}
          />
        </div>
      </div>

      {/* OCR Config */}
      <div className="space-y-2">
        <h4 className="text-xs font-medium text-gray-400 border-b border-gray-700 pb-1">OCR Config</h4>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className={labelClass}>Text Threshold</label>
            <input
              type="number"
              value={metadata.ocr_config.text_threshold}
              onChange={(e) => onChange({
                ...metadata,
                ocr_config: { ...metadata.ocr_config, text_threshold: Number(e.target.value) }
              })}
              min={0}
              max={1}
              step={0.1}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Box Threshold</label>
            <input
              type="number"
              value={metadata.ocr_config.box_threshold}
              onChange={(e) => onChange({
                ...metadata,
                ocr_config: { ...metadata.ocr_config, box_threshold: Number(e.target.value) }
              })}
              min={0}
              max={1}
              step={0.01}
              className={inputClass}
            />
          </div>
        </div>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={metadata.ocr_config.use_paddleocr}
            onChange={(e) => onChange({
              ...metadata,
              ocr_config: { ...metadata.ocr_config, use_paddleocr: e.target.checked }
            })}
            className="rounded border-gray-600 bg-gray-700 text-blue-500"
          />
          <span className="text-xs text-gray-400">Use PaddleOCR (uncheck for EasyOCR - better for stylized fonts)</span>
        </label>
      </div>

      {/* Tracing Config */}
      <div className="space-y-2">
        <h4 className="text-xs font-medium text-gray-400 border-b border-gray-700 pb-1">
          Tracing
          {wfTracingAgents.length > 0 && (
            <span className="ml-2 text-[10px] text-emerald-400/70">({wfTracingAgents.map(a => a.label).join(' + ')})</span>
          )}
        </h4>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={metadata.tracing?.enabled ?? false}
            onChange={(e) => onChange({
              ...metadata,
              tracing: {
                ...metadata.tracing,
                enabled: e.target.checked,
                agents: metadata.tracing?.agents ?? wfTracingAgents.map(a => a.id),
              }
            })}
            className="rounded border-gray-600 bg-gray-700 text-emerald-500"
          />
          <span className="text-xs text-gray-400">Enable tracing on benchmark steps (wait ≥30s)</span>
        </label>
        {metadata.tracing?.enabled && (
          <div className="pl-4 border-l-2 border-emerald-500/30 space-y-2">
            <div className="flex items-center gap-3 flex-wrap">
              {wfTracingAgents.map(agent => (
                <label key={agent.id} className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={metadata.tracing?.agents?.includes(agent.id) ?? true}
                    onChange={(e) => {
                      const agents = metadata.tracing?.agents ?? [];
                      onChange({
                        ...metadata,
                        tracing: {
                          ...metadata.tracing!,
                          agents: e.target.checked
                            ? [...agents.filter(a => a !== agent.id), agent.id]
                            : agents.filter(a => a !== agent.id)
                        }
                      });
                    }}
                    className="rounded border-gray-600 bg-gray-700 text-emerald-500"
                  />
                  <span className="text-[11px] text-gray-400">{agent.label}</span>
                </label>
              ))}
            </div>
            <div>
              <label className={labelClass}>Output Directory (on SUT)</label>
              <input
                type="text"
                value={metadata.tracing?.output_dir ?? ''}
                onChange={(e) => onChange({
                  ...metadata,
                  tracing: { ...metadata.tracing!, output_dir: e.target.value || undefined }
                })}
                placeholder="C:\Traces\{run_id}"
                className={inputClass}
              />
            </div>
          </div>
        )}
      </div>

      {/* Hooks Config */}
      <details className="group">
        <summary className="text-xs font-medium text-gray-400 cursor-pointer hover:text-gray-300 flex items-center gap-1">
          <svg className="w-3 h-3 transition-transform group-open:rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          Hooks
          <span className="ml-1 text-[10px] text-purple-400/70">(pre/post scripts)</span>
        </summary>
        <div className="mt-2 space-y-3 pl-4 border-l border-gray-700">
          {/* Pre-hooks */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className={labelClass}>Pre-Hooks (run before automation)</label>
              <button
                onClick={() => {
                  const preHooks = metadata.hooks?.pre ?? [];
                  onChange({
                    ...metadata,
                    hooks: {
                      ...metadata.hooks,
                      pre: [...preHooks, { path: '', args: [], timeout: 30, persistent: false }]
                    }
                  });
                }}
                className="text-[10px] text-purple-400 hover:text-purple-300"
              >
                + Add Hook
              </button>
            </div>
            {(metadata.hooks?.pre ?? []).map((hook, idx) => (
              <div key={idx} className="p-2 bg-gray-800/50 rounded border border-gray-700 space-y-1.5">
                <div className="flex items-center gap-1">
                  <input
                    type="text"
                    value={hook.path}
                    onChange={(e) => {
                      const preHooks = [...(metadata.hooks?.pre ?? [])];
                      preHooks[idx] = { ...preHooks[idx], path: e.target.value };
                      onChange({ ...metadata, hooks: { ...metadata.hooks, pre: preHooks } });
                    }}
                    placeholder="C:\Scripts\setup.bat"
                    className={`${inputClass} flex-1`}
                  />
                  <button
                    onClick={() => {
                      const preHooks = (metadata.hooks?.pre ?? []).filter((_, i) => i !== idx);
                      onChange({ ...metadata, hooks: { ...metadata.hooks, pre: preHooks.length > 0 ? preHooks : undefined } });
                    }}
                    className="px-1.5 text-red-400 hover:text-red-300"
                  >
                    ×
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={hook.args?.join(' ') ?? ''}
                    onChange={(e) => {
                      const preHooks = [...(metadata.hooks?.pre ?? [])];
                      preHooks[idx] = { ...preHooks[idx], args: e.target.value ? e.target.value.split(' ') : [] };
                      onChange({ ...metadata, hooks: { ...metadata.hooks, pre: preHooks } });
                    }}
                    placeholder="--arg1 value"
                    className={`${inputClass} flex-1`}
                  />
                  <input
                    type="number"
                    value={hook.timeout ?? 30}
                    onChange={(e) => {
                      const preHooks = [...(metadata.hooks?.pre ?? [])];
                      preHooks[idx] = { ...preHooks[idx], timeout: Number(e.target.value) };
                      onChange({ ...metadata, hooks: { ...metadata.hooks, pre: preHooks } });
                    }}
                    className={`${inputClass} w-16`}
                    title="Timeout (sec)"
                  />
                </div>
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-1 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={hook.persistent ?? false}
                      onChange={(e) => {
                        const preHooks = [...(metadata.hooks?.pre ?? [])];
                        preHooks[idx] = { ...preHooks[idx], persistent: e.target.checked };
                        onChange({ ...metadata, hooks: { ...metadata.hooks, pre: preHooks } });
                      }}
                      className="rounded border-gray-600 bg-gray-700 text-purple-500"
                    />
                    <span className="text-[10px] text-gray-500">Persistent</span>
                  </label>
                  <label className="flex items-center gap-1 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={hook.critical ?? false}
                      onChange={(e) => {
                        const preHooks = [...(metadata.hooks?.pre ?? [])];
                        preHooks[idx] = { ...preHooks[idx], critical: e.target.checked };
                        onChange({ ...metadata, hooks: { ...metadata.hooks, pre: preHooks } });
                      }}
                      className="rounded border-gray-600 bg-gray-700 text-red-500"
                    />
                    <span className="text-[10px] text-gray-500">Critical</span>
                  </label>
                </div>
              </div>
            ))}
          </div>

          {/* Post-hooks */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className={labelClass}>Post-Hooks (run after automation)</label>
              <button
                onClick={() => {
                  const postHooks = metadata.hooks?.post ?? [];
                  onChange({
                    ...metadata,
                    hooks: {
                      ...metadata.hooks,
                      post: [...postHooks, { path: '', args: [], timeout: 60 }]
                    }
                  });
                }}
                className="text-[10px] text-purple-400 hover:text-purple-300"
              >
                + Add Hook
              </button>
            </div>
            {(metadata.hooks?.post ?? []).map((hook, idx) => (
              <div key={idx} className="p-2 bg-gray-800/50 rounded border border-gray-700 space-y-1.5">
                <div className="flex items-center gap-1">
                  <input
                    type="text"
                    value={hook.path}
                    onChange={(e) => {
                      const postHooks = [...(metadata.hooks?.post ?? [])];
                      postHooks[idx] = { ...postHooks[idx], path: e.target.value };
                      onChange({ ...metadata, hooks: { ...metadata.hooks, post: postHooks } });
                    }}
                    placeholder="C:\Scripts\collect_results.py"
                    className={`${inputClass} flex-1`}
                  />
                  <button
                    onClick={() => {
                      const postHooks = (metadata.hooks?.post ?? []).filter((_, i) => i !== idx);
                      onChange({ ...metadata, hooks: { ...metadata.hooks, post: postHooks.length > 0 ? postHooks : undefined } });
                    }}
                    className="px-1.5 text-red-400 hover:text-red-300"
                  >
                    ×
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={hook.args?.join(' ') ?? ''}
                    onChange={(e) => {
                      const postHooks = [...(metadata.hooks?.post ?? [])];
                      postHooks[idx] = { ...postHooks[idx], args: e.target.value ? e.target.value.split(' ') : [] };
                      onChange({ ...metadata, hooks: { ...metadata.hooks, post: postHooks } });
                    }}
                    placeholder="--arg1 value"
                    className={`${inputClass} flex-1`}
                  />
                  <input
                    type="number"
                    value={hook.timeout ?? 60}
                    onChange={(e) => {
                      const postHooks = [...(metadata.hooks?.post ?? [])];
                      postHooks[idx] = { ...postHooks[idx], timeout: Number(e.target.value) };
                      onChange({ ...metadata, hooks: { ...metadata.hooks, post: postHooks } });
                    }}
                    className={`${inputClass} w-16`}
                    title="Timeout (sec)"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </details>

      {/* Technical */}
      <details className="group">
        <summary className="text-xs font-medium text-gray-400 cursor-pointer hover:text-gray-300 flex items-center gap-1">
          <svg className="w-3 h-3 transition-transform group-open:rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          Technical (Optional)
        </summary>
        <div className="mt-2 space-y-2 pl-4 border-l border-gray-700">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className={labelClass}>Engine</label>
              <input
                type="text"
                value={metadata.engine}
                onChange={(e) => onChange({ ...metadata, engine: e.target.value })}
                placeholder="e.g., Glacier 2"
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Graphics API</label>
              <input
                type="text"
                value={metadata.graphics_api}
                onChange={(e) => onChange({ ...metadata, graphics_api: e.target.value })}
                placeholder="e.g., DirectX 12"
                className={inputClass}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className={labelClass}>Version</label>
              <input
                type="text"
                value={metadata.version}
                onChange={(e) => onChange({ ...metadata, version: e.target.value })}
                placeholder="1.0"
                className={inputClass}
              />
            </div>
            <label className="flex items-center gap-2 cursor-pointer pt-4">
              <input
                type="checkbox"
                checked={metadata.use_ocr_fallback}
                onChange={(e) => onChange({ ...metadata, use_ocr_fallback: e.target.checked })}
                className="rounded border-gray-600 bg-gray-700 text-blue-500"
              />
              <span className="text-xs text-gray-400">OCR Fallback</span>
            </label>
          </div>
        </div>
      </details>
    </div>
  );
}

// Bottom panel with Elements and Console tabs
function BottomPanel({
  elements,
  selectedElement,
  onElementClick,
  logs,
  onClearLogs,
}: {
  elements: BoundingBox[];
  selectedElement: BoundingBox | null;
  onElementClick: (element: BoundingBox) => void;
  logs: LogEntry[];
  onClearLogs: () => void;
}) {
  const [activeTab, setActiveTab] = useState<'elements' | 'console'>('elements');
  const [filter, setFilter] = useState('');
  const [lastSeenLogCount, setLastSeenLogCount] = useState(0);
  const consoleEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll console
  useEffect(() => {
    if (activeTab === 'console' && consoleEndRef.current) {
      consoleEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, activeTab]);

  // Track unread logs
  useEffect(() => {
    if (activeTab === 'console') {
      setLastSeenLogCount(logs.length);
    }
  }, [activeTab, logs.length]);

  const unreadCount = activeTab !== 'console' ? logs.length - lastSeenLogCount : 0;

  const filteredElements = filter
    ? elements.filter(el => el.element_text.toLowerCase().includes(filter.toLowerCase()))
    : elements;

  return (
    <div className="flex-[2] flex flex-col bg-gray-800/30 rounded border border-gray-700 min-h-0 mt-2">
      {/* Tab bar */}
      <div className="flex items-center gap-1 px-2 pt-1.5 pb-1 border-b border-gray-700 flex-shrink-0">
        <button
          onClick={() => setActiveTab('elements')}
          className={`px-2.5 py-1 text-xs rounded-full transition-colors ${
            activeTab === 'elements'
              ? 'bg-blue-600 text-white'
              : 'text-gray-400 hover:text-gray-300 hover:bg-gray-700/50'
          }`}
        >
          Elements{elements.length > 0 && <span className="ml-1 opacity-70">({elements.length})</span>}
        </button>
        <button
          onClick={() => setActiveTab('console')}
          className={`px-2.5 py-1 text-xs rounded-full transition-colors flex items-center gap-1 ${
            activeTab === 'console'
              ? 'bg-blue-600 text-white'
              : 'text-gray-400 hover:text-gray-300 hover:bg-gray-700/50'
          }`}
        >
          Console
          {unreadCount > 0 && (
            <span className="px-1.5 py-0.5 text-[10px] bg-amber-500 text-white rounded-full min-w-[18px] text-center leading-none">
              {unreadCount}
            </span>
          )}
        </button>
        {activeTab === 'console' && logs.length > 0 && (
          <button
            onClick={onClearLogs}
            className="ml-auto text-[10px] text-gray-500 hover:text-gray-400"
          >
            Clear
          </button>
        )}
      </div>

      {/* Tab content */}
      {activeTab === 'elements' ? (
        <div className="flex-1 flex flex-col min-h-0">
          {/* Filter */}
          <div className="px-2 py-1 flex-shrink-0">
            <input
              type="text"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter elements..."
              className="w-full bg-gray-700/50 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 placeholder-gray-500"
            />
          </div>
          {/* Table */}
          <div className="flex-1 overflow-y-auto min-h-0">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-gray-800/90">
                <tr className="text-gray-500 text-left">
                  <th className="px-2 py-1 w-8">#</th>
                  <th className="px-2 py-1 w-14">Type</th>
                  <th className="px-2 py-1">Text</th>
                  <th className="px-2 py-1 w-14 text-right">Conf</th>
                  <th className="px-2 py-1 w-24 text-right">Position</th>
                </tr>
              </thead>
              <tbody>
                {filteredElements.map((el, idx) => {
                  const isSelected = selectedElement &&
                    selectedElement.x === el.x &&
                    selectedElement.y === el.y;
                  return (
                    <tr
                      key={idx}
                      onClick={() => onElementClick(el)}
                      className={`cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-yellow-400/20 text-yellow-200'
                          : 'hover:bg-gray-700/50 text-gray-300'
                      }`}
                    >
                      <td className="px-2 py-1 text-gray-500">{idx + 1}</td>
                      <td className="px-2 py-1">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                          el.element_type === 'icon'
                            ? 'bg-blue-900/50 text-blue-400'
                            : 'bg-emerald-900/50 text-emerald-400'
                        }`}>
                          {el.element_type}
                        </span>
                      </td>
                      <td className="px-2 py-1 truncate max-w-[200px] font-mono">{el.element_text}</td>
                      <td className="px-2 py-1 text-right text-gray-500">
                        {el.confidence != null ? `${(el.confidence * 100).toFixed(0)}%` : '-'}
                      </td>
                      <td className="px-2 py-1 text-right text-gray-500 font-mono text-[10px]">
                        {el.x},{el.y}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {filteredElements.length === 0 && (
              <div className="text-center py-4 text-gray-500 text-xs">
                {elements.length === 0 ? 'No elements detected' : 'No matches'}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto min-h-0 px-2 py-1 font-mono text-xs space-y-0.5">
          {logs.length === 0 ? (
            <div className="text-center py-4 text-gray-500">No log entries</div>
          ) : (
            logs.map((entry, idx) => {
              const time = new Date(entry.ts).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
              const levelColors: Record<string, string> = {
                info: 'text-gray-400 bg-gray-700/50',
                success: 'text-emerald-400 bg-emerald-900/30',
                warn: 'text-amber-400 bg-amber-900/30',
                error: 'text-red-400 bg-red-900/30',
              };
              return (
                <div key={idx} className="flex items-start gap-2 py-0.5">
                  <span className="text-gray-600 flex-shrink-0">{time}</span>
                  <span className={`px-1 rounded text-[10px] flex-shrink-0 ${levelColors[entry.level]}`}>
                    {entry.level.toUpperCase()}
                  </span>
                  <span className={`break-words ${
                    entry.level === 'error' ? 'text-red-300' :
                    entry.level === 'warn' ? 'text-amber-300' :
                    entry.level === 'success' ? 'text-emerald-300' :
                    'text-gray-300'
                  }`}>
                    {entry.msg}
                  </span>
                </div>
              );
            })
          )}
          <div ref={consoleEndRef} />
        </div>
      )}
    </div>
  );
}

// Main WorkflowBuilder page
export function WorkflowBuilder() {
  const { devices } = useDevices();
  const {
    screenshotUrl,
    screenshotBlob,
    annotatedImageUrl,
    elements,
    selectedElement,
    isCapturing,
    isParsing,
    error,
    captureAndParse,
    reparseWithOcrConfig,
    selectElement,
    testStepWithFind,
    clearError,
  } = useWorkflowBuilder();

  // Local state
  const [selectedSut, setSelectedSut] = useState<SUT | null>(null);
  const [zoom, setZoom] = useState(100);
  const [steps, setSteps] = useState<WorkflowStep[]>([]);
  const [draft, setDraft] = useState<DraftStep>({
    actionType: 'find_and_click',
    element: null,
    timeout: 20,
    delay: 2,
    optional: false,
    description: '',
    useCustomOcr: false,
    useSideload: false,
    useVerify: false,
    verifyElements: [],
  });
  const [selectedStepIndex, setSelectedStepIndex] = useState<number | null>(null);
  const [isTestingStep, setIsTestingStep] = useState<number | null>(null);
  const [metadata, setMetadata] = useState<GameMetadata>({
    game_name: '',
    preset_id: '',
    steam_app_id: '',
    launch_method: 'steam',
    path: '',
    process_id: '',
    process_name: '',
    game_process: '',
    startup_wait: 30,
    benchmark_duration: 120,
    benchmark_name: '',
    engine: '',
    graphics_api: '',
    version: '1.0',
    use_ocr_fallback: true,
    ocr_config: {
      use_paddleocr: true,
      text_threshold: 0.5,
      box_threshold: 0.05,
    },
    tracing: {
      enabled: false,
      agents: [],
    },
    hooks: undefined,
  });
  const [showYaml, setShowYaml] = useState(false);
  const [lastOcrTestResult, setLastOcrTestResult] = useState<{ found: boolean; elementCount: number } | null>(null);

  // Game state
  const [isGameRunning, setIsGameRunning] = useState(false);
  const [isCheckingProcess, setIsCheckingProcess] = useState(false);
  const [isLaunching, setIsLaunching] = useState(false);
  const [isKilling, setIsKilling] = useState(false);
  const [isRunningFlow, setIsRunningFlow] = useState(false);
  const [currentFlowStep, setCurrentFlowStep] = useState<number | null>(null);
  const [verifyPickMode, setVerifyPickMode] = useState(false);

  // Console log state
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const addLog = useCallback((level: LogEntry['level'], msg: string) => {
    setLogs(prev => [...prev, { ts: Date.now(), level, msg }]);
  }, []);

  // Workflow library state
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [currentWorkflow, setCurrentWorkflow] = useState<string | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [initialYaml, setInitialYaml] = useState<string>('');

  // Track changes to detect unsaved state
  useEffect(() => {
    if (currentWorkflow && initialYaml) {
      const currentYaml = generateYaml();
      setHasUnsavedChanges(currentYaml !== initialYaml);
    }
  }, [steps, metadata]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        if (e.key === 's') {
          e.preventDefault();
          if (currentWorkflow && hasUnsavedChanges) {
            handleSave();
          }
        } else if (e.key === 'n') {
          e.preventDefault();
          // Will be handled by sidebar "New Workflow" button
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentWorkflow, hasUnsavedChanges]);

  // Auto-detect if game is running when SUT or process name changes
  useEffect(() => {
    const checkGameProcess = async () => {
      const processToCheck = metadata.process_name || metadata.process_id;
      if (!selectedSut || !processToCheck) {
        setIsGameRunning(false);
        return;
      }

      setIsCheckingProcess(true);
      try {
        const running = await isProcessRunning(selectedSut.device_id, processToCheck);
        setIsGameRunning(running);
      } catch {
        setIsGameRunning(false);
      } finally {
        setIsCheckingProcess(false);
      }
    };

    checkGameProcess();
  }, [selectedSut, metadata.process_name, metadata.process_id]);

  // Parse YAML to load workflow
  const parseYamlToWorkflow = useCallback((yaml: string) => {
    try {
      const lines = yaml.split('\n');
      const newSteps: WorkflowStep[] = [];
      const newMetadata: GameMetadata = {
        game_name: '',
        preset_id: '',
        steam_app_id: '',
        launch_method: 'steam',
        path: '',
        process_id: '',
        process_name: '',
        game_process: '',
        startup_wait: 30,
        benchmark_duration: 120,
        benchmark_name: '',
        engine: '',
        graphics_api: '',
        version: '1.0',
        use_ocr_fallback: true,
        ocr_config: {
          use_paddleocr: true,
          text_threshold: 0.5,
          box_threshold: 0.05,
        },
        tracing: {
          enabled: false,
          agents: [],
        },
        hooks: undefined,
      };

      let currentStep: Partial<WorkflowStep> | null = null;
      let inSteps = false;
      let inFind = false;
      let inAction = false;
      let inStepOcrConfig = false;
      let inStepSideload = false;
      let inVerifySuccess = false;
      let inVerifyOcrConfig = false;

      const parseValue = (line: string): string => {
        const colonIdx = line.indexOf(':');
        if (colonIdx === -1) return '';
        return line.slice(colonIdx + 1).trim().replace(/^["']|["']$/g, '');
      };

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) continue;

        // Calculate indentation level (2 spaces = 1 level)
        const indent = line.search(/\S/);

        // Exit steps section when we hit fallbacks or another top-level key
        if (indent === 0 && trimmed !== 'steps:' && inSteps) {
          if (trimmed.startsWith('fallbacks:') || trimmed.endsWith(':')) {
            // Save current step before exiting
            if (currentStep && currentStep.description) {
              newSteps.push(currentStep as WorkflowStep);
              currentStep = null;
            }
            inSteps = false;
            continue;
          }
        }

        // Metadata section (indent 0 or 2 for nested metadata)
        if (!inSteps) {
          if (trimmed.startsWith('game_name:')) {
            newMetadata.game_name = parseValue(trimmed);
          } else if (trimmed.startsWith('preset_id:')) {
            newMetadata.preset_id = parseValue(trimmed);
          } else if (trimmed.startsWith('steam_app_id:')) {
            newMetadata.steam_app_id = parseValue(trimmed);
          } else if (trimmed.startsWith('launch_method:')) {
            const val = parseValue(trimmed);
            newMetadata.launch_method = val === 'exe' ? 'exe' : 'steam';
          } else if (trimmed.startsWith('path:')) {
            newMetadata.path = parseValue(trimmed);
          } else if (trimmed.startsWith('process_id:')) {
            newMetadata.process_id = parseValue(trimmed);
          } else if (trimmed.startsWith('process_name:')) {
            newMetadata.process_name = parseValue(trimmed);
          } else if (trimmed.startsWith('game_process:')) {
            newMetadata.game_process = parseValue(trimmed);
          } else if (trimmed.startsWith('startup_wait:')) {
            newMetadata.startup_wait = parseInt(parseValue(trimmed), 10) || 30;
          } else if (trimmed.startsWith('benchmark_duration:')) {
            newMetadata.benchmark_duration = parseInt(parseValue(trimmed), 10) || 120;
          } else if (trimmed.startsWith('benchmark_name:')) {
            newMetadata.benchmark_name = parseValue(trimmed);
          } else if (trimmed.startsWith('engine:')) {
            newMetadata.engine = parseValue(trimmed);
          } else if (trimmed.startsWith('graphics_api:')) {
            newMetadata.graphics_api = parseValue(trimmed);
          } else if (trimmed.startsWith('version:')) {
            newMetadata.version = parseValue(trimmed) || '1.0';
          } else if (trimmed.startsWith('use_ocr_fallback:')) {
            newMetadata.use_ocr_fallback = parseValue(trimmed) === 'true';
          } else if (trimmed.startsWith('use_paddleocr:')) {
            newMetadata.ocr_config.use_paddleocr = parseValue(trimmed) === 'true';
          } else if (trimmed.startsWith('text_threshold:')) {
            newMetadata.ocr_config.text_threshold = parseFloat(parseValue(trimmed)) || 0.5;
          } else if (trimmed.startsWith('box_threshold:')) {
            newMetadata.ocr_config.box_threshold = parseFloat(parseValue(trimmed)) || 0.05;
          }
        }

        // Steps section start
        if (trimmed === 'steps:') {
          inSteps = true;
          continue;
        }

        if (inSteps) {
          // Detect new step by numbered key (e.g., "1:", "2:", etc.) at indent 2
          const stepMatch = trimmed.match(/^(\d+):$/);
          if (stepMatch && indent === 2) {
            // Save previous step
            if (currentStep && currentStep.description) {
              newSteps.push(currentStep as WorkflowStep);
            }
            currentStep = {
              step_number: parseInt(stepMatch[1], 10),
              expected_delay: 2,
              timeout: 20,
              action_type: 'find_and_click',
            };
            inFind = false;
            inAction = false;
            inStepOcrConfig = false;
            inStepSideload = false;
            inVerifySuccess = false;
            inVerifyOcrConfig = false;
            continue;
          }

          // Track subsections
          if (trimmed === 'find:') {
            inFind = true;
            inAction = false;
            inStepOcrConfig = false;
            inVerifySuccess = false;
            inVerifyOcrConfig = false;
            if (currentStep) {
              currentStep.find = { type: 'any', text: '', text_match: 'contains' };
            }
            continue;
          }
          if (trimmed === 'action:') {
            inAction = true;
            inFind = false;
            inStepOcrConfig = false;
            inVerifySuccess = false;
            inVerifyOcrConfig = false;
            if (currentStep && !currentStep.action) {
              currentStep.action = { type: 'click' };
            }
            continue;
          }
          if (trimmed === 'ocr_config:' && !inVerifySuccess) {
            inStepOcrConfig = true;
            inAction = false;
            inFind = false;
            inStepSideload = false;
            inVerifyOcrConfig = false;
            if (currentStep) {
              currentStep.ocr_config = {};
            }
            continue;
          }
          if (trimmed === 'sideload:') {
            inStepSideload = true;
            inAction = false;
            inFind = false;
            inStepOcrConfig = false;
            inVerifySuccess = false;
            inVerifyOcrConfig = false;
            if (currentStep) {
              currentStep.sideload = { path: '', timeout: 60, wait_for_completion: true };
            }
            continue;
          }
          if (trimmed === 'verify_success:') {
            inVerifySuccess = true;
            inVerifyOcrConfig = false;
            inAction = false;
            inFind = false;
            inStepOcrConfig = false;
            inStepSideload = false;
            if (currentStep) {
              currentStep.verify_success = [];
            }
            continue;
          }

          // Parse fields within current step
          if (currentStep) {
            const colonIdx = trimmed.indexOf(':');
            if (colonIdx > 0) {
              const key = trimmed.slice(0, colonIdx).trim();
              const value = trimmed.slice(colonIdx + 1).trim().replace(/["']/g, '');

              if (inFind && currentStep.find) {
                switch (key) {
                  case 'type': currentStep.find.type = value as 'icon' | 'text' | 'any'; break;
                  case 'text': currentStep.find.text = value; break;
                  case 'text_match': currentStep.find.text_match = value as 'contains' | 'exact' | 'startswith' | 'endswith'; break;
                }
              } else if (inAction) {
                // Parse action type and action-specific fields
                if (key === 'type') {
                  if (value === 'click') currentStep.action_type = 'find_and_click';
                  else if (value === 'wait') currentStep.action_type = 'wait';
                  else if (value === 'key') currentStep.action_type = 'key';
                  else if (value === 'scroll') currentStep.action_type = 'scroll';
                  else if (value === 'text') currentStep.action_type = 'text';
                  else if (value === 'hotkey') currentStep.action_type = 'hotkey';
                } else if (key === 'key' && currentStep.action) {
                  currentStep.action.key = value;
                } else if (key === 'duration' && currentStep.action) {
                  currentStep.action.duration = parseInt(value, 10);
                } else if (key === 'direction' && currentStep.action) {
                  currentStep.action.direction = value as 'up' | 'down';
                } else if (key === 'clicks' && currentStep.action) {
                  currentStep.action.clicks = parseInt(value, 10);
                } else if (key === 'text' && currentStep.action) {
                  currentStep.action.text = value;
                }
              } else if (inStepOcrConfig && currentStep.ocr_config) {
                // Parse per-step OCR config fields
                switch (key) {
                  case 'use_paddleocr':
                    currentStep.ocr_config.use_paddleocr = value === 'true';
                    break;
                  case 'text_threshold':
                    currentStep.ocr_config.text_threshold = parseFloat(value);
                    break;
                  case 'box_threshold':
                    currentStep.ocr_config.box_threshold = parseFloat(value);
                    break;
                }
              } else if (inStepSideload && currentStep.sideload) {
                // Parse per-step sideload fields
                switch (key) {
                  case 'path':
                    currentStep.sideload.path = value;
                    break;
                  case 'args':
                    // Parse array format [arg1, arg2]
                    const argsMatch = value.match(/\[(.*)\]/);
                    if (argsMatch) {
                      currentStep.sideload.args = argsMatch[1].split(',').map(s => s.trim().replace(/["']/g, ''));
                    }
                    break;
                  case 'timeout':
                    currentStep.sideload.timeout = parseInt(value, 10);
                    break;
                  case 'wait_for_completion':
                    currentStep.sideload.wait_for_completion = value === 'true';
                    break;
                }
              } else if (inVerifySuccess && currentStep.verify_success) {
                // Parse verify_success list items
                // "- type: any" starts a new entry
                if (trimmed.startsWith('- type:')) {
                  inVerifyOcrConfig = false;
                  const typeVal = trimmed.slice(trimmed.indexOf(':') + 1).trim().replace(/["']/g, '');
                  currentStep.verify_success.push({
                    type: typeVal as 'icon' | 'text' | 'any',
                    text: '',
                    text_match: 'contains',
                  });
                } else if (trimmed === 'ocr_config:' && currentStep.verify_success.length > 0) {
                  inVerifyOcrConfig = true;
                  const lastV = currentStep.verify_success[currentStep.verify_success.length - 1];
                  lastV.ocr_config = {};
                } else if (inVerifyOcrConfig && currentStep.verify_success.length > 0) {
                  const lastV = currentStep.verify_success[currentStep.verify_success.length - 1];
                  if (lastV.ocr_config) {
                    switch (key) {
                      case 'use_paddleocr': lastV.ocr_config.use_paddleocr = value === 'true'; break;
                      case 'text_threshold': lastV.ocr_config.text_threshold = parseFloat(value); break;
                      case 'box_threshold': lastV.ocr_config.box_threshold = parseFloat(value); break;
                    }
                  }
                } else if (currentStep.verify_success.length > 0) {
                  inVerifyOcrConfig = false;
                  const lastV = currentStep.verify_success[currentStep.verify_success.length - 1];
                  switch (key) {
                    case 'text': lastV.text = value; break;
                    case 'text_match': lastV.text_match = value as 'contains' | 'exact' | 'startswith' | 'endswith'; break;
                  }
                }
              } else {
                // Top-level step fields
                switch (key) {
                  case 'description': currentStep.description = value; break;
                  case 'expected_delay': currentStep.expected_delay = parseInt(value, 10) || 2; break;
                  case 'timeout': currentStep.timeout = parseInt(value, 10) || 20; break;
                  case 'optional': currentStep.optional = value === 'true'; break;
                }
              }
            }
          }
        }
      }

      // Add last step
      if (currentStep && currentStep.description) {
        newSteps.push(currentStep as WorkflowStep);
      }

      // Sort by step number
      newSteps.sort((a, b) => a.step_number - b.step_number);

      return { steps: newSteps, metadata: newMetadata };
    } catch (err) {
      console.error('Failed to parse YAML:', err);
      return null;
    }
  }, []);

  // Handle loading a workflow
  const handleLoadWorkflow = useCallback((name: string, yaml: string) => {
    const parsed = parseYamlToWorkflow(yaml);
    if (parsed) {
      setSteps(parsed.steps);
      setMetadata(parsed.metadata);
      setCurrentWorkflow(name);
      setInitialYaml(yaml);
      setHasUnsavedChanges(false);
    }
  }, [parseYamlToWorkflow]);

  // Handle creating a new workflow
  const handleNewWorkflow = useCallback((name: string, yaml: string) => {
    const parsed = parseYamlToWorkflow(yaml);
    if (parsed) {
      setSteps(parsed.steps);
      setMetadata(parsed.metadata);
      setCurrentWorkflow(name);
      setInitialYaml(yaml);
      setHasUnsavedChanges(false);
    }
  }, [parseYamlToWorkflow]);

  // Helper to escape YAML strings (handles quotes, newlines, special chars)
  const escapeYamlString = (str: string): string => {
    if (!str) return '';
    // If string contains special chars, wrap in quotes and escape internal quotes
    const needsQuotes = /[:\#\[\]\{\}\,\&\*\?\|\-\<\>\=\!\%\@\`\n\r\t"']/.test(str);
    if (needsQuotes) {
      // Escape backslashes first, then quotes
      const escaped = str.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n').replace(/\r/g, '\\r');
      return `"${escaped}"`;
    }
    return str;
  };

  // Generate YAML (moved before handleSave to fix dependency order)
  const generateYaml = useCallback(() => {
    const now = new Date();
    const dateStr = now.toISOString().replace('T', ' ').slice(0, 19);

    // Build metadata section
    let yaml = `# ${metadata.game_name || 'Untitled Workflow'}\n`;
    yaml += `# Generated by Raptor X Workflow Builder\n\n`;
    yaml += `metadata:\n`;
    yaml += `  game_name: "${metadata.game_name}"\n`;
    if (metadata.preset_id) yaml += `  preset_id: ${metadata.preset_id}\n`;
    yaml += `  steam_app_id: '${metadata.steam_app_id}'\n`;
    if (metadata.launch_method !== 'steam') yaml += `  launch_method: ${metadata.launch_method}\n`;
    yaml += `  version: '${metadata.version || '1.0'}'\n`;
    yaml += `  created_with: Raptor X Workflow Builder\n`;
    yaml += `  created_date: '${dateStr}'\n`;
    if (metadata.path) yaml += `  path: ${escapeYamlString(metadata.path)}\n`;
    yaml += `  process_id: ${metadata.process_id}\n`;
    if (metadata.process_name) yaml += `  process_name: ${metadata.process_name}\n`;
    if (metadata.game_process) yaml += `  game_process: ${metadata.game_process}\n`;
    if (metadata.benchmark_name) yaml += `  benchmark_name: ${metadata.benchmark_name}\n`;
    yaml += `  benchmark_duration: ${metadata.benchmark_duration}\n`;
    yaml += `  startup_wait: ${metadata.startup_wait}\n`;
    if (metadata.engine) yaml += `  engine: ${metadata.engine}\n`;
    if (metadata.graphics_api) yaml += `  graphics_api: ${metadata.graphics_api}\n`;
    if (metadata.use_ocr_fallback) yaml += `  use_ocr_fallback: true\n`;

    // OCR config section
    yaml += `\nocr_config:\n`;
    yaml += `  use_paddleocr: ${metadata.ocr_config.use_paddleocr}\n`;
    yaml += `  text_threshold: ${metadata.ocr_config.text_threshold}\n`;
    yaml += `  box_threshold: ${metadata.ocr_config.box_threshold}\n`;

    // Tracing config section (if enabled)
    if (metadata.tracing?.enabled) {
      yaml += `\ntracing:\n`;
      yaml += `  enabled: true\n`;
      if (metadata.tracing.agents && metadata.tracing.agents.length > 0) {
        yaml += `  agents: [${metadata.tracing.agents.join(', ')}]\n`;
      }
      if (metadata.tracing.output_dir) {
        yaml += `  output_dir: ${escapeYamlString(metadata.tracing.output_dir)}\n`;
      }
    }

    // Hooks section (if any)
    if (metadata.hooks?.pre?.length || metadata.hooks?.post?.length) {
      yaml += `\nhooks:\n`;
      if (metadata.hooks.pre?.length) {
        yaml += `  pre:\n`;
        metadata.hooks.pre.forEach((hook) => {
          yaml += `    - path: ${escapeYamlString(hook.path)}\n`;
          if (hook.args?.length) {
            yaml += `      args: [${hook.args.map(a => `"${a}"`).join(', ')}]\n`;
          }
          if (hook.timeout && hook.timeout !== 30) {
            yaml += `      timeout: ${hook.timeout}\n`;
          }
          if (hook.persistent) {
            yaml += `      persistent: true\n`;
          }
          if (hook.critical) {
            yaml += `      critical: true\n`;
          }
        });
      }
      if (metadata.hooks.post?.length) {
        yaml += `  post:\n`;
        metadata.hooks.post.forEach((hook) => {
          yaml += `    - path: ${escapeYamlString(hook.path)}\n`;
          if (hook.args?.length) {
            yaml += `      args: [${hook.args.map(a => `"${a}"`).join(', ')}]\n`;
          }
          if (hook.timeout && hook.timeout !== 60) {
            yaml += `      timeout: ${hook.timeout}\n`;
          }
        });
      }
    }

    // Build steps section
    yaml += `\nsteps:\n`;
    steps.forEach((step, index) => {
      yaml += `  ${index + 1}:\n`;
      yaml += `    description: ${escapeYamlString(step.description)}\n`;

      if (step.find) {
        yaml += `    find:\n`;
        yaml += `      type: ${step.find.type}\n`;
        yaml += `      text: ${escapeYamlString(step.find.text)}\n`;
        yaml += `      text_match: ${step.find.text_match}\n`;
      }

      yaml += `    action:\n`;
      if (step.action_type === 'find_and_click' || step.action_type === 'double_click' || step.action_type === 'right_click') {
        yaml += `      type: click\n`;
        yaml += `      button: ${step.action_type === 'right_click' ? 'right' : 'left'}\n`;
        yaml += `      move_duration: 0.3\n`;
        yaml += `      click_delay: 0.7\n`;
      } else if (step.action_type === 'key' && step.action?.key) {
        yaml += `      type: key\n`;
        yaml += `      key: ${step.action.key}\n`;
      } else if (step.action_type === 'hotkey' && step.action?.keys) {
        yaml += `      type: hotkey\n`;
        yaml += `      keys: [${step.action.keys.map(k => escapeYamlString(k)).join(', ')}]\n`;
      } else if (step.action_type === 'text' && step.action?.text) {
        yaml += `      type: text\n`;
        yaml += `      text: ${escapeYamlString(step.action.text)}\n`;
      } else if (step.action_type === 'wait') {
        yaml += `      type: wait\n`;
        yaml += `      duration: ${step.action?.duration || step.timeout}\n`;
      } else if (step.action_type === 'scroll') {
        yaml += `      type: scroll\n`;
        yaml += `      direction: ${step.action?.direction || 'down'}\n`;
        yaml += `      clicks: ${step.action?.clicks || 3}\n`;
      }

      yaml += `    expected_delay: ${step.expected_delay || 2}\n`;
      yaml += `    timeout: ${step.timeout || 20}\n`;
      if (step.optional) yaml += `    optional: true\n`;

      // Per-step OCR config (only if different from defaults)
      if (step.ocr_config) {
        yaml += `    ocr_config:\n`;
        if (step.ocr_config.use_paddleocr !== undefined) {
          yaml += `      use_paddleocr: ${step.ocr_config.use_paddleocr}\n`;
        }
        if (step.ocr_config.text_threshold !== undefined) {
          yaml += `      text_threshold: ${step.ocr_config.text_threshold}\n`;
        }
        if (step.ocr_config.box_threshold !== undefined) {
          yaml += `      box_threshold: ${step.ocr_config.box_threshold}\n`;
        }
      }

      // Per-step sideload script
      if (step.sideload?.path) {
        yaml += `    sideload:\n`;
        yaml += `      path: ${escapeYamlString(step.sideload.path)}\n`;
        if (step.sideload.args?.length) {
          yaml += `      args: [${step.sideload.args.map(a => `"${a}"`).join(', ')}]\n`;
        }
        if (step.sideload.timeout && step.sideload.timeout !== 60) {
          yaml += `      timeout: ${step.sideload.timeout}\n`;
        }
        if (step.sideload.wait_for_completion === false) {
          yaml += `      wait_for_completion: false\n`;
        }
      }

      // Verify success conditions
      if (step.verify_success && step.verify_success.length > 0) {
        yaml += `    verify_success:\n`;
        step.verify_success.forEach(v => {
          yaml += `      - type: ${escapeYamlString(v.type)}\n`;
          yaml += `        text: ${escapeYamlString(v.text)}\n`;
          yaml += `        text_match: ${escapeYamlString(v.text_match)}\n`;
          if (v.ocr_config) {
            yaml += `        ocr_config:\n`;
            if (v.ocr_config.use_paddleocr !== undefined)
              yaml += `          use_paddleocr: ${v.ocr_config.use_paddleocr}\n`;
            if (v.ocr_config.text_threshold !== undefined)
              yaml += `          text_threshold: ${v.ocr_config.text_threshold}\n`;
            if (v.ocr_config.box_threshold !== undefined)
              yaml += `          box_threshold: ${v.ocr_config.box_threshold}\n`;
          }
        });
      }

      yaml += `\n`;
    });

    // Fallbacks section
    yaml += `fallbacks:\n`;
    yaml += `  general:\n`;
    yaml += `    action: key\n`;
    yaml += `    key: escape\n`;
    yaml += `    expected_delay: 1\n`;

    return yaml;
  }, [metadata, steps]);

  // Handle save
  const handleSave = useCallback(async () => {
    if (!currentWorkflow) return;

    try {
      setIsSaving(true);
      const yaml = generateYaml();
      console.log('[handleSave] Saving YAML for:', currentWorkflow, '\n', yaml);
      await saveWorkflowYaml(currentWorkflow, yaml);
      setInitialYaml(yaml);
      setHasUnsavedChanges(false);
      addLog('success', `Saved "${currentWorkflow}"`);
    } catch (err) {
      console.error('[handleSave] Save failed:', err);
      addLog('error', `Failed to save: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsSaving(false);
    }
  }, [currentWorkflow, generateYaml, addLog]);

  // Handle capture and parse in one click
  const handleCaptureAndParse = useCallback(async () => {
    if (!selectedSut) return;
    await captureAndParse(selectedSut.device_id);
    setLastOcrTestResult(null); // Clear previous test result when capturing new screenshot
  }, [selectedSut, captureAndParse]);

  // Handle re-parse with custom OCR config (for testing threshold tuning)
  const handleReparseWithOcrConfig = useCallback(async () => {
    if (!screenshotBlob || !draft.ocrConfig) return;

    try {
      // Use the hook's reparseWithOcrConfig which handles state updates
      const result = await reparseWithOcrConfig(draft.ocrConfig);

      if (result) {
        // Check if target element was found
        let found = false;
        if (draft.element?.text) {
          const searchText = draft.element.text.toLowerCase().trim();
          found = result.elements.some(el => {
            const elText = (el.element_text || '').toLowerCase().trim();
            return elText.includes(searchText) || searchText.includes(elText);
          });
        }

        setLastOcrTestResult({ found, elementCount: result.elements.length });
      }
    } catch (err) {
      console.error('Re-parse failed:', err);
      addLog('error', `Re-parse failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  }, [screenshotBlob, draft, reparseWithOcrConfig, addLog]);

  // Handle game launch
  const handleLaunchGame = useCallback(async () => {
    if (!selectedSut || !metadata.steam_app_id) {
      alert('Select a SUT and enter Steam App ID in Game Info');
      return;
    }

    try {
      setIsLaunching(true);
      addLog('info', `Launching game (Steam ID: ${metadata.steam_app_id})...`);
      const processName = metadata.process_name || metadata.process_id || undefined;
      await launchGame(selectedSut.device_id, metadata.steam_app_id, processName);
      setIsGameRunning(true);
      addLog('success', 'Game launched successfully');
    } catch (err) {
      addLog('error', `Failed to launch game: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsLaunching(false);
    }
  }, [selectedSut, metadata.steam_app_id, metadata.process_name, metadata.process_id, addLog]);

  // Handle game kill
  const handleKillGame = useCallback(async () => {
    const processToKill = metadata.process_name || metadata.process_id;
    if (!selectedSut || !processToKill) {
      alert('Select a SUT and enter Process Name in Game Info');
      return;
    }

    try {
      setIsKilling(true);
      addLog('info', `Killing process "${processToKill}"...`);
      await killProcess(selectedSut.device_id, processToKill);
      setIsGameRunning(false);
      addLog('success', `Process "${processToKill}" killed`);
    } catch (err) {
      addLog('error', `Failed to kill game: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsKilling(false);
    }
  }, [selectedSut, metadata.process_name, metadata.process_id, addLog]);

  // Handle element click
  const handleElementClick = useCallback((element: BoundingBox) => {
    selectElement(element);

    if (verifyPickMode) {
      // In verify pick mode: append to verify list instead of target
      setDraft(prev => ({
        ...prev,
        verifyElements: [
          ...prev.verifyElements,
          {
            type: element.element_type,
            text: element.element_text,
            textMatch: 'contains',
            useCustomOcr: false,
          },
        ],
      }));
      setVerifyPickMode(false);
      return;
    }

    // Normal mode: auto-populate draft target
    setDraft(prev => ({
      ...prev,
      element: {
        type: element.element_type,
        text: element.element_text,
        textMatch: 'contains',
      },
      description: prev.description || `Click "${element.element_text}"`,
    }));
  }, [selectElement, verifyPickMode]);

  // Add step to workflow
  const handleAddStep = useCallback(() => {
    const newStep: WorkflowStep = {
      step_number: steps.length + 1,
      description: draft.description || 'Step ' + (steps.length + 1),
      action_type: draft.actionType as WorkflowStep['action_type'],
      expected_delay: draft.delay,
      timeout: draft.timeout,
      optional: draft.optional,
    };

    // Add find config for click and scroll actions (scroll needs element position too)
    if (draft.element && ['find_and_click', 'double_click', 'right_click', 'scroll'].includes(draft.actionType)) {
      newStep.find = {
        type: draft.element.type,
        text: draft.element.text,
        text_match: draft.element.textMatch,
      };
    }

    // Add action config
    if (draft.actionType === 'key' && draft.key) {
      newStep.action = { type: 'key', key: draft.key };
    } else if (draft.actionType === 'hotkey' && draft.hotkey) {
      newStep.action = { type: 'hotkey', keys: draft.hotkey.split('+').map(k => k.trim()) };
    } else if (draft.actionType === 'text' && draft.text) {
      newStep.action = { type: 'text', text: draft.text };
    } else if (draft.actionType === 'wait') {
      newStep.action = { type: 'wait', duration: draft.duration || 1 };
    } else if (draft.actionType === 'scroll') {
      newStep.action = {
        type: 'scroll',
        direction: draft.scrollDirection || 'down',
        clicks: draft.scrollAmount || 3,
      };
    }

    // Add per-step OCR config if custom settings enabled
    if (draft.useCustomOcr && draft.ocrConfig) {
      newStep.ocr_config = {
        use_paddleocr: draft.ocrConfig.use_paddleocr,
        text_threshold: draft.ocrConfig.text_threshold,
        box_threshold: draft.ocrConfig.box_threshold,
      };
    }

    // Add per-step sideload if enabled
    if (draft.useSideload && draft.sideload?.path) {
      newStep.sideload = {
        path: draft.sideload.path,
        args: draft.sideload.args,
        timeout: draft.sideload.timeout,
        wait_for_completion: draft.sideload.wait_for_completion,
      };
    }

    // Add verify_success if enabled
    if (draft.useVerify && draft.verifyElements.length > 0) {
      newStep.verify_success = draft.verifyElements.map(ve => ({
        type: ve.type,
        text: ve.text,
        text_match: ve.textMatch as 'contains' | 'exact' | 'startswith' | 'endswith',
        ...(ve.useCustomOcr && ve.ocrConfig ? { ocr_config: ve.ocrConfig } : {}),
      }));
    }

    setSteps([...steps, newStep]);

    // Reset draft
    setDraft({
      actionType: 'find_and_click',
      element: null,
      timeout: 20,
      delay: 2,
      optional: false,
      description: '',
      useCustomOcr: false,
      useSideload: false,
      useVerify: false,
      verifyElements: [],
    });
    selectElement(null);
    setVerifyPickMode(false);
  }, [draft, steps, selectElement]);

  // Remove step
  const handleRemoveStep = useCallback((index: number) => {
    setSteps(steps.filter((_, i) => i !== index));
  }, [steps]);

  // Move step
  const handleMoveStep = useCallback((index: number, direction: 'up' | 'down') => {
    const newSteps = [...steps];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    [newSteps[index], newSteps[targetIndex]] = [newSteps[targetIndex], newSteps[index]];
    setSteps(newSteps);
  }, [steps]);

  // Select step for editing
  const handleSelectStep = useCallback((index: number | null) => {
    setSelectedStepIndex(index);

    if (index === null) {
      // Clear draft when deselecting
      setDraft({
        actionType: 'find_and_click',
        element: null,
        timeout: 20,
        delay: 2,
        optional: false,
        description: '',
        useCustomOcr: false,
        useSideload: false,
        useVerify: false,
        verifyElements: [],
      });
      selectElement(null);
      setVerifyPickMode(false);
      return;
    }

    // Populate draft with selected step data
    const step = steps[index];
    if (step) {
      // Check if step has custom OCR config
      const hasCustomOcr = !!(step.ocr_config?.use_paddleocr !== undefined ||
        step.ocr_config?.text_threshold !== undefined ||
        step.ocr_config?.box_threshold !== undefined);

      const hasSideload = !!step.sideload?.path;
      const hasVerify = !!(step.verify_success && step.verify_success.length > 0);
      setDraft({
        actionType: step.action_type,
        element: step.find ? {
          type: step.find.type,
          text: step.find.text,
          textMatch: step.find.text_match,
        } : null,
        key: step.action?.key,
        hotkey: step.action?.keys?.join('+'),
        text: step.action?.text,
        duration: step.action?.duration,
        scrollDirection: step.action?.direction,
        scrollAmount: step.action?.clicks,
        timeout: step.timeout || 20,
        delay: step.expected_delay || 2,
        optional: step.optional || false,
        description: step.description || '',
        useCustomOcr: hasCustomOcr,
        ocrConfig: hasCustomOcr ? step.ocr_config : undefined,
        useSideload: hasSideload,
        sideload: hasSideload ? step.sideload : undefined,
        useVerify: hasVerify,
        verifyElements: step.verify_success?.map(v => ({
          type: v.type,
          text: v.text,
          textMatch: v.text_match,
          useCustomOcr: !!v.ocr_config,
          ocrConfig: v.ocr_config,
        })) ?? [],
      });
    }
  }, [steps, selectElement]);

  // Update existing step
  const handleUpdateStep = useCallback(() => {
    if (selectedStepIndex === null) return;

    const updatedStep: WorkflowStep = {
      step_number: selectedStepIndex + 1,
      description: draft.description || `Step ${selectedStepIndex + 1}`,
      action_type: draft.actionType as WorkflowStep['action_type'],
      expected_delay: draft.delay,
      timeout: draft.timeout,
      optional: draft.optional,
    };

    // Add find config for click and scroll actions (scroll needs element position too)
    if (draft.element && ['find_and_click', 'double_click', 'right_click', 'scroll'].includes(draft.actionType)) {
      updatedStep.find = {
        type: draft.element.type,
        text: draft.element.text,
        text_match: draft.element.textMatch,
      };
    }

    // Add action config
    if (draft.actionType === 'key' && draft.key) {
      updatedStep.action = { type: 'key', key: draft.key };
    } else if (draft.actionType === 'hotkey' && draft.hotkey) {
      updatedStep.action = { type: 'hotkey', keys: draft.hotkey.split('+').map(k => k.trim()) };
    } else if (draft.actionType === 'text' && draft.text) {
      updatedStep.action = { type: 'text', text: draft.text };
    } else if (draft.actionType === 'wait') {
      updatedStep.action = { type: 'wait', duration: draft.duration || 1 };
    } else if (draft.actionType === 'scroll') {
      updatedStep.action = {
        type: 'scroll',
        direction: draft.scrollDirection || 'down',
        clicks: draft.scrollAmount || 3,
      };
    }

    // Add per-step OCR config if custom settings enabled
    if (draft.useCustomOcr && draft.ocrConfig) {
      updatedStep.ocr_config = {
        use_paddleocr: draft.ocrConfig.use_paddleocr,
        text_threshold: draft.ocrConfig.text_threshold,
        box_threshold: draft.ocrConfig.box_threshold,
      };
    }

    // Add per-step sideload if enabled
    if (draft.useSideload && draft.sideload?.path) {
      updatedStep.sideload = {
        path: draft.sideload.path,
        args: draft.sideload.args,
        timeout: draft.sideload.timeout,
        wait_for_completion: draft.sideload.wait_for_completion,
      };
    }

    // Add verify_success if enabled
    if (draft.useVerify && draft.verifyElements.length > 0) {
      updatedStep.verify_success = draft.verifyElements.map(ve => ({
        type: ve.type,
        text: ve.text,
        text_match: ve.textMatch as 'contains' | 'exact' | 'startswith' | 'endswith',
        ...(ve.useCustomOcr && ve.ocrConfig ? { ocr_config: ve.ocrConfig } : {}),
      }));
    }

    const newSteps = [...steps];
    newSteps[selectedStepIndex] = updatedStep;
    setSteps(newSteps);

    // Deselect after update
    setSelectedStepIndex(null);
    setDraft({
      actionType: 'find_and_click',
      element: null,
      timeout: 20,
      delay: 2,
      optional: false,
      description: '',
      useCustomOcr: false,
      useSideload: false,
      useVerify: false,
      verifyElements: [],
    });
    selectElement(null);
    setVerifyPickMode(false);
  }, [selectedStepIndex, draft, steps, selectElement]);

  // Test existing step - uses hook's testStepWithFind for full flow
  const handleTestExistingStep = useCallback(async (index: number) => {
    console.log('[handleTestExistingStep] Called for index:', index);

    if (!selectedSut) {
      alert('Please select a SUT first');
      return;
    }

    const step = steps[index];
    console.log('[handleTestExistingStep] Step:', step);
    if (!step) {
      console.error('[handleTestExistingStep] No step at index:', index);
      return;
    }

    setIsTestingStep(index);
    addLog('info', `Testing step ${index + 1}: "${step.description}"...`);

    try {
      const result = await testStepWithFind(selectedSut.device_id, step, metadata.ocr_config);
      console.log('[handleTestExistingStep] Result:', result);

      if (result.success) {
        addLog('success', `Step ${index + 1} passed`);
      } else {
        addLog('error', `Step ${index + 1} failed: ${result.message || result.error}`);
      }
    } catch (err) {
      console.error('[handleTestExistingStep] Error:', err);
      addLog('error', `Step ${index + 1} test error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsTestingStep(null);
    }
  }, [selectedSut, steps, testStepWithFind, metadata.ocr_config, addLog]);

  // Run all steps in sequence (Flow) - uses hook's testStepWithFind
  const handleRunFlow = useCallback(async () => {
    console.log('[handleRunFlow] Starting flow with', steps.length, 'steps');

    if (!selectedSut) {
      alert('Please select a SUT first');
      return;
    }

    if (steps.length === 0) {
      alert('No steps to run');
      return;
    }

    setIsRunningFlow(true);
    addLog('info', `Starting flow with ${steps.length} steps...`);

    try {
      for (let i = 0; i < steps.length; i++) {
        setCurrentFlowStep(i);
        setIsTestingStep(i);

        const step = steps[i];
        addLog('info', `Step ${i + 1}/${steps.length}: "${step.description}"`);

        // Skip click steps without target (user may have added placeholder steps)
        if (['find_and_click', 'double_click', 'right_click'].includes(step.action_type) && !step.find?.text) {
          addLog('warn', `Step ${i + 1} has no target element, skipping`);
          continue;
        }

        const result = await testStepWithFind(selectedSut.device_id, step, metadata.ocr_config);
        console.log(`[handleRunFlow] Step ${i + 1} result:`, result);

        if (!result.success) {
          // If optional step fails, continue; otherwise throw
          if (step.optional) {
            addLog('warn', `Optional step ${i + 1} failed, continuing: ${result.message}`);
            continue;
          }
          throw new Error(result.message || result.error || 'Step failed');
        }

        addLog('success', `Step ${i + 1} passed`);

        // Wait for expected_delay before next step
        if (step.expected_delay && i < steps.length - 1) {
          addLog('info', `Waiting ${step.expected_delay}s...`);
          await new Promise(resolve => setTimeout(resolve, step.expected_delay * 1000));
        }
      }

      addLog('success', `Flow completed successfully (${steps.length} steps)`);
    } catch (err) {
      const stepNum = (currentFlowStep ?? 0) + 1;
      console.error(`[handleRunFlow] Flow failed at step ${stepNum}:`, err);
      addLog('error', `Flow failed at step ${stepNum}: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsRunningFlow(false);
      setCurrentFlowStep(null);
      setIsTestingStep(null);
    }
  }, [selectedSut, steps, testStepWithFind, currentFlowStep, metadata.ocr_config, addLog]);

  return (
    <div className="flex h-screen bg-gray-900 text-gray-100 overflow-hidden">
      {/* Workflow Library Sidebar */}
      <WorkflowLibrary
        currentWorkflow={currentWorkflow}
        onLoadWorkflow={handleLoadWorkflow}
        onNewWorkflow={handleNewWorkflow}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        hasUnsavedChanges={hasUnsavedChanges}
      />

      {/* Main Content - flex column, no overflow */}
      <div className="flex-1 flex flex-col p-3 gap-2 overflow-hidden">
        {/* Header - Top Bar with SUT controls (compact) */}
        <div className="flex items-center justify-between gap-3 flex-shrink-0 relative z-10">
          {/* Left: Back button + Title + SUT Selector */}
          <div className="flex items-center gap-4 flex-1">
            <Link
              to="/"
              className="flex items-center gap-2 px-2 py-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
              title="Back to Dashboard"
            >
              <ArrowLeft className="w-4 h-4" />
              <div className="h-6 w-6 rounded bg-gradient-to-br from-cyan-400 via-blue-500 to-pink-500 flex items-center justify-center">
                <span className="font-mono text-white text-[10px] font-bold">RX</span>
              </div>
            </Link>
            <div className="flex items-center gap-2 min-w-0">
              <h1 className="text-lg font-bold text-white truncate">
                {currentWorkflow || 'Workflow Builder'}
              </h1>
              {hasUnsavedChanges && (
                <span className="w-2 h-2 rounded-full bg-warning flex-shrink-0" title="Unsaved changes" />
              )}
            </div>

            {/* Compact SUT Selector */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 hidden sm:inline">SUT:</span>
              <select
                value={selectedSut?.device_id || ''}
                onChange={(e) => {
                  const sut = devices.find(d => d.device_id === e.target.value);
                  setSelectedSut(sut || null);
                }}
                className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 max-w-[140px]"
              >
                <option value="">Select SUT...</option>
                {devices.filter(d => d.status === 'online').map((sut) => (
                  <option key={sut.device_id} value={sut.device_id}>
                    {sut.hostname || sut.ip}
                  </option>
                ))}
              </select>
              {selectedSut && (
                <StatusDot status="online" size="xs" />
              )}
            </div>
          </div>

          {/* Center: Capture + Kill buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleCaptureAndParse}
              disabled={!selectedSut || isCapturing || isParsing}
              className="px-3 py-1.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 disabled:from-gray-700 disabled:to-gray-700 disabled:text-gray-500 text-white text-xs font-medium rounded transition-colors flex items-center gap-1.5"
            >
              {isCapturing ? (
                <>
                  <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span className="hidden sm:inline">Capturing...</span>
                </>
              ) : isParsing ? (
                <>
                  <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span className="hidden sm:inline">Parsing...</span>
                </>
              ) : (
                <>
                  <Camera className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Capture</span>
                </>
              )}
            </button>

            <button
              onClick={isGameRunning ? handleKillGame : handleLaunchGame}
              disabled={!selectedSut || isLaunching || isKilling || isCheckingProcess || (!metadata.steam_app_id && !isGameRunning)}
              className={`px-3 py-1.5 text-xs font-medium rounded transition-colors flex items-center gap-1.5 ${
                isGameRunning
                  ? 'bg-red-600 hover:bg-red-500 disabled:bg-gray-700 disabled:text-gray-500 text-white'
                  : 'bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500 text-white'
              }`}
            >
              {isCheckingProcess ? (
                <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : isLaunching ? (
                <>
                  <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span className="hidden sm:inline">Launching...</span>
                </>
              ) : isKilling ? (
                <>
                  <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span className="hidden sm:inline">Killing...</span>
                </>
              ) : isGameRunning ? (
                <>
                  <StopCircle className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Kill</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span className="hidden sm:inline">Launch</span>
                </>
              )}
            </button>

            <div className="w-px h-5 bg-gray-700" />
          </div>

          {/* Right: Save + YAML buttons */}
          <div className="flex items-center gap-2">
            {currentWorkflow && (
              <button
                onClick={handleSave}
                disabled={!hasUnsavedChanges || isSaving}
                className="px-3 py-1.5 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-xs font-medium rounded transition-colors flex items-center gap-1.5"
              >
                {isSaving ? (
                  <>
                    <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                    </svg>
                    Save
                  </>
                )}
              </button>
            )}
            <button
              onClick={() => setShowYaml(!showYaml)}
              className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 text-xs font-medium rounded transition-colors"
            >
              {showYaml ? 'Hide' : 'YAML'}
            </button>
            <button
              onClick={() => {
                const yaml = generateYaml();
                navigator.clipboard.writeText(yaml);
              }}
              disabled={steps.length === 0}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-xs font-medium rounded transition-colors"
            >
              Copy
            </button>
          </div>
        </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center justify-between bg-red-900/30 border border-red-700/50 rounded-lg px-4 py-2 mb-4">
          <span className="text-red-300 text-sm">{error}</span>
          <button
            onClick={clearError}
            className="text-red-400 hover:text-red-300 text-sm"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* YAML Preview Modal */}
      {showYaml && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg border border-gray-700 w-full max-w-2xl max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-3 border-b border-gray-700">
              <h3 className="text-sm font-medium text-gray-200">Workflow YAML</h3>
              <button
                onClick={() => setShowYaml(false)}
                className="text-gray-500 hover:text-gray-400"
              >
                x
              </button>
            </div>
            <pre className="p-4 overflow-auto text-xs text-gray-300 font-mono max-h-[60vh]">
              {generateYaml()}
            </pre>
          </div>
        </div>
      )}

      {/* Main Content Area - 70% Screenshot, 30% Controls */}
      <div className="flex-1 flex gap-3 min-h-0">
        {/* Left: Screenshot (70%) */}
        <div className="w-[70%] flex flex-col min-h-0">
          <div className="flex items-center justify-between flex-shrink-0 mb-1">
            <span className="text-xs text-gray-500">
              {elements.length > 0 ? `${elements.length} elements` : 'No elements'} - Scroll to zoom
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setZoom(Math.max(100, zoom - 25))}
                disabled={zoom <= 100}
                className="px-2 py-0.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed text-gray-300 text-xs rounded"
                title="Zoom out (min: Fit)"
              >
                -
              </button>
              <span className="text-xs text-gray-400 w-10 text-center">{zoom}%</span>
              <button
                onClick={() => setZoom(Math.min(400, zoom + 25))}
                className="px-2 py-0.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded"
                title="Zoom in"
              >
                +
              </button>
              <button
                onClick={() => setZoom(100)}
                className={`px-2 py-0.5 text-xs rounded transition-colors ml-1 ${
                  zoom === 100
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                }`}
                title="Fit to view"
              >
                Fit
              </button>
            </div>
          </div>
          <div className="flex-[3] min-h-0">
            <ScreenshotCanvas
              imageUrl={annotatedImageUrl || screenshotUrl}
              elements={elements}
              selectedElement={selectedElement}
              onElementClick={handleElementClick}
              zoom={zoom}
              onZoomChange={setZoom}
              isParsing={isParsing}
            />
          </div>
          <BottomPanel
            elements={elements}
            selectedElement={selectedElement}
            onElementClick={handleElementClick}
            logs={logs}
            onClearLogs={() => setLogs([])}
          />
        </div>

        {/* Right: Controls Panel (30%) */}
        <div className="w-[30%] flex flex-col gap-2 min-h-0">
          {/* Step Editor */}
          <div className="bg-gray-800/30 rounded border border-gray-700 p-2 flex-1 overflow-y-auto min-h-0">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-medium text-gray-300">
                {selectedStepIndex !== null ? `Edit Step ${selectedStepIndex + 1}` : 'Define Action'}
              </h3>
              {/* Compact Game Info Toggle */}
              <details className="group relative">
                <summary className="text-xs text-gray-500 hover:text-gray-400 cursor-pointer list-none flex items-center gap-1">
                  {metadata.game_name || 'Game Info'}
                  <svg className="w-3 h-3 transition-transform group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </summary>
                <div className="absolute right-0 top-6 z-10 w-64 bg-gray-800 border border-gray-700 rounded-lg shadow-xl p-3">
                  <MetadataPanel metadata={metadata} onChange={setMetadata} />
                </div>
              </details>
            </div>
            <StepEditor
              draft={draft}
              selectedElement={selectedElement}
              onDraftChange={setDraft}
              onAddStep={handleAddStep}
              onUpdateStep={handleUpdateStep}
              onCancelEdit={() => handleSelectStep(null)}
              isEditing={selectedStepIndex !== null}
              editingStepIndex={selectedStepIndex}
              screenshotBlob={screenshotBlob}
              isParsing={isParsing}
              onReparseWithOcr={handleReparseWithOcrConfig}
              lastOcrTestResult={lastOcrTestResult}
              verifyPickMode={verifyPickMode}
              onVerifyPickModeChange={setVerifyPickMode}
            />
          </div>

          {/* Workflow Steps List */}
          <div className="bg-gray-800/30 rounded border border-gray-700 p-2 flex-1 overflow-hidden min-h-0">
            <StepsList
              steps={steps}
              selectedIndex={selectedStepIndex}
              onSelect={handleSelectStep}
              onRemove={handleRemoveStep}
              onMoveUp={(i) => handleMoveStep(i, 'up')}
              onMoveDown={(i) => handleMoveStep(i, 'down')}
              onTest={handleTestExistingStep}
              onRunFlow={handleRunFlow}
              onClear={() => setSteps([])}
              isTestingStep={isTestingStep}
              isRunningFlow={isRunningFlow}
            />
          </div>
        </div>
      </div>
      </div>
    </div>
  );
}
