import React from 'react';
import { useState, useEffect } from 'react';
import { Plus, Bot, MoreVertical, Share2, StopCircle, Trash2, Cloud, MessageSquare, Settings, Wrench } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './ui/alert-dialog';
import { apiClient } from '../api/client.js';

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'confab-chat' | 'configure';

interface AgentDashboardProps {
  onNavigate: (view: View, confabName?: string, version?: string, confabId?: number) => void;
}

interface Confab {
  id: number;
  name: string;
  description: string | null;
  status: string;  // Can be 'building', 'draft', 'published', 'archived'
  version: string;
  created_at: string;
  updated_at: string | null;
  // OASF fields (from new API)
  purpose?: string | null;
  guardrails?: Array<{ id: string; rule: string; severity: string; enabled: boolean }> | null;
  tests?: Array<{ id: string; name: string; input: string; expected_behavior: string }> | null;
  skills?: number[] | null;
  domains?: string[] | null;
  model_provider?: string | null;
  model_name?: string | null;
  temperature?: number;
  github_path?: string | null;  // was github_url
  github_synced_at?: string | null;
}

export function AgentDashboard({ onNavigate }: AgentDashboardProps) {
  const [confabs, setConfabs] = useState<Confab[]>([]);
  const [loading, setLoading] = useState(true);
  const [confabToDelete, setConfabToDelete] = useState<Confab | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const fetchConfabs = async () => {
      try {
        const data = await apiClient.getConfabs();
        setConfabs(data);
      } catch (error) {
        console.error('Failed to fetch confabs:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchConfabs();
  }, []);

  const handleDeleteConfab = async () => {
    if (!confabToDelete) return;
    setIsDeleting(true);
    try {
      await apiClient.deleteConfab(confabToDelete.id);
      setConfabs(prev => prev.filter(c => c.id !== confabToDelete.id));
      setConfabToDelete(null);
    } catch (error) {
      console.error('Failed to delete confab:', error);
    } finally {
      setIsDeleting(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'published':
        return 'bg-green-100 text-green-700';
      case 'building':
        return 'bg-amber-100 text-amber-700';
      case 'draft':
        return 'bg-blue-100 text-blue-700';
      case 'archived':
        return 'bg-slate-100 text-slate-700';
      default:
        return 'bg-slate-100 text-slate-700';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'building':
        return 'Building...';
      case 'published':
        return 'Published';
      default:
        return status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Unknown';
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
        <div>
          <h2 className="text-slate-900 mb-1">Confab Dashboard</h2>
          <p className="text-slate-600">Manage and monitor your AI confabs</p>
        </div>
        <Button onClick={() => onNavigate('create')} className="gap-2">
          <Plus className="w-4 h-4" />
          Create New Confab
        </Button>
      </div>

      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-slate-600">Loading confabs...</p>
        </div>
      ) : confabs.length === 0 ? (
        <div className="text-center py-12">
          <Bot className="w-12 h-12 text-slate-400 mx-auto mb-4" />
          <h3 className="text-slate-900 mb-2">No confabs yet</h3>
          <p className="text-slate-600 mb-4">Create your first confab to get started</p>
          <Button onClick={() => onNavigate('create')} className="gap-2">
            <Plus className="w-4 h-4" />
            Create Confab
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {confabs.map((confab) => (
            <Card key={confab.id} className="p-6 hover:shadow-lg transition-shadow">
              <div className="flex items-start justify-between mb-4">
                <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                  confab.status === 'building'
                    ? 'bg-gradient-to-br from-amber-500 to-orange-500'
                    : 'bg-gradient-to-br from-indigo-600 to-purple-600'
                }`}>
                  {confab.status === 'building' ? (
                    <Wrench className="w-6 h-6 text-white" />
                  ) : (
                    <Bot className="w-6 h-6 text-white" />
                  )}
                </div>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon">
                      <MoreVertical className="w-4 h-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem className="gap-2">
                      <Share2 className="w-4 h-4" />
                      Publish
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className="gap-2 text-red-600"
                      onClick={() => setConfabToDelete(confab)}
                    >
                      <Trash2 className="w-4 h-4" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              <h3 className="text-slate-900 mb-2">{confab.name}</h3>
              <Badge className={`${getStatusColor(confab.status)} mb-2`}>
                {getStatusLabel(confab.status)}
              </Badge>
              <p className="text-slate-600 text-sm mb-4">{confab.description || 'No description'}</p>

              <div className="space-y-2 mb-4">
                <div className="flex items-center justify-between text-sm pt-2 border-t border-slate-200">
                  <span className="text-xs text-slate-500">
                    {confab.updated_at ? new Date(confab.updated_at).toLocaleDateString() : 'Just now'}
                  </span>
                  <span className="text-xs text-slate-500">v{confab.version}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="mt-4 flex flex-col gap-2">
                {confab.status === 'building' ? (
                  <Button
                    variant="default"
                    size="sm"
                    className="gap-2"
                    style={{ backgroundColor: '#d97706' }}
                    onClick={() => onNavigate('create', confab.name, confab.version, confab.id)}
                  >
                    <Wrench className="w-3 h-3" />
                    Continue Building
                  </Button>
                ) : null}
                {confab.status === 'published' && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 gap-2"
                    onClick={() => onNavigate('confab-chat', confab.name, confab.version)}
                  >
                    <MessageSquare className="w-3 h-3" />
                    Chat
                  </Button>
                )}
                {confab.status === 'draft' && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 gap-2"
                    onClick={() => onNavigate('deploy')}
                  >
                    <Cloud className="w-3 h-3" />
                    Deploy
                  </Button>
                )}
                {/* Fallback for any status */}
                {!['building', 'published', 'draft'].includes(confab.status) && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 gap-2"
                    onClick={() => onNavigate('create', confab.name, confab.version, confab.id)}
                  >
                    <Settings className="w-3 h-3" />
                    Configure
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      <AlertDialog open={!!confabToDelete} onOpenChange={(open) => !open && setConfabToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Confab</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{confabToDelete?.name}"? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfab}
              disabled={isDeleting}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {isDeleting ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}