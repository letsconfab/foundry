import { useState } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { MessageSquare, Mail, Lock, Github, AlertCircle } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'login' | 'register' | 'confab-chat';

interface LoginProps {
  onNavigate: (view: View, confabName?: string) => void;
}

export function Login({ onNavigate }: LoginProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const { login, githubLogin } = useAuth();
  const hasStartedTyping = email.length > 0 || password.length > 0;
  const isMissingCredentials = hasStartedTyping && (!email.trim() || !password.trim());

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    if (!email || !password) {
      setError('Please fill in all fields');
      return;
    }

    setIsLoading(true);
    
    try {
      await login(email, password);
      // Navigation will be handled by AuthContext/App
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGitHubLogin = () => {
    githubLogin();
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 sm:px-6 lg:px-8 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <MessageSquare className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-slate-900 dark:text-white mb-2">Welcome back</h2>
          <p className="text-slate-600 dark:text-slate-400">Sign in to your Let's Confab account</p>
        </div>

        <Card className="p-6 sm:p-8">
          <div className="mb-6 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-300">
            Use your email and password if you created an account directly. If you joined with GitHub, use the GitHub button below.
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-md flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-500" />
              <span className="text-sm text-red-700 dark:text-red-400">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="email">Email address</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-10"
                  aria-invalid={isMissingCredentials && !email.trim()}
                  required
                  disabled={isLoading}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                <Input
                  id="password"
                  type="password"
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-10"
                  aria-invalid={isMissingCredentials && !password.trim()}
                  required
                  disabled={isLoading}
                />
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Password reset is not available in-product yet. If you normally sign in with GitHub, use that option instead.
              </p>
            </div>

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? 'Signing in...' : 'Sign in'}
            </Button>
            {isMissingCredentials && (
              <p className="text-xs text-amber-600 dark:text-amber-400">
                Enter both your email and password before signing in.
              </p>
            )}
          </form>

          <div className="mt-6">
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-slate-200 dark:border-slate-700" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white dark:bg-slate-800 text-slate-500 dark:text-slate-400">Or continue with</span>
              </div>
            </div>

            <div className="mt-6">
              <Button
                type="button"
                variant="outline"
                className="w-full gap-2"
                onClick={handleGitHubLogin}
                disabled={isLoading}
              >
                <Github className="w-5 h-5" />
                Sign in with GitHub
              </Button>
            </div>
          </div>

          <div className="mt-6 text-center">
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Don't have an account?{' '}
              <button
                onClick={() => onNavigate('register')}
                className="text-indigo-600 hover:text-indigo-500"
                disabled={isLoading}
              >
                Sign up
              </button>
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}
