import { useState } from 'react';
import { Plus, Bot, MoreVertical, Share2, StopCircle, Trash2, Cloud, MessageSquare, Settings } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'confab-chat' | 'configure';

interface AgentDashboardProps {
  onNavigate: (view: View, confabName?: string, version?: string) => void;
}

interface Agent {
  id: string;
  name: string;
  description: string;
  status: 'active' | 'draft' | 'deployed';
  llmProvider: string;
  cloudProvider?: string;
  lastModified: Date;
  version: string;
}

export function AgentDashboard({ onNavigate }: AgentDashboardProps) {
  const [agents] = useState<Agent[]>([
    {
      id: '1',
      name: 'Customer Support Bot',
      description: 'Handles customer inquiries and provides product information',
      status: 'deployed',
      llmProvider: 'OpenAI GPT-4',
      cloudProvider: 'AWS',
      lastModified: new Date('2025-11-15'),
      version: '1.0.0',
    },
    {
      id: '2',
      name: 'Data Analysis Bot',
      description: 'Analyzes data patterns and generates insights',
      status: 'active',
      llmProvider: 'Anthropic Claude',
      cloudProvider: 'GCP',
      lastModified: new Date('2025-11-16'),
      version: '1.0.1',
    },
    {
      id: '3',
      name: 'Code Review Assistant',
      description: 'Reviews code and suggests improvements',
      status: 'draft',
      llmProvider: 'Google AI',
      lastModified: new Date('2025-11-17'),
      version: '0.9.0',
    },
  ]);

  const getStatusColor = (status: Agent['status']) => {
    switch (status) {
      case 'deployed':
        return 'bg-green-100 text-green-700';
      case 'active':
        return 'bg-blue-100 text-blue-700';
      case 'draft':
        return 'bg-slate-100 text-slate-700';
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
        <div>
          <h2 className="text-slate-900 mb-1">Confab Dashboard</h2>
          <p className="text-slate-600">Manage and monitor your AI confabs</p>
        </div>
        <Button onClick={() => onNavigate('create')} className="gap-2">
          <Plus className="w-4 h-4" />
          Create New Confab
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {agents.map((agent) => (
          <Card key={agent.id} className="p-6 hover:shadow-lg transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-lg flex items-center justify-center">
                <Bot className="w-6 h-6 text-white" />
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon">
                    <MoreVertical className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem className="gap-2">
                    <Share2 className="w-4 h-4" />
                    Publish
                  </DropdownMenuItem>
                  <DropdownMenuItem className="gap-2">
                    <StopCircle className="w-4 h-4" />
                    Stop
                  </DropdownMenuItem>
                  <DropdownMenuItem className="gap-2 text-red-600">
                    <Trash2 className="w-4 h-4" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            <h3 className="text-slate-900 mb-2">{agent.name}</h3>
            {agent.status === 'deployed' && (
              <Badge className="bg-green-100 text-green-700 mb-2">
                Deployed
              </Badge>
            )}
            <p className="text-slate-600 text-sm mb-4">{agent.description}</p>

            <div className="space-y-2 mb-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">LLM Provider:</span>
                <span className="text-slate-900">{agent.llmProvider}</span>
              </div>
              {agent.cloudProvider && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-500">Cloud:</span>
                  <span className="text-slate-900">{agent.cloudProvider}</span>
                </div>
              )}
              <div className="flex items-center justify-between text-sm pt-2 border-t border-slate-200">
                <span className="text-xs text-slate-500">
                  {agent.lastModified.toLocaleDateString()}
                </span>
                <span className="text-xs text-slate-500">v{agent.version}</span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="mt-4 flex gap-2">
              {agent.status === 'deployed' ? (
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1 gap-2"
                  onClick={() => onNavigate('confab-chat', agent.name, agent.version)}
                >
                  <MessageSquare className="w-3 h-3" />
                  Chat
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1 gap-2"
                  onClick={() => onNavigate('deploy')}
                >
                  <Cloud className="w-3 h-3" />
                  Deploy
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                className="flex-1 gap-2"
                onClick={() => onNavigate('configure', agent.name, agent.version)}
              >
                <Settings className="w-3 h-3" />
                Configure
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}