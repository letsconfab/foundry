import { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, Save, Loader2, Paperclip, File, X, Github, Plus, Bot, Shield, Network, Users, Mail, User } from 'lucide-react';
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

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'confab-chat';

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

interface Participant {
  id: string;
  name: string;
  email?: string;
  role: 'owner' | 'admin' | 'editor' | 'viewer';
  avatar?: string;
  isOnline: boolean;
  type: 'user' | 'confab';
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
  { id: 7, label: 'Link GitHub Account', keywords: ['github', 'repository', 'repo', 'code', 'version'] },
  { id: 8, label: 'Review & Save', keywords: ['review', 'summary', 'confirm', 'save', 'finish'] },
];

export function AgentChat({ onNavigate }: AgentChatProps) {
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
  
  // Multi-Agent State
  const [multiAgentNodes, setMultiAgentNodes] = useState<AgentNode[]>([]);
  const [moderatorRules, setModeratorRules] = useState('');
  const [tieBreaker, setTieBreaker] = useState('');
  const [enableConflictResolution, setEnableConflictResolution] = useState(true);
  const [maxTurnsPerAgent, setMaxTurnsPerAgent] = useState('3');
  const [githubConnected, setGithubConnected] = useState(false);

  // Participants State
  const [participants] = useState<Participant[]>([
    { id: '1', name: 'John Smith', email: 'john@example.com', role: 'owner', isOnline: true, type: 'user' },
    { id: '2', name: 'Sarah Chen', email: 'sarah@example.com', role: 'editor', isOnline: true, type: 'user' },
    { id: '3', name: 'Mike Johnson', email: 'mike@example.com', role: 'viewer', isOnline: false, type: 'user' },
    { id: '4', name: 'Customer Support Bot', role: 'admin', isOnline: true, type: 'confab' },
    { id: '5', name: 'Data Analyzer', role: 'editor', isOnline: true, type: 'confab' },
    { id: '6', name: 'Code Review Assistant', role: 'viewer', isOnline: false, type: 'confab' },
  ]);
  const [currentUser] = useState('John Smith');

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

  const handleSend = () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    // Simulate AI response
    setTimeout(() => {
      const responses = [
        "Great! I'm building a confab that can help with that. What LLM provider would you prefer? We support OpenAI, Anthropic, Google AI, and more.",
        "Perfect! I'm configuring those capabilities now. Would you like this confab to have memory of past conversations?",
        "Excellent choice! Your confab is taking shape. Should it have access to any specific tools or APIs?",
        "Looking good! Let me summarize what we've built so far and you can review the configuration.",
      ];
      
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: responses[messages.filter(m => m.role === 'user').length % responses.length],
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setIsTyping(false);
      updateStep(assistantMessage.content);
    }, 1000);
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

          {/* GitHub Account Step */}
          {currentStep >= 7 && (
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Github className="w-5 h-5 text-slate-900" />
                <h3 className="text-slate-900">GitHub Account</h3>
              </div>
              {!githubConnected ? (
                <Button
                  onClick={() => setGithubConnected(true)}
                  className="w-full gap-2"
                  variant="outline"
                >
                  <Github className="w-4 h-4" />
                  Connect GitHub
                </Button>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 p-2 bg-green-50 rounded-lg">
                    <div className="w-2 h-2 bg-green-500 rounded-full" />
                    <span className="text-sm text-green-700">GitHub Connected</span>
                  </div>
                  <Input placeholder="Repository name (optional)" className="text-sm" />
                </div>
              )}
            </Card>
          )}
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
                      <span className="text-xs text-slate-600">{currentUser}</span>
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

        {/* Participants Sidebar */}
        <div className="lg:col-span-1">
          <Card className="p-4">
            <div className="flex items-center gap-2 mb-4">
              <Users className="w-5 h-5 text-slate-900" />
              <h3 className="text-slate-900">Participants</h3>
              <Badge variant="secondary" className="ml-auto">{participants.length}</Badge>
            </div>
            <div className="space-y-3">
              {participants.map((participant) => (
                <div key={participant.id} className="flex items-center gap-3">
                  <div className="relative">
                    <Avatar className="w-9 h-9">
                      <AvatarFallback className={`${
                        participant.type === 'confab'
                          ? 'bg-purple-100 text-purple-700'
                          : participant.role === 'owner' 
                          ? 'bg-indigo-100 text-indigo-700' 
                          : 'bg-slate-200 text-slate-700'
                      }`}>
                        {participant.type === 'confab' ? <Bot className="w-4 h-4" /> : participant.name.split(' ').map(n => n[0]).join('')}
                      </AvatarFallback>
                    </Avatar>
                    <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-white ${
                      participant.isOnline ? 'bg-green-500' : 'bg-slate-400'
                    }`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <p className="text-sm text-slate-900 truncate">{participant.name}</p>
                      {participant.type === 'confab' && (
                        <Badge variant="secondary" className="text-[10px] h-4 px-1">Confab</Badge>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 capitalize">{participant.role}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}