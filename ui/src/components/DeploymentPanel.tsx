import { useState } from 'react';
import { Cloud, Check, Settings, Rocket, Server, Download } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Label } from './ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'confab-chat';

interface DeploymentPanelProps {
  onNavigate: (view: View, confabName?: string) => void;
}

export function DeploymentPanel({ onNavigate }: DeploymentPanelProps) {
  const [selectedAgent, setSelectedAgent] = useState('1');
  const [cloudProvider, setCloudProvider] = useState('');
  const [llmProvider, setLlmProvider] = useState('');
  const [region, setRegion] = useState('');
  const [deploymentType, setDeploymentType] = useState<'cloud' | 'self-host'>('cloud');

  const agents = [
    { id: '1', name: 'Customer Support Agent' },
    { id: '2', name: 'Data Analysis Agent' },
    { id: '3', name: 'Code Review Assistant' },
  ];

  const cloudProviders = [
    { id: 'aws', name: 'Amazon Web Services (AWS)', regions: ['us-east-1', 'us-west-2', 'eu-west-1'] },
    { id: 'azure', name: 'Microsoft Azure', regions: ['eastus', 'westus', 'westeurope'] },
    { id: 'gcp', name: 'Google Cloud Platform', regions: ['us-central1', 'europe-west1', 'asia-east1'] },
    { id: 'digitalocean', name: 'DigitalOcean', regions: ['nyc1', 'sfo3', 'lon1'] },
  ];

  const llmProviders = [
    { id: 'openai', name: 'OpenAI', models: ['GPT-4', 'GPT-4 Turbo', 'GPT-3.5 Turbo'] },
    { id: 'anthropic', name: 'Anthropic', models: ['Claude 3 Opus', 'Claude 3 Sonnet', 'Claude 3 Haiku'] },
    { id: 'google', name: 'Google AI', models: ['Gemini Pro', 'Gemini Ultra', 'PaLM 2'] },
    { id: 'cohere', name: 'Cohere', models: ['Command', 'Command Light'] },
  ];

  const isFormValid = deploymentType === 'self-host' 
    ? selectedAgent && llmProvider
    : selectedAgent && cloudProvider && region && llmProvider;

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-lg flex items-center justify-center">
            <Cloud className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-slate-900">Deploy Agent</h2>
            <p className="text-slate-600 text-sm">Configure and deploy your AI agent</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Configuration Panel */}
        <div className="lg:col-span-2 space-y-6">
          {/* Deployment Type */}
          <Card className="p-6">
            <h3 className="text-slate-900 mb-4">Deployment Type</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                onClick={() => setDeploymentType('cloud')}
                className={`p-4 rounded-lg border-2 transition-all ${
                  deploymentType === 'cloud'
                    ? 'border-indigo-600 bg-indigo-50'
                    : 'border-slate-200 hover:border-indigo-300'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    deploymentType === 'cloud' ? 'bg-indigo-600' : 'bg-slate-100'
                  }`}>
                    <Cloud className={`w-5 h-5 ${deploymentType === 'cloud' ? 'text-white' : 'text-slate-600'}`} />
                  </div>
                  <div className="text-left">
                    <p className="text-slate-900">Cloud Deploy</p>
                    <p className="text-xs text-slate-600">Managed hosting</p>
                  </div>
                </div>
              </button>
              <button
                onClick={() => setDeploymentType('self-host')}
                className={`p-4 rounded-lg border-2 transition-all ${
                  deploymentType === 'self-host'
                    ? 'border-indigo-600 bg-indigo-50'
                    : 'border-slate-200 hover:border-indigo-300'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    deploymentType === 'self-host' ? 'bg-indigo-600' : 'bg-slate-100'
                  }`}>
                    <Server className={`w-5 h-5 ${deploymentType === 'self-host' ? 'text-white' : 'text-slate-600'}`} />
                  </div>
                  <div className="text-left">
                    <p className="text-slate-900">Self-Host</p>
                    <p className="text-xs text-slate-600">Run on your server</p>
                  </div>
                </div>
              </button>
            </div>
          </Card>

          {/* Agent Selection */}
          <Card className="p-6">
            <h3 className="text-slate-900 mb-4">Agent</h3>
            <div className="space-y-4">
              <div>
                <Label>Select Agent to Deploy</Label>
                <Select value={selectedAgent} onValueChange={setSelectedAgent}>
                  <SelectTrigger className="mt-2">
                    <SelectValue placeholder="Choose an agent" />
                  </SelectTrigger>
                  <SelectContent>
                    {agents.map((agent) => (
                      <SelectItem key={agent.id} value={agent.id}>
                        {agent.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <p className="text-sm text-slate-600">
                Select the agent you want to deploy.
              </p>
            </div>
          </Card>

          {/* Cloud Provider - Only show for cloud deployment */}
          {deploymentType === 'cloud' && (
            <Card className="p-6">
              <h3 className="text-slate-900 mb-4">Cloud</h3>
              <div className="space-y-4">
                <div>
                  <Label>Cloud Provider</Label>
                  <Select value={cloudProvider} onValueChange={setCloudProvider}>
                    <SelectTrigger className="mt-2">
                      <SelectValue placeholder="Choose a cloud provider" />
                    </SelectTrigger>
                    <SelectContent>
                      {cloudProviders.map((provider) => (
                        <SelectItem key={provider.id} value={provider.id}>
                          {provider.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {cloudProvider && (
                  <div>
                    <Label>Region</Label>
                    <Select value={region} onValueChange={setRegion}>
                      <SelectTrigger className="mt-2">
                        <SelectValue placeholder="Choose a region" />
                      </SelectTrigger>
                      <SelectContent>
                        {cloudProviders
                          .find((p) => p.id === cloudProvider)
                          ?.regions.map((r) => (
                            <SelectItem key={r} value={r}>
                              {r}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* LLM Provider */}
          <Card className="p-6">
            <h3 className="text-slate-900 mb-4">LLM Provider</h3>
            <div className="space-y-4">
              <div>
                <Label>LLM Provider</Label>
                <Select value={llmProvider} onValueChange={setLlmProvider}>
                  <SelectTrigger className="mt-2">
                    <SelectValue placeholder="Choose an LLM provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {llmProviders.map((provider) => (
                      <SelectItem key={provider.id} value={provider.id}>
                        {provider.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {llmProvider && (
                <div>
                  <Label>Model</Label>
                  <Select>
                    <SelectTrigger className="mt-2">
                      <SelectValue placeholder="Choose a model" />
                    </SelectTrigger>
                    <SelectContent>
                      {llmProviders
                        .find((p) => p.id === llmProvider)
                        ?.models.map((model) => (
                          <SelectItem key={model} value={model}>
                            {model}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* Summary Panel */}
        <div>
          <Card className="p-6 sticky top-24">
            <h3 className="text-slate-900 mb-4">Deployment Summary</h3>
            
            <div className="space-y-3 mb-6">
              <div className="flex items-start gap-2">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center mt-0.5 ${deploymentType ? 'bg-green-100' : 'bg-slate-100'}`}>
                  {deploymentType && <Check className="w-3 h-3 text-green-600" />}
                </div>
                <div className="flex-1">
                  <p className="text-sm text-slate-900">Deployment Type</p>
                  <p className="text-xs text-slate-600 capitalize">
                    {deploymentType === 'cloud' ? 'Cloud Deploy' : 'Self-Host'}
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center mt-0.5 ${selectedAgent ? 'bg-green-100' : 'bg-slate-100'}`}>
                  {selectedAgent && <Check className="w-3 h-3 text-green-600" />}
                </div>
                <div className="flex-1">
                  <p className="text-sm text-slate-900">Agent Selected</p>
                  {selectedAgent && (
                    <p className="text-xs text-slate-600">
                      {agents.find((a) => a.id === selectedAgent)?.name}
                    </p>
                  )}
                </div>
              </div>

              {deploymentType === 'cloud' && (
                <div className="flex items-start gap-2">
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center mt-0.5 ${cloudProvider && region ? 'bg-green-100' : 'bg-slate-100'}`}>
                    {cloudProvider && region && <Check className="w-3 h-3 text-green-600" />}
                  </div>
                  <div className="flex-1">
                    <p className="text-sm text-slate-900">Cloud Configured</p>
                    {cloudProvider && (
                      <p className="text-xs text-slate-600">
                        {cloudProviders.find((p) => p.id === cloudProvider)?.name}
                        {region && ` (${region})`}
                      </p>
                    )}
                  </div>
                </div>
              )}

              <div className="flex items-start gap-2">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center mt-0.5 ${llmProvider ? 'bg-green-100' : 'bg-slate-100'}`}>
                  {llmProvider && <Check className="w-3 h-3 text-green-600" />}
                </div>
                <div className="flex-1">
                  <p className="text-sm text-slate-900">LLM Configured</p>
                  {llmProvider && (
                    <p className="text-xs text-slate-600">
                      {llmProviders.find((p) => p.id === llmProvider)?.name}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {deploymentType === 'cloud' ? (
              <Button
                className="w-full gap-2"
                disabled={!isFormValid}
              >
                <Rocket className="w-4 h-4" />
                Deploy to Cloud
              </Button>
            ) : (
              <Button
                className="w-full gap-2"
                disabled={!isFormValid}
              >
                <Download className="w-4 h-4" />
                Download Package
              </Button>
            )}

            <Button
              variant="outline"
              className="w-full gap-2 mt-2"
              onClick={() => onNavigate('dashboard')}
            >
              <Settings className="w-4 h-4" />
              Advanced Settings
            </Button>
          </Card>
        </div>
      </div>
    </div>
  );
}