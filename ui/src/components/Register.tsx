import { useState } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { MessageSquare, Mail, Lock, User, Github, Globe, Clock, AlertCircle } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'login' | 'register' | 'confab-chat';

interface RegisterProps {
  onNavigate: (view: View, confabName?: string) => void;
}

export function Register({ onNavigate }: RegisterProps) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [country, setCountry] = useState('');
  const [timezone, setTimezone] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const { register, githubLogin } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    // Validation
    if (!name || !email || !password || !country || !timezone) {
      setError('Please fill in all fields');
      return;
    }
    
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    
    if (password.length < 6) {
      setError('Password must be at least 6 characters long');
      return;
    }

    setIsLoading(true);
    
    try {
      await register({
        name,
        email,
        password,
        country,
        timezone
      });
      // Navigation will be handled by AuthContext/App
    } catch (err: any) {
      setError(err.message || 'Registration failed. Please try again.');
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
          <h2 className="text-slate-900 mb-2">Create your account</h2>
          <p className="text-slate-600">Start building AI agents with Let's Confab</p>
        </div>

        <Card className="p-6 sm:p-8">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-500" />
              <span className="text-sm text-red-700">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="name">Full name</Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                <Input
                  id="name"
                  type="text"
                  placeholder="John Smith"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="pl-10"
                  required
                  disabled={isLoading}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email address</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-10"
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
                  placeholder="Create a password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-10"
                  required
                  disabled={isLoading}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                <Input
                  id="confirmPassword"
                  type="password"
                  placeholder="Confirm your password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="pl-10"
                  required
                  disabled={isLoading}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="country">Country</Label>
              <Select value={country} onValueChange={setCountry} required disabled={isLoading}>
                <SelectTrigger className="w-full">
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-slate-400" />
                    <SelectValue placeholder="Select your country" />
                  </div>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="us">United States</SelectItem>
                  <SelectItem value="ca">Canada</SelectItem>
                  <SelectItem value="uk">United Kingdom</SelectItem>
                  <SelectItem value="au">Australia</SelectItem>
                  <SelectItem value="de">Germany</SelectItem>
                  <SelectItem value="fr">France</SelectItem>
                  <SelectItem value="jp">Japan</SelectItem>
                  <SelectItem value="in">India</SelectItem>
                  <SelectItem value="br">Brazil</SelectItem>
                  <SelectItem value="sg">Singapore</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="timezone">Timezone</Label>
              <Select value={timezone} onValueChange={setTimezone} required disabled={isLoading}>
                <SelectTrigger className="w-full">
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-slate-400" />
                    <SelectValue placeholder="Select your timezone" />
                  </div>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="utc-12">UTC-12:00 (Baker Island)</SelectItem>
                  <SelectItem value="utc-11">UTC-11:00 (American Samoa)</SelectItem>
                  <SelectItem value="utc-10">UTC-10:00 (Hawaii)</SelectItem>
                  <SelectItem value="utc-9">UTC-09:00 (Alaska)</SelectItem>
                  <SelectItem value="utc-8">UTC-08:00 (Pacific Time)</SelectItem>
                  <SelectItem value="utc-7">UTC-07:00 (Mountain Time)</SelectItem>
                  <SelectItem value="utc-6">UTC-06:00 (Central Time)</SelectItem>
                  <SelectItem value="utc-5">UTC-05:00 (Eastern Time)</SelectItem>
                  <SelectItem value="utc-4">UTC-04:00 (Atlantic Time)</SelectItem>
                  <SelectItem value="utc-3">UTC-03:00 (Buenos Aires)</SelectItem>
                  <SelectItem value="utc-2">UTC-02:00 (Mid-Atlantic)</SelectItem>
                  <SelectItem value="utc-1">UTC-01:00 (Azores)</SelectItem>
                  <SelectItem value="utc">UTC±00:00 (London, Lisbon)</SelectItem>
                  <SelectItem value="utc+1">UTC+01:00 (Paris, Berlin)</SelectItem>
                  <SelectItem value="utc+2">UTC+02:00 (Cairo, Athens)</SelectItem>
                  <SelectItem value="utc+3">UTC+03:00 (Moscow, Istanbul)</SelectItem>
                  <SelectItem value="utc+4">UTC+04:00 (Dubai)</SelectItem>
                  <SelectItem value="utc+5">UTC+05:00 (Pakistan)</SelectItem>
                  <SelectItem value="utc+5:30">UTC+05:30 (India)</SelectItem>
                  <SelectItem value="utc+6">UTC+06:00 (Bangladesh)</SelectItem>
                  <SelectItem value="utc+7">UTC+07:00 (Bangkok, Jakarta)</SelectItem>
                  <SelectItem value="utc+8">UTC+08:00 (Singapore, Beijing)</SelectItem>
                  <SelectItem value="utc+9">UTC+09:00 (Tokyo, Seoul)</SelectItem>
                  <SelectItem value="utc+10">UTC+10:00 (Sydney)</SelectItem>
                  <SelectItem value="utc+11">UTC+11:00 (Solomon Islands)</SelectItem>
                  <SelectItem value="utc+12">UTC+12:00 (Auckland)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? 'Creating account...' : 'Create account'}
            </Button>
          </form>

          <div className="mt-6">
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-slate-200" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-slate-500">Or continue with</span>
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
                Sign up with GitHub
              </Button>
            </div>
          </div>

          <div className="mt-6 text-center">
            <p className="text-sm text-slate-600">
              Already have an account?{' '}
              <button
                onClick={() => onNavigate('login')}
                className="text-indigo-600 hover:text-indigo-500"
                disabled={isLoading}
              >
                Sign in
              </button>
            </p>
          </div>
        </Card>

        <p className="mt-6 text-center text-xs text-slate-500">
          By creating an account, you agree to our{' '}
          <a href="#" className="text-indigo-600 hover:text-indigo-500">
            Terms of Service
          </a>{' '}
          and{' '}
          <a href="#" className="text-indigo-600 hover:text-indigo-500">
            Privacy Policy
          </a>
        </p>
      </div>
    </div>
  );
}