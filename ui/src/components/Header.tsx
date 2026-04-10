import { MessageSquare, LayoutDashboard, Cloud, Network, Menu, X, Github, LogOut } from 'lucide-react';
import { Button } from './ui/button';
import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { ThemeToggle } from './ThemeToggle';

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'login' | 'register' | 'confab-chat';

interface HeaderProps {
  currentView: View;
  onNavigate: (view: View, confabName?: string) => void;
  user?: {
    id: number;
    name: string;
    email: string;
    country: string;
    timezone: string;
    github_connected: boolean;
    created_at: string;
  } | null;
}

export function Header({ currentView, onNavigate, user }: HeaderProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { logout } = useAuth();
  const isLoggedIn = !!user;

  const navItems = isLoggedIn
    ? [
        { id: 'dashboard' as View, label: 'Dashboard', icon: LayoutDashboard },
      ]
    : [];

  const handleLogout = () => {
    logout();
    setMobileMenuOpen(false);
  };

  return (
    <header className="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-700 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <button
            onClick={() => onNavigate('home')}
            className="flex items-center gap-2 hover:opacity-80 transition-opacity"
          >
            <div className="w-8 h-8 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-lg flex items-center justify-center">
              <MessageSquare className="w-5 h-5 text-white" />
            </div>
            <span className="text-slate-900 dark:text-white">Let's Confab</span>
          </button>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-2">
            {isLoggedIn ? (
              <>
                {navItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <Button
                      key={item.id}
                      variant={currentView === item.id ? 'default' : 'ghost'}
                      onClick={() => onNavigate(item.id)}
                      className="gap-2"
                    >
                      <Icon className="w-4 h-4" />
                      {item.label}
                    </Button>
                  );
                })}
                {user?.github_connected && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => window.open('https://github.com', '_blank')}
                    title="GitHub Connected"
                    className="text-green-600"
                  >
                    <Github className="w-5 h-5" />
                  </Button>
                )}
                <ThemeToggle />
                <div className="text-sm text-slate-600 dark:text-slate-300 mr-2">
                  {user?.name}
                </div>
                <Button
                  variant="ghost"
                  onClick={handleLogout}
                  className="gap-2"
                >
                  <LogOut className="w-4 h-4" />
                  Logout
                </Button>
              </>
            ) : (
              <>
                <ThemeToggle />
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => window.open('https://github.com', '_blank')}
                  title="GitHub"
                  className="text-slate-600 dark:text-slate-300"
                >
                  <Github className="w-5 h-5" />
                </Button>
                <Button
                  variant={currentView === 'login' ? 'default' : 'ghost'}
                  onClick={() => onNavigate('login')}
                  className={currentView === 'login' ? '' : 'text-slate-700 dark:text-slate-200'}
                >
                  Login
                </Button>
              </>
            )}
          </nav>

          {/* Mobile Menu Button */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </Button>
        </div>

        {/* Mobile Navigation */}
        {mobileMenuOpen && (
          <nav className="md:hidden py-4 border-t border-slate-200 dark:border-slate-700">
            <div className="flex flex-col gap-2">
              {isLoggedIn ? (
                <>
                  {user && (
                    <div className="px-3 py-2 text-sm text-slate-600 dark:text-slate-300">
                      Signed in as {user.name}
                    </div>
                  )}
                  {navItems.map((item) => {
                    const Icon = item.icon;
                    return (
                      <Button
                        key={item.id}
                        variant={currentView === item.id ? 'default' : 'ghost'}
                        onClick={() => {
                          onNavigate(item.id);
                          setMobileMenuOpen(false);
                        }}
                        className="gap-2 justify-start"
                      >
                        <Icon className="w-4 h-4" />
                        {item.label}
                      </Button>
                    );
                  })}
                  <Button
                    variant="ghost"
                    onClick={handleLogout}
                    className="gap-2 justify-start"
                  >
                    <LogOut className="w-4 h-4" />
                    Logout
                  </Button>
                </>
              ) : (
                <Button
                  variant={currentView === 'login' ? 'default' : 'ghost'}
                  onClick={() => {
                    onNavigate('login');
                    setMobileMenuOpen(false);
                  }}
                  className="justify-start"
                >
                  Login
                </Button>
              )}
            </div>
          </nav>
        )}
      </div>
    </header>
  );
}
