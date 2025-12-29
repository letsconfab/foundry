import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Header } from './components/Header';
import { HeroSection } from './components/HeroSection';
import { AgentChat } from './components/AgentChat';
import { AgentDashboard } from './components/AgentDashboard';
import { DeploymentPanel } from './components/DeploymentPanel';
import { MultiAgentBuilder } from './components/MultiAgentBuilder';
import { Login } from './components/Login';
import { Register } from './components/Register';
import { ConfabChat } from './components/ConfabChat';
import { ConfigureConfab } from './components/ConfigureConfab';
import { ConfigureConfabWithThreads } from './components/ConfigureConfabWithThreads';
import { GitHubCallback } from './components/GitHubCallback';
import { AuthProvider, useAuth } from './contexts/AuthContext';

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'login' | 'register' | 'confab-chat' | 'configure';

function AppContent() {
  const { isLoggedIn, isLoading, user } = useAuth();
  const [currentView, setCurrentView] = useState<View>('home');
  const [selectedConfabName, setSelectedConfabName] = useState('');
  const [selectedConfabVersion, setSelectedConfabVersion] = useState('1.0.0');

  const handleNavigate = (view: View, confabName?: string, version?: string) => {
    setCurrentView(view);
    if (confabName) {
      setSelectedConfabName(confabName);
    }
    if (version) {
      setSelectedConfabVersion(version);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-slate-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <Router>
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
        <Routes>
          <Route path="/auth/github/callback" element={<GitHubCallback />} />
          <Route path="/*" element={
            <>
              <Header 
                currentView={currentView} 
                onNavigate={handleNavigate} 
                isLoggedIn={isLoggedIn}
                user={user}
              />
              
              <main>
                {currentView === 'home' && <HeroSection onNavigate={handleNavigate} />}
                {currentView === 'login' && <Login onNavigate={handleNavigate} />}
                {currentView === 'register' && <Register onNavigate={handleNavigate} />}
                {currentView === 'create' && <AgentChat onNavigate={handleNavigate} />}
                {currentView === 'dashboard' && <AgentDashboard onNavigate={handleNavigate} />}
                {currentView === 'deploy' && <DeploymentPanel onNavigate={handleNavigate} />}
                {currentView === 'multi-agent' && <MultiAgentBuilder onNavigate={handleNavigate} />}
                {currentView === 'confab-chat' && <ConfabChat onNavigate={handleNavigate} confabName={selectedConfabName} version={selectedConfabVersion} />}
                {currentView === 'configure' && <ConfigureConfabWithThreads onNavigate={handleNavigate} confabName={selectedConfabName} version={selectedConfabVersion} />}
              </main>
            </>
          } />
        </Routes>
      </div>
    </Router>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}