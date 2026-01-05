/**
 * Workflow Builder API Client
 * Handles SUT screenshots, OmniParser parsing, and action execution
 * Routes through Discovery Service (port 5001) for SUT communication
 */

import type {
  ParsedScreenshot,
  ActionResult,
  PerformanceMetrics,
  WorkflowStep,
  Workflow,
} from '../types';

// Use proxy paths for cross-device compatibility (mobile, desktop)
const DISCOVERY_SERVICE_URL = '/discovery-api'; // Proxied to localhost:5001/api
const GEMMA_BACKEND_URL = '/api'; // Proxied to localhost:5000

class WorkflowBuilderError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'WorkflowBuilderError';
  }
}

async function fetchDiscoveryJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${DISCOVERY_SERVICE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }));
    throw new WorkflowBuilderError(response.status, error.detail || error.error || response.statusText);
  }

  return response.json();
}

// ============================================
// Screenshot API
// ============================================

/**
 * Take a screenshot from a SUT
 * @param sutId The unique ID of the SUT
 * @returns Blob containing the PNG image
 */
export async function takeScreenshot(sutId: string): Promise<Blob> {
  const response = await fetch(
    `${DISCOVERY_SERVICE_URL}/suts/${encodeURIComponent(sutId)}/screenshot`
  );

  if (!response.ok) {
    throw new WorkflowBuilderError(response.status, 'Failed to take screenshot');
  }

  return response.blob();
}

/**
 * Parse a screenshot with OmniParser (via Gemma backend)
 * @param imageBlob The screenshot image as a Blob
 * @param includeAnnotation Whether to include the annotated image
 * @returns Parsed elements and optional annotated image
 */
export async function parseScreenshot(
  imageBlob: Blob,
  includeAnnotation: boolean = true
): Promise<ParsedScreenshot> {
  const formData = new FormData();
  formData.append('screenshot', imageBlob, 'screenshot.png');
  if (includeAnnotation) {
    formData.append('include_annotation', 'true');
  }

  const response = await fetch(`${GEMMA_BACKEND_URL}/omniparser/analyze`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }));
    throw new WorkflowBuilderError(response.status, error.detail || error.error || 'Failed to parse screenshot');
  }

  const data = await response.json();
  return {
    elements: data.elements || [],
    annotated_image_base64: data.annotated_image_base64,
    element_count: data.element_count || data.elements?.length || 0,
    processing_time: data.response_time || 0,
  };
}

// ============================================
// SUT Action API
// ============================================

/**
 * Send an action to a SUT
 * @param sutId The unique ID of the SUT
 * @param action The action to perform
 */
export async function sendAction(
  sutId: string,
  action: {
    type: 'click' | 'right_click' | 'double_click' | 'key' | 'hotkey' | 'text' | 'drag' | 'scroll';
    x?: number;
    y?: number;
    button?: 'left' | 'right' | 'middle';
    key?: string;
    keys?: string[];
    text?: string;
    duration?: number;
    clicks?: number;
    direction?: 'up' | 'down';
    dest_x?: number;
    dest_y?: number;
  }
): Promise<ActionResult> {
  return fetchDiscoveryJson<ActionResult>(
    `/suts/${encodeURIComponent(sutId)}/action`,
    {
      method: 'POST',
      body: JSON.stringify(action),
    }
  );
}

/**
 * Launch a game/application on a SUT
 * @param sutId The unique ID of the SUT
 * @param steamAppId The Steam app ID to launch
 * @param processName Optional process name to check
 */
export async function launchGame(
  sutId: string,
  steamAppId: string,
  processName?: string
): Promise<ActionResult> {
  return fetchDiscoveryJson<ActionResult>(
    `/suts/${encodeURIComponent(sutId)}/launch`,
    {
      method: 'POST',
      body: JSON.stringify({
        steam_app_id: steamAppId,
        process_name: processName,
      }),
    }
  );
}

/**
 * Kill a process on a SUT
 * @param sutId The unique ID of the SUT
 * @param processName The name of the process to kill
 */
export async function killProcess(
  sutId: string,
  processName: string
): Promise<ActionResult> {
  return fetchDiscoveryJson<ActionResult>(
    `/suts/${encodeURIComponent(sutId)}/kill-process`,
    {
      method: 'POST',
      body: JSON.stringify({ process_name: processName }),
    }
  );
}

/**
 * Get performance metrics from a SUT
 * @param sutId The unique ID of the SUT
 */
export async function getPerformance(sutId: string): Promise<PerformanceMetrics> {
  return fetchDiscoveryJson<PerformanceMetrics>(
    `/suts/${encodeURIComponent(sutId)}/performance`
  );
}

/**
 * Get screen information from a SUT
 * @param sutId The unique ID of the SUT
 */
export async function getScreenInfo(sutId: string): Promise<{
  width: number;
  height: number;
  dpi: number;
}> {
  return fetchDiscoveryJson(
    `/suts/${encodeURIComponent(sutId)}/screen-info`
  );
}

/**
 * Get installed games on a SUT
 * @param sutId The unique ID of the SUT
 */
export async function getInstalledGames(sutId: string): Promise<Array<{
  name: string;
  steam_app_id?: string;
  install_path?: string;
}>> {
  return fetchDiscoveryJson(
    `/suts/${encodeURIComponent(sutId)}/games`
  );
}

// ============================================
// Workflow Execution API
// ============================================

/**
 * Test a single workflow step on a SUT
 * @param sutId The unique ID of the SUT
 * @param step The workflow step to test
 */
export async function testWorkflowStep(
  sutId: string,
  step: WorkflowStep
): Promise<ActionResult & { step_number: number }> {
  // Convert step to action based on action_type
  const action = buildActionFromStep(step);

  const result = await sendAction(sutId, action);
  return {
    ...result,
    step_number: step.step_number,
  };
}

/**
 * Run a full workflow on a SUT
 * This routes through Gemma backend to start an automation run
 */
export async function runWorkflow(
  sutIp: string,
  workflow: Workflow
): Promise<{
  status: string;
  run_id: string;
  message: string;
}> {
  const response = await fetch(`${GEMMA_BACKEND_URL}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sut_ip: sutIp,
      game_name: workflow.game_name,
      iterations: 1,
      custom_workflow: workflow,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }));
    throw new WorkflowBuilderError(response.status, error.detail || error.error || 'Failed to start workflow');
  }

  return response.json();
}

// ============================================
// Helper Functions
// ============================================

/**
 * Build an action object from a workflow step
 */
function buildActionFromStep(step: WorkflowStep): {
  type: 'click' | 'right_click' | 'double_click' | 'key' | 'hotkey' | 'text' | 'drag' | 'scroll';
  [key: string]: unknown;
} {
  switch (step.action_type) {
    case 'find_and_click':
      return {
        type: 'click',
        button: step.action?.button || 'left',
      };
    case 'right_click':
      return { type: 'right_click' };
    case 'double_click':
      return { type: 'double_click' };
    case 'middle_click':
      return { type: 'click', button: 'middle' };
    case 'key':
      return { type: 'key', key: step.action?.key };
    case 'hotkey':
      return { type: 'hotkey', keys: step.action?.keys };
    case 'text':
      return {
        type: 'text',
        text: step.action?.text,
        clear_first: step.action?.clear_first,
      };
    case 'drag':
      return {
        type: 'drag',
        dest_x: step.action?.dest_x,
        dest_y: step.action?.dest_y,
        duration: step.action?.duration,
      };
    case 'scroll':
      return {
        type: 'scroll',
        direction: step.action?.direction,
        clicks: step.action?.clicks,
      };
    default:
      return { type: 'click' };
  }
}

/**
 * Convert screenshot blob to base64 data URL
 */
export async function blobToDataURL(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

/**
 * Create an image element from a blob
 */
export async function blobToImageElement(blob: Blob): Promise<HTMLImageElement> {
  const url = URL.createObjectURL(blob);
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Failed to load image'));
    };
    img.src = url;
  });
}

export { WorkflowBuilderError };
