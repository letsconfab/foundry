import { useState, useEffect } from 'react';
import { Check, Eye, EyeOff, Key, Sparkles, Settings } from 'lucide-react';
import { Input } from './ui/input';
import { Card } from './ui/card';
import {
  getLLMCredentials,
  saveLLMCredentials,
  validateApiKeyFormat,
  hasLLMCredentials,
  AVAILABLE_MODELS,
  MODEL_DISPLAY_NAMES,
  DEFAULT_MODELS,
  type LLMProvider,
  type LLMCredentials,
} from '../utils/llmCredentials';

interface LLMSetupFlowProps {
  onSetupComplete: () => void;
  onSkip?: () => void;
}

type SetupStep = 'welcome' | 'provider' | 'apiKey' | 'model' | 'complete';

interface ConversationMessage {
  id: string;
  role: 'assistant' | 'user';
  content: React.ReactNode;
}

export function LLMSetupFlow({ onSetupComplete, onSkip }: LLMSetupFlowProps) {
  // Initialize state based on existing credentials
  const initialCreds = getLLMCredentials();
  const [step, setStep] = useState<SetupStep>(initialCreds ? 'welcome' : 'provider');
  const [provider, setProvider] = useState<LLMProvider | null>(initialCreds?.provider || null);
  const [apiKey, setApiKey] = useState(initialCreds?.apiKey || '');
  const [model, setModel] = useState(initialCreds?.model || '');
  const [showApiKey, setShowApiKey] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [existingCredentials] = useState<LLMCredentials | null>(initialCreds);
  const [messages, setMessages] = useState<ConversationMessage[]>([
    {
      id: '1',
      role: 'assistant',
      content: initialCreds ? (
        <div>
          <p className="mb-2">I see you already have <strong>{initialCreds.provider === 'anthropic' ? 'Anthropic (Claude)' : 'OpenAI (GPT)'}</strong> configured.</p>
          <p>Would you like to continue with your existing setup, or change your LLM provider?</p>
        </div>
      ) : (
        <div>
          <p className="mb-2">Before we define your confab's purpose, let's set up your AI assistant.</p>
          <p>Which LLM provider would you like to use for AI-assisted features?</p>
        </div>
      ),
    },
  ]);

  const addMessage = (msg: Omit<ConversationMessage, 'id'>) => {
    setMessages(prev => [...prev, { ...msg, id: Date.now().toString() }]);
  };

  const handleProviderSelect = (selectedProvider: LLMProvider) => {
    setProvider(selectedProvider);
    setModel(DEFAULT_MODELS[selectedProvider]);

    const providerName = selectedProvider === 'anthropic' ? 'Anthropic (Claude)' : 'OpenAI (GPT)';

    addMessage({
      role: 'user',
      content: providerName,
    });

    setTimeout(() => {
      addMessage({
        role: 'assistant',
        content: (
          <div>
            <p className="mb-2">Great choice! {selectedProvider === 'anthropic' ? 'Claude' : 'GPT'} models work wonderfully for conversational AI.</p>
            <p className="mb-2">Now I'll need your API key to connect. Don't worry — your key is stored only in your browser and never sent to our servers.</p>
            <p className="text-sm text-slate-600">
              {selectedProvider === 'anthropic' ? (
                <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">
                  Get your Anthropic API key →
                </a>
              ) : (
                <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">
                  Get your OpenAI API key →
                </a>
              )}
            </p>
          </div>
        ),
      });
      setStep('apiKey');
    }, 300);
  };

  const handleApiKeySubmit = () => {
    if (!provider) return;

    setError(null);

    if (!validateApiKeyFormat(provider, apiKey)) {
      setError('That doesn\'t look like a valid API key. Please check and try again.');
      return;
    }

    const maskedKey = `${apiKey.slice(0, 7)}...${apiKey.slice(-4)}`;

    addMessage({
      role: 'user',
      content: <span className="font-mono text-sm">{maskedKey}</span>,
    });

    setTimeout(() => {
      addMessage({
        role: 'assistant',
        content: (
          <div>
            <p className="mb-2">Perfect! Last step — which model would you prefer?</p>
            <p className="text-sm text-slate-600">You can always change this later.</p>
          </div>
        ),
      });
      setStep('model');
    }, 300);
  };

  const handleModelSelect = (selectedModel: string) => {
    setModel(selectedModel);

    addMessage({
      role: 'user',
      content: MODEL_DISPLAY_NAMES[selectedModel] || selectedModel,
    });

    if (provider) {
      saveLLMCredentials(provider, apiKey, selectedModel);
    }

    setTimeout(() => {
      addMessage({
        role: 'assistant',
        content: (
          <div>
            <p className="mb-2">Excellent! You're all set up and ready to go.</p>
            <p>Now let's define what your confab will do!</p>
          </div>
        ),
      });
      setStep('complete');
    }, 300);
  };

  const handleContinueWithExisting = () => {
    addMessage({
      role: 'user',
      content: 'Continue with existing setup',
    });

    setTimeout(() => {
      addMessage({
        role: 'assistant',
        content: (
          <div>
            <p>Perfect! Let's continue defining your confab's purpose.</p>
          </div>
        ),
      });
      setStep('complete');
    }, 300);
  };

  const handleChangeProvider = () => {
    addMessage({
      role: 'user',
      content: 'I\'d like to change my provider',
    });

    setTimeout(() => {
      addMessage({
        role: 'assistant',
        content: (
          <div>
            <p>No problem! Which LLM provider would you like to use instead?</p>
          </div>
        ),
      });
      setStep('provider');
      setApiKey('');
    }, 300);
  };

  return (
    <Card className="p-6 flex flex-col max-h-[600px]">
      <div className="flex items-center gap-2 mb-4 flex-shrink-0">
        <div className="w-8 h-8 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-lg flex items-center justify-center">
          <Sparkles className="w-4 h-4 text-white" />
        </div>
        <h3 className="text-slate-900 font-medium">AI Setup</h3>
        {hasLLMCredentials() && (
          <div className="ml-auto flex items-center gap-1 text-xs text-green-600">
            <Check className="w-3 h-3" />
            Configured
          </div>
        )}
      </div>

      <div className="space-y-4 mb-4 overflow-y-auto flex-1 min-h-0">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-4 py-3 ${
                msg.role === 'user'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 text-slate-800'
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
      </div>

      <div className="flex-shrink-0">

      {/* Welcome step - for existing users */}
      {step === 'welcome' && existingCredentials && (
        <div className="flex gap-2">
          <button
            onClick={handleContinueWithExisting}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-indigo-500 hover:bg-indigo-600 text-white font-medium rounded-lg transition-colors"
          >
            <Check className="w-4 h-4" />
            Continue with {existingCredentials.provider === 'anthropic' ? 'Claude' : 'GPT'}
          </button>
          <button
            onClick={handleChangeProvider}
            className="px-4 py-3 border-2 border-slate-300 hover:border-slate-400 text-slate-700 font-medium rounded-lg transition-colors flex items-center gap-2"
          >
            <Settings className="w-4 h-4" />
            Change
          </button>
        </div>
      )}

      {/* Provider selection step */}
      {step === 'provider' && (
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => handleProviderSelect('anthropic')}
            className="p-4 border-2 border-indigo-200 bg-indigo-50 rounded-lg hover:border-indigo-400 hover:bg-indigo-100 transition-all text-left"
          >
            <div className="font-medium text-indigo-900">Anthropic</div>
            <div className="text-sm text-indigo-600">Claude models</div>
          </button>
          <button
            onClick={() => handleProviderSelect('openai')}
            className="p-4 border-2 border-indigo-200 bg-indigo-50 rounded-lg hover:border-indigo-400 hover:bg-indigo-100 transition-all text-left"
          >
            <div className="font-medium text-indigo-900">OpenAI</div>
            <div className="text-sm text-indigo-600">GPT models</div>
          </button>
        </div>
      )}

      {/* API Key input step */}
      {step === 'apiKey' && provider && (
        <div className="space-y-3">
          <div className="relative">
            <Input
              type={showApiKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={provider === 'anthropic' ? 'sk-ant-...' : 'sk-...'}
              className="pr-10"
              onKeyDown={(e) => e.key === 'Enter' && handleApiKeySubmit()}
            />
            <button
              type="button"
              onClick={() => setShowApiKey(!showApiKey)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Key className="w-3 h-3" />
            Stored locally in your browser only
          </div>
          <button
            onClick={handleApiKeySubmit}
            disabled={!apiKey.trim()}
            className="w-full py-3 bg-indigo-500 hover:bg-indigo-600 disabled:bg-slate-300 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
          >
            Continue
          </button>
        </div>
      )}

      {/* Model selection step */}
      {step === 'model' && provider && (
        <div className="grid grid-cols-2 gap-2">
          {AVAILABLE_MODELS[provider].map((m) => (
            <button
              key={m}
              onClick={() => handleModelSelect(m)}
              className="p-3 border-2 border-indigo-200 bg-indigo-50 rounded-lg hover:border-indigo-400 hover:bg-indigo-100 transition-all text-left"
            >
              <div className="text-sm font-medium text-indigo-900">
                {MODEL_DISPLAY_NAMES[m] || m}
              </div>
              {m === DEFAULT_MODELS[provider] && (
                <div className="text-xs text-indigo-600 font-medium">Recommended</div>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Complete step */}
      {step === 'complete' && (
        <div className="pt-4 border-t border-slate-200">
          <button
            onClick={onSetupComplete}
            className="w-full h-12 flex items-center justify-center gap-2 bg-indigo-500 hover:bg-indigo-600 text-white text-base font-medium rounded-lg transition-colors"
          >
            <Sparkles className="w-5 h-5" />
            Next: Define Purpose
          </button>
        </div>
      )}

      {/* Skip option */}
      {step !== 'complete' && onSkip && (
        <button
          onClick={onSkip}
          className="w-full mt-3 text-sm text-slate-500 hover:text-slate-700"
        >
          Skip for now — I'll edit the purpose manually
        </button>
      )}
      </div>
    </Card>
  );
}
