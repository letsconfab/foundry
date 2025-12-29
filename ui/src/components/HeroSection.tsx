import { MessageSquare, Cloud, Zap, Network, ArrowRight, Bot, Users, Rocket } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';

type View = 'home' | 'create' | 'dashboard' | 'deploy' | 'multi-agent' | 'login' | 'register' | 'confab-chat';

interface HeroSectionProps {
  onNavigate: (view: View, confabName?: string) => void;
}

export function HeroSection({ onNavigate }: HeroSectionProps) {
  const features = [
    {
      icon: MessageSquare,
      title: 'Confab-Powered Creation',
      description: 'Your personal Confab guides you through building agents with natural conversations.',
    },
    {
      icon: Cloud,
      title: 'Multi-Cloud Deployment',
      description: 'Deploy your Confabs to AWS, Azure, GCP, or your preferred cloud provider.',
    },
    {
      icon: Zap,
      title: 'Multiple LLM Providers',
      description: 'Each Confab can use OpenAI, Anthropic, Google, and more.',
    },
    {
      icon: Network,
      title: 'Multi-Confab Systems',
      description: 'Build complex systems by connecting multiple Confabs together.',
    },
  ];

  return (
    <div className="relative overflow-hidden">
      {/* Hero Section */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
        <div className="text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-100 text-indigo-700 rounded-full mb-8">
            <Zap className="w-4 h-4" />
            <span className="text-sm">Transform Your Knowledge into Collaborative AI Agents</span>
          </div>
          
          <h1 className="text-slate-900 mb-6 max-w-4xl mx-auto">
            Your Confab Helps You Build Powerful Agents
          </h1>
          
          <p className="text-slate-600 mb-8 max-w-2xl mx-auto text-lg">
            A <strong>Confab</strong> is your intelligent agent builder. Chat with your Confab to define, configure, and deploy custom agents. 
            Each Confab you create becomes a reusable agent that can help others build even more agents—creating an ecosystem of collaborative AI.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Button
              size="lg"
              onClick={() => onNavigate('create')}
              className="gap-2 group"
            >
              Create Your First Confab
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Button>
            <Button
              size="lg"
              variant="outline"
              onClick={() => onNavigate('dashboard')}
            >
              View Dashboard
            </Button>
          </div>
        </div>

        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mt-20">
          {features.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <Card key={index} className="p-6 hover:shadow-lg transition-shadow">
                <div className="w-12 h-12 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-lg flex items-center justify-center mb-4">
                  <Icon className="w-6 h-6 text-white" />
                </div>
                <h3 className="text-slate-900 mb-2">{feature.title}</h3>
                <p className="text-slate-600 text-sm">{feature.description}</p>
              </Card>
            );
          })}
        </div>

        {/* How It Works Section */}
        <div className="mt-32">
          <div className="text-center mb-12">
            <h2 className="text-slate-900 mb-4">How Confabs Work</h2>
            <p className="text-slate-600 max-w-2xl mx-auto">
              Think of a Confab as an AI agent that specializes in building other AI agents. 
              Each one you create can be shared and reused to build more.
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-indigo-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Bot className="w-8 h-8 text-indigo-600" />
              </div>
              <h3 className="text-slate-900 mb-2">1. Chat with Your Confab</h3>
              <p className="text-slate-600 text-sm">
                Describe what you want your agent to do. Your Confab guides you through 8 simple steps to define purpose, tools, guardrails, and more.
              </p>
            </div>
            
            <div className="text-center">
              <div className="w-16 h-16 bg-purple-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Users className="w-8 h-8 text-purple-600" />
              </div>
              <h3 className="text-slate-900 mb-2">2. Collaborate & Configure</h3>
              <p className="text-slate-600 text-sm">
                Invite team members and even other Confabs to participate. Configure memory, LLM providers, APIs, and deployment settings together.
              </p>
            </div>
            
            <div className="text-center">
              <div className="w-16 h-16 bg-green-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Rocket className="w-8 h-8 text-green-600" />
              </div>
              <h3 className="text-slate-900 mb-2">3. Deploy & Reuse</h3>
              <p className="text-slate-600 text-sm">
                Deploy your new Confab to any cloud. It becomes a reusable agent that you—and others—can use to build even more specialized agents.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Background Decoration */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full max-w-7xl -z-10 opacity-30">
        <div className="absolute top-20 left-10 w-72 h-72 bg-indigo-400 rounded-full blur-3xl" />
        <div className="absolute bottom-20 right-10 w-96 h-96 bg-purple-400 rounded-full blur-3xl" />
      </div>
    </div>
  );
}