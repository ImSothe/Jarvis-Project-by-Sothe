import { getCloudKeyStatus } from './api';
import { useAppStore } from './store';

// Keep in sync with the Google entry in CommandPalette.tsx's CLOUD_PROVIDERS.
// Lite models: about 1s per step, versus about 6s for gemini-3.8-flash.
export const DEFAULT_CLOUD_MODEL_BY_KEY: Record<string, string> = {
  GEMINI_API_KEY: 'gemini-3.5-flash-lite',
  GOOGLE_API_KEY: 'gemini-3.5-flash-lite',
  ANTHROPIC_API_KEY: 'claude-sonnet-4-6',
  OPENAI_API_KEY: 'gpt-4o-mini',
};

/**
 * Make sure a model is selected. If none is, pick the default for the first cloud
 * key the server reports. Safe to call at any time (page load, a watcher, or right
 * before sending a message) so "Pick a model first" can never get stuck.
 * Returns the selected model id, or '' when nothing could be chosen.
 */
export async function ensureDefaultModel(): Promise<string> {
  const store = useAppStore.getState();
  if (store.selectedModel) return store.selectedModel;
  try {
    const status = await getCloudKeyStatus();
    const connectedKey = Object.entries(status).find(([, set]) => set)?.[0];
    const model = connectedKey ? DEFAULT_CLOUD_MODEL_BY_KEY[connectedKey] : '';
    if (model && !useAppStore.getState().selectedModel) {
      useAppStore.getState().setSelectedModel(model);
    }
  } catch {
    /* server not reachable yet: the caller or the watcher retries */
  }
  return useAppStore.getState().selectedModel;
}