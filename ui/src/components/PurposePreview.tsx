import { useMemo } from 'react';
import { FileText, Copy, Check } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { useState } from 'react';

interface PurposePreviewProps {
  content: string;
  confabName: string;
  onApply?: (content: string) => void;
}

/**
 * Extracts the PURPOSE.md content from a chat message.
 * Looks for markdown code blocks.
 */
function extractPurposeContent(fullText: string): string | null {
  // Look for markdown code block
  const codeBlockMatch = fullText.match(/```(?:markdown)?\s*([\s\S]*?)```/);
  if (codeBlockMatch) {
    return codeBlockMatch[1].trim();
  }
  return null;
}

/**
 * Parses PURPOSE.md content into sections for display.
 */
function parsePurposeSections(content: string): { title: string; content: string }[] {
  const sections: { title: string; content: string }[] = [];
  const lines = content.split('\n');

  let currentSection: { title: string; content: string } | null = null;

  for (const line of lines) {
    // Check for heading (## or #)
    const h2Match = line.match(/^##\s+(.+)$/);
    const h1Match = line.match(/^#\s+(.+)$/);

    if (h2Match) {
      if (currentSection) {
        sections.push(currentSection);
      }
      currentSection = { title: h2Match[1], content: '' };
    } else if (h1Match && !currentSection) {
      // Skip the main title (# Confab Name Purpose)
      continue;
    } else if (currentSection) {
      currentSection.content += line + '\n';
    }
  }

  if (currentSection) {
    sections.push(currentSection);
  }

  return sections.map(s => ({ ...s, content: s.content.trim() }));
}

export function PurposePreview({ content, confabName, onApply }: PurposePreviewProps) {
  const [copied, setCopied] = useState(false);

  const purposeContent = useMemo(() => extractPurposeContent(content), [content]);
  const sections = useMemo(
    () => (purposeContent ? parsePurposeSections(purposeContent) : []),
    [purposeContent]
  );

  const handleCopy = async () => {
    if (purposeContent) {
      await navigator.clipboard.writeText(purposeContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleApply = () => {
    if (purposeContent && onApply) {
      onApply(purposeContent);
    }
  };

  if (!purposeContent) {
    return (
      <Card className="p-4 bg-slate-50 border-dashed">
        <div className="flex items-center gap-2 mb-2">
          <FileText className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-medium text-slate-600">PURPOSE.md Preview</span>
        </div>
        <p className="text-sm text-slate-500">
          As you discuss your confab's purpose, the generated content will appear here.
        </p>
      </Card>
    );
  }

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-indigo-600" />
          <span className="text-sm font-medium text-slate-900">PURPOSE.md</span>
          <Badge variant="secondary" className="text-xs">Generated</Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={handleCopy}
          >
            {copied ? (
              <>
                <Check className="w-3 h-3 mr-1" />
                Copied
              </>
            ) : (
              <>
                <Copy className="w-3 h-3 mr-1" />
                Copy
              </>
            )}
          </Button>
          {onApply && (
            <Button size="sm" className="h-7 text-xs" onClick={handleApply}>
              Apply to Confab
            </Button>
          )}
        </div>
      </div>

      <div className="space-y-4 max-h-[400px] overflow-y-auto">
        {/* Title */}
        <div>
          <h3 className="text-lg font-semibold text-slate-900 mb-1">
            {confabName} Purpose
          </h3>
        </div>

        {/* Sections */}
        {sections.map((section, index) => (
          <div key={index} className="border-t border-slate-100 pt-3">
            <h4 className="text-sm font-medium text-indigo-700 mb-2">
              {section.title}
            </h4>
            <div className="text-sm text-slate-600 whitespace-pre-wrap">
              {section.content}
            </div>
          </div>
        ))}
      </div>

      {/* Raw Content Toggle (optional, for debugging) */}
      <details className="mt-4 pt-4 border-t border-slate-100">
        <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-700">
          View raw markdown
        </summary>
        <pre className="mt-2 p-3 bg-slate-50 rounded text-xs text-slate-600 overflow-x-auto whitespace-pre-wrap">
          {purposeContent}
        </pre>
      </details>
    </Card>
  );
}
