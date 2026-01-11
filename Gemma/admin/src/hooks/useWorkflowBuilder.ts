import { useState, useCallback } from 'react';
import {
  takeScreenshot,
  parseScreenshot,
  sendAction,
  launchGame,
  killProcess,
  getPerformance,
  getInstalledGames,
  testWorkflowStep,
  runWorkflow,
  blobToDataURL,
} from '../api/workflowBuilder';
import type {
  ParsedScreenshot,
  BoundingBox,
  WorkflowStep,
  Workflow,
  ActionResult,
  PerformanceMetrics,
} from '../types';

interface UseWorkflowBuilderResult {
  // Screenshot state
  screenshotUrl: string | null;
  screenshotBlob: Blob | null;
  elements: BoundingBox[];
  annotatedImageUrl: string | null;
  selectedElement: BoundingBox | null;

  // Loading states
  isCapturing: boolean;
  isParsing: boolean;
  isExecuting: boolean;

  // Error state
  error: string | null;

  // Performance
  performance: PerformanceMetrics | null;

  // Installed games
  installedGames: Array<{ name: string; steam_app_id?: string }>;

  // Actions
  captureScreenshot: (sutId: string) => Promise<void>;
  captureAndParse: (sutId: string) => Promise<void>;
  parseCurrentScreenshot: () => Promise<void>;
  reparseWithOcrConfig: (ocrConfig: {
    use_paddleocr?: boolean;
    text_threshold?: number;
    box_threshold?: number;
  }) => Promise<{ elements: BoundingBox[]; found: boolean } | null>;
  selectElement: (element: BoundingBox | null) => void;
  executeAction: (sutId: string, action: Parameters<typeof sendAction>[1]) => Promise<ActionResult>;
  executeStep: (sutId: string, step: WorkflowStep) => Promise<ActionResult>;
  testStepWithFind: (
    sutId: string,
    step: WorkflowStep,
    defaultOcrConfig: { use_paddleocr: boolean; text_threshold: number; box_threshold: number }
  ) => Promise<ActionResult>;
  launchGameOnSut: (sutId: string, steamAppId: string, processName?: string) => Promise<ActionResult>;
  killProcessOnSut: (sutId: string, processName: string) => Promise<ActionResult>;
  fetchPerformance: (sutId: string) => Promise<void>;
  fetchInstalledGames: (sutId: string) => Promise<void>;
  runFullWorkflow: (sutIp: string, workflow: Workflow) => Promise<{ run_id: string }>;
  clearScreenshot: () => void;
  clearError: () => void;
}

export function useWorkflowBuilder(): UseWorkflowBuilderResult {
  // Screenshot state
  const [screenshotUrl, setScreenshotUrl] = useState<string | null>(null);
  const [screenshotBlob, setScreenshotBlob] = useState<Blob | null>(null);
  const [elements, setElements] = useState<BoundingBox[]>([]);
  const [annotatedImageUrl, setAnnotatedImageUrl] = useState<string | null>(null);
  const [selectedElement, setSelectedElement] = useState<BoundingBox | null>(null);

  // Loading states
  const [isCapturing, setIsCapturing] = useState(false);
  const [isParsing, setIsParsing] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);

  // Error state
  const [error, setError] = useState<string | null>(null);

  // Performance & games
  const [performance, setPerformance] = useState<PerformanceMetrics | null>(null);
  const [installedGames, setInstalledGames] = useState<Array<{ name: string; steam_app_id?: string }>>([]);

  // Capture screenshot from SUT
  const captureScreenshot = useCallback(async (sutId: string) => {
    setIsCapturing(true);
    setError(null);

    try {
      const blob = await takeScreenshot(sutId);
      const dataUrl = await blobToDataURL(blob);

      setScreenshotBlob(blob);
      setScreenshotUrl(dataUrl);
      setElements([]);
      setAnnotatedImageUrl(null);
      setSelectedElement(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to capture screenshot');
    } finally {
      setIsCapturing(false);
    }
  }, []);

  // Capture and parse in one operation (avoids state timing issues)
  const captureAndParse = useCallback(async (sutId: string) => {
    setIsCapturing(true);
    setError(null);

    try {
      // Capture screenshot
      const blob = await takeScreenshot(sutId);
      const dataUrl = await blobToDataURL(blob);

      setScreenshotBlob(blob);
      setScreenshotUrl(dataUrl);
      setElements([]);
      setAnnotatedImageUrl(null);
      setSelectedElement(null);

      // Now parse immediately using the blob directly (not from state)
      setIsCapturing(false);
      setIsParsing(true);

      const result: ParsedScreenshot = await parseScreenshot(blob, true);

      setElements(result.elements);

      if (result.annotated_image_base64) {
        setAnnotatedImageUrl(`data:image/png;base64,${result.annotated_image_base64}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to capture and parse screenshot');
    } finally {
      setIsCapturing(false);
      setIsParsing(false);
    }
  }, []);

  // Parse the current screenshot with OmniParser
  const parseCurrentScreenshot = useCallback(async () => {
    if (!screenshotBlob) {
      setError('No screenshot to parse');
      return;
    }

    setIsParsing(true);
    setError(null);

    try {
      const result: ParsedScreenshot = await parseScreenshot(screenshotBlob, true);

      setElements(result.elements);

      if (result.annotated_image_base64) {
        setAnnotatedImageUrl(`data:image/png;base64,${result.annotated_image_base64}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to parse screenshot');
    } finally {
      setIsParsing(false);
    }
  }, [screenshotBlob]);

  // Re-parse the current screenshot with custom OCR config (for testing thresholds)
  const reparseWithOcrConfig = useCallback(async (ocrConfig: {
    use_paddleocr?: boolean;
    text_threshold?: number;
    box_threshold?: number;
  }): Promise<{ elements: BoundingBox[]; found: boolean } | null> => {
    if (!screenshotBlob) {
      setError('No screenshot to re-parse');
      return null;
    }

    setIsParsing(true);
    setError(null);

    try {
      const result: ParsedScreenshot = await parseScreenshot(screenshotBlob, true, ocrConfig);

      setElements(result.elements);

      if (result.annotated_image_base64) {
        setAnnotatedImageUrl(`data:image/png;base64,${result.annotated_image_base64}`);
      }

      return { elements: result.elements, found: result.elements.length > 0 };
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to re-parse screenshot');
      return null;
    } finally {
      setIsParsing(false);
    }
  }, [screenshotBlob]);

  // Select an element from the bounding boxes
  const selectElement = useCallback((element: BoundingBox | null) => {
    setSelectedElement(element);
  }, []);

  // Execute a generic action on SUT
  const executeAction = useCallback(async (
    sutId: string,
    action: Parameters<typeof sendAction>[1]
  ): Promise<ActionResult> => {
    setIsExecuting(true);
    setError(null);

    try {
      const result = await sendAction(sutId, action);
      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to execute action';
      setError(errorMessage);
      return { success: false, message: errorMessage, error: errorMessage };
    } finally {
      setIsExecuting(false);
    }
  }, []);

  // Execute a workflow step on SUT
  const executeStep = useCallback(async (
    sutId: string,
    step: WorkflowStep
  ): Promise<ActionResult> => {
    setIsExecuting(true);
    setError(null);

    try {
      const result = await testWorkflowStep(sutId, step);
      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to execute step';
      setError(errorMessage);
      return { success: false, message: errorMessage, error: errorMessage };
    } finally {
      setIsExecuting(false);
    }
  }, []);

  // Test step with find: screenshot → parse → find element → execute action
  const testStepWithFind = useCallback(async (
    sutId: string,
    step: WorkflowStep,
    defaultOcrConfig: { use_paddleocr: boolean; text_threshold: number; box_threshold: number }
  ): Promise<ActionResult> => {
    setIsExecuting(true);
    setError(null);

    try {
      console.log('[testStepWithFind] Starting test for step:', step.description);

      // Handle click actions - need to find element first
      if (['find_and_click', 'double_click', 'right_click'].includes(step.action_type)) {
        if (!step.find?.text) {
          const msg = 'Step has no target element defined';
          setError(msg);
          return { success: false, message: msg, error: msg };
        }

        // 1. Take screenshot
        console.log('[testStepWithFind] Taking screenshot from SUT:', sutId);
        const blob = await takeScreenshot(sutId);
        console.log('[testStepWithFind] Screenshot captured, size:', blob.size);

        // 2. Parse with OCR config (step-level overrides default)
        const ocrConfig = {
          use_paddleocr: step.ocr_config?.use_paddleocr ?? defaultOcrConfig.use_paddleocr,
          text_threshold: step.ocr_config?.text_threshold ?? defaultOcrConfig.text_threshold,
          box_threshold: step.ocr_config?.box_threshold ?? defaultOcrConfig.box_threshold,
        };
        console.log('[testStepWithFind] Parsing with OCR config:', ocrConfig);
        const parsed = await parseScreenshot(blob, false, ocrConfig);
        console.log('[testStepWithFind] Parsed, found elements:', parsed.elements.length);

        // 3. Find matching element
        const searchText = step.find.text.toLowerCase().trim().replace(/\s+/g, ' ');
        const matchType = step.find.text_match || 'contains';
        console.log('[testStepWithFind] Looking for:', searchText, 'match type:', matchType);

        const matchingElement = parsed.elements.find(el => {
          const elText = (el.element_text || '').toLowerCase().trim().replace(/\s+/g, ' ');
          switch (matchType) {
            case 'exact': return elText === searchText;
            case 'contains': return elText.includes(searchText) || searchText.includes(elText);
            case 'startswith': return elText.startsWith(searchText);
            case 'endswith': return elText.endsWith(searchText);
            default: return elText.includes(searchText) || searchText.includes(elText);
          }
        });

        if (!matchingElement) {
          const detectedTexts = parsed.elements
            .map(el => el.element_text)
            .filter(t => t && t.trim())
            .slice(0, 10)
            .join(', ');
          const msg = `Element "${step.find.text}" not found. Detected: ${detectedTexts || '(none)'}`;
          console.log('[testStepWithFind] Element not found:', msg);
          setError(msg);
          return { success: false, message: msg, error: msg };
        }

        console.log('[testStepWithFind] Found element:', matchingElement);

        // 4. Calculate center coordinates and click
        const x = Math.round(matchingElement.x + matchingElement.width / 2);
        const y = Math.round(matchingElement.y + matchingElement.height / 2);
        const clickType = step.action_type === 'find_and_click' ? 'click'
          : step.action_type === 'double_click' ? 'double_click'
          : 'right_click';

        console.log('[testStepWithFind] Clicking at:', x, y, 'type:', clickType);
        const result = await sendAction(sutId, {
          type: clickType as 'click' | 'double_click' | 'right_click',
          x,
          y
        });
        console.log('[testStepWithFind] Click result:', result);
        return result;

      } else if (step.action_type === 'key' && step.action?.key) {
        console.log('[testStepWithFind] Pressing key:', step.action.key);
        return await sendAction(sutId, { type: 'key', key: step.action.key });

      } else if (step.action_type === 'hotkey' && step.action?.keys) {
        console.log('[testStepWithFind] Pressing hotkey:', step.action.keys);
        return await sendAction(sutId, { type: 'hotkey', keys: step.action.keys });

      } else if (step.action_type === 'text' && step.action?.text) {
        console.log('[testStepWithFind] Typing text:', step.action.text);
        return await sendAction(sutId, { type: 'text', text: step.action.text });

      } else if (step.action_type === 'scroll') {
        // Scroll requires x, y - if element is specified, find it first
        let scrollX = 960;  // Default to center
        let scrollY = 540;

        if (step.find?.text) {
          // Find element to scroll at
          console.log('[testStepWithFind] Finding element for scroll:', step.find.text);
          const blob = await takeScreenshot(sutId);
          const ocrConfig = {
            use_paddleocr: step.ocr_config?.use_paddleocr ?? defaultOcrConfig.use_paddleocr,
            text_threshold: step.ocr_config?.text_threshold ?? defaultOcrConfig.text_threshold,
            box_threshold: step.ocr_config?.box_threshold ?? defaultOcrConfig.box_threshold,
          };
          const parsed = await parseScreenshot(blob, false, ocrConfig);

          const searchText = step.find.text.toLowerCase().trim().replace(/\s+/g, ' ');
          const matchType = step.find.text_match || 'contains';

          const matchingElement = parsed.elements.find(el => {
            const elText = (el.element_text || '').toLowerCase().trim().replace(/\s+/g, ' ');
            switch (matchType) {
              case 'exact': return elText === searchText;
              case 'contains': return elText.includes(searchText) || searchText.includes(elText);
              case 'startswith': return elText.startsWith(searchText);
              case 'endswith': return elText.endsWith(searchText);
              default: return elText.includes(searchText) || searchText.includes(elText);
            }
          });

          if (matchingElement) {
            scrollX = Math.round(matchingElement.x + matchingElement.width / 2);
            scrollY = Math.round(matchingElement.y + matchingElement.height / 2);
            console.log('[testStepWithFind] Found element for scroll at:', scrollX, scrollY);
          } else {
            const msg = `Scroll target "${step.find.text}" not found`;
            console.warn('[testStepWithFind]', msg);
            if (!step.optional) {
              setError(msg);
              return { success: false, message: msg, error: msg };
            }
          }
        }

        console.log('[testStepWithFind] Scrolling:', step.action?.direction, step.action?.clicks, 'at', scrollX, scrollY);
        return await sendAction(sutId, {
          type: 'scroll',
          x: scrollX,
          y: scrollY,
          direction: step.action?.direction || 'down',
          clicks: step.action?.clicks || 3
        });

      } else if (step.action_type === 'wait') {
        const duration = step.action?.duration || step.timeout || 1;
        console.log('[testStepWithFind] Waiting:', duration, 'seconds');
        await new Promise(resolve => setTimeout(resolve, duration * 1000));
        return { success: true, message: `Waited ${duration} seconds` };

      } else {
        const msg = `Unknown action type: ${step.action_type}`;
        setError(msg);
        return { success: false, message: msg, error: msg };
      }

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to test step';
      console.error('[testStepWithFind] Error:', errorMessage, err);
      setError(errorMessage);
      return { success: false, message: errorMessage, error: errorMessage };
    } finally {
      setIsExecuting(false);
    }
  }, []);

  // Launch game on SUT
  const launchGameOnSut = useCallback(async (
    sutId: string,
    steamAppId: string,
    processName?: string
  ): Promise<ActionResult> => {
    setIsExecuting(true);
    setError(null);

    try {
      const result = await launchGame(sutId, steamAppId, processName);
      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to launch game';
      setError(errorMessage);
      return { success: false, message: errorMessage, error: errorMessage };
    } finally {
      setIsExecuting(false);
    }
  }, []);

  // Kill process on SUT
  const killProcessOnSut = useCallback(async (
    sutId: string,
    processName: string
  ): Promise<ActionResult> => {
    setIsExecuting(true);
    setError(null);

    try {
      const result = await killProcess(sutId, processName);
      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to kill process';
      setError(errorMessage);
      return { success: false, message: errorMessage, error: errorMessage };
    } finally {
      setIsExecuting(false);
    }
  }, []);

  // Fetch performance metrics
  const fetchPerformance = useCallback(async (sutId: string) => {
    try {
      const perf = await getPerformance(sutId);
      setPerformance(perf);
    } catch (err) {
      console.error('Failed to fetch performance:', err);
    }
  }, []);

  // Fetch installed games
  const fetchInstalledGames = useCallback(async (sutId: string) => {
    try {
      const games = await getInstalledGames(sutId);
      setInstalledGames(games);
    } catch (err) {
      console.error('Failed to fetch installed games:', err);
    }
  }, []);

  // Run full workflow
  const runFullWorkflow = useCallback(async (
    sutIp: string,
    workflow: Workflow
  ): Promise<{ run_id: string }> => {
    setIsExecuting(true);
    setError(null);

    try {
      const result = await runWorkflow(sutIp, workflow);
      return { run_id: result.run_id };
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to run workflow';
      setError(errorMessage);
      throw err;
    } finally {
      setIsExecuting(false);
    }
  }, []);

  // Clear screenshot state
  const clearScreenshot = useCallback(() => {
    setScreenshotUrl(null);
    setScreenshotBlob(null);
    setElements([]);
    setAnnotatedImageUrl(null);
    setSelectedElement(null);
  }, []);

  // Clear error
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    // Screenshot state
    screenshotUrl,
    screenshotBlob,
    elements,
    annotatedImageUrl,
    selectedElement,

    // Loading states
    isCapturing,
    isParsing,
    isExecuting,

    // Error state
    error,

    // Performance & games
    performance,
    installedGames,

    // Actions
    captureScreenshot,
    captureAndParse,
    parseCurrentScreenshot,
    reparseWithOcrConfig,
    selectElement,
    executeAction,
    executeStep,
    testStepWithFind,
    launchGameOnSut,
    killProcessOnSut,
    fetchPerformance,
    fetchInstalledGames,
    runFullWorkflow,
    clearScreenshot,
    clearError,
  };
}
