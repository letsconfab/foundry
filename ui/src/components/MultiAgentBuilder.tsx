import { useState } from 'react';
import { Network, Plus, Bot, Settings, Play, Shield } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { Label } from './ui/label';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Checkbox } from './ui/checkbox';

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'confab-chat';

interface MultiAgentBuilderProps {
  onNavigate: (view: View, confabName?: string) => void;
}

interface AgentNode {
  id: string;
  name: string;
  role: string;
}

export function MultiAgentBuilder({ onNavigate }: MultiAgentBuilderProps) {
  const [systemName, setSystemName] = useState('');
  const [nodes, setNodes] = useState<AgentNode[]>([]);
  const [moderatorRules, setModeratorRules] = useState('');
  const [tieBreaker, setTieBreaker] = useState('');
  const [enableConflictResolution, setEnableConflictResolution] = useState(true);
  const [maxTurnsPerAgent, setMaxTurnsPerAgent] = useState('3');

  const availableAgents = [
    { id: '1', name: 'Customer Support Agent', role: 'Support' },
    { id: '2', name: 'Data Analysis Agent', role: 'Analysis' },
    { id: '3', name: 'Code Review Assistant', role: 'Review' },
  ];

  const addAgent = (agentId: string) => {
    const agent = availableAgents.find((a) => a.id === agentId);
    if (agent && !nodes.find((n) => n.id === agent.id)) {
      setNodes([...nodes, agent]);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-lg flex items-center justify-center">
            <Network className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-slate-900">Multi-Agent System Builder</h2>
            <p className="text-slate-600 text-sm">Create collaborative multi-agent systems</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Configuration Panel */}
        <div className="lg:col-span-2 space-y-6">
          {/* System Name */}
          <Card className="p-6">
            <Label>System Name</Label>
            <Input
              value={systemName}
              onChange={(e) => setSystemName(e.target.value)}
              placeholder="e.g., Customer Service Workflow"
              className="mt-2"
            />
          </Card>

          {/* Add Agents */}
          <Card className="p-6">
            <h3 className="text-slate-900 mb-4">Add Agents to System</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {availableAgents.map((agent) => (
                <Button
                  key={agent.id}
                  variant="outline"
                  onClick={() => addAgent(agent.id)}
                  disabled={nodes.some((n) => n.id === agent.id)}
                  className="justify-between"
                >
                  <span className="flex items-center gap-2">
                    <Bot className="w-4 h-4" />
                    {agent.name}
                  </span>
                  <Plus className="w-4 h-4" />
                </Button>
              ))}
            </div>
          </Card>

          {/* Active Agents */}
          {nodes.length > 0 && (
            <Card className="p-6">
              <h3 className="text-slate-900 mb-4">Active Agents</h3>
              <div className="space-y-3">
                {nodes.map((node) => (
                  <div key={node.id} className="flex items-center gap-3 p-4 bg-slate-50 rounded-lg">
                    <div className="w-10 h-10 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-lg flex items-center justify-center flex-shrink-0">
                      <Bot className="w-5 h-5 text-white" />
                    </div>
                    <div className="flex-1">
                      <p className="text-slate-900">{node.name}</p>
                      <Badge variant="secondary" className="text-xs mt-1">
                        {node.role}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Conversation Moderator */}
          {nodes.length >= 2 && (
            <Card className="p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-gradient-to-br from-amber-600 to-orange-600 rounded-lg flex items-center justify-center">
                  <Shield className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h3 className="text-slate-900">Conversation Moderator</h3>
                  <p className="text-sm text-slate-600">Control multi-agent interactions and resolve conflicts</p>
                </div>
              </div>

              <div className="space-y-4">
                {/* Moderator Rules */}
                <div>
                  <Label>Conversation Rules</Label>
                  <Textarea
                    value={moderatorRules}
                    onChange={(e) => setModeratorRules(e.target.value)}
                    placeholder="e.g., Customer Support Agent always has priority for customer-facing queries. Data Analysis Agent must validate all statistical claims..."
                    className="mt-2 min-h-[100px]"
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Define rules that govern how agents interact and who takes precedence in different scenarios
                  </p>
                </div>

                {/* Tie-Breaker Strategy */}
                <div>
                  <Label>Tie-Breaker Strategy</Label>
                  <Select value={tieBreaker} onValueChange={setTieBreaker}>
                    <SelectTrigger className="mt-2">
                      <SelectValue placeholder="Select a tie-breaker strategy" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="priority">Agent Priority Order</SelectItem>
                      <SelectItem value="random">Random Selection</SelectItem>
                      <SelectItem value="confidence">Highest Confidence Score</SelectItem>
                      <SelectItem value="round-robin">Round Robin</SelectItem>
                      <SelectItem value="human">Escalate to Human</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-slate-500 mt-1">
                    How should conflicts between agents be resolved when they disagree?
                  </p>
                </div>

                {/* Max Turns Per Agent */}
                <div>
                  <Label>Max Consecutive Turns Per Agent</Label>
                  <Input
                    type="number"
                    min="1"
                    max="10"
                    value={maxTurnsPerAgent}
                    onChange={(e) => setMaxTurnsPerAgent(e.target.value)}
                    className="mt-2"
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Prevent any single agent from dominating the conversation
                  </p>
                </div>

                {/* Conflict Resolution Toggle */}
                <div className="flex items-center space-x-2 pt-2">
                  <Checkbox
                    id="conflict-resolution"
                    checked={enableConflictResolution}
                    onCheckedChange={(checked) => setEnableConflictResolution(checked as boolean)}
                  />
                  <label
                    htmlFor="conflict-resolution"
                    className="text-sm text-slate-700 cursor-pointer"
                  >
                    Enable automatic conflict resolution
                  </label>
                </div>
              </div>
            </Card>
          )}
        </div>

        {/* Summary Panel */}
        <div>
          <Card className="p-6 sticky top-24">
            <h3 className="text-slate-900 mb-4">System Summary</h3>
            
            <div className="space-y-4 mb-6">
              <div>
                <p className="text-sm text-slate-600">Agents</p>
                <p className="text-2xl text-slate-900">{nodes.length}</p>
              </div>
            </div>

            <div className="space-y-2">
              <Button
                className="w-full gap-2"
                disabled={nodes.length === 0 || !systemName}
              >
                <Settings className="w-4 h-4" />
                Configure System
              </Button>
              <Button
                variant="outline"
                className="w-full gap-2"
                disabled={nodes.length < 2}
              >
                <Play className="w-4 h-4" />
                Test Workflow
              </Button>
              <Button
                variant="outline"
                className="w-full"
                onClick={() => onNavigate('dashboard')}
              >
                Save & Exit
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}