import React from 'react';
import { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, Save, Loader2, Paperclip, File, X, Users, User, Bot, HardHat } from 'lucide-react';
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
  senderName?: string;  // For detecting Foreman vs other agents
}

interface Participant {
  id: string;
  name: string;
  type: 'user' | 'system';
  email?: string;
  systemAgentName?: string;
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
      content: `Welcome to the Agent Foundry. I am the Foreman, and will walk you through the creation of this confab (Collaborative Agent).

I'll guide you through a simple 7-step process to configure your agent:
1. **Define purpose** - What should your agent do?
2. **Add participants** - Who can access it?
3. **Configure memory** - Should it remember conversations?
4. **Set up tools** - What external capabilities does it need?
5. **Establish guardrails** - What are its safety boundaries?
6. **Sample I/O** - Provide example interactions
7. **Review** - Finalize your configuration

Let's start with the most important part: **What would you like this agent to do?** Describe its main purpose and objectives.`,
      timestamp: new Date(),
      senderName: 'Foreman',
    },
  ]);

  // Participants list for the sidebar (Foreman is always present)
  const [participants, setParticipants] = useState<Participant[]>([
    { id: 'foreman', name: 'Foreman', type: 'system', systemAgentName: 'foreman' }
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

  // Chat ready state (replaces LLM health check - API is assumed available)
  const [chatReady, setChatReady] = useState(true);

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

        // Find the thread with Foreman as participant (the building conversation)
        const threads = await apiClient.getThreads();
        for (const thread of threads) {
          try {
            const participants = await apiClient.getThreadParticipants(thread.id);
            const hasForeman = participants.some(
              (p: any) => p.participant_type === 'system' && p.system_agent_name === 'foreman'
            );

            if (hasForeman) {
              // Found the thread - load messages
              setCurrentThreadId(thread.id);
              const threadMessages = await apiClient.getThreadMessages(thread.id);

              if (threadMessages && threadMessages.length > 0) {
                // Convert to Message format
                const loadedMessages: Message[] = threadMessages.map((msg: any) => ({
                  id: String(msg.id),
                  role: msg.role as 'user' | 'assistant',
                  content: msg.content,
                  timestamp: new Date(msg.created_at),
                  senderName: msg.sender_name || (msg.role === 'assistant' ? 'Foreman' : undefined),
                }));
                setMessages(loadedMessages);
              }
              break; // Found the thread, stop searching
            }
          } catch (participantError) {
            // Thread might not have participants, continue searching
            console.debug('Error checking thread participants:', participantError);
          }
        }
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

  // Add logged-in user to participants list
  useEffect(() => {
    if (user) {
      setParticipants(prev => {
        // Check if user already in list
        if (prev.some(p => p.type === 'user' && p.id === String(user.id))) {
          return prev;
        }
        return [
          ...prev,
          { id: String(user.id), name: user.name, type: 'user', email: user.email }
        ];
      });
    }
  }, [user]);

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

        // Add Foreman as participant for the building phase
        if (tid != null) {
          try {
            await apiClient.addThreadParticipant(tid, 'system', null, 'foreman', 'participant');
            console.log('[CLAUDE: IMPLEMENTATION] Foreman added as thread participant');
          } catch (participantError) {
            console.error('[CLAUDE: IMPLEMENTATION] Error adding thread participant:', participantError);
          }
        }
      } catch {
        tid = null;
      }
    }

    // === [CLAUDE: Send message via unified chat endpoint] ===
    // The chat endpoint handles message storage and agent responses
    try {
      let assistantContent = '';
      let response: any = null;

      if (tid != null) {
        try {
          // Use the unified chat endpoint - it handles everything
          response = await apiClient.chat(tid, content);

          // The response contains user_message and agent_responses
          if (response.agent_responses && response.agent_responses.length > 0) {
            // Add each agent response as a message
            for (const agentResp of response.agent_responses) {
              const agentMsg: Message = {
                id: String(agentResp.id),
                role: 'assistant',
                content: agentResp.content,
                timestamp: new Date(agentResp.created_at),
                senderName: agentResp.sender_name || 'Foreman',
              };
              setMessages((prev) => [...prev, agentMsg]);
            }
            assistantContent = response.agent_responses[response.agent_responses.length - 1].content;
          } else {
            // No agent response yet - this shouldn't happen with Foreman
            assistantContent = "Message sent. Waiting for agent response...";
          }
        } catch (chatError: any) {
          console.error('[CLAUDE: Chat API error]', chatError);
          assistantContent = `I encountered an error: ${chatError.message || 'Unable to send message'}. Please try again.`;

          // Add error as assistant message
          const errorMsg: Message = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: assistantContent,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, errorMsg]);
        }
      } else {
        // No thread - show error
        assistantContent = "Could not create a conversation thread. Please try again.";
        const errorMsg: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: assistantContent,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      }

      setIsTyping(false);
    } catch (error) {
      console.error('[CLAUDE: Error in handleSend]', error);
      setIsTyping(false);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: Failed to send message. ${error instanceof Error ? error.message : 'Unknown error'}`,
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
                          <AvatarFallback className={message.senderName === 'Foreman'
                            ? "bg-gradient-to-br from-amber-500 to-orange-600"
                            : "bg-gradient-to-br from-indigo-600 to-purple-600"
                          }>
                            {message.senderName === 'Foreman'
                              ? <HardHat className="w-4 h-4 text-white" />
                              : <Bot className="w-4 h-4 text-white" />
                            }
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
                        <AvatarFallback className="bg-gradient-to-br from-amber-500 to-orange-600">
                          <HardHat className="w-4 h-4 text-white" />
                        </AvatarFallback>
                      </Avatar>
                      <div className="bg-slate-100 rounded-lg px-4 py-3 flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin text-slate-600" />
                        <span className="text-slate-600">Foreman is thinking...</span>
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
            <div className="space-y-3">
              {participants.map((participant) => (
                <div
                  key={participant.id}
                  className={`flex items-center gap-3 p-3 rounded-lg ${
                    participant.type === 'system'
                      ? 'bg-amber-50 ring-1 ring-amber-200'
                      : 'bg-indigo-50 ring-1 ring-indigo-200'
                  }`}
                >
                  <Avatar className="w-9 h-9">
                    <AvatarFallback className={
                      participant.type === 'system'
                        ? "bg-gradient-to-br from-amber-500 to-orange-600"
                        : "bg-indigo-200 text-indigo-700"
                    }>
                      {participant.type === 'system' ? (
                        <HardHat className="w-4 h-4 text-white" />
                      ) : (
                        participant.name.split(' ').map(n => n[0]).join('') || '?'
                      )}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 truncate">{participant.name}</p>
                    <p className="text-xs text-slate-500 truncate">
                      {participant.email || (participant.type === 'system' ? 'System Agent' : '')}
                    </p>
                  </div>
                </div>
              ))}
              {participants.length === 0 && (
                <p className="text-sm text-slate-500 py-2">No participants yet.</p>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}