/**
 * Review Chats — lists threads from DB (table: threads) and messages (table: messages).
 * Data: users (id, name, email, createdAt, password_hash), threads (thread_id, thread_name, createdAt, owner_user_id), messages (id, thread_id, content, time).
 */
import { useState, useEffect } from 'react';
import { ArrowLeft, MessageSquare, Bot, User, Loader2 } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { apiClient } from '../api/client.js';

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'confab-chat' | 'configure' | 'review-chats';

interface ReviewChatsProps {
  onNavigate: (view: View) => void;
}

interface ThreadRow {
  id: number;
  thread_name: string;
  created_at: string;
  owner_user_id: number;
}

interface MessageRow {
  id: number;
  thread_id: number;
  content: string;
  time: string;
  role?: string;
}

export function ReviewChats({ onNavigate }: ReviewChatsProps) {
  const [threads, setThreads] = useState<ThreadRow[]>([]);
  const [messages, setMessages] = useState<MessageRow[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<number | null>(null);
  const [loadingThreads, setLoadingThreads] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setLoadingThreads(true);
    apiClient
      .getThreads()
      .then((data) => {
        if (!cancelled) setThreads(Array.isArray(data) ? data : []);
      })
      .catch((err) => {
        if (!cancelled) setError(err?.message || 'Failed to load threads');
      })
      .finally(() => {
        if (!cancelled) setLoadingThreads(false);
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (selectedThreadId == null) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    setLoadingMessages(true);
    setError(null);
    apiClient
      .getThreadMessages(selectedThreadId)
      .then((data) => {
        if (!cancelled) setMessages(Array.isArray(data) ? data : []);
      })
      .catch((err) => {
        if (!cancelled) setError(err?.message || 'Failed to load messages');
      })
      .finally(() => {
        if (!cancelled) setLoadingMessages(false);
      });
    return () => { cancelled = true; };
  }, [selectedThreadId]);

  const selectedThread = threads.find((t) => t.id === selectedThreadId);
  const formatDate = (s: string) => {
    try {
      const d = new Date(s);
      return d.toLocaleDateString(undefined, { dateStyle: 'short' }) + ' ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    } catch {
      return s;
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6 flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => onNavigate('dashboard')}>
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div>
          <h2 className="text-slate-900">Review Chats</h2>
          <p className="text-slate-600 text-sm">View your saved chat threads and messages</p>
        </div>
      </div>

      {error && (
        <Card className="p-4 mb-4 bg-red-50 border-red-200 text-red-800">
          {error}
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Thread list */}
        <Card className="md:col-span-1 p-4">
          <h3 className="text-slate-900 font-medium mb-3 flex items-center gap-2">
            <MessageSquare className="w-4 h-4" />
            Threads
          </h3>
          {loadingThreads ? (
            <div className="flex items-center gap-2 text-slate-500 py-4">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading…
            </div>
          ) : threads.length === 0 ? (
            <p className="text-slate-500 text-sm py-4">No threads yet.</p>
          ) : (
            <ul className="space-y-1">
              {threads.map((t) => (
                <li key={t.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedThreadId(t.id)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                      selectedThreadId === t.id
                        ? 'bg-indigo-100 text-indigo-900'
                        : 'hover:bg-slate-100 text-slate-700'
                    }`}
                  >
                    <span className="block truncate">{t.thread_name}</span>
                    <span className="text-xs text-slate-500">{formatDate(t.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Messages for selected thread */}
        <div className="md:col-span-2">
          <Card className="p-4 min-h-[320px]">
            {selectedThreadId == null ? (
              <div className="flex flex-col items-center justify-center py-12 text-slate-500">
                <MessageSquare className="w-12 h-12 mb-2 opacity-50" />
                <p>Select a thread to review messages</p>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-slate-900 font-medium truncate">
                    {selectedThread?.thread_name ?? 'Thread'}
                  </h3>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedThreadId(null)}
                  >
                    Clear
                  </Button>
                </div>
                {loadingMessages ? (
                  <div className="flex items-center gap-2 text-slate-500 py-8">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Loading messages…
                  </div>
                ) : messages.length === 0 ? (
                  <p className="text-slate-500 text-sm py-8">No messages in this thread.</p>
                ) : (
                  <div className="space-y-4 overflow-y-auto max-h-[400px] pr-2">
                    {messages.map((msg) => {
                      const isUser = (msg.role || 'user') === 'user';
                      return (
                        <div
                          key={msg.id}
                          className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
                        >
                          {!isUser && (
                            <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                              <Bot className="w-4 h-4 text-indigo-600" />
                            </div>
                          )}
                          <div
                            className={`max-w-[85%] rounded-lg px-3 py-2 ${
                              isUser ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-900'
                            }`}
                          >
                            <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                            <p className={`text-xs mt-1 ${isUser ? 'text-indigo-200' : 'text-slate-500'}`}>
                              {formatDate(msg.time)}
                            </p>
                          </div>
                          {isUser && (
                            <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0">
                              <User className="w-4 h-4 text-slate-600" />
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
