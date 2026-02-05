import { useState, useEffect } from 'react';
import { Key, Eye, EyeOff, Check, AlertCircle } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import {
  getLLMCredentials,
  saveLLMCredentials,
  validateApiKeyFormat,
  AVAILABLE_MODELS,
  MODEL_DISPLAY_NAMES,
  DEFAULT_MODELS,
  type LLMProvider,
} from '../utils/llmCredentials';

interface LLMCredentialsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCredentialsSaved?: () => void;
}

export function LLMCredentialsDialog({
  open,
  onOpenChange,
  onCredentialsSaved,
}: LLMCredentialsDialogProps) {
  const [provider, setProvider] = useState<LLMProvider>('anthropic');
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState(DEFAULT_MODELS.anthropic);
  const [showApiKey, setShowApiKey] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasExistingCredentials, setHasExistingCredentials] = useState(false);

  // Load existing credentials on mount
  useEffect(() => {
    if (open) {
      const credentials = getLLMCredentials();
      if (credentials) {
        setProvider(credentials.provider);
        setApiKey(credentials.apiKey);
        setModel(credentials.model);
        setHasExistingCredentials(true);
      } else {
        setHasExistingCredentials(false);
      }
    }
  }, [open]);

  // Update model when provider changes
  useEffect(() => {
    setModel(DEFAULT_MODELS[provider]);
  }, [provider]);

  const handleSave = () => {
    setError(null);

    // Validate API key format
    if (!validateApiKeyFormat(provider, apiKey)) {
      setError('Invalid API key format. Please check your key and try again.');
      return;
    }

    // Save credentials
    saveLLMCredentials(provider, apiKey, model);
    onCredentialsSaved?.();
    onOpenChange(false);
  };

  const getProviderLabel = (p: LLMProvider) => {
    return p === 'anthropic' ? 'Anthropic (Claude)' : 'OpenAI (GPT)';
  };

  const getApiKeyPlaceholder = () => {
    return provider === 'anthropic' ? 'sk-ant-...' : 'sk-...';
  };

  const getApiKeyHelp = () => {
    if (provider === 'anthropic') {
      return (
        <a
          href="https://console.anthropic.com/settings/keys"
          target="_blank"
          rel="noopener noreferrer"
          className="text-indigo-600 hover:text-indigo-700 underline"
        >
          Get your Anthropic API key
        </a>
      );
    }
    return (
      <a
        href="https://platform.openai.com/api-keys"
        target="_blank"
        rel="noopener noreferrer"
        className="text-indigo-600 hover:text-indigo-700 underline"
      >
        Get your OpenAI API key
      </a>
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Key className="w-5 h-5 text-indigo-600" />
            LLM API Configuration
          </DialogTitle>
          <DialogDescription>
            Configure your LLM provider to use AI-assisted features. Your API key is stored
            locally in your browser and never sent to our servers.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Provider Selection */}
          <div className="space-y-2">
            <Label htmlFor="provider">Provider</Label>
            <Select
              value={provider}
              onValueChange={(value) => setProvider(value as LLMProvider)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="anthropic">{getProviderLabel('anthropic')}</SelectItem>
                <SelectItem value="openai">{getProviderLabel('openai')}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* API Key Input */}
          <div className="space-y-2">
            <Label htmlFor="apiKey">API Key</Label>
            <div className="relative">
              <Input
                id="apiKey"
                type={showApiKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={getApiKeyPlaceholder()}
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                {showApiKey ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
            <p className="text-xs text-slate-500">{getApiKeyHelp()}</p>
          </div>

          {/* Model Selection */}
          <div className="space-y-2">
            <Label htmlFor="model">Model</Label>
            <Select value={model} onValueChange={setModel}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AVAILABLE_MODELS[provider].map((m) => (
                  <SelectItem key={m} value={m}>
                    {MODEL_DISPLAY_NAMES[m] || m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Error Message */}
          {error && (
            <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
              <AlertCircle className="w-4 h-4 text-red-600 mt-0.5" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {/* Security Notice */}
          <div className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <Key className="w-4 h-4 text-blue-600 mt-0.5" />
            <div className="text-xs text-blue-700">
              <p className="font-medium mb-1">Security Notice</p>
              <p>
                Your API key is stored only in your browser's local storage. It is passed
                directly to the LLM provider and never stored on our servers.
              </p>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={!apiKey.trim()}>
            <Check className="w-4 h-4 mr-2" />
            {hasExistingCredentials ? 'Update' : 'Save'} Configuration
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
