/**
 * LLM Credentials utility for managing API keys in localStorage.
 *
 * SECURITY NOTE: API keys are stored in browser localStorage only.
 * They are passed via request headers and NEVER stored on the server.
 */

const LLM_CREDENTIALS_KEY = 'llm_credentials';

export type LLMProvider = 'anthropic' | 'openai';

export interface LLMCredentials {
  provider: LLMProvider;
  apiKey: string;
  model: string;
}

/**
 * Save LLM credentials to localStorage.
 */
export function saveLLMCredentials(
  provider: LLMProvider,
  apiKey: string,
  model: string
): void {
  const credentials: LLMCredentials = {
    provider,
    apiKey,
    model,
  };
  localStorage.setItem(LLM_CREDENTIALS_KEY, JSON.stringify(credentials));
}

/**
 * Get LLM credentials from localStorage.
 * Returns null if no credentials are stored.
 */
export function getLLMCredentials(): LLMCredentials | null {
  const stored = localStorage.getItem(LLM_CREDENTIALS_KEY);
  if (!stored) {
    return null;
  }
  try {
    return JSON.parse(stored) as LLMCredentials;
  } catch {
    return null;
  }
}

/**
 * Check if LLM credentials are stored.
 */
export function hasLLMCredentials(): boolean {
  return getLLMCredentials() !== null;
}

/**
 * Clear LLM credentials from localStorage.
 * Should be called on logout.
 */
export function clearLLMCredentials(): void {
  localStorage.removeItem(LLM_CREDENTIALS_KEY);
}

/**
 * Validate that an API key looks reasonable (basic format check).
 * This is NOT a security check - just catches obvious typos.
 */
export function validateApiKeyFormat(provider: LLMProvider, apiKey: string): boolean {
  if (!apiKey || apiKey.length < 10) {
    return false;
  }

  if (provider === 'anthropic') {
    // Anthropic keys typically start with 'sk-ant-'
    return apiKey.startsWith('sk-ant-') || apiKey.length > 20;
  }

  if (provider === 'openai') {
    // OpenAI keys typically start with 'sk-'
    return apiKey.startsWith('sk-');
  }

  return true;
}

/**
 * Default models for each provider.
 */
export const DEFAULT_MODELS: Record<LLMProvider, string> = {
  anthropic: 'claude-sonnet-4-20250514',
  openai: 'gpt-4o',
};

/**
 * Available models for each provider.
 */
export const AVAILABLE_MODELS: Record<LLMProvider, string[]> = {
  anthropic: [
    'claude-sonnet-4-20250514',
    'claude-opus-4-20250514',
    'claude-3-5-sonnet-20241022',
    'claude-3-5-haiku-20241022',
  ],
  openai: [
    'gpt-4o',
    'gpt-4o-mini',
    'gpt-4-turbo',
    'gpt-3.5-turbo',
  ],
};

/**
 * Human-readable names for models.
 */
export const MODEL_DISPLAY_NAMES: Record<string, string> = {
  'claude-sonnet-4-20250514': 'Claude Sonnet 4',
  'claude-opus-4-20250514': 'Claude Opus 4',
  'claude-3-5-sonnet-20241022': 'Claude 3.5 Sonnet',
  'claude-3-5-haiku-20241022': 'Claude 3.5 Haiku',
  'gpt-4o': 'GPT-4o',
  'gpt-4o-mini': 'GPT-4o Mini',
  'gpt-4-turbo': 'GPT-4 Turbo',
  'gpt-3.5-turbo': 'GPT-3.5 Turbo',
};
