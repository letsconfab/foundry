import React from 'react';
import { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, Save, Loader2, Paperclip, File, X, Github, Plus, Bot, Shield, Network, Users, Mail, User, TestTube, CheckCircle, AlertCircle } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { Label } from './ui/label';
import { Input } from './ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { Checkbox } from './ui/checkbox';
import { Avatar, AvatarFallback } from './ui/avatar';
import { apiClient } from '../api/client.js';
import { useAuth } from '../contexts/AuthContext';

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'confab-chat' | 'review-chats';

interface AgentChatProps {
  onNavigate: (view: View, confabName?: string) => void;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  userName?: string;
}

interface UploadedFile {
  name: string;
  size: number;
}

interface AgentNode {
  id: string;
  name: string;
  role: string;
}

const PROMPT_SUGGESTIONS = [
  "Create a customer support agent that handles refunds and returns",
  "Build an agent that analyzes sales data and generates weekly reports",
  "I need an agent to review code for security vulnerabilities",
  "Create an agent that summarizes meeting transcripts",
];

const AGENT_CREATION_STEPS = [
  { id: 1, label: 'Define Purpose', keywords: ['what', 'do', 'help', 'agent', 'create', 'build'] },
  { id: 2, label: 'Add Participants', keywords: ['participant', 'collaborator', 'team', 'member', 'invite', 'share', 'permission'] },
  { id: 3, label: 'Configure Memory', keywords: ['memory', 'remember', 'conversation', 'history', 'context'] },
  { id: 4, label: 'Add Tools & APIs', keywords: ['tool', 'api', 'access', 'integrate', 'connect'] },
  { id: 5, label: 'Guardrails', keywords: ['guardrail', 'safety', 'limit', 'restrict', 'boundary', 'rule', 'policy'] },
  { id: 6, label: 'Sample Inputs/Outputs', keywords: ['sample', 'example', 'input', 'output', 'test', 'response', 'demo'] },
  { id: 7, label: 'Review & Save', keywords: ['review', 'summary', 'confirm', 'save', 'finish'] },
];

export function AgentChat({ onNavigate }: AgentChatProps) {
  const { user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: "Hi! I'm your AI confab builder assistant. Let's create an amazing AI confab together. Tell me what you'd like your confab to do, and I'll help you configure it step by step.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [currentStep, setCurrentStep] = useState(1);
  const [isTestingRepo, setIsTestingRepo] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [testError, setTestError] = useState('');
  /** Thread id for storing this conversation in DB (threads + messages tables). */
  const [currentThreadId, setCurrentThreadId] = useState<number | null>(null);

  // [CLAUDE: IMPLEMENTATION - Create confab_id on page load and link to thread_mapping]
  // Stores the confab (agent configuration) ID created when entering this page
  const [currentConfabId, setCurrentConfabId] = useState<number | null>(null);
  const [isConfabCreating, setIsConfabCreating] = useState(false);
  // === [CLAUDE: ADDED state for confab builder inputs] ===
  const [purposeText, setPurposeText] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [repoOwnerInput, setRepoOwnerInput] = useState('');
  const [repoNameInput, setRepoNameInput] = useState('');
  const [memoryEnabledLocal, setMemoryEnabledLocal] = useState(true);
  const [memoryNotes, setMemoryNotes] = useState('');
  const [guardrailsText, setGuardrailsText] = useState('');
  const [sampleIO, setSampleIO] = useState('');
  const [saveResult, setSaveResult] = useState<any>(null);
  
  // Multi-Agent State
  const [multiAgentNodes, setMultiAgentNodes] = useState<AgentNode[]>([]);
  const [moderatorRules, setModeratorRules] = useState('');
  const [tieBreaker, setTieBreaker] = useState('');
  const [enableConflictResolution, setEnableConflictResolution] = useState(true);
  const [maxTurnsPerAgent, setMaxTurnsPerAgent] = useState('3');
  const [githubConnected, setGithubConnected] = useState(false);

  // === [CLAUDE: Ollama-related state for dynamic chat] ===
  const [ollamaHealthy, setOllamaHealthy] = useState(false);
  const [ollamaError, setOllamaError] = useState<string | null>(null);

  // Check Ollama health on component mount
  useEffect(() => {
    const checkOllama = async () => {
      try {
        const health = await apiClient.ollamaHealthCheck();
        setOllamaHealthy(health.healthy);
        if (!health.healthy) {
          setOllamaError('Ollama service is not available. Running at http://localhost:11434');
        }
      } catch (error) {
        setOllamaHealthy(false);
        setOllamaError('Could not connect to Ollama service');
      }
    };
    checkOllama();

    // [CLAUDE: IMPLEMENTATION - Create confab on page load]
    // This creates a confab entry in the database when entering @agentchat page
    // The confab_id will be linked to the thread via thread_mapping on first message
    const createInitialConfab = async () => {
      if (isConfabCreating) return; // Prevent duplicate creation
      
      try {
        setIsConfabCreating(true);
        const confabName = `Agent Chat – ${new Date().toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}`;
        const confab = await apiClient.createConfab({
          name: confabName,
          description: 'Auto-generated confab for agent chat conversation',
        });
        
        if (confab?.id) {
          setCurrentConfabId(confab.id);
          console.log('[CLAUDE: IMPLEMENTATION] Confab created with ID:', confab.id);
        }
      } catch (error) {
        console.error('[CLAUDE: IMPLEMENTATION] Error creating confab:', error);
        // Continue gracefully - confab creation is optional for demo
      } finally {
        setIsConfabCreating(false);
      }
    };
    
    createInitialConfab();
  }, []);

  // Determine GitHub repo naming convention
  const getRepoNamingConvention = () => {
    if (user?.github_connected) {
      return 'username/confabs (will be set based on your GitHub username)';
    } else {
      return 'letsconfab/confabs (for email users)';
    }
  };

  const availableAgents = [
    { id: '1', name: 'Customer Support Agent', role: 'Support' },
    { id: '2', name: 'Data Analysis Agent', role: 'Analysis' },
    { id: '3', name: 'Code Review Assistant', role: 'Review' },
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;
    const content = input.trim();

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    // === [CLAUDE: Initialize or use existing thread for conversation storage] ===
    let tid = currentThreadId;
    if (tid == null) {
      try {
        const name = `Create Confab – ${new Date().toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}`;
        const thread = await apiClient.createThread(name);
        tid = thread?.id ?? null;
        if (tid != null) setCurrentThreadId(tid);
        if (tid != null && messages[0]?.role === 'assistant') {
          await apiClient.addMessage(tid, messages[0].content, 'assistant');
        }

        // [CLAUDE: IMPLEMENTATION - Create thread_mapping on first message]
        // Links the confab (created when entering page) to the thread (created when sending first message)
        // This establishes the relationship: confab_id -> thread_id in thread_mapping table
        if (tid != null && currentConfabId != null) {
          try {
            const mapping = await apiClient.createThreadMapping(currentConfabId, tid);
            console.log('[CLAUDE: IMPLEMENTATION] Thread mapping created:', mapping);
          } catch (mappingError) {
            console.error('[CLAUDE: IMPLEMENTATION] Error creating thread mapping:', mappingError);
            // Continue gracefully - the thread is still created even if mapping fails
          }
        } else if (tid != null && currentConfabId == null) {
          console.warn('[CLAUDE: IMPLEMENTATION] Thread created but confab_id is missing:', {
            threadId: tid,
            confabId: currentConfabId,
          });
        }
      } catch {
        tid = null;
      }
    }

    // === [CLAUDE: Store user message in database if thread exists] ===
    if (tid != null) {
      apiClient.addMessage(tid, content, 'user').catch(() => {});
    }

    // === [CLAUDE: Generate AI response from Ollama API] ===
    try {
      let assistantContent = '';

      if (!ollamaHealthy) {
        assistantContent = "I notice that the Ollama service is not currently available. Please ensure Ollama is running at http://localhost:11434 and try again. In the meantime, I can provide general guidance about confab configuration.";
      } else {
        try {
          // Call the new Ollama-powered chat endpoint
          if (tid != null) {
            const response = await apiClient.chatWithOllama(tid, content);
            assistantContent = response.assistant_message?.content || "I couldn't generate a response. Please try again.";
          } else {
            // Fallback: use direct Ollama generation if no thread
            const response = await apiClient.ollamaGenerateResponse(
              `User asked: ${content}\n\nProvide a helpful response about building an AI confab:`
            );
            assistantContent = response.response || "I couldn't generate a response. Please try again.";
          }
        } catch (error: any) {
          console.error('[CLAUDE: Ollama API error]', error);
          assistantContent = `I encountered an error: ${error.message || 'Unable to generate response from Ollama'}. Please try again or check if Ollama is running.`;
          setOllamaError(error.message);
        }
      }

      setIsTyping(false);

      // === [CLAUDE: Add AI response to messages state] ===
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: assistantContent,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      updateStep(assistantContent);

      // === [CLAUDE: ADDED] If current step fields are missing, ask a targeted follow-up question ===
      const followUps:any = {
        1: () => !purposeText && "Can you briefly describe the primary purpose of this confab? (This will be saved to PURPOSE.md)",
        3: () => memoryEnabledLocal && !memoryNotes && "What should the agent remember across conversations? Provide short notes for memory.",
        4: () => (!apiKey && !repoOwnerInput && !repoNameInput) && "If you want the agent to use external tools, provide an API key or repository owner/name to save the confab.",
        5: () => !guardrailsText && "Any guardrails to enforce? (e.g., do not provide legal advice, avoid personal data)",
        6: () => !sampleIO && "Can you provide one or two sample inputs and expected outputs to help generate tests/examples?"
      };

      const follow = followUps[currentStep]?.();
      if (follow) {
        const followMessage: Message = {
          id: (Date.now() + 2).toString(),
          role: 'assistant',
          content: follow,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, followMessage]);
      }

      // === [CLAUDE: Store AI response in database if thread exists] ===
      if (tid != null) {
        apiClient.addMessage(tid, assistantContent, 'assistant').catch(() => {});
      }
    } catch (error) {
      console.error('[CLAUDE: Error in handleSend]', error);
      setIsTyping(false);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: Failed to generate response. ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      const newFiles = Array.from(files).map(file => ({ name: file.name, size: file.size }));
      setUploadedFiles(prev => [...prev, ...newFiles]);
    }
  };

  const handleRemoveFile = (index: number) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const updateStep = (messageContent: string) => {
    const content = messageContent.toLowerCase();
    
    // Find the first step that matches keywords in the message
    for (let i = AGENT_CREATION_STEPS.length - 1; i >= 0; i--) {
      const step = AGENT_CREATION_STEPS[i];
      if (step.keywords.some(keyword => content.includes(keyword))) {
        setCurrentStep(Math.min(step.id + 1, AGENT_CREATION_STEPS.length));
        return;
      }
    }
  };

  const addMultiAgent = (agentId: string) => {
    const agent = availableAgents.find((a) => a.id === agentId);
    if (agent && !multiAgentNodes.find((n) => n.id === agent.id)) {
      setMultiAgentNodes([...multiAgentNodes, agent]);
    }
  };

  const handleTestRepo = async () => {
    setIsTestingRepo(true);
    setTestError('');
    setTestResult(null);
    
    try {
      const result = await apiClient.testRepoInitialization();
      setTestResult(result);
    } catch (error: any) {
      setTestError(error.message || 'Failed to test repository initialization');
    } finally {
      setIsTestingRepo(false);
    }
  };

  // === [CLAUDE: ADDED] Save confab handler that compiles collected inputs and calls createConfab ===
  const handleSaveConfab = async () => {
    setIsConfabCreating(true);
    setSaveResult(null);

    try {
      const confabName = `Confab - ${new Date().toLocaleString()}`;
      const confabDescription = purposeText || 'Created via agent chat';

      const confabConfig: any = {
        conversation: {
          system_prompt: purposeText || 'You are an assistant for this confab.',
          memory_enabled: memoryEnabledLocal,
        },
        integrations: {
          apis: []
        },
        custom_settings: {
          sample_io: sampleIO,
          guardrails: guardrailsText,
          memory_notes: memoryNotes
        }
      };

      if (apiKey) {
        confabConfig.integrations.apis.push({ name: 'custom_api', key: apiKey });
      }

      // If user entered explicit repo owner / name, attach into custom settings so backend may use it
      if (repoOwnerInput || repoNameInput) {
        confabConfig.custom_settings.repo_override = {
          owner: repoOwnerInput,
          repo: repoNameInput
        };
      }

      const response = await apiClient.createConfab({
        name: confabName,
        description: confabDescription,
        config: confabConfig
      });

      setSaveResult(response);
      if (response?.id) {
        setCurrentConfabId(response.id);
      }
    } catch (error:any) {
      setSaveResult({ error: error.message || 'Failed to save confab' });
    } finally {
      setIsConfabCreating(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-lg flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-slate-900">Create New Confab</h2>
              <p className="text-slate-600 text-sm">Chat with AI to build your confab</p>
            </div>
          </div>
          <Badge variant="secondary" className="gap-1">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            Active
          </Badge>
        </div>
        
        {/* Progress Bar */}
        <div className="mt-6">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-slate-700">
              Step {currentStep} of {AGENT_CREATION_STEPS.length}
            </span>
            <span className="text-sm text-slate-600">
              {AGENT_CREATION_STEPS[currentStep - 1]?.label}
            </span>
          </div>
          <Progress value={(currentStep / AGENT_CREATION_STEPS.length) * 100} className="h-2" />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Steps Panel */}
        <div className="space-y-4">
          <Card className="p-4">
            <h3 className="text-slate-900 mb-3">Configuration Steps</h3>
            <div className="space-y-2">
              {AGENT_CREATION_STEPS.map(step => (
                <div 
                  key={step.id} 
                  className={`text-sm p-3 rounded-lg transition-all ${
                    step.id === currentStep 
                      ? 'bg-indigo-100 text-indigo-700 border-2 border-indigo-300' 
                      : step.id < currentStep 
                      ? 'bg-green-50 text-green-700 border border-green-200' 
                      : 'bg-slate-50 text-slate-500 border border-slate-200'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                      step.id === currentStep 
                        ? 'bg-indigo-600 text-white' 
                        : step.id < currentStep 
                        ? 'bg-green-600 text-white' 
                        : 'bg-slate-300 text-white'
                    }`}>
                      {step.id}
                    </div>
                    <span>{step.label}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Add Collaborators Step */}
          {/* Define Purpose Step */}
          {currentStep >= 1 && (
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles className="w-5 h-5 text-slate-900" />
                <h3 className="text-slate-900">Define Purpose</h3>
              </div>
              <div className="space-y-3">
                <Textarea
                  value={purposeText}
                  onChange={(e) => setPurposeText(e.target.value)}
                  placeholder="Describe the purpose of this confab (this will be written to PURPOSE.md)"
                  className="text-sm min-h-[80px]"
                />
                <p className="text-xs text-slate-600">This will be saved to the repository as PURPOSE.md inside the confab directory.</p>
              </div>
            </Card>
          )}

          {currentStep >= 2 && (
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Users className="w-5 h-5 text-slate-900" />
                <h3 className="text-slate-900">Add Participants</h3>
              </div>
              <div className="space-y-3">
                <div className="flex gap-2">
                  <Input
                    type="email"
                    placeholder="Enter email address"
                    className="text-sm"
                  />
                  <Button size="sm" variant="outline">
                    <Mail className="w-3 h-3" />
                  </Button>
                </div>
                <p className="text-xs text-slate-600">
                  Invite team members to participate in this confab
                </p>
                <div>
                  <Label className="text-xs">Permission Level</Label>
                  <Select defaultValue="editor">
                    <SelectTrigger className="mt-1 text-xs h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="viewer">Viewer</SelectItem>
                      <SelectItem value="editor">Editor</SelectItem>
                      <SelectItem value="admin">Admin</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </Card>
          )}

          {/* Configure Memory Step */}
          {currentStep >= 3 && (
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Shield className="w-5 h-5 text-slate-900" />
                <h3 className="text-slate-900">Configure Memory</h3>
              </div>
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Checkbox checked={memoryEnabledLocal} onCheckedChange={(v:any) => setMemoryEnabledLocal(!!v)} />
                  <Label className="text-sm">Enable long-term memory</Label>
                </div>
                <Textarea
                  value={memoryNotes}
                  onChange={(e) => setMemoryNotes(e.target.value)}
                  placeholder="Notes about what the agent should remember (optional)"
                  className="text-sm min-h-[80px]"
                />
                <p className="text-xs text-slate-600">Memory helps the agent remember important details across conversations.</p>
              </div>
            </Card>
          )}

          {/* GitHub Repository Information */}
          <Card className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Github className="w-5 h-5 text-slate-900" />
              <h3 className="text-slate-900">Repository Configuration</h3>
            </div>
            <div className="space-y-3">
              {/* === [CLAUDE: Ollama Service Status Display] === */}
              {!ollamaHealthy && (
                <div className="p-3 bg-yellow-50 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <AlertCircle className="w-4 h-4 text-yellow-600" />
                    <span className="text-sm font-medium text-yellow-800">
                      Ollama Service Status
                    </span>
                  </div>
                  <p className="text-sm text-yellow-700">{ollamaError || 'Ollama is not available'}</p>
                  <p className="text-xs text-yellow-600 mt-1">
                    Ensure Ollama is running at http://localhost:11434 for dynamic chat responses
                  </p>
                </div>
              )}
              
              {ollamaHealthy && (
                <div className="p-3 bg-green-50 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <CheckCircle className="w-4 h-4 text-green-600" />
                    <span className="text-sm font-medium text-green-800">
                      Ollama Service Active
                    </span>
                  </div>
                  <p className="text-xs text-green-600">
                    Using model: gemma3:4b | Connection: http://localhost:11434
                  </p>
                </div>
              )}

              <div className="p-3 bg-blue-50 rounded-lg">
                <p className="text-sm text-blue-800">
                  <strong>Repository Naming Convention:</strong>
                </p>
                <p className="text-sm text-blue-700 mt-1">
                  {getRepoNamingConvention()}
                </p>
              </div>

              {/* === [CLAUDE: ADDED Tools & APIs inputs for Step 4] === */}
              {currentStep >= 4 && (
                <div className="mt-3">
                  <Label className="text-xs">API Key / Tool Secret</Label>
                  <Input
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    type="password"
                    placeholder="Optional: paste API key for external tool"
                    className="mt-1 text-sm"
                  />

                  <div className="flex gap-2 mt-2">
                    <Input
                      value={repoOwnerInput}
                      onChange={(e) => setRepoOwnerInput(e.target.value)}
                      placeholder="Repository owner (optional)"
                      className="text-sm"
                    />
                    <Input
                      value={repoNameInput}
                      onChange={(e) => setRepoNameInput(e.target.value)}
                      placeholder="Repository name (optional)"
                      className="text-sm"
                    />
                  </div>
                  <p className="text-xs text-slate-600 mt-1">If provided, these values will be used when creating the confab files (overrides connected GitHub settings).</p>
                </div>
              )}
              
              <div className="flex items-center gap-2">
                <Button
                  onClick={handleTestRepo}
                  disabled={isTestingRepo}
                  variant="outline"
                  size="sm"
                  className="gap-2"
                >
                  <TestTube className="w-4 h-4" />
                  {isTestingRepo ? 'Testing...' : 'TEST'}
                </Button>
                <span className="text-sm text-slate-600">
                  Initialize repository with dummy data
                </span>

                {currentStep >= 7 && (
                  <div className="ml-2">
                    <Button
                      onClick={handleSaveConfab}
                      disabled={isConfabCreating}
                      size="sm"
                      className="gap-2"
                    >
                      {isConfabCreating ? 'Saving...' : 'Save & Create'}
                    </Button>
                  </div>
                )}
              </div>
              
              {testResult && (
                <div className="p-3 bg-green-50 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <CheckCircle className="w-4 h-4 text-green-600" />
                    <span className="text-sm font-medium text-green-800">
                      Test Successful
                    </span>
                  </div>
                  <p className="text-sm text-green-700 mb-2">
                    {testResult.message}
                  </p>
                  <div className="text-xs text-green-600">
                    <p><strong>Repository:</strong> {testResult.repo_name}</p>
                    <p><strong>Status:</strong> {testResult.status}</p>
                    {testResult.dummy_data && (
                      <p><strong>Test Files:</strong> {testResult.dummy_data.test_files?.join(', ')}</p>
                    )}
                  </div>
                </div>
              )}
              
              {testError && (
                <div className="p-3 bg-red-50 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <AlertCircle className="w-4 h-4 text-red-600" />
                    <span className="text-sm font-medium text-red-800">
                      Test Failed
                    </span>
                  </div>
                  <p className="text-sm text-red-700">{testError}</p>
                </div>
              )}

              {/* === [CLAUDE: ADDED Guardrails (Step 5) and Samples (Step 6) inside repo card] === */}
              {currentStep >= 5 && (
                <div className="p-3 bg-slate-50 rounded-lg mt-3">
                  <h4 className="text-sm font-medium mb-2">Guardrails</h4>
                  <Textarea
                    value={guardrailsText}
                    onChange={(e) => setGuardrailsText(e.target.value)}
                    placeholder="Optional: add guardrails that will be saved to GUARDRAILS.md"
                    className="text-sm min-h-[80px]"
                  />
                </div>
              )}

              {currentStep >= 6 && (
                <div className="p-3 bg-slate-50 rounded-lg mt-3">
                  <h4 className="text-sm font-medium mb-2">Sample Inputs / Outputs</h4>
                  <Textarea
                    value={sampleIO}
                    onChange={(e) => setSampleIO(e.target.value)}
                    placeholder={'Examples:\nUser: How do I reset my password?\nAssistant: Ask the user to confirm email...'}
                    className="text-sm min-h-[80px]"
                  />
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* Conversation Area */}
        <div className="lg:col-span-2">
          <Card className="flex flex-col min-h-[600px]">
            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {message.role === 'assistant' && (
                    <Avatar className="w-8 h-8 flex-shrink-0">
                      <AvatarFallback className="bg-gradient-to-br from-indigo-600 to-purple-600">
                        <Bot className="w-4 h-4 text-white" />
                      </AvatarFallback>
                    </Avatar>
                  )}
                  <div
                    className={`max-w-[80%] rounded-lg px-4 py-3 ${
                      message.role === 'user'
                        ? 'bg-indigo-600 text-white'
                        : 'bg-slate-100 text-slate-900'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{message.content}</p>
                    <p
                      className={`text-xs mt-1 ${
                        message.role === 'user' ? 'text-indigo-200' : 'text-slate-500'
                      }`}
                    >
                      {message.timestamp.toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>
                  {message.role === 'user' && (
                    <div className="flex flex-col items-center gap-1">
                      <Avatar className="w-8 h-8 flex-shrink-0">
                        <AvatarFallback className="bg-slate-300">
                          <User className="w-4 h-4 text-slate-600" />
                        </AvatarFallback>
                      </Avatar>
                      <span className="text-xs text-slate-600">{user?.name ?? 'You'}</span>
                    </div>
                  )}
                </div>
              ))}
              
              {isTyping && (
                <div className="flex gap-3 justify-start">
                  <Avatar className="w-8 h-8 flex-shrink-0">
                    <AvatarFallback className="bg-gradient-to-br from-indigo-600 to-purple-600">
                      <Bot className="w-4 h-4 text-white" />
                    </AvatarFallback>
                  </Avatar>
                  <div className="bg-slate-100 rounded-lg px-4 py-3 flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-slate-600" />
                    <span className="text-slate-600">Assistant is thinking...</span>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="border-t border-slate-200 p-4">
              <div className="flex gap-2">
                <Textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Describe what you want your confab to do..."
                  className="min-h-[60px] max-h-32 resize-none"
                />
                <div className="flex flex-col gap-2">
                  <Button
                    onClick={handleSend}
                    disabled={!input.trim() || isTyping}
                    size="icon"
                    className="h-[60px]"
                  >
                    <Send className="w-5 h-5" />
                  </Button>
                  <Button
                    onClick={() => onNavigate('dashboard')}
                    variant="outline"
                    size="icon"
                    title="Save and continue later"
                  >
                    <Save className="w-5 h-5" />
                  </Button>
                  {currentThreadId && (
                    <span className="text-xs text-emerald-600 self-center" title="Conversation saved to Review Chats">
                      Saved
                    </span>
                  )}
                </div>
              </div>
              <p className="text-xs text-slate-500 mt-2">
                Press Enter to send, Shift+Enter for new line
              </p>
              
              {/* Prompt Suggestions */}
              {messages.length === 1 && (
                <div className="mt-4">
                  <p className="text-xs text-slate-600 mb-2">Try these examples:</p>
                  <div className="flex gap-2 overflow-x-auto pb-2 -mx-4 px-4">
                    {PROMPT_SUGGESTIONS.map((suggestion, index) => (
                      <button
                        key={index}
                        onClick={() => handleSuggestionClick(suggestion)}
                        className="flex-shrink-0 text-left p-3 rounded-lg border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors text-sm text-slate-700 hover:text-indigo-700 min-w-[280px]"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              
              {/* File Upload */}
              <div className="mt-4">
                <div className="flex items-center gap-2">
                  <input
                    type="file"
                    multiple
                    onChange={handleFileUpload}
                    className="hidden"
                    id="file-upload"
                  />
                  <label
                    htmlFor="file-upload"
                    className="inline-flex items-center gap-2 px-3 py-2 text-sm cursor-pointer rounded-lg border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 transition-colors"
                  >
                    <Paperclip className="w-4 h-4" />
                    Upload Document
                  </label>
                  <span className="text-xs text-slate-500">PDF, TXT, DOCX (optional)</span>
                </div>
                {uploadedFiles.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {uploadedFiles.map((file, index) => (
                      <div key={index} className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                        <div className="flex items-center gap-2">
                          <File className="w-4 h-4 text-slate-600" />
                          <p className="text-sm text-slate-700">{file.name}</p>
                          <span className="text-xs text-slate-500">
                            ({(file.size / 1024).toFixed(1)} KB)
                          </span>
                        </div>
                        <button
                          onClick={() => handleRemoveFile(index)}
                          className="text-slate-400 hover:text-red-600 transition-colors"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </Card>
        </div>

        {/* Participants Sidebar — logged-in user only (name + email from users table) */}
        <div className="lg:col-span-1">
          <Card className="p-4">
            <div className="flex items-center gap-2 mb-4">
              <Users className="w-5 h-5 text-slate-900" />
              <h3 className="text-slate-900">Participants</h3>
            </div>
            {user ? (
              <div className="space-y-3">
                <div className="flex items-center gap-3 p-3 rounded-lg bg-indigo-50 ring-1 ring-indigo-200">
                  <Avatar className="w-9 h-9">
                    <AvatarFallback className="bg-indigo-200 text-indigo-700">
                      {user.name.split(' ').map(n => n[0]).join('') || '?'}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 truncate">{user.name}</p>
                    <p className="text-xs text-slate-500 truncate">{user.email}</p>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-500 py-2">Sign in to see your profile.</p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}