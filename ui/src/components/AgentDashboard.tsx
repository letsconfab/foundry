import React from 'react';
import { useState, useEffect } from 'react';
import { Plus, Bot, MoreVertical, Share2, StopCircle, Trash2, Cloud, MessageSquare, Settings, Wrench, Github } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from './ui/dialog';
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
  
  // GitHub repository states
  const [showRepoModal, setShowRepoModal] = useState(false);
  const [repoName, setRepoName] = useState('confabs');
  const [isCheckingRepo, setIsCheckingRepo] = useState(false);
  const [isCreatingRepo, setIsCreatingRepo] = useState(false);
  const [githubRepo, setGithubRepo] = useState<any>(null);
  const [githubError, setGithubError] = useState<string | null>(null);

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

  const handleCreateNewConfab = async () => {
    setIsCheckingRepo(true);
    setGithubError(null);
    
    try {
      // Check if user is logged in with GitHub
      const currentUser = await apiClient.getCurrentUser();
      
      if (!currentUser.github_connected) {
        setShowRepoModal(true);
        return;
      }

      // Check if 'confabs' repository exists
      const repoCheck = await apiClient.checkGitHubRepoExists('confabs');
      
      if (repoCheck.exists) {
        console.log('GitHub repository found:', repoCheck.repo);
        console.log('GitHub URL:', repoCheck.repo.html_url);
        console.log('Repository name:', repoCheck.repo.name);
        
        // Repository exists, continue to confab creation
        onNavigate('create');
      } else {
        // Repository doesn't exist, show modal to create it
        setShowRepoModal(true);
      }
    } catch (error: any) {
      console.error('Error checking GitHub repository:', error);
      setGithubError(error.message || 'Failed to check GitHub repository');
      setShowRepoModal(true);
    } finally {
      setIsCheckingRepo(false);
    }
  };

  const handleCreateRepo = async () => {
    if (!repoName.trim()) {
      setGithubError('Repository name is required');
      return;
    }

    setIsCreatingRepo(true);
    setGithubError(null);

    try {
      const result = await apiClient.createGitHubRepo(repoName);
      
      // Backend returns { message: "...", repository: {...} } not { success: true, repo: {...} }
      if (result.repository) {
        console.log('GitHub repository created:', result.repository);
        console.log('GitHub URL:', result.repository.html_url);
        console.log('Repository name:', result.repository.name);
        
        setGithubRepo(result.repository);
        setShowRepoModal(false);
        onNavigate('create');
      }
    } catch (error: any) {
      console.error('Error creating GitHub repository:', error);
      setGithubError(error.message || 'Failed to create GitHub repository');
    } finally {
      setIsCreatingRepo(false);
    }
  };

  const handleLoginWithGitHub = () => {
    window.location.href = apiClient.getGitHubAuthUrl();
  };

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
        <Button onClick={handleCreateNewConfab} disabled={isCheckingRepo} className="gap-2">
          <Plus className="w-4 h-4" />
          {isCheckingRepo ? 'Checking GitHub...' : 'Create New Confab'}
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
          <Button onClick={handleCreateNewConfab} disabled={isCheckingRepo} className="gap-2">
            <Plus className="w-4 h-4" />
            {isCheckingRepo ? 'Checking GitHub...' : 'Create Confab'}
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

      {/* GitHub Repository Modal */}
      <Dialog open={showRepoModal} onOpenChange={setShowRepoModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Github className="w-5 h-5" />
              GitHub Repository Setup
            </DialogTitle>
            <DialogDescription>
              {githubError ? (
                <span className="text-red-600">Error: {githubError}</span>
              ) : (
                "Set up your GitHub repository to store Confab files"
              )}
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            {/* Check if user is logged in with GitHub */}
            {!githubError && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <label htmlFor="repo-name" className="text-sm font-medium">
                    Repository Name
                  </label>
                  <Input
                    id="repo-name"
                    value={repoName}
                    onChange={(e) => setRepoName(e.target.value)}
                    placeholder="confabs"
                    disabled={isCreatingRepo}
                  />
                </div>
                
                <div className="text-sm text-slate-600">
                  <p>All Confab data will be stored in this repository.</p>
                  <p>The repository will be created as public.</p>
                </div>
              </div>
            )}
            
            {/* Show login prompt if GitHub not connected */}
            {githubError && githubError.includes('GitHub not connected') && (
              <div className="space-y-4">
                <p className="text-sm text-slate-600">
                  Please create or login with GitHub account first
                </p>
                <Button 
                  onClick={handleLoginWithGitHub}
                  className="w-full gap-2"
                  variant="outline"
                >
                  <Github className="w-4 h-4" />
                  Login with GitHub
                </Button>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowRepoModal(false)}
              disabled={isCreatingRepo}
            >
              Cancel
            </Button>
            
            {!githubError || !githubError.includes('GitHub not connected') ? (
              <Button
                onClick={handleCreateRepo}
                disabled={isCreatingRepo || !repoName.trim()}
                className="gap-2"
              >
                {isCreatingRepo ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    Creating Repository...
                  </>
                ) : (
                  <>
                    <Github className="w-4 h-4" />
                    Create Repository
                  </>
                )}
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}