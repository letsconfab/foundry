import React from 'react';
import { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, Save, Loader2, Paperclip, File, X, Users, User, Bot, HardHat, Pencil, Check, Trash2, FileText, Wrench, Activity } from 'lucide-react';
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
  toolCalls?: ToolCall[];  // Tool calls made in this message
  toolResults?: ToolResult[];  // Tool results from this message
}

interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, any>;
  timestamp: Date;
}

interface ToolResult {
  toolName: string;
  result: string;
  success: boolean;
  timestamp: Date;
}

interface Participant {
  id: string;
  name: string;
  type: 'user' | 'system';
  email?: string;
  systemAgentName?: string;
}

interface UploadedFile {
  tempId: string;
  name: string;
  size: number;
  id?: number;
  status: 'pending' | 'uploading' | 'indexed' | 'duplicate' | 'failed';
  error?: string;
  chunkCount?: number;
  file?: File;
}

interface DocumentListItem {
  id: number;
  filename: string;
  content_type: string;
  chunk_count: number;
  status: string;
  created_at?: string;
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

// Tool Activity Panel Component
const ToolActivityPanel = ({ recentToolActivity }: { recentToolActivity: ToolResult[] }) => {
  if (recentToolActivity.length === 0) return null;
  
  return (
    <div className="mb-4 p-3 bg-slate-50 border border-slate-200 rounded-lg">
      <div className="flex items-center gap-2 mb-2">
        <Activity className="w-4 h-4 text-slate-600" />
        <span className="text-sm font-medium text-slate-700">Recent Tool Activity</span>
        <Badge variant="secondary" className="ml-auto">
          {recentToolActivity.length}
        </Badge>
      </div>
      <div className="space-y-1">
        {recentToolActivity.slice(-3).map((tool, index) => (
          <div key={index} className="flex items-start gap-2 text-xs">
            <Wrench className={`w-3 h-3 mt-0.5 flex-shrink-0 ${tool.success ? 'text-green-600' : 'text-red-600'}`} />
            <div className="flex-1">
              <span className="font-medium text-slate-700">{tool.toolName}</span>
              <span className="text-slate-500 ml-1">
                {tool.success ? '✅' : '❌'}
              </span>
              <p className="text-slate-600 truncate">{tool.result}</p>
            </div>
            <span className="text-slate-400">
              {tool.timestamp.toLocaleTimeString()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// Enhanced Message Component with Tool Information
const EnhancedMessage = ({ message, isUser, user }: { message: Message; isUser: boolean; user?: any }) => {
  const showToolInfo = message.toolCalls && message.toolCalls.length > 0;
  const showToolResults = message.toolResults && message.toolResults.length > 0;
  
  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
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
      <div className={`max-w-[80%] rounded-lg px-4 py-3 ${
        isUser ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-900'
      }`}>
        <MessageContent content={message.content} variant={message.role} />
        
        {/* Tool Calls Display */}
        {showToolInfo && (
          <div className="mt-2 pt-2 border-t border-slate-300">
            <div className="flex items-center gap-1 mb-1">
              <Wrench className="w-3 h-3 text-slate-600" />
              <span className="text-xs font-medium text-slate-700">Tools Used:</span>
            </div>
            <div className="space-y-1">
              {message.toolCalls?.map((call, idx) => (
                <div key={idx} className="text-xs bg-slate-200 rounded px-2 py-1">
                  <span className="font-mono text-slate-700">{call.name}</span>
                  <span className="text-slate-500 ml-1">
                    {JSON.stringify(call.arguments).substring(0, 50)}...
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Tool Results Display */}
        {showToolResults && (
          <div className="mt-2 pt-2 border-t border-slate-300">
            <div className="flex items-center gap-1 mb-1">
              <Activity className="w-3 h-3 text-slate-600" />
              <span className="text-xs font-medium text-slate-700">Tool Results:</span>
            </div>
            <div className="space-y-1">
              {message.toolResults?.map((result, idx) => (
                <div key={idx} className="text-xs">
                  <span className={`font-medium ${result.success ? 'text-green-700' : 'text-red-700'}`}>
                    {result.toolName}: {result.success ? '✅' : '❌'}
                  </span>
                  <p className="text-slate-600 truncate">{result.result}</p>
                </div>
              ))}
            </div>
          </div>
        )}
        
        <p className={`text-xs mt-1 ${
          isUser ? 'text-indigo-200' : 'text-slate-500'
        }`}>
          {message.timestamp.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      </div>
      {isUser && (
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
  );
};

const PROMPT_SUGGESTIONS = [
  "Create a customer support agent that handles refunds and returns",
  "Build an agent that analyzes sales data and generates weekly reports",
  "I need an agent to review code for security vulnerabilities",
  "Create an agent that summarizes meeting transcripts",
];

// Helper functions to parse tool information from agent responses
const parseToolCalls = (content: string): ToolCall[] => {
  const toolCalls: ToolCall[] = [];
  const callRegex = /\[TOOL CALL\] Calling tool: (\w+) with arguments: ({.*?})/g;
  let match;
  
  while ((match = callRegex.exec(content)) !== null) {
    try {
      toolCalls.push({
        id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
        name: match[1],
        arguments: JSON.parse(match[2]),
        timestamp: new Date()
      });
    } catch (e) {
      console.warn('Failed to parse tool call:', match[0]);
    }
  }
  
  return toolCalls;
};

const parseToolResults = (content: string): ToolResult[] => {
  const toolResults: ToolResult[] = [];
  const resultRegex = /\[TOOL RESULT\] (\w+) completed: (.*)/g;
  let match;
  
  while ((match = resultRegex.exec(content)) !== null) {
    const toolName = match[1];
    const result = match[2];
    
    // Determine success based on result content
    const success = result.includes('successfully') || 
                   result.includes('completed') || 
                   result.includes('created') ||
                   result.includes('updated') ||
                   !result.includes('failed') && !result.includes('error');
    
    toolResults.push({
      toolName,
      result,
      success,
      timestamp: new Date()
    });
  }
  
  return toolResults;
};


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
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentError, setDocumentError] = useState<string | null>(null);
  /** Thread id for storing this conversation in DB (threads + messages tables). */
  const [currentThreadId, setCurrentThreadId] = useState<number | null>(null);

  /** Guard against rapid double-sends before React processes state updates */
  const sendingRef = useRef(false);

  // [CLAUDE: IMPLEMENTATION - Create confab_id on page load and link to thread_mapping]
  const [currentConfabId, setCurrentConfabId] = useState<number | null>(null);
  const [isConfabCreating, setIsConfabCreating] = useState(false);

  // Loading state for resuming existing confab
  const [isLoadingExisting, setIsLoadingExisting] = useState(!!existingConfabId);

  // Confab name state (editable)
  const [confabName, setConfabName] = useState<string>('New Confab');
  const [isEditingName, setIsEditingName] = useState(false);
  const [editNameValue, setEditNameValue] = useState('');
  
  // Multi-Agent State (if we ever support it)
  const [multiAgentNodes, setMultiAgentNodes] = useState<AgentNode[]>([]);
  const [moderatorRules, setModeratorRules] = useState('');
  const [tieBreaker, setTieBreaker] = useState('');
  const [enableConflictResolution, setEnableConflictResolution] = useState(true);
  const [maxTurnsPerAgent, setMaxTurnsPerAgent] = useState('3');
  const [githubConnected, setGithubConnected] = useState(false);
  
  // Tool activity tracking
  const [recentToolActivity, setRecentToolActivity] = useState<ToolResult[]>([]);

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
        if (confab.name) {
          setConfabName(confab.name);
        }

        // Find the thread for THIS specific confab (must have both Foreman AND this confab as participants)
        const threads = await apiClient.getThreads();
        for (const thread of threads) {
          try {
            const participants = await apiClient.getThreadParticipants(thread.id);
            const hasForeman = participants.some(
              (p: any) => p.participant_type === 'system' && p.system_agent_name === 'foreman'
            );
            const hasThisConfab = participants.some(
              (p: any) => p.participant_type === 'confab' && p.participant_id === existingConfabId
            );

            if (hasForeman && hasThisConfab) {
              // Found the correct thread for this confab - load messages
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

  // Load existing documents when confab is available
  useEffect(() => {
    if (!currentConfabId) return;
    let cancelled = false;

    setDocumentsLoading(true);
    apiClient.listDocuments(currentConfabId)
      .then((docs: DocumentListItem[]) => {
        if (!cancelled) setDocuments(docs);
      })
      .catch((err: Error) => {
        if (!cancelled) setDocumentError(err.message);
      })
      .finally(() => {
        if (!cancelled) setDocumentsLoading(false);
      });

    return () => { cancelled = true; };
  }, [currentConfabId]);

  // Start editing the confab name
  const startEditingName = () => {
    setEditNameValue(confabName);
    setIsEditingName(true);
  };

  // Save the edited confab name
  const saveConfabName = async () => {
    if (!editNameValue.trim() || !currentConfabId) {
      setIsEditingName(false);
      return;
    }

    try {
      await apiClient.updateConfab(currentConfabId, { name: editNameValue.trim() });
      setConfabName(editNameValue.trim());
    } catch (error) {
      console.error('Failed to update confab name:', error);
    }
    setIsEditingName(false);
  };

  // Refresh confab name from server (called after chat responses)
  const refreshConfabName = async () => {
    if (!currentConfabId) return;
    try {
      const confab = await apiClient.getConfab(currentConfabId);
      if (confab.name && confab.name !== confabName) {
        setConfabName(confab.name);
      }
    } catch (error) {
      console.debug('Failed to refresh confab name:', error);
    }
  };

  // Enhanced GitHub push functionality with tool information
  const handleGitHubPush = async () => {
    if (!currentConfabId) {
      const errorMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '❌ No confab found. Please create a confab first before pushing to GitHub.',
        timestamp: new Date(),
        senderName: 'Foreman'
      };
      setMessages(prev => [...prev, errorMsg]);
      return;
    }

    let loadingMsgId: string | null = null;

    try {
      // Show loading message
      loadingMsgId = (Date.now() + 1).toString();
      const loadingMsg: Message = {
        id: loadingMsgId,
        role: 'assistant',
        content: '🚀 Pushing your confab and tool information to GitHub...',
        timestamp: new Date(),
        senderName: 'Foreman'
      };
      setMessages(prev => [...prev, loadingMsg]);

      const response = await apiClient.pushConfabToGitHub(currentConfabId);
      
      // Remove loading message and add success message with tool info
      setMessages(prev => prev.filter(msg => msg.id !== loadingMsgId));
      
      // Add tool activity summary
      const toolSummary = recentToolActivity.length > 0 
        ? `\n\n🛠️ **Recent Tool Activity:**\n${recentToolActivity.slice(-5).map(tool => 
            `• ${tool.toolName}: ${tool.success ? '✅' : '❌'} ${tool.result.substring(0, 100)}${tool.result.length > 100 ? '...' : ''}`
          ).join('\n')}`
        : '';
      
      const successMsg: Message = {
        id: (Date.now() + 2).toString(),
        role: 'assistant',
        content: `✅ Your confab "${confabName}" has been pushed to GitHub!\n\n📁 Repository: ${response.repo_url}\n📂 Folder: confabs/${confabName}/\n🛠️ All tool configurations and documentation have been version-controlled.${toolSummary}`,
        timestamp: new Date(),
        senderName: 'Foreman'
      };
      setMessages(prev => [...prev, successMsg]);
      
      // Clear recent tool activity after successful push
      setRecentToolActivity([]);
    } catch (error: any) {
      // Remove loading message and add error message
      if (loadingMsgId) {
        setMessages(prev => prev.filter(msg => msg.id !== loadingMsgId));
      }
      
      const errorMsg: Message = {
        id: (Date.now() + 2).toString(),
        role: 'assistant',
        content: `❌ Failed to push to GitHub: ${error.message || 'Unknown error occurred'}. Please check your GitHub connection and try again.`,
        timestamp: new Date(),
        senderName: 'Foreman'
      };
      setMessages(prev => [...prev, errorMsg]);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || sendingRef.current) return;
    sendingRef.current = true;  // Lock immediately, synchronously
    const content = input.trim();

    // Check for push commands before processing as regular chat
    const PUSH_COMMANDS = ['push my data', 'push to github', 'save to repo', 'push the purpose'];
    const isPushCommand = PUSH_COMMANDS.some(cmd => 
      content.toLowerCase().includes(cmd.toLowerCase())
    );

    if (isPushCommand) {
      await handleGitHubPush();
      setInput('');
      sendingRef.current = false;
      return;
    }

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

        // Automatically create confab folder structure in GitHub
        try {
          console.log('[GITHUB STORAGE] Creating confab folder structure...');
          // This will be handled by the agent tools when the first purpose is set
          console.log('[GITHUB STORAGE] Folder structure will be created when purpose is defined');
        } catch (folderError) {
          console.error('[GITHUB STORAGE] Failed to create folder structure:', folderError);
        }
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

        // Add Foreman as participant FIRST (critical for chat to work)
        if (tid != null) {
          try {
            await apiClient.addThreadParticipant(tid, 'system', null, 'foreman', 'participant');
            console.log('[CLAUDE: IMPLEMENTATION] Foreman added as thread participant');
          } catch (participantError) {
            console.error('[CLAUDE: IMPLEMENTATION] Error adding thread participant:', participantError);
          }
        }

        // Add confab as participant (links this thread to the specific confab for Continue Building)
        if (tid != null && confabId != null) {
          try {
            await apiClient.addThreadParticipant(tid, 'confab', confabId, null, 'participant');
            console.log('[CLAUDE: IMPLEMENTATION] Confab added as thread participant');
          } catch (participantError) {
            console.error('[CLAUDE: IMPLEMENTATION] Error adding confab participant:', participantError);
          }
        }

        // Save welcome message with proper Foreman attribution (non-critical)
        if (tid != null && messages[0]?.role === 'assistant') {
          try {
            await apiClient.addMessage(tid, messages[0].content, 'assistant', 'system', 'Foreman');
          } catch (welcomeError) {
            console.error('Failed to save welcome message:', welcomeError);
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
              // Parse tool calls and results from the response content
              const toolCalls = parseToolCalls(agentResp.content);
              const toolResults = parseToolResults(agentResp.content);
              
              // Update recent tool activity
              if (toolResults.length > 0) {
                const newToolResults = toolResults.map((result: ToolResult) => ({
                  toolName: result.toolName,
                  result: result.result,
                  success: result.success,
                  timestamp: new Date()
                }));
                setRecentToolActivity(prev => [...prev, ...newToolResults]);
              }
              
              const agentMsg: Message = {
                id: String(agentResp.id),
                role: 'assistant',
                content: agentResp.content,
                timestamp: new Date(agentResp.created_at),
                senderName: agentResp.sender_name || 'Foreman',
                toolCalls,
                toolResults
              };
              setMessages((prev) => [...prev, agentMsg]);
            }
            assistantContent = response.agent_responses[response.agent_responses.length - 1].content;

            // Refresh confab name in case Foreman set it
            refreshConfabName();
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
      sendingRef.current = false;  // Unlock
    } catch (error) {
      console.error('[CLAUDE: Error in handleSend]', error);
      setIsTyping(false);
      sendingRef.current = false;  // Unlock on error
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

  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || !currentConfabId) {
      if (!currentConfabId) {
        setDocumentError('Please wait for the confab to be created before uploading files');
      }
      return;
    }

    for (const file of Array.from(files)) {
      const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
      if (!['.pdf', '.txt', '.md'].includes(ext)) {
        setDocumentError(`Unsupported file type: ${file.name}`);
        continue;
      }

      if (file.size > MAX_FILE_SIZE) {
        setDocumentError(`File too large: ${file.name} (max 10MB)`);
        continue;
      }

      const tempId = crypto.randomUUID();
      const pending: UploadedFile = {
        tempId,
        name: file.name,
        size: file.size,
        status: 'uploading',
        file,
      };
      setUploadedFiles(prev => [...prev, pending]);

      let response;
      try {
        response = await apiClient.uploadDocument(currentConfabId, file);
        setDocumentError(null);
        setUploadedFiles(prev =>
          prev.map(f => f.tempId === tempId ? {
            ...f,
            id: response.status === 'duplicate' ? undefined : response.document_id,
            status: response.status,
            chunkCount: response.chunk_count,
            file: undefined,
          } : f)
        );
      } catch (err: unknown) {
        const errorMessage = err instanceof Error ? err.message : 'Upload failed';
        setUploadedFiles(prev =>
          prev.map(f => f.tempId === tempId ? {
            ...f,
            status: 'failed',
            error: errorMessage,
          } : f)
        );
        continue;
      }

      try {
        const docs = await apiClient.listDocuments(currentConfabId);
        setDocuments(docs);
      } catch {
        // List refresh failure is non-critical
      }
    }
    e.target.value = '';
  };

  const handleDeleteDocument = async (documentId: number) => {
    if (!currentConfabId) return;
    try {
      await apiClient.deleteDocument(currentConfabId, documentId);
      setDocumentError(null);
      setDocuments(prev => prev.filter(d => d.id !== documentId));
      setUploadedFiles(prev => prev.filter(f => f.id !== documentId));
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Delete failed';
      setDocumentError(errorMessage);
    }
  };

  const handleRemoveFile = async (index: number) => {
    const file = uploadedFiles[index];
    if (file.id && currentConfabId) {
      await handleDeleteDocument(file.id);
    } else {
      setUploadedFiles(prev => prev.filter((_, i) => i !== index));
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
              <div className="flex items-center gap-2">
                {isEditingName ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={editNameValue}
                      onChange={(e) => setEditNameValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') saveConfabName();
                        if (e.key === 'Escape') setIsEditingName(false);
                      }}
                      className="text-slate-900 font-medium border border-slate-300 rounded px-2 py-0.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      autoFocus
                    />
                    <button
                      onClick={saveConfabName}
                      className="p-1 hover:bg-slate-100 rounded"
                      title="Save name"
                    >
                      <Check className="w-4 h-4 text-green-600" />
                    </button>
                  </div>
                ) : (
                  <>
                    <h2 className="text-slate-900">{confabName}</h2>
                    {currentConfabId && (
                      <button
                        onClick={startEditingName}
                        className="p-1 hover:bg-slate-100 rounded"
                        title="Edit name"
                      >
                        <Pencil className="w-3.5 h-3.5 text-slate-400" />
                      </button>
                    )}
                  </>
                )}
              </div>
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
                  {/* Tool Activity Panel */}
                  <ToolActivityPanel recentToolActivity={recentToolActivity} />
                  
                  {messages.map((message) => (
                    <EnhancedMessage 
                      key={message.id} 
                      message={message} 
                      isUser={message.role === 'user'} 
                      user={user}
                    />
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
                    onClick={() => {
                      handleGitHubPush();
                      onNavigate('dashboard');
                    }}
                    variant="outline"
                    size="icon"
                    title="Save and push to GitHub"
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
                {/* Error Alert */}
                {documentError && (
                  <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center justify-between">
                    <p className="text-sm text-red-700">{documentError}</p>
                    <button onClick={() => setDocumentError(null)} className="text-red-400 hover:text-red-600">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.txt,.md"
                    onChange={handleFileUpload}
                    className="hidden"
                    id="file-upload"
                    disabled={!currentConfabId}
                  />
                  <label
                    htmlFor="file-upload"
                    className={`inline-flex items-center gap-2 px-3 py-2 text-sm cursor-pointer rounded-lg border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 transition-colors ${!currentConfabId ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <Paperclip className="w-4 h-4" />
                    Upload Document
                  </label>
                  <span className="text-xs text-slate-500">PDF, TXT, MD</span>
                </div>

                {!currentConfabId && (
                  <p className="text-xs text-amber-600 mt-2">Send a message first to create the confab before uploading files</p>
                )}

                {/* Pending Uploads with Status */}
                {uploadedFiles.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {uploadedFiles.map((file, index) => (
                      <div key={file.tempId} className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                        <div className="flex items-center gap-2 flex-1 min-w-0">
                          <File className="w-4 h-4 text-slate-600 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-slate-700 truncate">{file.name}</p>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-slate-500">({(file.size / 1024).toFixed(1)} KB)</span>
                              {file.status === 'uploading' && (
                                <Badge variant="secondary" className="text-xs">
                                  <Loader2 className="w-3 h-3 animate-spin mr-1" />
                                  Uploading
                                </Badge>
                              )}
                              {file.status === 'indexed' && (
                                <Badge className="text-xs bg-green-100 text-green-700">
                                  Indexed ({file.chunkCount} chunks)
                                </Badge>
                              )}
                              {file.status === 'duplicate' && (
                                <Badge className="text-xs bg-amber-100 text-amber-700">Duplicate</Badge>
                              )}
                              {file.status === 'failed' && (
                                <Badge variant="destructive" className="text-xs">Failed: {file.error}</Badge>
                              )}
                            </div>
                          </div>
                        </div>
                        <button
                          onClick={() => handleRemoveFile(index)}
                          className="text-slate-400 hover:text-red-600 transition-colors ml-2"
                          disabled={file.status === 'uploading'}
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Loading Documents */}
                {documentsLoading && (
                  <div className="mt-3 flex items-center gap-2 text-slate-500">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm">Loading documents...</span>
                  </div>
                )}

                {/* Existing Documents from Server */}
                {documents.length > 0 && (
                  <div className="mt-4">
                    <h4 className="text-sm font-medium text-slate-700 mb-2">
                      Uploaded Documents ({documents.length})
                    </h4>
                    <div className="space-y-2">
                      {documents.map((doc) => (
                        <div key={doc.id} className="flex items-center justify-between p-2 bg-white border border-slate-200 rounded-lg">
                          <div className="flex items-center gap-2">
                            <FileText className="w-4 h-4 text-slate-600" />
                            <div>
                              <p className="text-sm text-slate-700">{doc.filename}</p>
                              <p className="text-xs text-slate-500">
                                {doc.content_type} | {doc.chunk_count} chunks
                              </p>
                            </div>
                          </div>
                          <button
                            onClick={() => handleDeleteDocument(doc.id)}
                            className="text-slate-400 hover:text-red-600 transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>
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