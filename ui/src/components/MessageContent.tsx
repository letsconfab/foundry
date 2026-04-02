import React, { useState, useMemo } from 'react';
import { ChevronDown, ChevronRight, Brain } from 'lucide-react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from './ui/collapsible';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MessageContentProps {
  content: string;
  className?: string;
  /** Set to 'user' for dark backgrounds, 'assistant' for light backgrounds */
  variant?: 'user' | 'assistant';
}

interface ParsedContent {
  mainContent: string;
  thinkBlocks: string[];
}

/**
 * Parses message content to extract <think>...</think> blocks
 */
function parseThinkBlocks(content: string): ParsedContent {
  // Case-insensitive regex for think blocks
  const thinkRegex = /<think>([\s\S]*?)<\/think>/gi;
  const thinkBlocks: string[] = [];

  // Extract all think blocks, filtering out empty ones
  let match;
  while ((match = thinkRegex.exec(content)) !== null) {
    const trimmed = match[1].trim();
    if (trimmed) {
      thinkBlocks.push(trimmed);
    }
  }

  // Remove think blocks from main content (use fresh regex to avoid lastIndex issues)
  const mainContent = content
    .replace(/<think>[\s\S]*?<\/think>/gi, '')
    .trim()
    // Clean up extra newlines left behind
    .replace(/\n{3,}/g, '\n\n');

  return { mainContent, thinkBlocks };
}

/**
 * MessageContent component that renders message text with collapsible think blocks.
 * Think blocks from QWEN model are hidden by default and can be expanded.
 */
export function MessageContent({ content, className = '', variant = 'assistant' }: MessageContentProps) {
  const [isOpen, setIsOpen] = useState(false);

  const { mainContent, thinkBlocks } = useMemo(
    () => parseThinkBlocks(content),
    [content]
  );

  // Styling based on variant (dark vs light background)
  const isUserVariant = variant === 'user';
  const triggerStyles = isUserVariant
    ? 'text-indigo-200 hover:text-white'
    : 'text-slate-500 hover:text-slate-700';
  const blockStyles = isUserVariant
    ? 'bg-indigo-500/30 border-indigo-400/50 text-indigo-100'
    : 'bg-slate-50 border border-slate-200 text-slate-600';
  const labelStyles = isUserVariant ? 'text-indigo-300' : 'text-slate-400';

  // Markdown component classes based on variant
  const markdownClasses = isUserVariant
    ? 'markdown-content markdown-dark'
    : 'markdown-content markdown-light';

  // If no think blocks, render content normally
  if (thinkBlocks.length === 0) {
    return (
      <div className={`${markdownClasses} ${className}`}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    );
  }

  return (
    <div className={className}>
      {/* Main response content */}
      {mainContent && (
        <div className={markdownClasses}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{mainContent}</ReactMarkdown>
        </div>
      )}

      {/* Collapsible think blocks */}
      {thinkBlocks.length > 0 && (
        <Collapsible open={isOpen} onOpenChange={setIsOpen} className="mt-3">
          <CollapsibleTrigger
            className={`flex items-center gap-1.5 text-xs transition-colors ${triggerStyles}`}
            aria-label={isOpen ? 'Hide model reasoning' : 'Show model reasoning'}
          >
            {isOpen ? (
              <ChevronDown className="w-3 h-3" />
            ) : (
              <ChevronRight className="w-3 h-3" />
            )}
            <Brain className="w-3 h-3" />
            <span>{isOpen ? 'Hide reasoning' : 'Show reasoning'}</span>
            {thinkBlocks.length > 1 && (
              <span className={labelStyles}>({thinkBlocks.length} blocks)</span>
            )}
          </CollapsibleTrigger>

          <CollapsibleContent className="mt-2">
            <div className={`rounded-md p-3 space-y-3 ${blockStyles}`}>
              {thinkBlocks.map((block, index) => (
                <div key={index} className="text-sm italic whitespace-pre-wrap">
                  {thinkBlocks.length > 1 && (
                    <span className={`text-xs not-italic block mb-1 ${labelStyles}`}>
                      Reasoning {index + 1}:
                    </span>
                  )}
                  {block}
                </div>
              ))}
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
}

export default MessageContent;
