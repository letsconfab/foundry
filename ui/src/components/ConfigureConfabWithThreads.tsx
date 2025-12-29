import { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, Save, Loader2, Paperclip, File, X, Github, Plus, Bot, Shield, Network, Users, Mail, User, ArrowLeft, Folder, FileText, ChevronRight, ChevronDown, ChevronLeft, Menu, MessageSquare, List } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Label } from './ui/label';
import { Input } from './ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { Avatar, AvatarFallback } from './ui/avatar';

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'confab-chat' | 'configure';

interface ConfigureConfabProps {
  onNavigate: (view: View, confabName?: string) => void;
  confabName: string;
  version: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  userName?: string;
}

interface SubThread {
  id: string;
  parentMessageId: string;
  title: string;
  messages: Message[];
  createdAt: Date;
}

interface UploadedFile {
  name: string;
  size: number;
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
  "Add a new capability to handle product recommendations",
  "Update the response tone to be more professional",
  "Add integration with Slack for notifications",
  "Improve memory retention for customer preferences",
];

const AGENT_CREATION_STEPS = [
  { id: 1, label: 'GitHub Account', keywords: ['github', 'repository', 'repo', 'code', 'version'] },
  { id: 2, label: 'Purpose', keywords: ['what', 'do', 'help', 'agent', 'create', 'build'] },
  { id: 3, label: 'Participants', keywords: ['participant', 'collaborator', 'team', 'member', 'invite', 'share', 'permission'] },
  { id: 4, label: 'Memory', keywords: ['memory', 'remember', 'conversation', 'history', 'context'] },
  { id: 5, label: 'Tools & APIs', keywords: ['tool', 'api', 'access', 'integrate', 'connect'] },
  { id: 6, label: 'Guardrails', keywords: ['guardrail', 'safety', 'limit', 'restrict', 'boundary', 'rule', 'policy'] },
  { id: 7, label: 'Sample Inputs/Outputs', keywords: ['sample', 'example', 'input', 'output', 'test', 'response', 'demo'] },
  { id: 8, label: 'Review & Save', keywords: ['review', 'summary', 'confirm', 'save', 'finish'] },
];

export function ConfigureConfabWithThreads({ onNavigate, confabName, version }: ConfigureConfabProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: `Hi! I'm ready to help you configure "${confabName}". What would you like to update or change?`,
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedConfigStep, setSelectedConfigStep] = useState<number | null>(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [githubConnected, setGithubConnected] = useState(true);
  const [currentUser] = useState('John Smith');

  // Thread State
  const [subThreads, setSubThreads] = useState<SubThread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [showThreadsList, setShowThreadsList] = useState(false);
  const [hoveredMessageId, setHoveredMessageId] = useState<string | null>(null);
  const [expandedThreads, setExpandedThreads] = useState<Set<string>>(new Set());

  // Participants State
  const [participants] = useState<Participant[]>([
    { id: '1', name: 'John Smith', email: 'john@example.com', role: 'owner', isOnline: true, type: 'user' },
    { id: '2', name: 'Sarah Chen', email: 'sarah@example.com', role: 'editor', isOnline: true, type: 'user' },
    { id: '3', name: 'Mike Johnson', email: 'mike@example.com', role: 'viewer', isOnline: false, type: 'user' },
    { id: '4', name: 'Customer Support Bot', role: 'admin', isOnline: true, type: 'confab' },
    { id: '5', name: 'Data Analyzer', role: 'editor', isOnline: true, type: 'confab' },
    { id: '6', name: 'Code Review Assistant', role: 'viewer', isOnline: false, type: 'confab' },
  ]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, activeThreadId]);

  const handleSend = () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    if (activeThreadId) {
      // Add to subthread
      setSubThreads(prev => prev.map(thread => 
        thread.id === activeThreadId 
          ? { ...thread, messages: [...thread.messages, userMessage] }
          : thread
      ));
    } else {
      // Add to main conversation
      setMessages((prev) => [...prev, userMessage]);
    }
    
    setInput('');
    setIsTyping(true);

    // Simulate AI response
    setTimeout(() => {
      const responses = [
        "Great! I'm updating the confab configuration with that change. What LLM provider would you prefer for this update? We support OpenAI, Anthropic, Google AI, and more.",
        "Perfect! I'm configuring those capabilities now. Would you like to adjust the memory settings for this confab?",
        "Excellent choice! Your confab configuration is being updated. Should I modify any tool or API access?",
        "Looking good! Let me summarize what we've configured and you can review the changes before saving.",
      ];
      
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: responses[messages.filter(m => m.role === 'user').length % responses.length],
        timestamp: new Date(),
      };

      if (activeThreadId) {
        setSubThreads(prev => prev.map(thread => 
          thread.id === activeThreadId 
            ? { ...thread, messages: [...thread.messages, assistantMessage] }
            : thread
        ));
      } else {
        setMessages((prev) => [...prev, assistantMessage]);
      }
      
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
    
    for (let i = AGENT_CREATION_STEPS.length - 1; i >= 0; i--) {
      const step = AGENT_CREATION_STEPS[i];
      if (step.keywords.some(keyword => content.includes(keyword))) {
        setCurrentStep(Math.min(step.id + 1, AGENT_CREATION_STEPS.length));
        return;
      }
    }
  };

  const createSubThread = (parentMessageId: string) => {
    const parentMessage = messages.find(m => m.id === parentMessageId);
    if (!parentMessage) return;

    const newThread: SubThread = {
      id: `thread-${Date.now()}`,
      parentMessageId,
      title: `Discussion: ${parentMessage.content.substring(0, 40)}...`,
      messages: [],
      createdAt: new Date(),
    };

    setSubThreads(prev => [...prev, newThread]);
    setActiveThreadId(newThread.id);
    setShowThreadsList(false);
  };

  const toggleThreadExpansion = (threadId: string) => {
    setExpandedThreads(prev => {
      const newSet = new Set(prev);
      if (newSet.has(threadId)) {
        newSet.delete(threadId);
      } else {
        newSet.add(threadId);
      }
      return newSet;
    });
  };

  const getThreadSummary = (thread: SubThread) => {
    if (thread.messages.length === 0) return "No messages yet";
    const lastMessage = thread.messages[thread.messages.length - 1];
    return lastMessage.content.substring(0, 80) + (lastMessage.content.length > 80 ? "..." : "");
  };

  const getThreadsByParent = (parentId: string) => {
    return subThreads.filter(thread => thread.parentMessageId === parentId);
  };

  const getCurrentMessages = () => {
    if (activeThreadId) {
      const thread = subThreads.find(t => t.id === activeThreadId);
      return thread?.messages || [];
    }
    return messages;
  };

  const backToMainThread = () => {
    setActiveThreadId(null);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onNavigate('dashboard')}
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div className="w-10 h-10 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-lg flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-slate-900">Configure Confab</h2>
                <Badge variant="outline" className="text-xs">
                  v{version}
                </Badge>
              </div>
              <p className="text-slate-600 text-sm">{confabName}</p>
            </div>
          </div>
          <Badge variant="secondary" className="gap-1">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            Active
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Collapsed Sidebar Toggle Button */}
        {isSidebarCollapsed && (
          <div className="fixed left-4 top-1/2 -translate-y-1/2 z-10">
            <Button
              variant="outline"
              size="icon"
              className="h-10 w-10 shadow-lg"
              onClick={() => setIsSidebarCollapsed(false)}
              title="Expand sidebar"
            >
              <ChevronRight className="w-5 h-5" />
            </Button>
          </div>
        )}

        {/* Steps Panel */}
        {!isSidebarCollapsed && (
          <div className="space-y-4">
            <Card className="p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-slate-900">Configuration</h3>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => setIsSidebarCollapsed(true)}
                  title="Collapse sidebar"
                >
                  <ChevronLeft className="w-4 h-4" />
                </Button>
              </div>
            <div className="space-y-2">
              {AGENT_CREATION_STEPS.map(step => (
                <button
                  key={step.id}
                  onClick={() => setSelectedConfigStep(step.id)}
                  className={`w-full text-sm p-3 rounded-lg transition-all text-left ${
                    selectedConfigStep === step.id
                      ? 'bg-indigo-600 text-white border-2 border-indigo-700'
                      : step.id === currentStep 
                      ? 'bg-indigo-100 text-indigo-700 border-2 border-indigo-300' 
                      : step.id < currentStep 
                      ? 'bg-green-50 text-green-700 border border-green-200 hover:bg-green-100' 
                      : 'bg-slate-50 text-slate-500 border border-slate-200 hover:bg-slate-100'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                      selectedConfigStep === step.id
                        ? 'bg-white text-indigo-600'
                        : step.id === currentStep 
                        ? 'bg-indigo-600 text-white' 
                        : step.id < currentStep 
                        ? 'bg-green-600 text-white' 
                        : 'bg-slate-300 text-white'
                    }`}>
                      {step.id}
                    </div>
                    <span>{step.label}</span>
                  </div>
                </button>
              ))}
            </div>
            </Card>
          </div>
        )}

        {/* Center Panel - Dynamic Content Based on Selected Step */}
        <div className={isSidebarCollapsed ? "lg:col-span-2" : "lg:col-span-2"}>
          {/* Default view when no step is selected */}
          {!selectedConfigStep && (
            <Card className="p-6">
              <div className="text-center py-12">
                <div className="w-16 h-16 bg-indigo-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Sparkles className="w-8 h-8 text-indigo-600" />
                </div>
                <h3 className="text-slate-900 mb-2">Select a Configuration Step</h3>
                <p className="text-sm text-slate-600 max-w-sm mx-auto">
                  Choose a step from the left sidebar to view and edit that configuration section
                </p>
              </div>
            </Card>
          )}

          {/* Step 1: GitHub Account */}
          {selectedConfigStep === 1 && (
            <Card className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <Github className="w-5 h-5 text-slate-900" />
                <h3 className="text-slate-900">GitHub Integration</h3>
              </div>
              
              {githubConnected ? (
                <div className="space-y-4">
                  <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 bg-green-600 rounded-full flex items-center justify-center flex-shrink-0">
                        <Github className="w-5 h-5 text-white" />
                      </div>
                      <div className="flex-1">
                        <h4 className="text-green-900 mb-1">Connected to GitHub</h4>
                        <p className="text-sm text-green-700 mb-2">@johnsmith/confab-agents</p>
                        <p className="text-xs text-green-600">Last synced: 2 hours ago</p>
                      </div>
                    </div>
                  </div>
                  
                  <div className="space-y-3">
                    <div>
                      <Label className="text-sm text-slate-700">Repository</Label>
                      <Input 
                        value="johnsmith/confab-agents" 
                        readOnly 
                        className="mt-1 bg-slate-50"
                      />
                    </div>
                    <div>
                      <Label className="text-sm text-slate-700">Branch</Label>
                      <Select defaultValue="main">
                        <SelectTrigger className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="main">main</SelectItem>
                          <SelectItem value="develop">develop</SelectItem>
                          <SelectItem value="staging">staging</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  
                  <div className="flex gap-2 pt-2">
                    <Button variant="outline" className="flex-1 gap-2">
                      <Github className="w-4 h-4" />
                      Change Repository
                    </Button>
                    <Button variant="outline" className="gap-2">
                      Sync Now
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8">
                  <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <Github className="w-8 h-8 text-slate-600" />
                  </div>
                  <h4 className="text-slate-900 mb-2">Connect to GitHub</h4>
                  <p className="text-sm text-slate-600 mb-6 max-w-sm mx-auto">
                    Link your GitHub account to store and version control your confab configuration
                  </p>
                  <Button className="gap-2">
                    <Github className="w-4 h-4" />
                    Connect GitHub Account
                  </Button>
                </div>
              )}
            </Card>
          )}

          {/* Step 2: Purpose */}
          {selectedConfigStep === 2 && (
            <Card className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <FileText className="w-5 h-5 text-slate-900" />
                <h3 className="text-slate-900">Confab Purpose</h3>
                <Badge variant="secondary" className="ml-auto text-xs">purpose.md</Badge>
              </div>
              
              <div className="space-y-4">
                <div>
                  <Label className="text-sm text-slate-700 mb-2 block">Purpose Definition</Label>
                  <Textarea 
                    className="min-h-[400px] font-mono text-sm"
                    defaultValue={`# ${confabName} Purpose

## Overview
This confab is designed to assist users with intelligent, context-aware responses for customer support and product inquiries.

## Primary Objectives
- Provide accurate and helpful responses to customer queries
- Maintain a professional and friendly tone
- Escalate complex issues to human agents when necessary
- Learn from interactions to improve response quality

## Key Capabilities
- Natural language understanding
- Multi-turn conversation handling
- Integration with knowledge base
- Sentiment analysis and adaptive responses

## Success Metrics
- Customer satisfaction scores
- Response accuracy rate
- Average resolution time
- Escalation rate

## Constraints
- Must not provide medical or legal advice
- Should respect user privacy and data protection
- Cannot make financial commitments on behalf of the company`}
                  />
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" className="flex-1">
                    Reset to Default
                  </Button>
                  <Button className="flex-1">
                    Save Purpose
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {/* Step 3: Participants */}
          {selectedConfigStep === 3 && (
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
              <div className="mt-4 pt-4 border-t border-slate-200">
                <Button variant="outline" size="sm" className="w-full gap-2">
                  <Plus className="w-4 h-4" />
                  Add Participant
                </Button>
              </div>
            </Card>
          )}

          {/* Step 4: Memory */}
          {selectedConfigStep === 4 && (
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-4">
                <Folder className="w-5 h-5 text-slate-900" />
                <h3 className="text-slate-900">Memory & Files</h3>
                <Badge variant="secondary" className="ml-auto text-xs">GitHub Repo</Badge>
              </div>
              <div className="space-y-2">
                {/* Root Files */}
                <div className="space-y-1">
                  <div className="flex items-center gap-2 p-2 hover:bg-slate-50 rounded-lg cursor-pointer">
                    <FileText className="w-4 h-4 text-slate-600" />
                    <span className="text-sm text-slate-900">README.md</span>
                    <span className="text-xs text-slate-500 ml-auto">2 KB</span>
                  </div>
                  <div className="flex items-center gap-2 p-2 hover:bg-slate-50 rounded-lg cursor-pointer">
                    <FileText className="w-4 h-4 text-slate-600" />
                    <span className="text-sm text-slate-900">purpose.md</span>
                    <span className="text-xs text-slate-500 ml-auto">1.5 KB</span>
                  </div>
                </div>

                {/* Conversation History Folder */}
                <div className="space-y-1">
                  <div className="flex items-center gap-2 p-2 hover:bg-slate-50 rounded-lg cursor-pointer">
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                    <Folder className="w-4 h-4 text-blue-600" />
                    <span className="text-sm text-slate-900">conversations/</span>
                  </div>
                  <div className="ml-6 space-y-1">
                    <div className="flex items-center gap-2 p-2 hover:bg-slate-50 rounded-lg cursor-pointer">
                      <FileText className="w-4 h-4 text-slate-600" />
                      <span className="text-xs text-slate-700">session_2024-01.json</span>
                      <span className="text-xs text-slate-500 ml-auto">45 KB</span>
                    </div>
                    <div className="flex items-center gap-2 p-2 hover:bg-slate-50 rounded-lg cursor-pointer">
                      <FileText className="w-4 h-4 text-slate-600" />
                      <span className="text-xs text-slate-700">session_2024-02.json</span>
                      <span className="text-xs text-slate-500 ml-auto">38 KB</span>
                    </div>
                  </div>
                </div>

                {/* Knowledge Base Folder */}
                <div className="space-y-1">
                  <div className="flex items-center gap-2 p-2 hover:bg-slate-50 rounded-lg cursor-pointer">
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                    <Folder className="w-4 h-4 text-purple-600" />
                    <span className="text-sm text-slate-900">knowledge/</span>
                  </div>
                  <div className="ml-6 space-y-1">
                    <div className="flex items-center gap-2 p-2 hover:bg-slate-50 rounded-lg cursor-pointer">
                      <File className="w-4 h-4 text-slate-600" />
                      <span className="text-xs text-slate-700">product_guide.pdf</span>
                      <span className="text-xs text-slate-500 ml-auto">2.3 MB</span>
                    </div>
                    <div className="flex items-center gap-2 p-2 hover:bg-slate-50 rounded-lg cursor-pointer">
                      <File className="w-4 h-4 text-slate-600" />
                      <span className="text-xs text-slate-700">faq_database.txt</span>
                      <span className="text-xs text-slate-500 ml-auto">156 KB</span>
                    </div>
                    <div className="flex items-center gap-2 p-2 hover:bg-slate-50 rounded-lg cursor-pointer">
                      <FileText className="w-4 h-4 text-slate-600" />
                      <span className="text-xs text-slate-700">policies.md</span>
                      <span className="text-xs text-slate-500 ml-auto">12 KB</span>
                    </div>
                  </div>
                </div>

                {/* Config Folder */}
                <div className="space-y-1">
                  <div className="flex items-center gap-2 p-2 hover:bg-slate-50 rounded-lg cursor-pointer">
                    <ChevronRight className="w-4 h-4 text-slate-400" />
                    <Folder className="w-4 h-4 text-green-600" />
                    <span className="text-sm text-slate-900">config/</span>
                  </div>
                </div>
              </div>
              <div className="mt-4 pt-4 border-t border-slate-200">
                <Button variant="outline" size="sm" className="w-full gap-2">
                  <Plus className="w-4 h-4" />
                  Add File to Memory
                </Button>
              </div>
            </Card>
          )}

          {/* Step 5: Tools & APIs */}
          {selectedConfigStep === 5 && (
            <Card className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <Network className="w-5 h-5 text-slate-900" />
                <h3 className="text-slate-900">Tools & APIs</h3>
                <Badge variant="secondary" className="ml-auto text-xs">Optional</Badge>
              </div>
              
              <div className="space-y-3">
                <p className="text-sm text-slate-600 mb-4">
                  Connect MCP tools to extend your confab's capabilities
                </p>
                
                {/* Connected Tools */}
                <div className="space-y-2 mb-6">
                  <Label className="text-sm text-slate-700">Connected Tools</Label>
                  
                  <div className="border border-green-200 bg-green-50 rounded-lg p-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-green-600 rounded flex items-center justify-center">
                        <Bot className="w-4 h-4 text-white" />
                      </div>
                      <div className="flex-1">
                        <p className="text-sm text-green-900">Web Search</p>
                        <p className="text-xs text-green-700">Search the web for real-time information</p>
                      </div>
                      <Button variant="ghost" size="sm" className="text-red-600 hover:text-red-700">
                        Remove
                      </Button>
                    </div>
                  </div>
                  
                  <div className="border border-green-200 bg-green-50 rounded-lg p-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center">
                        <FileText className="w-4 h-4 text-white" />
                      </div>
                      <div className="flex-1">
                        <p className="text-sm text-green-900">Document Analyzer</p>
                        <p className="text-xs text-green-700">Extract insights from documents</p>
                      </div>
                      <Button variant="ghost" size="sm" className="text-red-600 hover:text-red-700">
                        Remove
                      </Button>
                    </div>
                  </div>
                </div>
                
                {/* Available Tools */}
                <div className="space-y-2">
                  <Label className="text-sm text-slate-700">Available MCP Tools</Label>
                  
                  <div className="border border-slate-200 rounded-lg p-3 hover:border-indigo-300 hover:bg-indigo-50 transition-colors cursor-pointer">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-purple-600 rounded flex items-center justify-center">
                        <Mail className="w-4 h-4 text-white" />
                      </div>
                      <div className="flex-1">
                        <p className="text-sm text-slate-900">Email Integration</p>
                        <p className="text-xs text-slate-600">Send and receive emails</p>
                      </div>
                      <Button variant="outline" size="sm">
                        <Plus className="w-3 h-3 mr-1" />
                        Add
                      </Button>
                    </div>
                  </div>
                  
                  <div className="border border-slate-200 rounded-lg p-3 hover:border-indigo-300 hover:bg-indigo-50 transition-colors cursor-pointer">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-orange-600 rounded flex items-center justify-center">
                        <Network className="w-4 h-4 text-white" />
                      </div>
                      <div className="flex-1">
                        <p className="text-sm text-slate-900">Database Query</p>
                        <p className="text-xs text-slate-600">Query SQL databases</p>
                      </div>
                      <Button variant="outline" size="sm">
                        <Plus className="w-3 h-3 mr-1" />
                        Add
                      </Button>
                    </div>
                  </div>
                  
                  <div className="border border-slate-200 rounded-lg p-3 hover:border-indigo-300 hover:bg-indigo-50 transition-colors cursor-pointer">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-pink-600 rounded flex items-center justify-center">
                        <Shield className="w-4 h-4 text-white" />
                      </div>
                      <div className="flex-1">
                        <p className="text-sm text-slate-900">Authentication Service</p>
                        <p className="text-xs text-slate-600">User authentication and authorization</p>
                      </div>
                      <Button variant="outline" size="sm">
                        <Plus className="w-3 h-3 mr-1" />
                        Add
                      </Button>
                    </div>
                  </div>
                </div>
                
                <div className="pt-4">
                  <Button variant="outline" className="w-full gap-2">
                    <Plus className="w-4 h-4" />
                    Browse More Tools
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {/* Step 6: Guardrails */}
          {selectedConfigStep === 6 && (
            <Card className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <Shield className="w-5 h-5 text-slate-900" />
                <h3 className="text-slate-900">Guardrails & Rules</h3>
                <Badge variant="secondary" className="ml-auto text-xs">guardrails.txt</Badge>
              </div>
              
              <div className="space-y-4">
                <div>
                  <Label className="text-sm text-slate-700 mb-2 block">System Prompt Extensions</Label>
                  <Textarea 
                    className="min-h-[400px] font-mono text-sm"
                    defaultValue={`# Guardrails for ${confabName}

## Mandatory Rules (Cannot be overridden)

1. **Privacy & Data Protection**
   - Never share or store personally identifiable information (PII)
   - Do not request sensitive information like passwords or SSNs
   - Comply with GDPR and data protection regulations

2. **Safety & Ethics**
   - Refuse requests for harmful, illegal, or unethical content
   - Do not provide medical, legal, or financial advice
   - Avoid discriminatory or biased responses

3. **Operational Boundaries**
   - Cannot access systems outside designated APIs
   - Must verify user permissions before executing actions
   - Log all interactions for audit purposes

## Behavioral Guidelines

1. **Tone & Communication**
   - Maintain professional and friendly tone
   - Be concise but thorough in responses
   - Acknowledge uncertainty when appropriate

2. **Escalation Triggers**
   - Complex technical issues beyond scope
   - Customer dissatisfaction or complaints
   - Requests requiring human judgment

3. **Content Restrictions**
   - No political or religious discussions
   - Avoid controversial topics
   - Stay within domain expertise

## Error Handling
- Gracefully handle API failures
- Provide clear error messages to users
- Auto-retry with exponential backoff`}
                  />
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" className="flex-1">
                    Reset to Default
                  </Button>
                  <Button className="flex-1">
                    Save Guardrails
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {/* Step 7: Sample Inputs/Outputs */}
          {selectedConfigStep === 7 && (
            <Card className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <FileText className="w-5 h-5 text-slate-900" />
                <h3 className="text-slate-900">Sample Inputs/Outputs</h3>
              </div>
              
              <div className="space-y-4">
                <p className="text-sm text-slate-600">
                  Define example conversations to guide your confab's behavior
                </p>
                
                {/* Sample 1 */}
                <div className="border border-slate-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <Label className="text-sm text-slate-900">Sample Conversation 1</Label>
                    <Button variant="ghost" size="sm" className="h-6 text-xs">
                      <X className="w-3 h-3" />
                    </Button>
                  </div>
                  <div className="space-y-3">
                    <div>
                      <Label className="text-xs text-slate-600">User Input</Label>
                      <Textarea 
                        className="mt-1 text-sm" 
                        rows={2}
                        defaultValue="What are your business hours?"
                      />
                    </div>
                    <div>
                      <Label className="text-xs text-slate-600">Expected Output</Label>
                      <Textarea 
                        className="mt-1 text-sm" 
                        rows={3}
                        defaultValue="Our business hours are Monday through Friday, 9 AM to 6 PM EST. We're closed on weekends and major holidays. If you need assistance outside these hours, you can submit a request through our website and we'll respond within 24 hours."
                      />
                    </div>
                  </div>
                </div>
                
                {/* Sample 2 */}
                <div className="border border-slate-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <Label className="text-sm text-slate-900">Sample Conversation 2</Label>
                    <Button variant="ghost" size="sm" className="h-6 text-xs">
                      <X className="w-3 h-3" />
                    </Button>
                  </div>
                  <div className="space-y-3">
                    <div>
                      <Label className="text-xs text-slate-600">User Input</Label>
                      <Textarea 
                        className="mt-1 text-sm" 
                        rows={2}
                        defaultValue="How do I reset my password?"
                      />
                    </div>
                    <div>
                      <Label className="text-xs text-slate-600">Expected Output</Label>
                      <Textarea 
                        className="mt-1 text-sm" 
                        rows={4}
                        defaultValue="To reset your password:\n1. Go to the login page\n2. Click 'Forgot Password'\n3. Enter your email address\n4. Check your email for a reset link\n5. Follow the link and create a new password\n\nIf you don't receive the email within 5 minutes, please check your spam folder or contact our support team."
                      />
                    </div>
                  </div>
                </div>
                
                <Button variant="outline" className="w-full gap-2">
                  <Plus className="w-4 h-4" />
                  Add Sample Conversation
                </Button>
              </div>
            </Card>
          )}

          {/* Step 8: Review & Save */}
          {selectedConfigStep === 8 && (
            <Card className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <Save className="w-5 h-5 text-slate-900" />
                <h3 className="text-slate-900">Review & Save</h3>
              </div>
              
              <div className="space-y-4">
                <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
                  <h4 className="text-indigo-900 mb-2">Configuration Summary</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-indigo-700">Confab Name:</span>
                      <span className="text-indigo-900">{confabName}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-indigo-700">Version:</span>
                      <span className="text-indigo-900">v{version}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-indigo-700">GitHub:</span>
                      <span className="text-indigo-900">Connected</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-indigo-700">Participants:</span>
                      <span className="text-indigo-900">{participants.length} members</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-indigo-700">MCP Tools:</span>
                      <span className="text-indigo-900">2 connected</span>
                    </div>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <h4 className="text-slate-900 text-sm">Completed Steps</h4>
                  {AGENT_CREATION_STEPS.slice(0, -1).map(step => (
                    <div key={step.id} className="flex items-center gap-2 text-sm">
                      <div className="w-5 h-5 bg-green-600 rounded-full flex items-center justify-center">
                        <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                      <span className="text-slate-700">{step.label}</span>
                    </div>
                  ))}
                </div>
                
                <div className="pt-4 space-y-2">
                  <Button className="w-full gap-2" size="lg">
                    <Save className="w-4 h-4" />
                    Save Configuration
                  </Button>
                  <Button variant="outline" className="w-full" size="lg">
                    Export Configuration
                  </Button>
                </div>
              </div>
            </Card>
          )}
        </div>

        {/* Conversation Area - Right Side */}
        <div className={isSidebarCollapsed ? "lg:col-span-2" : "lg:col-span-1"}>
          <Card className="flex flex-col min-h-[600px]">
            {/* Header with Thread Navigation */}
            <div className="border-b border-slate-200 p-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                {activeThreadId && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={backToMainThread}
                  >
                    <ArrowLeft className="w-4 h-4 mr-1" />
                    Back
                  </Button>
                )}
                <h3 className="text-sm text-slate-700">
                  {activeThreadId 
                    ? subThreads.find(t => t.id === activeThreadId)?.title 
                    : 'Main Conversation'}
                </h3>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => setShowThreadsList(!showThreadsList)}
                title="View all threads"
              >
                <List className="w-4 h-4" />
              </Button>
            </div>

            {/* Threads List Modal */}
            {showThreadsList && (
              <div className="absolute right-0 top-14 w-80 bg-white border border-slate-200 rounded-lg shadow-lg z-20 max-h-96 overflow-y-auto">
                <div className="p-4 border-b border-slate-200 flex items-center justify-between">
                  <h3 className="text-slate-900">All Threads</h3>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => setShowThreadsList(false)}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
                <div className="p-2">
                  <button
                    onClick={() => {
                      setActiveThreadId(null);
                      setShowThreadsList(false);
                    }}
                    className="w-full text-left p-3 rounded-lg hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <MessageSquare className="w-4 h-4 text-indigo-600" />
                      <span className="text-sm text-slate-900">Main Conversation</span>
                    </div>
                    <p className="text-xs text-slate-600">{messages.length} messages</p>
                  </button>
                  {subThreads.map(thread => (
                    <button
                      key={thread.id}
                      onClick={() => {
                        setActiveThreadId(thread.id);
                        setShowThreadsList(false);
                      }}
                      className="w-full text-left p-3 rounded-lg hover:bg-slate-50 transition-colors"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <MessageSquare className="w-4 h-4 text-purple-600" />
                        <span className="text-sm text-slate-900 truncate">{thread.title}</span>
                      </div>
                      <p className="text-xs text-slate-600">{thread.messages.length} messages</p>
                    </button>
                  ))}
                  {subThreads.length === 0 && (
                    <div className="p-4 text-center text-sm text-slate-500">
                      No subthreads yet. Hover over any message to create one.
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
              {getCurrentMessages().map((message, index) => {
                const messageThreads = !activeThreadId ? getThreadsByParent(message.id) : [];
                return (
                  <div key={message.id}>
                    <div
                      onMouseEnter={() => setHoveredMessageId(message.id)}
                      onMouseLeave={() => setHoveredMessageId(null)}
                      className="relative"
                    >
                      <div
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
                      
                      {/* Create Thread Button (on hover) */}
                      {!activeThreadId && hoveredMessageId === message.id && (
                        <div className="absolute -bottom-2 left-1/2 transform -translate-x-1/2 z-10">
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-6 text-xs gap-1 bg-white shadow-md"
                            onClick={() => createSubThread(message.id)}
                          >
                            <MessageSquare className="w-3 h-3" />
                            Start thread
                          </Button>
                        </div>
                      )}
                    </div>

                    {/* Subthread Summaries */}
                    {messageThreads.length > 0 && !activeThreadId && (
                      <div className="ml-11 mt-2 space-y-2">
                        {messageThreads.map(thread => {
                          const isExpanded = expandedThreads.has(thread.id);
                          return (
                            <div
                              key={thread.id}
                              className="bg-purple-50 border border-purple-200 rounded-lg p-3 cursor-pointer hover:bg-purple-100 transition-colors"
                            >
                              <div
                                onClick={() => toggleThreadExpansion(thread.id)}
                                className="flex items-start gap-2"
                              >
                                <MessageSquare className="w-4 h-4 text-purple-600 mt-0.5 flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="text-xs text-purple-900 truncate">{thread.title}</span>
                                    <Badge variant="secondary" className="text-[10px] h-4 px-1">
                                      {thread.messages.length}
                                    </Badge>
                                  </div>
                                  {isExpanded ? (
                                    <p className="text-xs text-purple-700">{getThreadSummary(thread)}</p>
                                  ) : (
                                    <p className="text-xs text-purple-700 line-clamp-2">{getThreadSummary(thread)}</p>
                                  )}
                                </div>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-6 w-6 p-0 flex-shrink-0"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setActiveThreadId(thread.id);
                                  }}
                                >
                                  <ChevronRight className="w-3 h-3" />
                                </Button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
              
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
                  placeholder={activeThreadId ? "Reply in thread..." : "Describe the changes you want to make..."}
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
              {messages.length === 1 && !activeThreadId && (
                <div className="mt-4">
                  <p className="text-xs text-slate-600 mb-2">Suggested updates:</p>
                  <div className="flex gap-2 overflow-x-auto pb-2 -mx-4 px-4">
                    {PROMPT_SUGGESTIONS.map((suggestion, index) => (
                      <button
                        key={index}
                        onClick={() => handleSuggestionClick(suggestion)}
                        className="flex-shrink-0 text-left p-3 rounded-lg border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors text-sm text-slate-700 hover:text-indigo-700 min-w-[280px]"
                      >
                        {suggestion}
                      </button>
                    ))}</div>
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
      </div>
    </div>
  );
}