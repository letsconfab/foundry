import React from 'react';
import { Moon, Sun, Monitor } from 'lucide-react';
import { Button } from './ui/button';
import { useTheme } from '../contexts/ThemeContext';

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  const cycleTheme = () => {
    const order: Array<'light' | 'dark' | 'system'> = ['light', 'dark', 'system'];
    const current = order.indexOf(theme);
    const next = order[(current + 1) % order.length];
    setTheme(next);
  };

  const icon = theme === 'dark' ? (
    <Moon className="w-4 h-4" />
  ) : theme === 'system' ? (
    <Monitor className="w-4 h-4" />
  ) : (
    <Sun className="w-4 h-4" />
  );

  const label = theme === 'dark' ? 'Dark' : theme === 'system' ? 'System' : 'Light';

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={cycleTheme}
      className="gap-1.5 text-slate-600 dark:text-slate-300"
      title={`Theme: ${label}`}
    >
      {icon}
      <span className="hidden sm:inline text-xs">{label}</span>
    </Button>
  );
}
