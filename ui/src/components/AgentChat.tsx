import React from 'react';
import { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, Save, Loader2, Paperclip, File, X, Users, User, Bot, TestTube, CheckCircle, AlertCircle } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Avatar, AvatarFallback } from './ui/avatar';
import { apiClient } from '../api/client.js';
import { useAuth } from '../contexts/AuthContext';
import { MessageContent } from './MessageContent';

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'confab-chat' | 'review-chats';

interface AgentChatProps {
  onNavigate: (view: View, confabName?: string) => void;
  existingConfabId?: number;  // For resuming building confabs
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

// the server prepends the following system prompt to every chat request:
//
// You are a Confab Setup Agent.
//
// You must:
// - Detect which setup step the user is working on
// - Call the correct tool
// - Update step progress
// - Guide user to next step
//
// Available steps:
// 1 Define Purpose
// 2 Add Participants
// 3 Configure Memory
// 4 Add Tools & APIs
// 5 Guardrails
// 6 Sample Inputs/Outputs
// 7 Review & Save
//
// The agent also has access to helper tools that let it read or write
// configuration documents directly.  When a writing tool is used the
// backend will open a GitHub branch and commit a markdown file (eg.
// PURPOSE.md or a knowledge-base note).  The resulting pull request URL
// comes back in the tool response.

const PROMPT_SUGGESTIONS = [
  "Create a customer support agent that handles refunds and returns",
  "Build an agent that analyzes sales data and generates weekly reports",
  "I need an agent to review code for security vulnerabilities",
  "Create an agent that summarizes meeting transcripts",
];


export function AgentChat({ onNavigate, existingConfabId }: AgentChatProps) {
  const { user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: "Hi! I'm your AI confab builder assistant. Let's build your confab step by step through conversation.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  /** Thread id for storing this conversation in DB (threads + messages tables). */
  const [currentThreadId, setCurrentThreadId] = useState<number | null>(null);

  // [CLAUDE: IMPLEMENTATION - Create confab_id on page load and link to thread_mapping]
  const [currentConfabId, setCurrentConfabId] = useState<number | null>(null);
  const [isConfabCreating, setIsConfabCreating] = useState(false);

  // Loading state for resuming existing confab
  const [isLoadingExisting, setIsLoadingExisting] = useState(!!existingConfabId);
  
  // Multi-Agent State (if we ever support it)
  const [multiAgentNodes, setMultiAgentNodes] = useState<AgentNode[]>([]);
  const [moderatorRules, setModeratorRules] = useState('');
  const [tieBreaker, setTieBreaker] = useState('');
  const [enableConflictResolution, setEnableConflictResolution] = useState(true);
  const [maxTurnsPerAgent, setMaxTurnsPerAgent] = useState('3');
  const [githubConnected, setGithubConnected] = useState(false);

  // repository test helpers (same as ConfabConfigForm)
  const [isTestingRepo, setIsTestingRepo] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [testError, setTestError] = useState('');

  // === [CLAUDE: LLM-related state for dynamic chat] ===
  const [llmHealthy, setLlmHealthy] = useState(false);
  const [llmError, setLlmError] = useState<string | null>(null);

  // Check LLM health on component mount
  useEffect(() => {
    const checkLLM = async () => {
      try {
        const health = await apiClient.llmHealthCheck();
        setLlmHealthy(health.healthy);
        if (!health.healthy) {
          setLlmError('LLM service is not available');
        }
      } catch (error) {
        setLlmHealthy(false);
        setLlmError('Could not connect to LLM service');
      }
    };
    checkLLM();
  }, []);

  // Load existing confab data if resuming
  useEffect(() => {
    const loadExistingConfab = async () => {
      if (!existingConfabId) {
        setIsLoadingExisting(false);
        return;
      }

      setIsLoadingExisting(true);
      try {
        // Load existing confab
        const confab = await apiClient.getConfab(existingConfabId);
        setCurrentConfabId(confab.id);

        // Load existing thread and messages
        const threads = await apiClient.getConfabThreads(existingConfabId);
        if (threads.length > 0) {
          const thread = threads[0];
          setCurrentThreadId(thread.id);
          const msgs = await apiClient.getThreadMessages(thread.id);
          if (msgs.length > 0) {
            setMessages(msgs.map((m: any) => ({
              id: String(m.id),
              role: m.role,
              content: m.content,
              timestamp: new Date(m.time),
            })));
          }
          // If no messages but thread exists, keep the default welcome message
        }
        // If no threads exist, keep the default welcome message
      } catch (error) {
        console.error('Failed to load existing confab:', error);
        // Reset to fresh state if resume fails
        setCurrentConfabId(null);
        setCurrentThreadId(null);
      } finally {
        setIsLoadingExisting(false);
      }
    };

    loadExistingConfab();
  }, [existingConfabId]);

  // Determine GitHub repo naming convention
  const getRepoNamingConvention = () => {
    if (user?.github_connected) {
      return 'username/confabs (will be set based on your GitHub username)';
    } else {
      return 'letsconfab/confabs (for email users)';
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

    // Create confab on first message if not exists
    // Track the confab ID locally to avoid race condition with state update
    let confabId = currentConfabId;
    if (confabId == null) {
      try {
        const confab = await apiClient.createConfab({
          generate_placeholder: true,
          status: 'building'
        });
        console.log('Created new confab:', confab);
        confabId = confab.id;
        setCurrentConfabId(confab.id);
      } catch (error) {
        console.error('Failed to create confab:', error);
      }
    }

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
        // Use local confabId variable to avoid race condition with state update
        if (tid != null && confabId != null) {
          try {
            const mapping = await apiClient.createThreadMapping(confabId, tid);
            console.log('[CLAUDE: IMPLEMENTATION] Thread mapping created:', mapping);
          } catch (mappingError) {
            console.error('[CLAUDE: IMPLEMENTATION] Error creating thread mapping:', mappingError);
            // Continue gracefully - the thread is still created even if mapping fails
          }
        } else if (tid != null && confabId == null) {
          console.warn('[CLAUDE: IMPLEMENTATION] Thread created but confab_id is missing:', {
            threadId: tid,
            confabId: confabId,
          });
        }
      } catch {
        tid = null;
      }
    }

    // === [CLAUDE: Store user message in database if thread exists] ===
    // NOTE: Only store if NOT using LangGraph agent, as Foreman handles message storage
    const usingLangGraphAgent = confabId != null;
    if (tid != null && !usingLangGraphAgent) {
      apiClient.addMessage(tid, content, 'user').catch(() => {});
    }

    // === [CLAUDE: Generate AI response from LangGraph Agent API] ===
    try {
      let assistantContent = '';
      let response: any = null;

      // Try LangGraph agent if we have a confab, otherwise use direct LLM
      // Use local confabId variable to avoid race condition with state update
      if (confabId != null) {
        try {
          // Foreman/LangGraph agent handles message storage internally
          response = await apiClient.chatWithLangGraphAgent(confabId, content);
          assistantContent = response.response || "I couldn't generate a response. Please try again.";
        } catch (langGraphError: any) {
          console.error('[CLAUDE: LangGraph Agent API error]', langGraphError);
          // Fallback to direct LLM if LangGraph fails
          try {
            response = await apiClient.llmGenerateResponse(
              `User asked: ${content}\n\nProvide a helpful response:`
            );
            assistantContent = response.response || "I couldn't generate a response. Please try again.";
          } catch (llmError: any) {
            console.error('[CLAUDE: LLM API error]', llmError);
            assistantContent = `I encountered an error: ${llmError.message || 'Unable to generate response'}. Please try again.`;
          }
        }
      } else {
        // No confab selected - use direct LLM generation
        try {
          response = await apiClient.llmGenerateResponse(
            `User asked: ${content}\n\nProvide a helpful response about building an AI confab:`
          );
          assistantContent = response.response || "I couldn't generate a response. Please try again.";
        } catch (llmError: any) {
          console.error('[CLAUDE: LLM API error]', llmError);
          assistantContent = `I encountered an error: ${llmError.message || 'Unable to generate response'}. Please try again.`;
        }
      }

      setIsTyping(false);

      // === [CLAUDE: Add AI response to messages state] ===
      // if the backend returned a tool_message, display it first
      if (response && response.tool_message) {
        const toolMsg: Message = {
          id: `tool-${Date.now()}`,
          role: 'assistant',
          content: response.tool_message.content,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, toolMsg]);
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: assistantContent,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      // step tracking is handled by the backend agent via tools

      // === [CLAUDE: Store AI response in database if thread exists] ===
      // NOTE: Only store if NOT using LangGraph agent, as Foreman handles message storage
      if (tid != null && !usingLangGraphAgent) {
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
              <h2 className="text-slate-900">{existingConfabId ? 'Continue Building' : 'Create New Confab'}</h2>
              <p className="text-slate-600 text-sm">
                {existingConfabId ? 'Resume your conversation to continue building' : 'Chat with AI to build your confab'}
              </p>
            </div>
          </div>
          <Badge variant="secondary" className="gap-1">
            <div className={`w-2 h-2 rounded-full animate-pulse ${existingConfabId ? 'bg-amber-500' : 'bg-green-500'}`} />
            {existingConfabId ? 'Resuming' : 'Active'}
          </Badge>
        </div>
        {/* repository info / test button */}
        <div className="mt-4 p-3 bg-blue-50 rounded-lg">
          <p className="text-sm text-blue-800">
            <strong>Repository Naming Convention:</strong>
          </p>
          <p className="text-sm text-blue-700 mt-1">
            {getRepoNamingConvention()}
          </p>
          <div className="flex items-center gap-2 mt-2">
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
          </div>
          {testResult && (
            <div className="mt-3 p-3 bg-green-50 rounded-lg">
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle className="w-4 h-4 text-green-600" />
                <span className="text-sm font-medium text-green-800">
                  Test Successful
                </span>
              </div>
              <p className="text-sm text-green-700">
                {testResult.message}
              </p>
            </div>
          )}
          {testError && (
            <div className="mt-3 p-3 bg-red-50 rounded-lg">
              <div className="flex items-center gap-2 mb-1">
                <AlertCircle className="w-4 h-4 text-red-600" />
                <span className="text-sm font-medium text-red-800">
                  Test Failed
                </span>
              </div>
              <p className="text-sm text-red-700">
                {testError}
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* conversation area will occupy two columns */}
        <div className="lg:col-span-2">
          <Card className="flex flex-col min-h-[600px]">
            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
              {isLoadingExisting ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto mb-3" />
                    <p className="text-slate-600">Loading your conversation...</p>
                  </div>
                </div>
              ) : (
                <>
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
                        <MessageContent content={message.content} variant={message.role} />
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
                </>
              )}
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