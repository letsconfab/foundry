import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Upload, FileText, Loader2, Trash2, RefreshCw, AlertCircle } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { cn } from './ui/utils';
import { apiClient } from '../api/client.js';
import { toast } from 'sonner';

interface DocumentListItem {
  id: number;
  document_uuid?: string;
  filename: string;
  content_type: string;
  status: string;
  version_count?: number;
  created_at?: string;
}

interface DocumentManagementDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  confabId: number;
  confabName: string;
}

const MAX_FILE_SIZE = 50 * 1024 * 1024;
const ALLOWED_EXTENSIONS = [
  '.txt', '.md', '.csv', '.json', '.yaml', '.yml', '.toml',
  '.pdf', '.docx', '.xlsx',
  '.png', '.jpg', '.jpeg', '.gif', '.webp', '.tiff',
];

const validateFile = (file: File): string | null => {
  if (file.size > MAX_FILE_SIZE) {
    return `File too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Maximum is 50MB.`;
  }
  const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return `Unsupported file type "${ext}". Supported: ${ALLOWED_EXTENSIONS.join(', ')}`;
  }
  return null;
};

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};

const formatTimestamp = (value?: string): string => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
};

export function DocumentManagementDialog({
  open,
  onOpenChange,
  confabId,
  confabName,
}: DocumentManagementDialogProps) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [replacingId, setReplacingId] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const replaceInputRef = useRef<HTMLInputElement>(null);
  const replaceTargetRef = useRef<number | null>(null);

  const fetchDocuments = useCallback(async () => {
    setLoadingDocs(true);
    try {
      const docs = await apiClient.listDocuments(confabId);
      setDocuments(docs || []);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load documents';
      toast.error(message);
    } finally {
      setLoadingDocs(false);
    }
  }, [confabId]);

  useEffect(() => {
    if (open) {
      fetchDocuments();
    } else {
      setDocuments([]);
      setDeletingId(null);
      setReplacingId(null);
      setUploading(false);
    }
  }, [open, fetchDocuments]);

  const handleUpload = async (file: File) => {
    const error = validateFile(file);
    if (error) {
      toast.error(error);
      return;
    }
    setUploading(true);
    try {
      const response = await apiClient.uploadDocument(confabId, file);
      const doc = response.document;
      if (doc) {
        setDocuments(prev => [...prev, doc]);
      }
      toast.success(`Uploaded ${file.name}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      toast.error(message);
    } finally {
      setUploading(false);
    }
  };

  const handleReplace = async (documentId: number, file: File) => {
    const error = validateFile(file);
    if (error) {
      toast.error(error);
      return;
    }
    setReplacingId(documentId);
    try {
      await apiClient.createDocumentVersion(confabId, documentId, file);
      setDocuments(prev =>
        prev.map(d =>
          d.id === documentId
            ? { ...d, version_count: (d.version_count || 1) + 1 }
            : d
        )
      );
      toast.success(`Replaced with ${file.name}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Replace failed';
      toast.error(message);
    } finally {
      setReplacingId(null);
    }
  };

  const handleDelete = async (documentId: number) => {
    setDeletingId(documentId);
    try {
      await apiClient.deleteDocument(confabId, documentId);
      setDocuments(prev => prev.filter(d => d.id !== documentId));
      toast.success('Document deleted');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Delete failed';
      toast.error(message);
    } finally {
      setDeletingId(null);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!uploading) setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (uploading) return;
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
    e.target.value = '';
  };

  const handleReplaceInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    const targetId = replaceTargetRef.current;
    if (file && targetId != null) {
      handleReplace(targetId, file);
    }
    e.target.value = '';
    replaceTargetRef.current = null;
  };

  const triggerReplace = (documentId: number) => {
    replaceTargetRef.current = documentId;
    replaceInputRef.current?.click();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Manage Documents
          </DialogTitle>
          <DialogDescription>
            for {confabName}
          </DialogDescription>
        </DialogHeader>

        <Badge variant="secondary" className="w-fit bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
          {documents.length} document{documents.length !== 1 ? 's' : ''}
        </Badge>

        {/* Upload dropzone */}
        <div
          className={cn(
            'border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors',
            uploading && 'opacity-50 cursor-not-allowed',
            isDragging
              ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30'
              : 'border-slate-300 dark:border-slate-600 hover:border-indigo-400 hover:bg-slate-50 dark:hover:bg-slate-800/50'
          )}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !uploading && fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={ALLOWED_EXTENSIONS.join(',')}
            className="hidden"
            onChange={handleFileInputChange}
          />
          {uploading ? (
            <>
              <Loader2 className="h-8 w-8 mx-auto mb-2 text-indigo-500 animate-spin" />
              <p className="text-sm text-slate-600 dark:text-slate-300">Uploading...</p>
            </>
          ) : (
            <>
              <Upload className="h-8 w-8 mx-auto mb-2 text-slate-400 dark:text-slate-500" />
              <p className="text-sm text-slate-600 dark:text-slate-300 mb-1">
                Drop a file here or click to browse
              </p>
              <p className="text-xs text-slate-400 dark:text-slate-500">
                PDF, TXT, MD, CSV, JSON, YAML, TOML, DOCX, XLSX, images — up to 50MB
              </p>
            </>
          )}
        </div>

        {/* Hidden input for version replacement */}
        <input
          ref={replaceInputRef}
          type="file"
          accept={ALLOWED_EXTENSIONS.join(',')}
          className="hidden"
          onChange={handleReplaceInputChange}
        />

        {/* Document list */}
        {loadingDocs ? (
          <div className="flex items-center justify-center py-6">
            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
            <span className="ml-2 text-sm text-slate-500">Loading documents...</span>
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-4">
            <AlertCircle className="h-6 w-6 mx-auto mb-2 text-slate-300 dark:text-slate-600" />
            <p className="text-sm text-slate-500 dark:text-slate-400">No documents yet</p>
          </div>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between gap-3 rounded-md border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900/60"
              >
                <div className="min-w-0 flex items-start gap-2">
                  <FileText className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-400" />
                  <div className="min-w-0">
                    <p className="truncate text-sm text-slate-700 dark:text-slate-200">
                      {doc.filename}
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                      {formatTimestamp(doc.created_at) && <span>{formatTimestamp(doc.created_at)}</span>}
                      {doc.version_count ? (
                        <span>{doc.version_count} version{doc.version_count !== 1 ? 's' : ''}</span>
                      ) : null}
                      <span className="uppercase">{doc.content_type?.split('/').pop() || 'file'}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    disabled={replacingId === doc.id}
                    onClick={() => triggerReplace(doc.id)}
                    title="Replace with new version"
                  >
                    {replacingId === doc.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" />
                    ) : (
                      <RefreshCw className="h-3.5 w-3.5 text-slate-400 hover:text-indigo-500" />
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    disabled={deletingId === doc.id}
                    onClick={() => handleDelete(doc.id)}
                    title="Delete document"
                  >
                    {deletingId === doc.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5 text-slate-400 hover:text-red-500" />
                    )}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}

        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
