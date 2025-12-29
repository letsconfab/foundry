import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { MessageSquare, Github, AlertCircle, CheckCircle } from 'lucide-react';
import { apiClient } from '../api/client.js';
import { useAuth } from '../contexts/AuthContext';

export function GitHubCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { refreshUser } = useAuth();
  const [status, setStatus] = useState('loading');
  const [message, setMessage] = useState('Connecting to GitHub...');

  useEffect(() => {
    const handleGitHubCallback = async () => {
      const accessToken = searchParams.get('access_token');
      const githubId = searchParams.get('github_id');
      const githubUsername = searchParams.get('github_username');

      if (!accessToken || !githubId || !githubUsername) {
        setStatus('error');
        setMessage('Missing required GitHub information');
        return;
      }

      try {
        // Check if user is already logged in
        const token = localStorage.getItem('access_token');
        if (token) {
          // User is logged in, connect GitHub account
          await apiClient.connectGitHub({
            github_id: parseInt(githubId),
            github_username: githubUsername,
            access_token: accessToken,
            selected_repo: 'confabs', // Default repo
            selected_org: undefined
          });
          setStatus('success');
          setMessage('GitHub account connected successfully!');
        } else {
          // User is not logged in: perform app login via backend exchange
          await apiClient.loginWithGitHub({
            github_id: parseInt(githubId),
            github_username: githubUsername,
            access_token: accessToken,
            selected_repo: 'confabs',
            selected_org: undefined,
          });

          await refreshUser();
          setStatus('success');
          setMessage('GitHub login successful! Redirecting to dashboard...');
          setTimeout(() => {
            navigate('/');
          }, 800);
        }
      } catch (error) {
        setStatus('error');
        setMessage(error.message || 'Failed to connect GitHub account');
      }
    };

    handleGitHubCallback();
  }, [searchParams, navigate, refreshUser]);

  const handleContinue = () => {
    navigate('/dashboard');
  };

  const handleRetry = () => {
    navigate('/login');
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 sm:px-6 lg:px-8 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <MessageSquare className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-slate-900 mb-2">GitHub Connection</h2>
        </div>

        <Card className="p-6 sm:p-8">
          <div className="text-center">
            <div className="mb-4">
              {status === 'loading' && (
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
              )}
              {status === 'success' && (
                <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-4" />
              )}
              {status === 'error' && (
                <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
              )}
            </div>

            <div className="mb-6">
              <Github className="w-8 h-8 text-slate-600 mx-auto mb-2" />
              <p className="text-slate-600">{message}</p>
            </div>

            {status === 'success' && (
              <Button onClick={handleContinue} className="w-full">
                Continue to Dashboard
              </Button>
            )}

            {status === 'error' && (
              <div className="space-y-3">
                <Button onClick={handleRetry} variant="outline" className="w-full">
                  Try Again
                </Button>
                <Button onClick={() => navigate('/')} variant="ghost" className="w-full">
                  Go Home
                </Button>
              </div>
            )}

            {status === 'loading' && (
              <p className="text-sm text-slate-500">Please wait while we connect your account...</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
