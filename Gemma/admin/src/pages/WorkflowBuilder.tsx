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
}

// Screenshot canvas with bounding box overlay - 16:9 aspect ratio, fit-to-container zoom
function ScreenshotCanvas({
  imageUrl,
  elements,
  selectedElement,
  onElementClick,
  zoom,
  onZoomChange,
}: {
  imageUrl: string | null;
  elements: BoundingBox[];
  selectedElement: BoundingBox | null;
  onElementClick: (element: BoundingBox) => void;
  zoom: number;
  onZoomChange?: (newZoom: number) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

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
        className="flex-1 flex items-center justify-center bg-gray-800/50 rounded border border-gray-700"
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

  return (
    <div
      ref={containerRef}
      className={`flex-1 bg-gray-900 rounded border border-gray-700 ${showScrollbars ? 'overflow-auto' : 'overflow-hidden'}`}
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
                <span className="text-sm text-gray-200 font-mono">
                  "{draft.element.text}"
                </span>
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
              <div className="text-xs text-gray-500">
                {step.action_type}
                {step.optional && ' (optional)'}
                {step.find?.text && ` → "${step.find.text}"`}
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
      };

      let currentStep: Partial<WorkflowStep> | null = null;
      let inSteps = false;
      let inFind = false;
      let inAction = false;
      let inStepOcrConfig = false;

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
            continue;
          }

          // Track subsections
          if (trimmed === 'find:') {
            inFind = true;
            inAction = false;
            inStepOcrConfig = false;
            if (currentStep) {
              currentStep.find = { type: 'any', text: '', text_match: 'contains' };
            }
            continue;
          }
          if (trimmed === 'action:') {
            inAction = true;
            inFind = false;
            inStepOcrConfig = false;
            if (currentStep && !currentStep.action) {
              currentStep.action = { type: 'click' };
            }
            continue;
          }
          if (trimmed === 'ocr_config:') {
            inStepOcrConfig = true;
            inAction = false;
            inFind = false;
            if (currentStep) {
              currentStep.ocr_config = {};
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
    if (metadata.path) yaml += `  path: '${metadata.path}'\n`;
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
      await saveWorkflowYaml(currentWorkflow, yaml);
      setInitialYaml(yaml);
      setHasUnsavedChanges(false);
    } catch (err) {
      alert(`Failed to save: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsSaving(false);
    }
  }, [currentWorkflow, generateYaml]);

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
      alert(`Failed to re-parse: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  }, [screenshotBlob, draft, reparseWithOcrConfig]);

  // Handle game launch
  const handleLaunchGame = useCallback(async () => {
    if (!selectedSut || !metadata.steam_app_id) {
      alert('Select a SUT and enter Steam App ID in Game Info');
      return;
    }

    try {
      setIsLaunching(true);
      const processName = metadata.process_name || metadata.process_id || undefined;
      await launchGame(selectedSut.device_id, metadata.steam_app_id, processName);
      setIsGameRunning(true);
    } catch (err) {
      alert(`Failed to launch game: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsLaunching(false);
    }
  }, [selectedSut, metadata.steam_app_id, metadata.process_name, metadata.process_id]);

  // Handle game kill
  const handleKillGame = useCallback(async () => {
    const processToKill = metadata.process_name || metadata.process_id;
    if (!selectedSut || !processToKill) {
      alert('Select a SUT and enter Process Name in Game Info');
      return;
    }

    try {
      setIsKilling(true);
      await killProcess(selectedSut.device_id, processToKill);
      setIsGameRunning(false);
    } catch (err) {
      alert(`Failed to kill game: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsKilling(false);
    }
  }, [selectedSut, metadata.process_name, metadata.process_id]);

  // Handle element click
  const handleElementClick = useCallback((element: BoundingBox) => {
    selectElement(element);
    // Auto-populate draft
    setDraft(prev => ({
      ...prev,
      element: {
        type: element.element_type,
        text: element.element_text,
        textMatch: 'contains',
      },
      description: `Click "${element.element_text}"`,
    }));
  }, [selectElement]);

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
    });
    selectElement(null);
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
      });
      selectElement(null);
      return;
    }

    // Populate draft with selected step data
    const step = steps[index];
    if (step) {
      // Check if step has custom OCR config
      const hasCustomOcr = !!(step.ocr_config?.use_paddleocr !== undefined ||
        step.ocr_config?.text_threshold !== undefined ||
        step.ocr_config?.box_threshold !== undefined);

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
    });
    selectElement(null);
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

    try {
      const result = await testStepWithFind(selectedSut.device_id, step, metadata.ocr_config);
      console.log('[handleTestExistingStep] Result:', result);

      if (!result.success) {
        alert(`Step failed: ${result.message || result.error}`);
      }
    } catch (err) {
      console.error('[handleTestExistingStep] Error:', err);
      alert(`Test failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsTestingStep(null);
    }
  }, [selectedSut, steps, testStepWithFind, metadata.ocr_config]);

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

    try {
      for (let i = 0; i < steps.length; i++) {
        setCurrentFlowStep(i);
        setIsTestingStep(i);

        const step = steps[i];
        console.log(`[handleRunFlow] Step ${i + 1}/${steps.length}:`, step.description);

        // Skip click steps without target (user may have added placeholder steps)
        if (['find_and_click', 'double_click', 'right_click'].includes(step.action_type) && !step.find?.text) {
          console.warn(`[handleRunFlow] Step ${i + 1} has no target element, skipping`);
          continue;
        }

        const result = await testStepWithFind(selectedSut.device_id, step, metadata.ocr_config);
        console.log(`[handleRunFlow] Step ${i + 1} result:`, result);

        if (!result.success) {
          // If optional step fails, continue; otherwise throw
          if (step.optional) {
            console.warn(`[handleRunFlow] Optional step ${i + 1} failed, continuing:`, result.message);
            continue;
          }
          throw new Error(result.message || result.error || 'Step failed');
        }

        // Wait for expected_delay before next step
        if (step.expected_delay && i < steps.length - 1) {
          console.log(`[handleRunFlow] Waiting ${step.expected_delay}s before next step`);
          await new Promise(resolve => setTimeout(resolve, step.expected_delay * 1000));
        }
      }

      console.log('[handleRunFlow] Flow completed successfully');
    } catch (err) {
      const stepNum = (currentFlowStep ?? 0) + 1;
      console.error(`[handleRunFlow] Flow failed at step ${stepNum}:`, err);
      alert(`Flow failed at step ${stepNum}: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsRunningFlow(false);
      setCurrentFlowStep(null);
      setIsTestingStep(null);
    }
  }, [selectedSut, steps, testStepWithFind, currentFlowStep, metadata.ocr_config]);

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
        <div className="flex items-center justify-between gap-3 flex-shrink-0">
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
          <ScreenshotCanvas
            imageUrl={annotatedImageUrl || screenshotUrl}
            elements={elements}
            selectedElement={selectedElement}
            onElementClick={handleElementClick}
            zoom={zoom}
            onZoomChange={setZoom}
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
