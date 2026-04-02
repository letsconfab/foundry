import { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, Save, Loader2, Paperclip, File, X, Github, Plus, Bot, Shield, Network, Users, Mail, User, ArrowLeft, Folder, FileText, ChevronRight, ChevronDown, ChevronLeft, MessageSquare, List, Trash2, RefreshCw, Eye, Pencil, CheckCircle2, AlertTriangle, GitBranch } from 'lucide-react';
import { apiClient } from '../api/client';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Label } from './ui/label';
import { Input } from './ui/input';
import ReactMarkdown from 'react-markdown';
import { useAuth } from '../contexts/AuthContext';
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
  confabId?: number;
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

interface Participant {
  id: string;
  name: string;
  email?: string;
  role: 'owner' | 'admin' | 'editor' | 'viewer';
  avatar?: string;
  isOnline: boolean;
  type: 'user' | 'confab';
}

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
  branch: string;
  folder_path: string;
  committed_files: string[];
  commit_sha?: string | null;
  status: 'committed' | 'no-op';
  synced_at: string;
}

interface DefinitionConflict {
  fileKey: DefinitionFileKey;
  local: string;
  remote: string;
  mode: 'choose' | 'manual';
  merged: string;
}

// V2 Foreman metadata from API response
interface ForemanV2Metadata {
  stage: string;
  stage_status: 'complete' | 'clarify' | 'skip' | 'error' | null;
  saved_fields: Record<string, unknown> | null;
  next_question: string | null;
  next_stage: string | null;
  clarification_needed: boolean;
}

interface ForemanMetadata {
  response: string;
  confab_id: number;
  thread_id: number;
  setup_progress: {
    completed_steps: number[];
    current_stage: string;
    total_steps: number;
    remaining_steps: number[];
  } | null;
  v2_metadata: ForemanV2Metadata | null;
  is_v2: boolean;
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

export function ConfigureConfabWithThreads({ onNavigate, confabName, version, confabId }: ConfigureConfabProps) {
  const { user } = useAuth();
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

  // Document State
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentError, setDocumentError] = useState<string | null>(null);

  // Participants State
  const [participants] = useState<Participant[]>([
    { id: '1', name: 'John Smith', email: 'john@example.com', role: 'owner', isOnline: true, type: 'user' },
    { id: '2', name: 'Sarah Chen', email: 'sarah@example.com', role: 'editor', isOnline: true, type: 'user' },
    { id: '3', name: 'Mike Johnson', email: 'mike@example.com', role: 'viewer', isOnline: false, type: 'user' },
    { id: '4', name: 'Customer Support Bot', role: 'admin', isOnline: true, type: 'confab' },
    { id: '5', name: 'Data Analyzer', role: 'editor', isOnline: true, type: 'confab' },
    { id: '6', name: 'Code Review Assistant', role: 'viewer', isOnline: false, type: 'confab' },
  ]);

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

  // V2 Foreman state
  const [threadId, setThreadId] = useState<number | null>(null);
  const [foremanMetadata, setForemanMetadata] = useState<ForemanMetadata | null>(null);
  const [stageSummaries, setStageSummaries] = useState<Record<string, string>>({});

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, activeThreadId]);

  // Initialize thread for Foreman chat
  useEffect(() => {
    if (!confabId) return;
    let cancelled = false;

    const initThread = async () => {
      try {
        // Create a new thread for this confab configuration session
        const thread = await apiClient.createThread(`Configure ${confabName}`);
        if (!cancelled && thread?.id) {
          setThreadId(thread.id);
          // Add Foreman as a participant
          await apiClient.addThreadParticipant(thread.id, 'system', null, 'foreman');
        }
      } catch (err) {
        console.error('Failed to initialize thread:', err);
      }
    };

    initThread();
    return () => { cancelled = true; };
  }, [confabId, confabName]);

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

  // Load existing documents when confabId is available
  useEffect(() => {
    if (!confabId) return;
    let cancelled = false;

    setDocumentsLoading(true);
    apiClient.listDocuments(confabId)
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
  }, [confabId]);

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

      if (!hasConflict) {
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

  useEffect(() => {
    if (!confabId) return;
    let cancelled = false;

    const bootstrap = async () => {
      await loadConfabDefinitionData(confabId);
      if (!cancelled) {
        await refreshDefinitionFromRemote(confabId);
      }
    };

    bootstrap();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [confabId]);

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
    if (!confabId) return;
    setDefinitionError(null);

    try {
      const file = definitionFiles[fileKey];
      const updatePayload: Record<string, unknown> = {};

      if (fileKey === 'purpose') {
        updatePayload.purpose = file.content;
      } else {
        updatePayload.guardrails = guardrailsFromMarkdown(file.content);
      }

      await apiClient.updateConfab(confabId, updatePayload);
      const refreshed: ConfabRecord = await apiClient.getConfab(confabId);
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
    if (!confabId) return;
    const purposeChanged = definitionFiles.purpose.content !== definitionFiles.purpose.savedContent;
    const guardrailsChanged = definitionFiles.guardrails.content !== definitionFiles.guardrails.savedContent;

    if (!purposeChanged && !guardrailsChanged) return;

    const updatePayload: Record<string, unknown> = {};
    if (purposeChanged) updatePayload.purpose = definitionFiles.purpose.content;
    if (guardrailsChanged) updatePayload.guardrails = guardrailsFromMarkdown(definitionFiles.guardrails.content);

    await apiClient.updateConfab(confabId, updatePayload);
    const refreshed: ConfabRecord = await apiClient.getConfab(confabId);
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
    if (!confabId) return;
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
      const response: CommitDefinitionResponse = await apiClient.acceptAndCommitDefinitionFiles(confabId, {
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

      setDefinitionCommitInfo(
        response.status === 'no-op'
          ? 'No file changes to commit.'
          : `Committed ${response.committed_files.length} file(s) on ${response.branch}${response.commit_sha ? ` (${response.commit_sha.slice(0, 7)})` : ''}.`
      );
      setRemoteBranchHint(response.branch);
      await loadConfabDefinitionData(confabId);
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

  const handleSend = async () => {
    if (!input.trim() || !threadId) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
      userName: user?.name || 'You',
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

    const messageContent = input;
    setInput('');
    setIsTyping(true);

    try {
      // Call the actual chat API
      const response = await apiClient.chat(threadId, messageContent);

      // Extract Foreman's response from agent_responses
      const foremanResponse = response.agent_responses?.find(
        (r: { sender_name: string }) => r.sender_name === 'Foreman'
      );

      if (foremanResponse) {
        const assistantMessage: Message = {
          id: foremanResponse.id?.toString() || (Date.now() + 1).toString(),
          role: 'assistant',
          content: foremanResponse.content,
          timestamp: new Date(foremanResponse.created_at || Date.now()),
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
      }

      // Update state from foreman metadata (V2 flow)
      if (response.foreman_metadata) {
        setForemanMetadata(response.foreman_metadata);

        // Update current step based on backend state
        const setupProgress = response.foreman_metadata.setup_progress;
        if (setupProgress) {
          const stageToStep: Record<string, number> = {
            purpose: 2,
            participants: 3,
            memory: 4,
            tools: 5,
            guardrails: 6,
            sample_io: 7,
            review: 8,
          };
          const newStep = stageToStep[setupProgress.current_stage] || currentStep;
          setCurrentStep(newStep);
        }

        // Update stage summaries for completed stages
        const v2 = response.foreman_metadata.v2_metadata;
        if (v2?.stage_status === 'complete' && v2?.saved_fields) {
          const stage = v2.stage;
          const summary = JSON.stringify(v2.saved_fields).slice(0, 100);
          setStageSummaries(prev => ({ ...prev, [stage]: summary }));
        }
      }
    } catch (err) {
      console.error('Chat API error:', err);
      // Add error message
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
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
    if (!files || !confabId) return;

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
        response = await apiClient.uploadDocument(confabId, file);
        setDocumentError(null); // Clear error on success
        setUploadedFiles(prev =>
          prev.map(f => f.tempId === tempId ? {
            ...f,
            // Don't store id for duplicates - prevents accidental deletion of existing doc
            id: response.status === 'duplicate' ? undefined : response.document_id,
            status: response.status,
            chunkCount: response.chunk_count,
            file: undefined, // Clear file blob to free memory
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
        const docs = await apiClient.listDocuments(confabId);
        setDocuments(docs);
      } catch {
        // List refresh failure is non-critical
      }
    }
    e.target.value = '';
  };

  const handleDeleteDocument = async (documentId: number) => {
    if (!confabId) return;
    try {
      await apiClient.deleteDocument(confabId, documentId);
      setDocumentError(null); // Clear error on success
      setDocuments(prev => prev.filter(d => d.id !== documentId));
      setUploadedFiles(prev => prev.filter(f => f.id !== documentId));
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Delete failed';
      setDocumentError(errorMessage);
    }
  };

  const handleRemoveFile = async (index: number) => {
    const file = uploadedFiles[index];
    if (file.id && confabId) {
      await handleDeleteDocument(file.id);
    } else {
      setUploadedFiles(prev => prev.filter((_, i) => i !== index));
    }
  };

  // DEPRECATED: V1 keyword-based step detection
  // V2 uses backend metadata from foreman_metadata.setup_progress
  const updateStep = (messageContent: string) => {
    // Only use keyword detection as fallback when V2 metadata is not available
    if (foremanMetadata?.is_v2) return;

    const content = messageContent.toLowerCase();

    for (let i = AGENT_CREATION_STEPS.length - 1; i >= 0; i--) {
      const step = AGENT_CREATION_STEPS[i];
      if (step.keywords.some(keyword => content.includes(keyword))) {
        setCurrentStep(Math.min(step.id + 1, AGENT_CREATION_STEPS.length));
        return;
      }
    }
  };

  // V2: Send skip message to Foreman
  const handleSkipStep = async () => {
    if (!threadId) return;
    setInput('skip');
    await handleSend();
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
              {AGENT_CREATION_STEPS.map(step => {
                const stageKey = ['github', 'purpose', 'participants', 'memory', 'tools', 'guardrails', 'sample_io', 'review'][step.id - 1];
                const stageSummary = stageSummaries[stageKey];
                const isCompleted = step.id < currentStep;
                const isCurrent = step.id === currentStep;

                return (
                  <button
                    key={step.id}
                    onClick={() => setSelectedConfigStep(step.id)}
                    className={`w-full text-sm p-3 rounded-lg transition-all text-left ${
                      selectedConfigStep === step.id
                        ? 'bg-indigo-600 text-white border-2 border-indigo-700'
                        : isCurrent
                        ? 'bg-indigo-100 text-indigo-700 border-2 border-indigo-300'
                        : isCompleted
                        ? 'bg-green-50 text-green-700 border border-green-200 hover:bg-green-100'
                        : 'bg-slate-50 text-slate-500 border border-slate-200 hover:bg-slate-100'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                        selectedConfigStep === step.id
                          ? 'bg-white text-indigo-600'
                          : isCurrent
                          ? 'bg-indigo-600 text-white'
                          : isCompleted
                          ? 'bg-green-600 text-white'
                          : 'bg-slate-300 text-white'
                      }`}>
                        {isCompleted ? <CheckCircle2 className="w-4 h-4" /> : step.id}
                      </div>
                      <div className="flex-1">
                        <span className="block">{step.label}</span>
                        {isCompleted && stageSummary && (
                          <span className="text-xs opacity-70 truncate block">{stageSummary}</span>
                        )}
                        {isCurrent && foremanMetadata?.is_v2 && (
                          <span className="text-xs text-indigo-500 block">Current step</span>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
            {/* Skip Step Button */}
            {foremanMetadata?.is_v2 && currentStep > 1 && currentStep < 8 && (
              <Button
                variant="ghost"
                size="sm"
                className="w-full mt-2 text-slate-500 hover:text-slate-700"
                onClick={handleSkipStep}
              >
                Skip this step
              </Button>
            )}
            </Card>
          </div>
        )}

        {/* Center Panel - Dynamic Content Based on Selected Step */}
        <div className={isSidebarCollapsed ? "lg:col-span-2" : "lg:col-span-2"}>
          <Card className="p-4 mb-4">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <div className="flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-slate-700" />
                <h3 className="text-slate-900">Definition Files</h3>
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-2"
                  disabled={!confabId || definitionLoading}
                  onClick={() => confabId && refreshDefinitionFromRemote(confabId)}
                >
                  <RefreshCw className="w-3 h-3" />
                  Refresh from GitHub
                </Button>
                <Button
                  size="sm"
                  className="gap-2"
                  disabled={!confabId || isCommittingDefinitions || (!definitionFiles.purpose.visible && !definitionFiles.guardrails.visible)}
                  onClick={handleAcceptChangesAndCommit}
                >
                  {isCommittingDefinitions ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                  accept-changes-and-commit
                </Button>
              </div>
            </div>

            {remoteBranchHint && (
              <p className="text-xs text-slate-500 mb-2">
                Remote branch: <span className="font-mono">{remoteBranchHint}</span>
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
                  <p className="text-sm text-amber-900">
                    Remote changes conflict with unsaved local edits in {definitionConflict.fileKey === 'purpose' ? 'PURPOSE.md' : 'GUARDRAILS.md'}.
                  </p>
                </div>
                {definitionConflict.mode === 'manual' ? (
                  <div className="space-y-2">
                    <Textarea
                      className="min-h-[180px] font-mono text-sm"
                      value={definitionConflict.merged}
                      onChange={(e) => setDefinitionConflict((prev) => prev ? { ...prev, merged: e.target.value } : prev)}
                    />
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => applyConflictResolution('manual')}>Apply Merge</Button>
                      <Button size="sm" variant="outline" onClick={() => setDefinitionConflict((prev) => prev ? { ...prev, mode: 'choose' } : prev)}>Back</Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => applyConflictResolution('use-local')}>Keep Local</Button>
                    <Button size="sm" variant="outline" onClick={() => applyConflictResolution('use-remote')}>Use Remote</Button>
                    <Button size="sm" onClick={() => setDefinitionConflict((prev) => prev ? ({ ...prev, mode: 'manual', merged: `${prev.local}\n\n<<<<<<< REMOTE\n${prev.remote}\n>>>>>>>` }) : prev)}>
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
                  <div key={key} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-slate-600" />
                      <span className="text-sm text-slate-900">{file.fileName}</span>
                      <Badge className={`text-[10px] ${statusBadgeClass(status)}`}>{status}</Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="ghost" onClick={() => setSelectedConfigStep(key === 'purpose' ? 2 : 6)}>
                        Open
                      </Button>
                    </div>
                  </div>
                );
              })}
              {!definitionFiles.purpose.visible && !definitionFiles.guardrails.visible && (
                <p className="text-sm text-slate-500">
                  Files will appear as the confab conversation generates drafts.
                </p>
              )}
            </div>
          </Card>

          <Card className="p-4 mb-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Folder className="w-4 h-4 text-slate-700" />
                <h3 className="text-slate-900">Documents</h3>
              </div>
              <Badge variant="secondary" className="text-xs">
                {documentsLoading ? 'Loading' : `${documents.length} file${documents.length === 1 ? '' : 's'}`}
              </Badge>
            </div>

            {documentError && (
              <div className="mb-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                {documentError}
              </div>
            )}

            {!confabId && (
              <p className="text-sm text-amber-700">
                Save your confab first to enable document uploads and indexing.
              </p>
            )}

            {confabId && documentsLoading && (
              <div className="flex items-center gap-2 text-slate-500 text-sm">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading documents...
              </div>
            )}

            {confabId && !documentsLoading && documents.length === 0 && (
              <p className="text-sm text-slate-500">
                No documents uploaded yet. Use <span className="font-medium">Upload Document</span> in the chat panel below.
              </p>
            )}

            {confabId && !documentsLoading && documents.length > 0 && (
              <div className="space-y-2">
                {documents.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2">
                    <div className="min-w-0">
                      <p className="text-sm text-slate-900 truncate">{doc.filename}</p>
                      <p className="text-xs text-slate-500">
                        {doc.content_type} | {doc.chunk_count} chunks
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-red-600 hover:text-red-700"
                      onClick={() => handleDeleteDocument(doc.id)}
                    >
                      Remove
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </Card>

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
                <Badge variant="secondary" className="ml-auto text-xs">PURPOSE.md</Badge>
              </div>
              
              <div className="space-y-4">
                <div>
                  <Label className="text-sm text-slate-700 mb-2 block">Purpose Definition</Label>
                  {definitionFiles.purpose.isEditing ? (
                    <Textarea
                      className="min-h-[400px] font-mono text-sm"
                      value={definitionFiles.purpose.content}
                      onChange={(e) => handleDefinitionContentChange('purpose', e.target.value)}
                    />
                  ) : (
                    <div className="min-h-[240px] max-h-[400px] overflow-auto rounded-lg border border-slate-200 bg-white p-4 prose prose-slate max-w-none">
                      {definitionFiles.purpose.content.trim() ? (
                        <ReactMarkdown>{definitionFiles.purpose.content}</ReactMarkdown>
                      ) : (
                        <p className="text-sm text-slate-500">No purpose draft yet.</p>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex gap-2 flex-wrap">
                  <Button
                    variant="outline"
                    className="gap-2"
                    onClick={() => toggleDefinitionEdit('purpose', !definitionFiles.purpose.isEditing)}
                  >
                    {definitionFiles.purpose.isEditing ? <Eye className="w-4 h-4" /> : <Pencil className="w-4 h-4" />}
                    {definitionFiles.purpose.isEditing ? 'Preview' : 'Edit In Place'}
                  </Button>
                  <Button
                    className="gap-2"
                    disabled={!confabId || definitionFiles.purpose.content.trim().length === 0}
                    onClick={() => saveDefinitionFile('purpose')}
                  >
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
                <Badge variant="secondary" className="ml-auto text-xs">GUARDRAILS.md</Badge>
              </div>
              
              <div className="space-y-4">
                <div>
                  <Label className="text-sm text-slate-700 mb-2 block">System Prompt Extensions</Label>
                  {definitionFiles.guardrails.isEditing ? (
                    <Textarea
                      className="min-h-[400px] font-mono text-sm"
                      value={definitionFiles.guardrails.content}
                      onChange={(e) => handleDefinitionContentChange('guardrails', e.target.value)}
                    />
                  ) : (
                    <div className="min-h-[240px] max-h-[400px] overflow-auto rounded-lg border border-slate-200 bg-white p-4 prose prose-slate max-w-none">
                      {definitionFiles.guardrails.content.trim() ? (
                        <ReactMarkdown>{definitionFiles.guardrails.content}</ReactMarkdown>
                      ) : (
                        <p className="text-sm text-slate-500">No guardrails draft yet.</p>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex gap-2 flex-wrap">
                  <Button
                    variant="outline"
                    className="gap-2"
                    onClick={() => toggleDefinitionEdit('guardrails', !definitionFiles.guardrails.isEditing)}
                  >
                    {definitionFiles.guardrails.isEditing ? <Eye className="w-4 h-4" /> : <Pencil className="w-4 h-4" />}
                    {definitionFiles.guardrails.isEditing ? 'Preview' : 'Edit In Place'}
                  </Button>
                  <Button
                    className="gap-2"
                    disabled={!confabId || definitionFiles.guardrails.content.trim().length === 0}
                    onClick={() => saveDefinitionFile('guardrails')}
                  >
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
                    disabled={!confabId}
                  />
                  <label
                    htmlFor="file-upload"
                    className={`inline-flex items-center gap-2 px-3 py-2 text-sm cursor-pointer rounded-lg border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 transition-colors ${!confabId ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <Paperclip className="w-4 h-4" />
                    Upload Document
                  </label>
                  <span className="text-xs text-slate-500">PDF, TXT, MD</span>
                </div>

                {!confabId && (
                  <p className="text-xs text-amber-600 mt-2">Save your confab first to enable document uploads</p>
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
      </div>
    </div>
  );
}
