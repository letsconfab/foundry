import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiClient } from '../api/client.js';

interface User {
  id: number;
  name: string;
  email: string;
  country: string;
  timezone: string;
  github_connected: boolean;
  created_at: string;
  updated_at?: string;
}

interface UserCreateData {
  name: string;
  email: string;
  password: string;
  country: string;
  timezone: string;
}

interface AuthContextType {
  user: User | null;
  isLoggedIn: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (userData: UserCreateData) => Promise<void>;
  logout: () => void;
  githubLogin: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (token) {
        const userData = await apiClient.getCurrentUser();
        setUser(userData);
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      apiClient.clearToken();
    } finally {
      setIsLoading(false);
    }
  };

  const refreshUser = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      setUser(null);
      return;
    }
    const userData = await apiClient.getCurrentUser();
    setUser(userData);
  };

  const login = async (email: string, password: string) => {
    try {
      const userData = await apiClient.login({ email, password });
      setUser(userData);
    } catch (error) {
      throw error;
    }
  };

  const register = async (userData: UserCreateData) => {
    try {
      const response = await apiClient.register(userData);
      setUser(response);
    } catch (error) {
      throw error;
    }
  };

  const logout = () => {
    apiClient.clearToken();
    setUser(null);
  };

  const githubLogin = () => {
    // Redirect to GitHub OAuth
    window.location.href = apiClient.getGitHubAuthUrl();
  };

  const value = {
    user,
    isLoggedIn: !!user,
    isLoading,
    login,
    register,
    logout,
    githubLogin,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
