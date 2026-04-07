import React, { useState, useRef } from 'react';
import { Upload, FileText, Check, AlertCircle, Loader2, Trash2 } from 'lucide-react';
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

interface UploadedFile {
  tempId: string;
  name: string;
  size: number;
  id?: number;
  status: 'uploading' | 'indexed' | 'failed';
  error?: string;
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

interface DocumentUploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  confabId: number;
  onUploadComplete?: (count: number) => void;
  existingDocuments?: DocumentListItem[];
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const ALLOWED_EXTENSIONS = ['.pdf', '.txt', '.md'];

const validateFile = (file: File): string | null => {
  if (file.size > MAX_FILE_SIZE) {
    return `File too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Maximum is 10MB.`;
  }

  const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return `Unsupported file type. Use PDF, TXT, or MD.`;
  }

  return null;
};

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};

export function DocumentUploadDialog({
  open,
  onOpenChange,
  confabId,
  onUploadComplete,
  existingDocuments = [],
}: DocumentUploadDialogProps) {
  const [uploadState, setUploadState] = useState<'ready' | 'uploading' | 'success' | 'error'>('ready');
  const [currentFile, setCurrentFile] = useState<File | null>(null);
  const [uploadedInSession, setUploadedInSession] = useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (uploadState !== 'uploading') {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (uploadState === 'uploading') return;

    const file = e.dataTransfer.files[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
    // Reset input so same file can be selected again
    e.target.value = '';
  };

  const handleFileSelect = async (file: File) => {
    // Client-side validation
    const validationError = validateFile(file);
    if (validationError) {
      setErrorMessage(validationError);
      setUploadState('error');
      return;
    }

    setCurrentFile(file);
    setUploadState('uploading');
    setErrorMessage(null);

    const tempId = crypto.randomUUID();

    try {
      const response = await apiClient.uploadDocument(confabId, file);
      const uploadedDoc = response.document;

      const uploadedFile: UploadedFile = {
        tempId,
        name: file.name,
        size: file.size,
        id: uploadedDoc?.id,
        status: uploadedDoc?.status === 'active' ? 'indexed' : 'failed',
      };

      setUploadedInSession((prev) => [...prev, uploadedFile]);
      setUploadState('success');

      // Auto-reset to ready after brief success feedback
      setTimeout(() => {
        setUploadState('ready');
        setCurrentFile(null);
      }, 2000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      setErrorMessage(message);
      setUploadState('error');
    }
  };

  const handleRetry = () => {
    if (currentFile) {
      handleFileSelect(currentFile);
    }
  };

  const handleSkipError = () => {
    setUploadState('ready');
    setCurrentFile(null);
    setErrorMessage(null);
  };

  const handleDeleteDocument = async (docId: number, tempId: string) => {
    try {
      await apiClient.deleteDocument(confabId, docId);
      setUploadedInSession((prev) => prev.filter((f) => f.tempId !== tempId));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Delete failed';
      setErrorMessage(message);
    }
  };

  const handleDone = () => {
    const successCount = uploadedInSession.filter((f) => f.status === 'indexed').length;
    onUploadComplete?.(successCount);
    onOpenChange(false);
    // Reset state for next open
    setUploadedInSession([]);
    setUploadState('ready');
    setCurrentFile(null);
    setErrorMessage(null);
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      // User is closing without clicking Done - still call onUploadComplete
      const successCount = uploadedInSession.filter((f) => f.status === 'indexed').length;
      if (successCount > 0) {
        onUploadComplete?.(successCount);
      }
      // Reset state
      setUploadedInSession([]);
      setUploadState('ready');
      setCurrentFile(null);
      setErrorMessage(null);
    }
    onOpenChange(newOpen);
  };

  const totalExisting = existingDocuments.length;
  const totalUploaded = uploadedInSession.filter((f) => f.status === 'indexed').length;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Upload Documents
            {totalExisting > 0 && (
              <span className="text-sm font-normal text-slate-500">
                ({totalExisting} already uploaded)
              </span>
            )}
          </DialogTitle>
          <DialogDescription>
            Add reference documents for your agent. Supported formats: PDF, TXT, MD
          </DialogDescription>
        </DialogHeader>

        {/* Dropzone */}
        <div
          className={cn(
            'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors',
            uploadState === 'uploading' && 'opacity-50 cursor-not-allowed',
            isDragging
              ? 'border-indigo-500 bg-indigo-50'
              : 'border-slate-300 hover:border-indigo-400 hover:bg-slate-50'
          )}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => uploadState !== 'uploading' && fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.md"
            className="hidden"
            onChange={handleFileInputChange}
          />

          {uploadState === 'ready' && (
            <>
              <Upload className="h-10 w-10 mx-auto mb-3 text-slate-400" />
              <p className="text-sm text-slate-600 mb-1">
                Drop a file here or click to browse
              </p>
              <p className="text-xs text-slate-400">
                PDF, TXT, or MD up to 10MB
              </p>
            </>
          )}

          {uploadState === 'uploading' && currentFile && (
            <>
              <Loader2 className="h-10 w-10 mx-auto mb-3 text-indigo-500 animate-spin" />
              <p className="text-sm text-slate-600 mb-1">
                Uploading {currentFile.name}...
              </p>
              <p className="text-xs text-slate-400">
                {formatFileSize(currentFile.size)}
              </p>
            </>
          )}

          {uploadState === 'success' && currentFile && (
            <>
              <Check className="h-10 w-10 mx-auto mb-3 text-green-500" />
              <p className="text-sm text-green-600 mb-1">
                {currentFile.name} uploaded!
              </p>
              <p className="text-xs text-slate-400">
                Drop another file or click Done
              </p>
            </>
          )}

          {uploadState === 'error' && (
            <>
              <AlertCircle className="h-10 w-10 mx-auto mb-3 text-red-500" />
              <p className="text-sm text-red-600 mb-2">
                {errorMessage || 'Upload failed'}
              </p>
              <div className="flex gap-2 justify-center">
                {currentFile && (
                  <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); handleRetry(); }}>
                    Try Again
                  </Button>
                )}
                <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); handleSkipError(); }}>
                  Skip
                </Button>
              </div>
            </>
          )}
        </div>

        {/* Session uploads list */}
        {uploadedInSession.length > 0 && (
          <div className="mt-4">
            <p className="text-sm font-medium text-slate-700 mb-2">
              Uploaded this session
            </p>
            <div className="space-y-2 max-h-32 overflow-y-auto">
              {uploadedInSession.map((file) => (
                <div
                  key={file.tempId}
                  className="flex items-center justify-between p-2 bg-slate-50 rounded-md"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="h-4 w-4 text-slate-400 flex-shrink-0" />
                    <span className="text-sm text-slate-700 truncate">
                      {file.name}
                    </span>
                    <span className="text-xs text-slate-400 flex-shrink-0">
                      {formatFileSize(file.size)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {file.status === 'indexed' && (
                      <Badge variant="secondary" className="bg-green-100 text-green-700">
                        Uploaded
                      </Badge>
                    )}
                    {file.status === 'failed' && (
                      <Badge variant="destructive">
                        Failed
                      </Badge>
                    )}
                    {file.id && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={() => handleDeleteDocument(file.id!, file.tempId)}
                      >
                        <Trash2 className="h-3 w-3 text-slate-400 hover:text-red-500" />
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <DialogFooter>
          <Button onClick={handleDone}>
            Done{totalUploaded > 0 && ` - ${totalUploaded} document${totalUploaded !== 1 ? 's' : ''} uploaded`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
