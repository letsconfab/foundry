import { useState, useRef, useEffect } from 'react';
import { Send, ThumbsUp, ThumbsDown, ArrowLeft, Bot, User, Users } from 'lucide-react';
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

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'confab-chat' | 'configure';

interface ConfabChatProps {
  onNavigate: (view: View) => void;
  confabName: string;
  version: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  feedback?: 'up' | 'down' | null;
}

interface Participant {
  id: string;
  name: string;
  email?: string;
  avatar?: string;
  isOnline: boolean;
}

export function ConfabChat({ onNavigate, confabName, version }: ConfabChatProps) {
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
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Participants connected to this chat
  const [participants] = useState<Participant[]>([
    { id: '1', name: 'You', isOnline: true },
    { id: '2', name: 'John Smith', email: 'john@example.com', isOnline: true },
    { id: '3', name: 'Sarah Chen', email: 'sarah@example.com', isOnline: false },
  ]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
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
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `I understand you're asking about "${input}". Let me help you with that. This is a demo response to show how the chat interface works with feedback buttons.`,
        timestamp: new Date(),
        feedback: null,
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsTyping(false);
    }, 1500);
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
                  <p className="whitespace-pre-wrap">{message.content}</p>
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

      {/* Participants Sidebar */}
      <div className="hidden lg:block w-80 bg-white border-l border-slate-200 overflow-y-auto">
        <div className="p-6">
          <div className="flex items-center gap-2 mb-6">
            <Users className="w-5 h-5 text-slate-600" />
            <h3 className="text-slate-900">Participants</h3>
            <span className="ml-auto text-sm text-slate-500">
              {participants.filter(p => p.isOnline).length} online
            </span>
          </div>

          <div className="space-y-3">
            {participants.map((participant) => (
              <div
                key={participant.id}
                className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-50 transition-colors"
              >
                <div className="relative">
                  <Avatar className="w-10 h-10">
                    <AvatarFallback className="bg-indigo-100 text-indigo-600">
                      {participant.name.split(' ').map(n => n[0]).join('')}
                    </AvatarFallback>
                  </Avatar>
                  {participant.isOnline && (
                    <div className="absolute bottom-0 right-0 w-3 h-3 bg-green-500 border-2 border-white rounded-full" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-900 truncate">
                    {participant.name}
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