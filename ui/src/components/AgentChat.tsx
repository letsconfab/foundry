import React from 'react';
import { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, Save, Loader2, Paperclip, File, X, Users, User, Bot, HardHat, Pencil, Check, Trash2, FileText, RefreshCw, Eye, CheckCircle2, AlertTriangle, GitBranch } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Avatar, AvatarFallback } from './ui/avatar';
import { apiClient } from '../api/client.js';
import { useAuth } from '../contexts/AuthContext';
import { MessageContent } from './MessageContent';

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'confab-chat';

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
  tempId: string;
  name: string;
  size: number;
  id?: number;
  status: 'pending' | 'uploading' | 'indexed' | 'duplicate' | 'failed';
  error?: string;
  file?: File;
}

interface DocumentListItem {
  id: number;
  document_uuid?: string;
  filename: string;
  content_type: string;
  status: string;
  version_count?: number;
  created_at?: string;
}

interface AgentNode {
  id: string;
  name: string;
  role: string;
}

// Definition Files types and helpers
type DefinitionFileKey = 'purpose' | 'guardrails';
type DefinitionFileStatus = 'hidden' | 'uncommitted' | 'locally-modified' | 'ready-to-push' | 'up-to-date';

interface DefinitionFileState {
  key: DefinitionFileKey;
  fileName: 'PURPOSE.md' | 'GUARDRAILS.md';
  content: string;
  savedContent: string;
  remoteContent: string | null;
  isEditing: boolean;
  visible: boolean;
  acceptedForCommit: boolean;
}

interface ConfabRecord {
  id: number;
  name: string;
  version: string;
  purpose?: string | null;
  guardrails?: Array<{ id: string; rule: string; severity: string; enabled: boolean }> | null;
  github_synced_at?: string | null;
  github_path?: string | null;
}

interface RefreshDefinitionResponse {
  confab_id: number;
  purpose: string | null;
  guardrails_markdown: string | null;
  remote_branch: string | null;
  remote_source: 'branch' | 'default' | 'none' | null;
  refreshed_at: string;
}

interface CommitDefinitionResponse {
  confab_id: number;
  branch?: string | null;
  folder_path?: string | null;
  committed_files: string[];
  commit_sha?: string | null;
  status: 'committed' | 'no-op' | 'saved-locally';
  synced_at: string;
  message?: string | null;
}

interface DefinitionConflict {
  fileKey: DefinitionFileKey;
  local: string;
  remote: string;
  mode: 'choose' | 'manual';
  merged: string;
}

const PURPOSE_TEMPLATE = (name: string, firstUserInput: string) => `# ${name} Purpose

## Overview
${firstUserInput || 'Define what this confab should accomplish for users.'}

## Primary Objectives
- Clarify expected outcomes for this confab
- Keep behavior consistent and measurable
- Document constraints and boundaries
`;

const guardrailsToMarkdown = (name: string, guardrails: Array<{ id: string; rule: string; severity: string; enabled: boolean }> | null | undefined) => {
  if (!guardrails || guardrails.length === 0) {
    return `# Guardrails for ${name}\n\n_No guardrails defined yet._\n`;
  }

  const lines = [`# Guardrails for ${name}`, '', '## Rules', ''];
  guardrails.forEach((g, idx) => {
    lines.push(`${idx + 1}. ${g.rule}`);
  });
  lines.push('');
  return lines.join('\n');
};

const guardrailsFromMarkdown = (markdown: string) => {
  const rules: Array<{ id: string; rule: string; severity: 'error' | 'warning' | 'info'; enabled: boolean }> = [];
  const lines = (markdown || '').split('\n');
  lines.forEach((line) => {
    const trimmed = line.trim();
    const numbered = trimmed.match(/^\d+\.\s+(.*)$/);
    const bulleted = trimmed.match(/^[-*]\s+(.*)$/);
    const match = numbered || bulleted;
    if (!match) return;
    const value = match[1].trim();
    if (!value || value.startsWith('severity:') || value.startsWith('status:')) return;
    rules.push({
      id: `gr-${rules.length + 1}`,
      rule: value,
      severity: 'error',
      enabled: true,
    });
  });

  if (rules.length === 0 && markdown.trim()) {
    rules.push({
      id: 'gr-1',
      rule: markdown.trim(),
      severity: 'error',
      enabled: true,
    });
  }

  return rules;
};

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
      content: `Hi, I'm the Foreman. I'll help you build your agent through a quick conversation.

Let's start with the basics: **What should this agent do?**

Here are some examples:
- "A customer support bot that handles refund requests and tracks order status"
- "An internal assistant that answers questions about company policies"
- "A code reviewer that checks for security issues and suggests fixes"

What's your agent's main job?`,
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

  // Chat ready state (replaces LLM health check - API is assumed available)
  const [chatReady, setChatReady] = useState(true);

  // Definition Files state
  const [confabRecord, setConfabRecord] = useState<ConfabRecord | null>(null);
  const [definitionFiles, setDefinitionFiles] = useState<Record<DefinitionFileKey, DefinitionFileState>>({
    purpose: {
      key: 'purpose',
      fileName: 'PURPOSE.md',
      content: '',
      savedContent: '',
      remoteContent: null,
      isEditing: false,
      visible: false,
      acceptedForCommit: false,
    },
    guardrails: {
      key: 'guardrails',
      fileName: 'GUARDRAILS.md',
      content: '',
      savedContent: '',
      remoteContent: null,
      isEditing: false,
      visible: false,
      acceptedForCommit: false,
    },
  });
  const [definitionLoading, setDefinitionLoading] = useState(false);
  const [definitionError, setDefinitionError] = useState<string | null>(null);
  const [isCommittingDefinitions, setIsCommittingDefinitions] = useState(false);
  const [definitionCommitInfo, setDefinitionCommitInfo] = useState<string | null>(null);
  const [remoteBranchHint, setRemoteBranchHint] = useState<string | null>(null);
  const [definitionConflict, setDefinitionConflict] = useState<DefinitionConflict | null>(null);
  const [showRegistryTokenBanner, setShowRegistryTokenBanner] = useState(false);

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

  // Load confab definition data when confab is available (wait for existing confab to finish loading first)
  useEffect(() => {
    if (!currentConfabId || isLoadingExisting) return;
    let cancelled = false;

    const bootstrap = async () => {
      await loadConfabDefinitionData(currentConfabId);
      if (!cancelled) {
        await refreshDefinitionFromRemote(currentConfabId);
      }
    };

    bootstrap();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentConfabId, isLoadingExisting]);

  // Auto-create purpose draft from first user message
  useEffect(() => {
    // As soon as first question is answered, create a purpose draft if none exists yet.
    const firstUserMessage = messages.find((m) => m.role === 'user');
    if (!firstUserMessage) return;

    setDefinitionFiles((prev) => {
      if (prev.purpose.content.trim()) return prev;
      const draft = PURPOSE_TEMPLATE(confabRecord?.name || confabName, firstUserMessage.content);
      return {
        ...prev,
        purpose: {
          ...prev.purpose,
          content: draft,
          savedContent: prev.purpose.savedContent || draft,
          visible: true,
        },
      };
    });
  }, [messages, confabName, confabRecord?.name]);

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

  const handleSend = async () => {
    if (!input.trim() || sendingRef.current) return;
    sendingRef.current = true;  // Lock immediately, synchronously
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

            // Refresh confab name in case Foreman set it
            refreshConfabName();

            // Refresh definition files in case Foreman updated purpose/guardrails via tools
            if (confabId) {
              loadConfabDefinitionData(confabId);
            }
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
        // V2 response: { document: { id, filename, status, ... }, message }
        const uploadedDoc = response.document;
        setUploadedFiles(prev =>
          prev.map(f => f.tempId === tempId ? {
            ...f,
            id: uploadedDoc?.id,
            status: uploadedDoc?.status === 'active' ? 'indexed' : 'failed',
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

  // Definition Files functions
  const getDefinitionFileStatus = (file: DefinitionFileState): DefinitionFileStatus => {
    if (!file.visible) return 'hidden';
    if (file.acceptedForCommit) return 'ready-to-push';
    const remote = file.remoteContent;
    const current = file.content.trim();
    if (!remote || remote.trim() === '') return 'uncommitted';
    if (current !== remote.trim()) return 'locally-modified';
    return 'up-to-date';
  };

  const updateDefinitionFile = (fileKey: DefinitionFileKey, updater: (prev: DefinitionFileState) => DefinitionFileState) => {
    setDefinitionFiles((prev) => ({
      ...prev,
      [fileKey]: updater(prev[fileKey]),
    }));
  };

  const loadConfabDefinitionData = async (id: number) => {
    setDefinitionLoading(true);
    setDefinitionError(null);
    try {
      const confab: ConfabRecord = await apiClient.getConfab(id);
      setConfabRecord(confab);
      const purpose = confab.purpose || '';
      const guardrailsMd = confab.guardrails && confab.guardrails.length > 0
        ? guardrailsToMarkdown(confab.name || confabName, confab.guardrails || [])
        : '';

      setDefinitionFiles((prev) => ({
        ...prev,
        purpose: {
          ...prev.purpose,
          content: purpose,
          savedContent: purpose,
          visible: prev.purpose.visible || purpose.trim().length > 0,
          acceptedForCommit: false,
        },
        guardrails: {
          ...prev.guardrails,
          content: guardrailsMd,
          savedContent: guardrailsMd,
          visible: prev.guardrails.visible || guardrailsMd.trim().length > 0,
          acceptedForCommit: false,
        },
      }));
      setGithubConnected(!!confab.github_path);
    } catch (err: unknown) {
      setDefinitionError(err instanceof Error ? err.message : 'Failed to load confab definition');
    } finally {
      setDefinitionLoading(false);
    }
  };

  const refreshDefinitionFromRemote = async (id: number) => {
    try {
      const remote: RefreshDefinitionResponse = await apiClient.refreshDefinitionFiles(id);
      setShowRegistryTokenBanner(false);
      setRemoteBranchHint(remote.remote_branch || null);

      // If remote_source is "none", content came from DB not GitHub - don't treat as remote
      const hasGitHubSource = remote.remote_source === 'branch' || remote.remote_source === 'default';

      if (!hasGitHubSource) {
        // No GitHub content found - clear remoteContent and reload from DB to sync UI state
        setDefinitionFiles((prev) => ({
          ...prev,
          purpose: { ...prev.purpose, remoteContent: null },
          guardrails: { ...prev.guardrails, remoteContent: null },
        }));
        await loadConfabDefinitionData(id);
        return;
      }

      const incoming: Partial<Record<DefinitionFileKey, string>> = {
        purpose: remote.purpose || '',
        guardrails: remote.guardrails_markdown || '',
      };
      let hasConflict = false;

      (['purpose', 'guardrails'] as DefinitionFileKey[]).forEach((fileKey) => {
        const remoteContent = incoming[fileKey] ?? '';
        if (!remoteContent.trim()) return;

        const localFile = definitionFiles[fileKey];
        const localUnsaved = localFile.content !== localFile.savedContent;
        const remoteDiffersFromLocal = localFile.content.trim() !== remoteContent.trim();

        if (localUnsaved && remoteDiffersFromLocal) {
          hasConflict = true;
          setDefinitionConflict({
            fileKey,
            local: localFile.content,
            remote: remoteContent,
            mode: 'choose',
            merged: localFile.content,
          });
          return;
        }

        setDefinitionFiles((prev) => ({
          ...prev,
          [fileKey]: {
            ...prev[fileKey],
            content: remoteContent,
            savedContent: remoteContent,
            remoteContent,
            visible: true,
            acceptedForCommit: false,
          },
        }));
      });

      // Only reload from DB if we actually applied remote content (not when remote was empty)
      const hasRemoteContent = (incoming.purpose?.trim() || incoming.guardrails?.trim());
      if (!hasConflict && hasRemoteContent) {
        await loadConfabDefinitionData(id);
      }
    } catch (err: unknown) {
      // Remote refresh is best effort; local editing should continue.
      const message = err instanceof Error ? err.message : 'Failed to refresh definition files from GitHub';
      setDefinitionError(message);
      if (!user?.github_connected && message.toLowerCase().includes('registry sync token missing')) {
        setShowRegistryTokenBanner(true);
      }
    }
  };

  const toggleDefinitionEdit = (fileKey: DefinitionFileKey, isEditing: boolean) => {
    updateDefinitionFile(fileKey, (prev) => ({ ...prev, isEditing }));
  };

  const handleDefinitionContentChange = (fileKey: DefinitionFileKey, content: string) => {
    updateDefinitionFile(fileKey, (prev) => ({
      ...prev,
      content,
      visible: prev.visible || content.trim().length > 0,
      acceptedForCommit: false,
    }));
  };

  const saveDefinitionFile = async (fileKey: DefinitionFileKey) => {
    if (!currentConfabId) return;
    setDefinitionError(null);

    try {
      const file = definitionFiles[fileKey];
      const updatePayload: Record<string, unknown> = {};

      if (fileKey === 'purpose') {
        updatePayload.purpose = file.content;
      } else {
        updatePayload.guardrails = guardrailsFromMarkdown(file.content);
      }

      await apiClient.updateConfab(currentConfabId, updatePayload);
      const refreshed: ConfabRecord = await apiClient.getConfab(currentConfabId);
      setConfabRecord(refreshed);

      const nextSaved = file.content;
      updateDefinitionFile(fileKey, (prev) => ({
        ...prev,
        savedContent: nextSaved,
        visible: true,
        isEditing: false,
        acceptedForCommit: false,
      }));
      setShowRegistryTokenBanner(false);
    } catch (err: unknown) {
      setDefinitionError(err instanceof Error ? err.message : 'Failed to save file');
    }
  };

  const saveAllPendingDefinitionEdits = async () => {
    if (!currentConfabId) return;
    const purposeChanged = definitionFiles.purpose.content !== definitionFiles.purpose.savedContent;
    const guardrailsChanged = definitionFiles.guardrails.content !== definitionFiles.guardrails.savedContent;

    if (!purposeChanged && !guardrailsChanged) return;

    const updatePayload: Record<string, unknown> = {};
    if (purposeChanged) updatePayload.purpose = definitionFiles.purpose.content;
    if (guardrailsChanged) updatePayload.guardrails = guardrailsFromMarkdown(definitionFiles.guardrails.content);

    await apiClient.updateConfab(currentConfabId, updatePayload);
    const refreshed: ConfabRecord = await apiClient.getConfab(currentConfabId);
    setConfabRecord(refreshed);

    setDefinitionFiles((prev) => ({
      ...prev,
      purpose: purposeChanged
        ? { ...prev.purpose, savedContent: prev.purpose.content }
        : prev.purpose,
      guardrails: guardrailsChanged
        ? { ...prev.guardrails, savedContent: prev.guardrails.content }
        : prev.guardrails,
    }));
  };

  const handleAcceptChangesAndCommit = async () => {
    if (!currentConfabId) return;
    setDefinitionError(null);
    setDefinitionCommitInfo(null);
    setIsCommittingDefinitions(true);

    const purposeShouldCommit = definitionFiles.purpose.visible && definitionFiles.purpose.content.trim().length > 0;
    const guardrailsShouldCommit = definitionFiles.guardrails.visible && definitionFiles.guardrails.content.trim().length > 0;

    setDefinitionFiles((prev) => ({
      ...prev,
      purpose: purposeShouldCommit ? { ...prev.purpose, acceptedForCommit: true } : prev.purpose,
      guardrails: guardrailsShouldCommit ? { ...prev.guardrails, acceptedForCommit: true } : prev.guardrails,
    }));

    try {
      await saveAllPendingDefinitionEdits();
      const response: CommitDefinitionResponse = await apiClient.acceptAndCommitDefinitionFiles(currentConfabId, {
        commit_message: `accept-changes-and-commit ${confabRecord?.name || confabName}`,
        include_purpose: purposeShouldCommit,
        include_guardrails: guardrailsShouldCommit,
      });
      setShowRegistryTokenBanner(false);

      const committedSet = new Set(response.committed_files || []);
      setDefinitionFiles((prev) => ({
        ...prev,
        purpose: {
          ...prev.purpose,
          acceptedForCommit: false,
          remoteContent: committedSet.has('PURPOSE.md') ? prev.purpose.content : prev.purpose.remoteContent,
        },
        guardrails: {
          ...prev.guardrails,
          acceptedForCommit: false,
          remoteContent: committedSet.has('GUARDRAILS.md') ? prev.guardrails.content : prev.guardrails.remoteContent,
        },
      }));

      if (response.status === 'saved-locally') {
        setDefinitionCommitInfo('Saved locally. ' + (response.message || 'GitHub sync unavailable.'));
        setRemoteBranchHint(null);
      } else if (response.status === 'no-op') {
        setDefinitionCommitInfo('No file changes to commit.');
        setRemoteBranchHint(response.branch || null);
      } else {
        setDefinitionCommitInfo(
          `Committed ${response.committed_files.length} file(s) on ${response.branch}${response.commit_sha ? ` (${response.commit_sha.slice(0, 7)})` : ''}.`
        );
        setRemoteBranchHint(response.branch || null);
      }
      await loadConfabDefinitionData(currentConfabId);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to commit definition files';
      setDefinitionError(message);
      if (!user?.github_connected && message.toLowerCase().includes('registry sync token missing')) {
        setShowRegistryTokenBanner(true);
      }
    } finally {
      setIsCommittingDefinitions(false);
    }
  };

  const applyConflictResolution = async (action: 'use-local' | 'use-remote' | 'manual') => {
    if (!definitionConflict) return;
    const { fileKey, local, remote, merged } = definitionConflict;

    if (action === 'use-local') {
      updateDefinitionFile(fileKey, (prev) => ({
        ...prev,
        content: local,
      }));
    }

    if (action === 'use-remote') {
      updateDefinitionFile(fileKey, (prev) => ({
        ...prev,
        content: remote,
        savedContent: remote,
        remoteContent: remote,
        acceptedForCommit: false,
      }));
    }

    if (action === 'manual') {
      updateDefinitionFile(fileKey, (prev) => ({
        ...prev,
        content: merged,
      }));
    }

    setDefinitionConflict(null);
  };

  const statusBadgeClass = (status: DefinitionFileStatus) => {
    if (status === 'up-to-date') return 'bg-green-100 text-green-700';
    if (status === 'ready-to-push') return 'bg-blue-100 text-blue-700';
    if (status === 'locally-modified') return 'bg-amber-100 text-amber-700';
    if (status === 'uncommitted') return 'bg-slate-200 text-slate-700';
    return 'bg-slate-100 text-slate-500';
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
                    <span className="text-xs text-emerald-600 self-center" title="Conversation saved">
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
                                  Uploaded
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

              </div>
            </div>
          </Card>
        </div>

        {/* Right Sidebar */}
        <div className="lg:col-span-1 space-y-4">
          {/* Definition Files Card */}
          <Card className="p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <div className="flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-slate-700" />
                <h3 className="text-slate-900 text-sm font-medium">Definition Files</h3>
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1 text-xs h-7"
                  disabled={!currentConfabId || definitionLoading}
                  onClick={() => currentConfabId && refreshDefinitionFromRemote(currentConfabId)}
                >
                  <RefreshCw className="w-3 h-3" />
                  Refresh
                </Button>
                <Button
                  size="sm"
                  className="gap-1 text-xs h-7"
                  disabled={!currentConfabId || isCommittingDefinitions || (!definitionFiles.purpose.visible && !definitionFiles.guardrails.visible)}
                  onClick={handleAcceptChangesAndCommit}
                >
                  {isCommittingDefinitions ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                  Commit
                </Button>
              </div>
            </div>

            {remoteBranchHint && (
              <p className="text-xs text-slate-500 mb-2">
                Branch: <span className="font-mono">{remoteBranchHint}</span>
              </p>
            )}

            {definitionError && (
              <div className="mb-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                {definitionError}
              </div>
            )}

            {definitionCommitInfo && (
              <div className="mb-2 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-700">
                {definitionCommitInfo}
              </div>
            )}

            {showRegistryTokenBanner && !user?.github_connected && (
              <div className="mb-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                Email-login sync requires server configuration. Ask an admin to set `REGISTRY_GITHUB_TOKEN` for writes to `letsconfab/registry`.
              </div>
            )}

            {definitionConflict && (
              <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 p-3">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-amber-700" />
                  <p className="text-xs text-amber-900">
                    Remote changes conflict with local edits in {definitionConflict.fileKey === 'purpose' ? 'PURPOSE.md' : 'GUARDRAILS.md'}.
                  </p>
                </div>
                {definitionConflict.mode === 'manual' ? (
                  <div className="space-y-2">
                    <Textarea
                      className="min-h-[120px] font-mono text-xs"
                      value={definitionConflict.merged}
                      onChange={(e) => setDefinitionConflict((prev) => prev ? { ...prev, merged: e.target.value } : prev)}
                    />
                    <div className="flex gap-2">
                      <Button size="sm" className="text-xs h-7" onClick={() => applyConflictResolution('manual')}>Apply Merge</Button>
                      <Button size="sm" variant="outline" className="text-xs h-7" onClick={() => setDefinitionConflict((prev) => prev ? { ...prev, mode: 'choose' } : prev)}>Back</Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" className="text-xs h-7" onClick={() => applyConflictResolution('use-local')}>Keep Local</Button>
                    <Button size="sm" variant="outline" className="text-xs h-7" onClick={() => applyConflictResolution('use-remote')}>Use Remote</Button>
                    <Button size="sm" className="text-xs h-7" onClick={() => setDefinitionConflict((prev) => prev ? ({ ...prev, mode: 'manual', merged: `${prev.local}\n\n<<<<<<< REMOTE\n${prev.remote}\n>>>>>>>` }) : prev)}>
                      Manual Merge
                    </Button>
                  </div>
                )}
              </div>
            )}

            <div className="space-y-2">
              {(['purpose', 'guardrails'] as DefinitionFileKey[]).map((key) => {
                const file = definitionFiles[key];
                const status = getDefinitionFileStatus(file);
                if (!file.visible) return null;
                return (
                  <div key={key} className="rounded-lg border border-slate-200 p-2">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <FileText className="w-3 h-3 text-slate-600" />
                        <span className="text-xs text-slate-900 font-medium">{file.fileName}</span>
                        <Badge className={`text-[10px] px-1.5 py-0 ${statusBadgeClass(status)}`}>{status}</Badge>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 w-6 p-0"
                          onClick={() => toggleDefinitionEdit(key, !file.isEditing)}
                        >
                          {file.isEditing ? <Eye className="w-3 h-3" /> : <Pencil className="w-3 h-3" />}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 w-6 p-0"
                          disabled={!currentConfabId || file.content.trim().length === 0}
                          onClick={() => saveDefinitionFile(key)}
                        >
                          <Save className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                    {file.isEditing ? (
                      <Textarea
                        className="min-h-[100px] font-mono text-xs"
                        value={file.content}
                        onChange={(e) => handleDefinitionContentChange(key, e.target.value)}
                      />
                    ) : (
                      <div className="max-h-[150px] overflow-auto rounded border border-slate-100 bg-white p-2 prose prose-slate prose-sm max-w-none">
                        {file.content.trim() ? (
                          <ReactMarkdown>{file.content}</ReactMarkdown>
                        ) : (
                          <p className="text-xs text-slate-500">No content yet.</p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
              {!definitionFiles.purpose.visible && !definitionFiles.guardrails.visible && (
                <p className="text-xs text-slate-500">
                  Files will appear as the confab conversation generates drafts.
                </p>
              )}
            </div>
          </Card>

          {/* Documents Card */}
          <Card className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <FileText className="w-4 h-4 text-slate-700" />
              <h3 className="text-slate-900 text-sm font-medium">Documents</h3>
              <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">
                {documents.length}
              </span>
            </div>

            {documentsLoading && (
              <div className="flex items-center gap-2 text-slate-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm">Loading...</span>
              </div>
            )}

            {documents.length > 0 ? (
              <div className="space-y-2 max-h-[200px] overflow-y-auto">
                {documents.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="w-4 h-4 text-slate-600 flex-shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm text-slate-700 truncate">{doc.filename}</p>
                        <p className="text-xs text-slate-500">{doc.content_type}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeleteDocument(doc.id)}
                      className="text-slate-400 hover:text-red-600 transition-colors ml-2"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              !documentsLoading && (
                <p className="text-sm text-slate-500">No documents uploaded yet.</p>
              )
            )}
          </Card>

          {/* Participants Card */}
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