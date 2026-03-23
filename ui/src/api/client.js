const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
console.log('API Client: API_BASE_URL set to:', API_BASE_URL);

class ApiClient {
  constructor() {
    this.baseURL = API_BASE_URL;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    console.log('API Client: Request method called for:', url, 'with options:', options);

    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    // Add auth token if available
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    try {
      console.log('API Client: About to fetch:', url);
      const response = await fetch(url, config);
      console.log('API Client: Fetch response received:', response.status, response.statusText);

      if (!response.ok) {
        let errorData = {};
        try {
          errorData = await response.json();
        } catch (e) {
          // If body isn't JSON, fall back to text for debugging-friendly message.
          const text = await response.text();
          errorData = { message: text };
        }
        const errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}: ${response.statusText}`;
        throw new Error(errorMessage);
      }

      const data = await response.json();
      console.log('API Client: Request successful, returning data:', data);
      return data;
    } catch (error) {
      console.error('API Client: Request failed:', error);
      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        throw new Error(`Network error: Cannot connect to API at ${url}. Please check your connection and ensure the backend server is running at ${this.baseURL}.`);
      }
      throw error;
    }
  }

  // Auth endpoints
  async register(userData) {
    console.log('API Client: Register called with:', { ...userData, password: '***' });
    console.log('API Client: Making request to:', `${this.baseURL}/auth/register`);
    
    const response = await this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    });

    console.log('API Client: Register response received:', response);

    // Store token in localStorage
    if (response.access_token) {
      console.log('API Client: Storing access token in localStorage');
      localStorage.setItem('access_token', response.access_token);
    }

    return response;
  }

  async login(credentials) {
    const response = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
    
    // Store token in localStorage
    if (response.access_token) {
      localStorage.setItem('access_token', response.access_token);
    }
    
    return response;
  }

  async getCurrentUser() {
    return this.request('/auth/me');
  }

  async getUsers() {
    return this.request('/users');
  }

  getGitHubAuthUrl() {
    return `${this.baseURL}/auth/github/authorize`;
  }

  async connectGitHub(githubData) {
    return this.request('/auth/github/connect', {
      method: 'POST',
      body: JSON.stringify(githubData),
    });
  }

  async loginWithGitHub(githubData) {
    const response = await this.request('/auth/github/login', {
      method: 'POST',
      body: JSON.stringify(githubData),
    });

    if (response.access_token) {
      localStorage.setItem('access_token', response.access_token);
    }

    return response;
  }

  async getGitHubRepos() {
    return this.request('/auth/github/repos');
  }

  // Confab endpoints
  async createConfab(confabData) {
    return this.request('/confabs', {
      method: 'POST',
      body: JSON.stringify(confabData),
    });
  }

  async getConfabs() {
    return this.request('/confabs');
  }

  async getConfab(id) {
    return this.request(`/confabs/${id}`);
  }

  async updateConfab(id, confabData) {
    return this.request(`/confabs/${id}`, {
      method: 'PUT',
      body: JSON.stringify(confabData),
    });
  }

  async deleteConfab(id) {
    return this.request(`/confabs/${id}`, {
      method: 'DELETE',
    });
  }

  async testRepoInitialization() {
    return this.request('/confabs/test-repo', {
      method: 'POST',
    });
  }

  // Threads & messages (review chats) — tables: users, threads, messages
  async getThreads() {
    return this.request('/threads');
  }

  async createThread(threadName) {
    return this.request('/threads', {
      method: 'POST',
      body: JSON.stringify({ thread_name: threadName }),
    });
  }

  async getThread(threadId) {
    return this.request(`/threads/${threadId}`);
  }

  async getThreadMessages(threadId) {
    return this.request(`/threads/${threadId}/messages`);
  }

  async addMessage(threadId, content, role = 'user') {
    return this.request(`/threads/${threadId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content, role }),
    });
  }

  // === [CLAUDE: LLM API endpoints for dynamic chat responses] ===

  async chatWithLLM(threadId, message) {
    console.log('API Client: Chatting with LLM for thread:', threadId);
    return this.request(`/threads/${threadId}/chat`, {
      method: 'POST',
      body: JSON.stringify({ content: message, role: 'user' }),
    });
  }

  async llmHealthCheck() {
    try {
      return await this.request('/llm/health');
    } catch (error) {
      console.error('API Client: LLM health check failed:', error);
      return { status: 'unavailable', healthy: false };
    }
  }

  async llmGenerateResponse(prompt) {
    console.log('API Client: Generating LLM response');
    return this.request('/llm/generate', {
      method: 'POST',
      body: JSON.stringify({ prompt }),
    });
  }

  async llmListModels() {
    return this.request('/llm/models');
  }

  // === [CLAUDE: Thread mapping endpoints] ===
  
  async createThreadMapping(confabId, threadId) {
    return this.request('/thread-mappings', {
      method: 'POST',
      body: JSON.stringify({ confab_id: confabId, thread_id: threadId }),
    });
  }

  async getThreadMappings() {
    return this.request('/thread-mappings');
  }

  async getConfabThreads(confabId) {
    return this.request(`/confab/${confabId}/threads`);
  }

  // === [CLAUDE: LangGraph Agent endpoints] ===
  
  async chatWithLangGraphAgent(confabId, message) {
    console.log('API Client: Chatting with LangGraph agent for confab:', confabId);
    return this.request(`/agent/chat/${confabId}`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  }

  async getAgentStatus() {
    return this.request('/agent/status');
  }

  clearToken() {
    localStorage.removeItem('access_token');
  }

}

// Create a singleton instance
export const apiClient = new ApiClient();
