import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Send,
  Sparkles,
  Loader2,
  Bot,
  User,
  Settings,
  StopCircle,
  RefreshCw,
  X,
} from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Avatar, AvatarFallback } from './ui/avatar';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { LLMCredentialsDialog } from './LLMCredentialsDialog';
import { PurposePreview } from './PurposePreview';
import { useLLMChat, ChatMessage } from '../hooks/useLLMChat';
import { hasLLMCredentials, getLLMCredentials, MODEL_DISPLAY_NAMES } from '../utils/llmCredentials';

// System prompt for the Purpose Defining Agent
const PURPOSE_AGENT_SYSTEM_PROMPT = `You are a friendly, thoughtful assistant helping users define the purpose of their AI confab (a custom AI agent configuration).

## Your Approach:
- Ask ONE question at a time
- Wait for the user's response before moving on
- Be genuinely curious and encourage elaboration
- Reflect back what you understand to confirm
- Don't rush - this is an unhurried discovery process
- Be warm and conversational, not robotic

## Topics to Cover (in roughly this order):
1. **Core Problem** - What problem or need does this confab solve? What gap does it fill?
2. **Target Users** - Who will use this confab? What are their characteristics?
3. **Key Capabilities** - What should the confab be able to do? What actions, tasks, or responses?
4. **Constraints** - What should it NOT do? What's out of scope?
5. **Success Criteria** - How will you know if it's working well? What does success look like?
6. **Tone & Style** - How should it communicate? Formal, casual, technical, friendly?

## Important Guidelines:
- Start by warmly greeting the user and asking about the core problem their confab should solve
- After each response, acknowledge what they said and ask a natural follow-up
- If answers are brief, gently probe for more detail
- When you've covered all topics, summarize what you've learned
- Only then generate the structured PURPOSE.md content

## When Ready to Generate:
After covering all topics, say something like "I think I have a good understanding now. Let me create a PURPOSE.md for you..."

Then generate a well-structured markdown document with these sections:
- **Overview** - A clear, concise description of what this confab is and does
- **Primary Objectives** - Bullet points of the main goals
- **Key Capabilities** - What the confab can do
- **Target Use Cases** - Who uses it and for what
- **Constraints & Boundaries** - What it won't do
- **Success Metrics** - How to measure effectiveness

Format the PURPOSE.md content inside a code block like:
\`\`\`markdown
# [Confab Name] Purpose

## Overview
...

## Primary Objectives
...
\`\`\`

This allows the user to easily copy and use it.`;

interface PurposeDefiningAgentProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  confabName: string;
  onPurposeGenerated?: (content: string) => void;
}

export function PurposeDefiningAgent({
  open,
  onOpenChange,
  confabName,
  onPurposeGenerated,
}: PurposeDefiningAgentProps) {
  const [input, setInput] = useState('');
  const [showCredentialsDialog, setShowCredentialsDialog] = useState(false);
  const [credentialsConfigured, setCredentialsConfigured] = useState(false);
  const [generatedPurpose, setGeneratedPurpose] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    messages,
    isStreaming,
    error,
    sendMessage,
    abort,
    clearMessages,
    setMessages,
  } = useLLMChat({
    systemPrompt: PURPOSE_AGENT_SYSTEM_PROMPT,
    onError: (err) => {
      console.error('LLM Chat error:', err);
    },
    onStreamEnd: (fullResponse) => {
      // Check if response contains PURPOSE.md content
      if (fullResponse.includes('```markdown') || fullResponse.includes('```')) {
        setGeneratedPurpose(fullResponse);
      }
    },
  });

  // Check for credentials on mount and when dialog opens
  useEffect(() => {
    if (open) {
      setCredentialsConfigured(hasLLMCredentials());
    }
  }, [open]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Add initial greeting when opening (if no messages exist)
  useEffect(() => {
    if (open && messages.length === 0 && credentialsConfigured) {
      // Add a welcome message from the assistant
      const welcomeMessage: ChatMessage = {
        id: 'welcome',
        role: 'assistant',
        content: `Hi! I'm here to help you define the purpose of "${confabName}". Let's take our time to really understand what you're trying to build.\n\nTo start, could you tell me: **What problem or need is this confab meant to solve?** What gap are you trying to fill?`,
        timestamp: new Date(),
      };
      setMessages([welcomeMessage]);
    }
  }, [open, credentialsConfigured, confabName, messages.length, setMessages]);

  const handleSend = useCallback(() => {
    if (!input.trim() || isStreaming) return;
    sendMessage(input);
    setInput('');
  }, [input, isStreaming, sendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleReset = () => {
    clearMessages();
    setGeneratedPurpose(null);
    // Re-add welcome message
    if (credentialsConfigured) {
      const welcomeMessage: ChatMessage = {
        id: 'welcome-' + Date.now(),
        role: 'assistant',
        content: `Hi! I'm here to help you define the purpose of "${confabName}". Let's take our time to really understand what you're trying to build.\n\nTo start, could you tell me: **What problem or need is this confab meant to solve?** What gap are you trying to fill?`,
        timestamp: new Date(),
      };
      setMessages([welcomeMessage]);
    }
  };

  const handleApplyPurpose = (content: string) => {
    onPurposeGenerated?.(content);
    onOpenChange(false);
  };

  const credentials = getLLMCredentials();
  const modelName = credentials ? (MODEL_DISPLAY_NAMES[credentials.model] || credentials.model) : '';

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-4xl h-[80vh] flex flex-col p-0">
          <DialogHeader className="px-6 py-4 border-b border-slate-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-lg flex items-center justify-center">
                  <Sparkles className="w-5 h-5 text-white" />
                </div>
                <div>
                  <DialogTitle>AI-Assisted Purpose Discovery</DialogTitle>
                  <p className="text-sm text-slate-500">
                    Let's define what "{confabName}" should do
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {credentialsConfigured && (
                  <Badge variant="secondary" className="text-xs">
                    {modelName}
                  </Badge>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => setShowCredentialsDialog(true)}
                  title="Configure LLM"
                >
                  <Settings className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </DialogHeader>

          {!credentialsConfigured ? (
            // Credentials Not Configured State
            <div className="flex-1 flex items-center justify-center p-6">
              <div className="text-center max-w-md">
                <div className="w-16 h-16 bg-indigo-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Settings className="w-8 h-8 text-indigo-600" />
                </div>
                <h3 className="text-lg font-semibold text-slate-900 mb-2">
                  Configure Your LLM
                </h3>
                <p className="text-sm text-slate-600 mb-6">
                  To use AI-assisted purpose discovery, you'll need to provide your own
                  API key for Anthropic (Claude) or OpenAI (GPT).
                </p>
                <Button onClick={() => setShowCredentialsDialog(true)}>
                  <Settings className="w-4 h-4 mr-2" />
                  Set Up API Key
                </Button>
              </div>
            </div>
          ) : (
            // Chat Interface
            <div className="flex-1 flex overflow-hidden">
              {/* Messages Area */}
              <div className="flex-1 flex flex-col min-w-0">
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex gap-3 ${
                        message.role === 'user' ? 'justify-end' : 'justify-start'
                      }`}
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
                        <div className="whitespace-pre-wrap text-sm">
                          {message.content}
                          {message.isStreaming && (
                            <span className="inline-block w-2 h-4 bg-current animate-pulse ml-1" />
                          )}
                        </div>
                        <p
                          className={`text-xs mt-2 ${
                            message.role === 'user'
                              ? 'text-indigo-200'
                              : 'text-slate-500'
                          }`}
                        >
                          {message.timestamp.toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </p>
                      </div>
                      {message.role === 'user' && (
                        <Avatar className="w-8 h-8 flex-shrink-0">
                          <AvatarFallback className="bg-slate-300">
                            <User className="w-4 h-4 text-slate-600" />
                          </AvatarFallback>
                        </Avatar>
                      )}
                    </div>
                  ))}

                  {isStreaming && messages[messages.length - 1]?.role === 'user' && (
                    <div className="flex gap-3 justify-start">
                      <Avatar className="w-8 h-8 flex-shrink-0">
                        <AvatarFallback className="bg-gradient-to-br from-indigo-600 to-purple-600">
                          <Bot className="w-4 h-4 text-white" />
                        </AvatarFallback>
                      </Avatar>
                      <div className="bg-slate-100 rounded-lg px-4 py-3 flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin text-slate-600" />
                        <span className="text-sm text-slate-600">Thinking...</span>
                      </div>
                    </div>
                  )}

                  {error && (
                    <div className="flex justify-center">
                      <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 max-w-md">
                        <p className="text-sm text-red-700">{error}</p>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="mt-2 text-red-600 hover:text-red-700"
                          onClick={() => setShowCredentialsDialog(true)}
                        >
                          Check API Settings
                        </Button>
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
                      placeholder="Share your thoughts..."
                      className="min-h-[60px] max-h-32 resize-none"
                      disabled={isStreaming}
                    />
                    <div className="flex flex-col gap-2">
                      {isStreaming ? (
                        <Button
                          onClick={abort}
                          variant="destructive"
                          size="icon"
                          className="h-[60px]"
                          title="Stop generating"
                        >
                          <StopCircle className="w-5 h-5" />
                        </Button>
                      ) : (
                        <Button
                          onClick={handleSend}
                          disabled={!input.trim()}
                          size="icon"
                          className="h-[60px]"
                        >
                          <Send className="w-5 h-5" />
                        </Button>
                      )}
                      <Button
                        onClick={handleReset}
                        variant="outline"
                        size="icon"
                        title="Start over"
                        disabled={isStreaming}
                      >
                        <RefreshCw className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                  <p className="text-xs text-slate-500 mt-2">
                    Press Enter to send, Shift+Enter for new line
                  </p>
                </div>
              </div>

              {/* Preview Panel (shows when purpose is generated) */}
              {generatedPurpose && (
                <div className="w-80 border-l border-slate-200 p-4 overflow-y-auto bg-slate-50">
                  <PurposePreview
                    content={generatedPurpose}
                    confabName={confabName}
                    onApply={handleApplyPurpose}
                  />
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      <LLMCredentialsDialog
        open={showCredentialsDialog}
        onOpenChange={setShowCredentialsDialog}
        onCredentialsSaved={() => {
          setCredentialsConfigured(true);
          // Trigger welcome message after credentials are saved
          if (messages.length === 0) {
            const welcomeMessage: ChatMessage = {
              id: 'welcome-' + Date.now(),
              role: 'assistant',
              content: `Hi! I'm here to help you define the purpose of "${confabName}". Let's take our time to really understand what you're trying to build.\n\nTo start, could you tell me: **What problem or need is this confab meant to solve?** What gap are you trying to fill?`,
              timestamp: new Date(),
            };
            setMessages([welcomeMessage]);
          }
        }}
      />
    </>
  );
}
