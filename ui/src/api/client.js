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
  async createConfab(options = {}) {
    console.log('API Client: Creating confab with options:', options);
    return this.request('/confabs', {
      method: 'POST',
      body: JSON.stringify({
        name: options.name || 'New Confab',
        description: options.description || '',
        generate_placeholder: options.generate_placeholder || false,
        status: options.status || 'building',
      }),
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

  async refreshDefinitionFiles(confabId) {
    return this.request(`/confabs/${confabId}/definition-files/refresh`, {
      method: 'POST',
    });
  }

  async acceptAndCommitDefinitionFiles(confabId, payload = {}) {
    return this.request(`/confabs/${confabId}/definition-files/accept-and-commit`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // REMOVED: testRepoInitialization - endpoint no longer exists

  // Threads & messages (review chats) — tables: users, threads, messages
  async getThreads() {
    return this.request('/threads');
  }

  async createThread(threadName) {
    return this.request('/threads', {
      method: 'POST',
      body: JSON.stringify({ name: threadName }),
    });
  }

  async getThread(threadId) {
    return this.request(`/threads/${threadId}`);
  }

  async getThreadMessages(threadId) {
    return this.request(`/threads/${threadId}/messages`);
  }

  async addMessage(threadId, content, role = 'user', senderType = 'user', senderName = null) {
    const body = { content, role, sender_type: senderType };
    if (senderName) {
      body.sender_name = senderName;
    }
    return this.request(`/threads/${threadId}/messages`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  // === [CLAUDE: Unified chat endpoint - replaces all previous LLM/agent endpoints] ===

  /**
   * Send a chat message to a thread.
   * This is the unified chat endpoint that handles all messaging.
   * @param {number} threadId - The thread ID
   * @param {string} content - The message content
   * @param {Array<{type: string, id?: number, name?: string}>} addressedTo - Optional array of recipients
   * @param {number} inReplyTo - Optional message ID this is replying to
   */
  async chat(threadId, content, addressedTo = null, inReplyTo = null) {
    console.log('API Client: Sending chat message to thread:', threadId);
    const body = { content };
    if (addressedTo) body.addressed_to = addressedTo;
    if (inReplyTo) body.in_reply_to = inReplyTo;
    return this.request(`/threads/${threadId}/chat`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  // === [CLAUDE: Thread participant endpoints] ===

  async getThreadParticipants(threadId) {
    return this.request(`/threads/${threadId}/participants`);
  }

  async addThreadParticipant(threadId, participantType, participantId = null, systemAgentName = null, role = 'participant') {
    return this.request(`/threads/${threadId}/participants`, {
      method: 'POST',
      body: JSON.stringify({
        participant_type: participantType,
        participant_id: participantId,
        system_agent_name: systemAgentName,
        role: role,
      }),
    });
  }

  // === [CLAUDE: Confab learning endpoints] ===

  async getConfabLearnings(confabId) {
    return this.request(`/confabs/${confabId}/learnings`);
  }

  async createConfabLearning(confabId, content, summary = null, tags = [], source = 'manual', sourceThreadId = null) {
    return this.request(`/confabs/${confabId}/learnings`, {
      method: 'POST',
      body: JSON.stringify({
        content,
        summary,
        tags,
        source,
        source_thread_id: sourceThreadId,
      }),
    });
  }

  async updateConfabLearning(confabId, learningId, updates) {
    return this.request(`/confabs/${confabId}/learnings/${learningId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  async deleteConfabLearning(confabId, learningId) {
    return this.request(`/confabs/${confabId}/learnings/${learningId}`, {
      method: 'DELETE',
    });
  }

  // === Document Store endpoints ===

  async uploadDocument(confabId, file, metadata = null) {
    const url = `${this.baseURL}/confabs/${confabId}/documents`;
    const formData = new FormData();
    formData.append('file', file);
    if (metadata) {
      formData.append('metadata', JSON.stringify(metadata));
    }

    const token = localStorage.getItem('access_token');
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Upload failed: ${response.status}`);
    }
    return response.json();
  }

  async listDocuments(confabId) {
    return this.request(`/confabs/${confabId}/documents`);
  }

  async getDocument(confabId, documentId) {
    return this.request(`/confabs/${confabId}/documents/${documentId}`);
  }

  async deleteDocument(confabId, documentId) {
    return this.request(`/confabs/${confabId}/documents/${documentId}`, {
      method: 'DELETE',
    });
  }

  async searchDocuments(confabId, query, topK = 5, filterType = null) {
    return this.request(`/confabs/${confabId}/documents/search`, {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK, filter_type: filterType }),
    });
  }

  async getDocumentStats(confabId) {
    return this.request(`/confabs/${confabId}/documents/stats`);
  }

  // REMOVED: chatWithLangGraphAgent - use chat() instead
  // REMOVED: getAgentStatus - endpoint no longer exists
  // REMOVED: llmHealthCheck - endpoint no longer exists
  // REMOVED: llmGenerateResponse - endpoint no longer exists
  // REMOVED: llmListModels - endpoint no longer exists
  // REMOVED: createThreadMapping - replaced by addThreadParticipant
  // REMOVED: getThreadMappings - endpoint no longer exists
  // REMOVED: getConfabThreads - endpoint no longer exists

  clearToken() {
    localStorage.removeItem('access_token');
  }

}

// Create a singleton instance
export const apiClient = new ApiClient();
