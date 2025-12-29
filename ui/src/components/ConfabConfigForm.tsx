import { useState } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Textarea } from './ui/textarea';
import { Checkbox } from './ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Badge } from './ui/badge';
import { Settings, Brain, Shield, Database, Globe, Zap, Plus, X } from 'lucide-react';

interface SimpleConfig {
  model_provider: 'openai' | 'anthropic' | 'google' | 'local';
  model_name: string;
  system_prompt: string;
  temperature: number;
  max_tokens?: number;
}

interface ConfabConfigFormProps {
  onSubmit: (config: SimpleConfig | any) => void;
  initialConfig?: SimpleConfig | any;
  isLoading?: boolean;
}

export function ConfabConfigForm({ onSubmit, initialConfig, isLoading = false }: ConfabConfigFormProps) {
  const [configType, setConfigType] = useState<'simple' | 'advanced'>('simple');
  const [simpleConfig, setSimpleConfig] = useState<SimpleConfig>({
    model_provider: 'openai',
    model_name: 'gpt-4',
    system_prompt: 'You are a helpful AI assistant. Provide clear, accurate, and well-structured responses.',
    temperature: 0.7,
    max_tokens: 2000,
    ...initialConfig
  });

  const [advancedConfig, setAdvancedConfig] = useState({
    capabilities: {
      text_generation: true,
      code_generation: false,
      data_analysis: false,
      web_search: false,
      file_processing: false,
      image_analysis: false,
      custom_tools: []
    },
    model: {
      provider: 'openai',
      model_name: 'gpt-4',
      temperature: 0.7,
      max_tokens: 2000,
      top_p: 1.0,
      frequency_penalty: 0.0,
      presence_penalty: 0.0
    },
    knowledge_base: {
      enabled: false,
      type: 'documents',
      source: '',
      indexing_method: 'vector',
      chunk_size: 1000,
      overlap: 200
    },
    conversation: {
      system_prompt: 'You are a helpful AI assistant specialized in software development.',
      max_conversation_length: 50,
      memory_enabled: true,
      context_window_size: 10,
      greeting_message: '',
      error_message: ''
    },
    security: {
      content_filtering: true,
      allowed_domains: [],
      blocked_keywords: [],
      rate_limiting: true,
      max_requests_per_minute: 60,
      authentication_required: true
    },
    integrations: {
      apis: [],
      webhooks: [],
      databases: [],
      storage: null
    },
    deployment: {
      environment: 'development',
      scaling: {},
      monitoring: true,
      logging_level: 'INFO',
      health_checks: true
    },
    custom_settings: {}
  });

  const [newCustomTool, setNewCustomTool] = useState('');
  const [newAllowedDomain, setNewAllowedDomain] = useState('');
  const [newBlockedKeyword, setNewBlockedKeyword] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const config = configType === 'simple' ? simpleConfig : advancedConfig;
    onSubmit(config);
  };

  const addCustomTool = () => {
    if (newCustomTool.trim()) {
      setAdvancedConfig(prev => ({
        ...prev,
        capabilities: {
          ...prev.capabilities,
          custom_tools: [...prev.capabilities.custom_tools, newCustomTool.trim()]
        }
      }));
      setNewCustomTool('');
    }
  };

  const removeCustomTool = (index: number) => {
    setAdvancedConfig(prev => ({
      ...prev,
      capabilities: {
        ...prev.capabilities,
        custom_tools: prev.capabilities.custom_tools.filter((_, i) => i !== index)
      }
    }));
  };

  const addAllowedDomain = () => {
    if (newAllowedDomain.trim()) {
      setAdvancedConfig(prev => ({
        ...prev,
        security: {
          ...prev.security,
          allowed_domains: [...prev.security.allowed_domains, newAllowedDomain.trim()]
        }
      }));
      setNewAllowedDomain('');
    }
  };

  const removeAllowedDomain = (index: number) => {
    setAdvancedConfig(prev => ({
      ...prev,
      security: {
        ...prev.security,
        allowed_domains: prev.security.allowed_domains.filter((_, i) => i !== index)
      }
    }));
  };

  const addBlockedKeyword = () => {
    if (newBlockedKeyword.trim()) {
      setAdvancedConfig(prev => ({
        ...prev,
        security: {
          ...prev.security,
          blocked_keywords: [...prev.security.blocked_keywords, newBlockedKeyword.trim()]
        }
      }));
      setNewBlockedKeyword('');
    }
  };

  const removeBlockedKeyword = (index: number) => {
    setAdvancedConfig(prev => ({
      ...prev,
      security: {
        ...prev.security,
        blocked_keywords: prev.security.blocked_keywords.filter((_, i) => i !== index)
      }
    }));
  };

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Configure Your Confab</h2>
        <p className="text-slate-600">Choose between simple or advanced configuration</p>
      </div>

      <Tabs value={configType} onValueChange={(value) => setConfigType(value as 'simple' | 'advanced')}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="simple" className="flex items-center gap-2">
            <Zap className="w-4 h-4" />
            Simple Configuration
          </TabsTrigger>
          <TabsTrigger value="advanced" className="flex items-center gap-2">
            <Settings className="w-4 h-4" />
            Advanced Configuration
          </TabsTrigger>
        </TabsList>

        <TabsContent value="simple" className="space-y-6">
          <Card className="p-6">
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label htmlFor="model_provider">AI Provider</Label>
                  <Select 
                    value={simpleConfig.model_provider} 
                    onValueChange={(value: any) => setSimpleConfig(prev => ({ ...prev, model_provider: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="openai">OpenAI</SelectItem>
                      <SelectItem value="anthropic">Anthropic</SelectItem>
                      <SelectItem value="google">Google</SelectItem>
                      <SelectItem value="local">Local Model</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="model_name">Model Name</Label>
                  <Input
                    id="model_name"
                    value={simpleConfig.model_name}
                    onChange={(e) => setSimpleConfig(prev => ({ ...prev, model_name: e.target.value }))}
                    placeholder="e.g., gpt-4, claude-3-sonnet"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="temperature">Temperature: {simpleConfig.temperature}</Label>
                  <input
                    type="range"
                    id="temperature"
                    min="0"
                    max="2"
                    step="0.1"
                    value={simpleConfig.temperature}
                    onChange={(e) => setSimpleConfig(prev => ({ ...prev, temperature: parseFloat(e.target.value) }))}
                    className="w-full"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="max_tokens">Max Tokens</Label>
                  <Input
                    id="max_tokens"
                    type="number"
                    value={simpleConfig.max_tokens || ''}
                    onChange={(e) => setSimpleConfig(prev => ({ ...prev, max_tokens: e.target.value ? parseInt(e.target.value) : undefined }))}
                    placeholder="Maximum response tokens"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="system_prompt">System Prompt</Label>
                <Textarea
                  id="system_prompt"
                  value={simpleConfig.system_prompt}
                  onChange={(e) => setSimpleConfig(prev => ({ ...prev, system_prompt: e.target.value }))}
                  placeholder="Define the AI's behavior and personality"
                  rows={4}
                />
              </div>

              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? 'Creating Confab...' : 'Create Confab'}
              </Button>
            </form>
          </Card>
        </TabsContent>

        <TabsContent value="advanced" className="space-y-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Capabilities */}
            <Card className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <Brain className="w-5 h-5" />
                <h3 className="text-lg font-semibold">Agent Capabilities</h3>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
                {Object.entries(advancedConfig.capabilities).map(([key, value]) => {
                  if (key === 'custom_tools') return null;
                  return (
                    <div key={key} className="flex items-center space-x-2">
                      <Checkbox
                        id={key}
                        checked={value as boolean}
                        onCheckedChange={(checked) => 
                          setAdvancedConfig(prev => ({
                            ...prev,
                            capabilities: { ...prev.capabilities, [key]: checked }
                          }))
                        }
                      />
                      <Label htmlFor={key} className="text-sm capitalize">
                        {key.replace(/_/g, ' ')}
                      </Label>
                    </div>
                  );
                })}
              </div>
              
              <div className="space-y-2">
                <Label>Custom Tools</Label>
                <div className="flex gap-2">
                  <Input
                    value={newCustomTool}
                    onChange={(e) => setNewCustomTool(e.target.value)}
                    placeholder="Add custom tool name"
                  />
                  <Button type="button" onClick={addCustomTool} size="sm">
                    <Plus className="w-4 h-4" />
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {advancedConfig.capabilities.custom_tools.map((tool, index) => (
                    <Badge key={index} variant="secondary" className="flex items-center gap-1">
                      {tool}
                      <button
                        type="button"
                        onClick={() => removeCustomTool(index)}
                        className="ml-1 hover:text-red-500"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              </div>
            </Card>

            {/* Model Configuration */}
            <Card className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <Settings className="w-5 h-5" />
                <h3 className="text-lg font-semibold">Model Configuration</h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Provider</Label>
                  <Select 
                    value={advancedConfig.model.provider} 
                    onValueChange={(value) => 
                      setAdvancedConfig(prev => ({
                        ...prev,
                        model: { ...prev.model, provider: value }
                      }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="openai">OpenAI</SelectItem>
                      <SelectItem value="anthropic">Anthropic</SelectItem>
                      <SelectItem value="google">Google</SelectItem>
                      <SelectItem value="local">Local Model</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Model Name</Label>
                  <Input
                    value={advancedConfig.model.model_name}
                    onChange={(e) => 
                      setAdvancedConfig(prev => ({
                        ...prev,
                        model: { ...prev.model, model_name: e.target.value }
                      }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Temperature: {advancedConfig.model.temperature}</Label>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={advancedConfig.model.temperature}
                    onChange={(e) => 
                      setAdvancedConfig(prev => ({
                        ...prev,
                        model: { ...prev.model, temperature: parseFloat(e.target.value) }
                      }))
                    }
                    className="w-full"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Max Tokens</Label>
                  <Input
                    type="number"
                    value={advancedConfig.model.max_tokens || ''}
                    onChange={(e) => 
                      setAdvancedConfig(prev => ({
                        ...prev,
                        model: { ...prev.model, max_tokens: e.target.value ? parseInt(e.target.value) : undefined }
                      }))
                    }
                  />
                </div>
              </div>
            </Card>

            {/* Security Settings */}
            <Card className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <Shield className="w-5 h-5" />
                <h3 className="text-lg font-semibold">Security Settings</h3>
              </div>
              <div className="space-y-4">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="content_filtering"
                    checked={advancedConfig.security.content_filtering}
                    onCheckedChange={(checked) => 
                      setAdvancedConfig(prev => ({
                        ...prev,
                        security: { ...prev.security, content_filtering: checked as boolean }
                      }))
                    }
                  />
                  <Label htmlFor="content_filtering">Enable Content Filtering</Label>
                </div>
                
                <div className="space-y-2">
                  <Label>Allowed Domains</Label>
                  <div className="flex gap-2">
                    <Input
                      value={newAllowedDomain}
                      onChange={(e) => setNewAllowedDomain(e.target.value)}
                      placeholder="Add allowed domain"
                    />
                    <Button type="button" onClick={addAllowedDomain} size="sm">
                      <Plus className="w-4 h-4" />
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {advancedConfig.security.allowed_domains.map((domain, index) => (
                      <Badge key={index} variant="secondary" className="flex items-center gap-1">
                        {domain}
                        <button
                          type="button"
                          onClick={() => removeAllowedDomain(index)}
                          className="ml-1 hover:text-red-500"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Blocked Keywords</Label>
                  <div className="flex gap-2">
                    <Input
                      value={newBlockedKeyword}
                      onChange={(e) => setNewBlockedKeyword(e.target.value)}
                      placeholder="Add blocked keyword"
                    />
                    <Button type="button" onClick={addBlockedKeyword} size="sm">
                      <Plus className="w-4 h-4" />
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {advancedConfig.security.blocked_keywords.map((keyword, index) => (
                      <Badge key={index} variant="destructive" className="flex items-center gap-1">
                        {keyword}
                        <button
                          type="button"
                          onClick={() => removeBlockedKeyword(index)}
                          className="ml-1 hover:text-white"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>
            </Card>

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? 'Creating Confab...' : 'Create Advanced Confab'}
            </Button>
          </form>
        </TabsContent>
      </Tabs>
    </div>
  );
}
