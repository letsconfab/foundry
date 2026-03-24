import React from 'react';
import { useState, useRef, useEffect } from 'react';
import { Send, ThumbsUp, ThumbsDown, ArrowLeft, Bot, User, Users, Save, Loader2 } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Textarea } from './ui/textarea';
import { Avatar, AvatarFallback } from './ui/avatar';
import { Badge } from './ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { apiClient } from '../api/client.js';
import { useAuth } from '../contexts/AuthContext';
import { MessageContent } from './MessageContent';

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'confab-chat' | 'configure' | 'review-chats';

interface ConfabChatProps {
  onNavigate: (view: View) => void;
  confabName: string;
  version: string;
  /** When set, load messages from this thread and persist new messages to DB */
  threadId?: number | null;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  feedback?: 'up' | 'down' | null;
}

interface Participant {
  id: number | string;
  name: string;
  email?: string;
  avatar?: string;
  isOnline?: boolean;
  isCurrentUser?: boolean;
}

export function ConfabChat({ onNavigate, confabName, version, threadId: threadIdProp }: ConfabChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: `Hello! I'm ${confabName}. How can I help you today?`,
      timestamp: new Date(),
      feedback: null,
    },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [feedbackDialogOpen, setFeedbackDialogOpen] = useState(false);
  const [feedbackText, setFeedbackText] = useState('');
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);
  const [savingToChats, setSavingToChats] = useState(false);
  /** Thread id from API: either passed in (review) or auto-created on first send. Used to persist every message. */
  const [currentThreadId, setCurrentThreadId] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  /** Participants loaded from users table */
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [participantsLoading, setParticipantsLoading] = useState(true);
  const { user: currentUser } = useAuth();

  const effectiveThreadId = threadIdProp ?? currentThreadId;

  // Load messages from DB when threadId is provided (review/continue chat)
  useEffect(() => {
    if (threadIdProp == null) return;
    apiClient.getThreadMessages(threadIdProp).then((list) => {
      if (!Array.isArray(list) || list.length === 0) return;
      const loaded: Message[] = list.map((m) => ({
        id: String(m.id),
        role: (m.role === 'assistant' ? 'assistant' : 'user') as 'user' | 'assistant',
        content: m.content,
        timestamp: new Date(m.time),
        feedback: null,
      }));
      setMessages(loaded);
    }).catch(() => {});
  }, [threadIdProp]);

  // Load participants from users table
  useEffect(() => {
    let cancelled = false;
    setParticipantsLoading(true);
    apiClient
      .getUsers()
      .then((list) => {
        if (cancelled || !Array.isArray(list)) return;
        const currentId = currentUser?.id;
        const mapped: Participant[] = list.map((u) => ({
          id: u.id,
          name: u.name,
          email: u.email,
          isCurrentUser: u.id === currentId,
        }));
        setParticipants(mapped);
      })
      .catch(() => {
        if (!cancelled) setParticipants([]);
      })
      .finally(() => {
        if (!cancelled) setParticipantsLoading(false);
      });
    return () => { cancelled = true; };
  }, [currentUser?.id]);

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

    let tid = effectiveThreadId;
    if (tid == null) {
      try {
        const name = `${confabName} – ${new Date().toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}`;
        const thread = await apiClient.createThread(name);
        tid = thread?.id ?? null;
        if (tid != null) setCurrentThreadId(tid);
        if (tid != null && messages[0]?.role === 'assistant') {
          await apiClient.addMessage(tid, messages[0].content, 'assistant');
        }
      } catch {
        tid = null;
      }
    }
    if (tid != null) {
      apiClient.addMessage(tid, content, 'user').catch(() => {});
    }

    const assistantContent = `I understand you're asking about "${content}". Let me help you with that. This is a demo response to show how the chat interface works with feedback buttons.`;
    setTimeout(() => {
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: assistantContent,
        timestamp: new Date(),
        feedback: null,
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsTyping(false);
      if (tid != null) {
        apiClient.addMessage(tid, assistantContent, 'assistant').catch(() => {});
      }
    }, 1500);
  };

  const handleSaveToMyChats = async () => {
    if (messages.length === 0) return;
    setSavingToChats(true);
    try {
      const name = `${confabName} – ${new Date().toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}`;
      const thread = await apiClient.createThread(name);
      const tid = thread?.id;
      if (tid) {
        for (const m of messages) {
          if (m.role === 'assistant' && m.content === `Hello! I'm ${confabName}. How can I help you today?`) continue;
          await apiClient.addMessage(tid, m.content, m.role);
        }
        onNavigate('review-chats');
      }
    } catch {
      // ignore
    } finally {
      setSavingToChats(false);
    }
  };

  const handleFeedback = (messageId: string, feedback: 'up' | 'down') => {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId
          ? { ...msg, feedback: msg.feedback === feedback ? null : feedback }
          : msg
      )
    );
  };

  const openFeedbackDialog = (messageId: string) => {
    setSelectedMessageId(messageId);
    setFeedbackDialogOpen(true);
  };

  const submitFeedback = () => {
    if (selectedMessageId && feedbackText.trim()) {
      // In a real app, this would send the feedback to the confab creator
      console.log('Feedback submitted for message:', selectedMessageId, feedbackText);
      handleFeedback(selectedMessageId, 'down');
    }
    setFeedbackDialogOpen(false);
    setFeedbackText('');
    setSelectedMessageId(null);
  };

  return (
    <div className="flex h-[calc(100vh-64px)]">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Chat Header */}
        <div className="bg-white border-b border-slate-200 px-4 sm:px-6 py-4">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onNavigate('dashboard')}
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-lg flex items-center justify-center">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-slate-900">{confabName}</h2>
                  <Badge variant="outline" className="text-xs">
                    v{version}
                  </Badge>
                </div>
                <p className="text-sm text-slate-500">Online</p>
              </div>
            </div>
            {!effectiveThreadId && messages.length > 1 && (
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                disabled={savingToChats}
                onClick={handleSaveToMyChats}
              >
                {savingToChats ? <span className="animate-pulse">Saving…</span> : <Save className="w-4 h-4" />}
                Save to my chats
              </Button>
            )}
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-6 space-y-6">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex gap-3 ${
                message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              {message.role === 'assistant' && (
                <div className="w-8 h-8 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-full flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4 text-white" />
                </div>
              )}
              
              <div className={`flex flex-col gap-2 max-w-[70%] ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
                <Card
                  className={`p-4 ${
                    message.role === 'user'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white text-slate-900'
                  }`}
                >
                  <MessageContent content={message.content} variant={message.role} />
                </Card>
                
                {/* Feedback buttons for assistant messages */}
                {message.role === 'assistant' && (
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className={`h-8 px-2 ${
                        message.feedback === 'up'
                          ? 'text-green-600 bg-green-50'
                          : 'text-slate-400 hover:text-green-600'
                      }`}
                      onClick={() => handleFeedback(message.id, 'up')}
                    >
                      <ThumbsUp className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className={`h-8 px-2 ${
                        message.feedback === 'down'
                          ? 'text-red-600 bg-red-50'
                          : 'text-slate-400 hover:text-red-600'
                      }`}
                      onClick={() => {
                        handleFeedback(message.id, 'down');
                        openFeedbackDialog(message.id);
                      }}
                    >
                      <ThumbsDown className="w-4 h-4" />
                    </Button>
                    <span className="text-xs text-slate-400 ml-2">
                      {message.timestamp.toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>
                )}

                {/* Timestamp for user messages */}
                {message.role === 'user' && (
                  <span className="text-xs text-slate-400">
                    {message.timestamp.toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                )}
              </div>

              {message.role === 'user' && (
                <div className="w-8 h-8 bg-slate-200 rounded-full flex items-center justify-center flex-shrink-0">
                  <User className="w-4 h-4 text-slate-600" />
                </div>
              )}
            </div>
          ))}

          {isTyping && (
            <div className="flex gap-3 items-start">
              <div className="w-8 h-8 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-full flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <Card className="p-4 bg-white">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </Card>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="bg-white border-t border-slate-200 p-4 sm:p-6">
          <div className="flex gap-3 items-end">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Type your message..."
              className="min-h-[44px] max-h-32 resize-none"
            />
            <Button
              onClick={handleSend}
              disabled={!input.trim() || isTyping}
              className="flex-shrink-0"
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Press Enter to send, Shift+Enter for new line
          </p>
        </div>
      </div>

      {/* Participants Sidebar — loaded from users table */}
      <div className="hidden lg:block w-80 bg-white border-l border-slate-200 overflow-y-auto">
        <div className="p-6">
          <div className="flex items-center gap-2 mb-6">
            <Users className="w-5 h-5 text-slate-600" />
            <h3 className="text-slate-900">Participants</h3>
            {!participantsLoading && (
              <span className="ml-auto text-sm text-slate-500">
                {participants.length} user{participants.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>

          {participantsLoading ? (
            <div className="flex items-center gap-2 text-slate-500 py-4">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading…
            </div>
          ) : participants.length === 0 ? (
            <p className="text-sm text-slate-500 py-4">No users yet.</p>
          ) : (
            <div className="space-y-3">
              {participants.map((participant) => (
                <div
                  key={participant.id}
                  className={`flex items-center gap-3 p-3 rounded-lg transition-colors ${
                    participant.isCurrentUser ? 'bg-indigo-50 ring-1 ring-indigo-200' : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="relative">
                    <Avatar className="w-10 h-10">
                      <AvatarFallback className={participant.isCurrentUser ? 'bg-indigo-200 text-indigo-700' : 'bg-indigo-100 text-indigo-600'}>
                        {participant.name.split(' ').map(n => n[0]).join('') || '?'}
                      </AvatarFallback>
                    </Avatar>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-900 truncate flex items-center gap-1.5">
                      {participant.name}
                      {participant.isCurrentUser && (
                        <span className="text-xs text-indigo-600 font-medium">(you)</span>
                      )}
                    </p>
                    {participant.email && (
                      <p className="text-xs text-slate-500 truncate">
                        {participant.email}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Feedback Dialog */}
      <Dialog open={feedbackDialogOpen} onOpenChange={setFeedbackDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Provide Feedback</DialogTitle>
            <DialogDescription>
              Let us know how we can improve our response.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <Textarea
              value={feedbackText}
              onChange={(e) => setFeedbackText(e.target.value)}
              placeholder="Type your feedback..."
              className="min-h-[44px] max-h-32 resize-none"
            />
          </div>
          <DialogFooter>
            <Button
              onClick={submitFeedback}
              disabled={!feedbackText.trim()}
              className="flex-shrink-0"
            >
              Submit Feedback
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}