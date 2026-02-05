/**
 * Custom hook for streaming LLM chat conversations.
 *
 * Handles:
 * - SSE streaming from the backend
 * - Message state management
 * - Abort capability
 * - Error handling
 */

import { useState, useCallback, useRef } from 'react';
import { getLLMCredentials, LLMCredentials } from '../utils/llmCredentials';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

interface UseLLMChatOptions {
  systemPrompt?: string;
  onError?: (error: string) => void;
  onStreamStart?: () => void;
  onStreamEnd?: (fullResponse: string) => void;
}

interface UseLLMChatReturn {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  sendMessage: (content: string) => Promise<void>;
  abort: () => void;
  clearMessages: () => void;
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export function useLLMChat(options: UseLLMChatOptions = {}): UseLLMChatReturn {
  const { systemPrompt, onError, onStreamStart, onStreamEnd } = options;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (content: string) => {
    // Get credentials from localStorage
    const credentials = getLLMCredentials();
    if (!credentials) {
      const errorMsg = 'No LLM credentials configured. Please set up your API key.';
      setError(errorMsg);
      onError?.(errorMsg);
      return;
    }

    // Get auth token
    const token = localStorage.getItem('access_token');
    if (!token) {
      const errorMsg = 'Not authenticated. Please log in.';
      setError(errorMsg);
      onError?.(errorMsg);
      return;
    }

    // Add user message
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setError(null);
    setIsStreaming(true);
    onStreamStart?.();

    // Create abort controller
    abortControllerRef.current = new AbortController();

    // Prepare assistant message placeholder
    const assistantMessageId = `assistant-${Date.now()}`;
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
    };

    setMessages(prev => [...prev, assistantMessage]);

    try {
      // Build messages array for API (excluding system messages, they go in systemPrompt)
      const apiMessages = [...messages, userMessage]
        .filter(m => m.role !== 'system')
        .map(m => ({
          role: m.role,
          content: m.content,
        }));

      const response = await fetch(`${API_BASE_URL}/llm/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'X-LLM-API-Key': credentials.apiKey,
        },
        body: JSON.stringify({
          provider: credentials.provider,
          model: credentials.model,
          messages: apiMessages,
          system_prompt: systemPrompt,
          temperature: 0.7,
          max_tokens: 4096,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      // Handle SSE stream
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      const decoder = new TextDecoder();
      let fullResponse = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);

            if (data === '[DONE]') {
              continue;
            }

            if (data.startsWith('[ERROR]')) {
              const errorMsg = data.slice(8);
              throw new Error(errorMsg);
            }

            // Append text chunk
            fullResponse += data;

            // Update message content
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantMessageId
                  ? { ...m, content: fullResponse }
                  : m
              )
            );
          }
        }
      }

      // Mark streaming as complete
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantMessageId
            ? { ...m, isStreaming: false }
            : m
        )
      );

      onStreamEnd?.(fullResponse);

    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        // User cancelled - just mark as complete
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantMessageId
              ? { ...m, isStreaming: false, content: m.content + ' [cancelled]' }
              : m
          )
        );
      } else {
        const errorMsg = err instanceof Error ? err.message : 'Unknown error';
        setError(errorMsg);
        onError?.(errorMsg);

        // Remove the empty assistant message on error
        setMessages(prev => prev.filter(m => m.id !== assistantMessageId));
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, [messages, systemPrompt, onError, onStreamStart, onStreamEnd]);

  const abort = useCallback(() => {
    abortControllerRef.current?.abort();
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    isStreaming,
    error,
    sendMessage,
    abort,
    clearMessages,
    setMessages,
  };
}
