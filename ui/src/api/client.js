const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8011';
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

  async deployConfab(id) {
    return this.request(`/confabs/${id}/deploy`, { method: 'POST' });
  }

  async undeployConfab(id) {
    return this.request(`/confabs/${id}/undeploy`, { method: 'POST' });
  }

  async getDeployStatus(id) {
    return this.request(`/confabs/${id}/deploy-status`);
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

  // === Low-level Thread/Message APIs (for review/admin tooling) ===
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

  // Legacy unified chat — prefer sendConversationMessage for new code
  async chat(threadId, content, addressedTo = null, inReplyTo = null) {
    const body = { content };
    if (addressedTo) body.addressed_to = addressedTo;
    if (inReplyTo) body.in_reply_to = inReplyTo;
    return this.request(`/threads/${threadId}/chat`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  // === Low-level Participant APIs (for review/admin tooling) ===

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

  // === Document Store endpoints (V2 - Versioned) ===

  async uploadDocument(confabId, file, metadata = null) {
    // Convert file to base64 for V2 API
    const arrayBuffer = await file.arrayBuffer();
    const uint8Array = new Uint8Array(arrayBuffer);
    let binary = '';
    for (let i = 0; i < uint8Array.length; i++) {
      binary += String.fromCharCode(uint8Array[i]);
    }
    const base64 = btoa(binary);

    return this.request(`/confabs/${confabId}/documents`, {
      method: 'POST',
      body: JSON.stringify({
        filename: file.name,
        content_base64: base64,
        content_type: file.type || 'application/octet-stream',
        metadata: metadata,
      }),
    });
  }

  async listDocuments(confabId) {
    const response = await this.request(`/confabs/${confabId}/documents`);
    return response.documents; // V2 returns { documents: [...], total: N }
  }

  async getDocument(confabId, documentId) {
    return this.request(`/confabs/${confabId}/documents/${documentId}`);
  }

  async deleteDocument(confabId, documentId) {
    return this.request(`/confabs/${confabId}/documents/${documentId}`, {
      method: 'DELETE',
    });
  }

  async createDocumentVersion(confabId, documentId, file, metadata = null) {
    const arrayBuffer = await file.arrayBuffer();
    const uint8Array = new Uint8Array(arrayBuffer);
    let binary = '';
    for (let i = 0; i < uint8Array.length; i++) {
      binary += String.fromCharCode(uint8Array[i]);
    }
    const base64 = btoa(binary);

    return this.request(`/confabs/${confabId}/documents/${documentId}/versions`, {
      method: 'POST',
      body: JSON.stringify({
        content_base64: base64,
        metadata: metadata,
      }),
    });
  }

  async listDocumentVersions(confabId, documentId) {
    return this.request(`/confabs/${confabId}/documents/${documentId}/versions`);
  }

  // === High-level Conversation API (Phase 6) ===

  /**
   * Start a new foreman build conversation.
   * Creates confab, thread, participants, and welcome message in one call.
   */
  async startForemanConversation() {
    return this.request('/conversations/foreman/start', { method: 'POST' });
  }

  /**
   * Resume an existing foreman build conversation.
   * @param {number} confabId
   */
  async resumeForemanConversation(confabId) {
    return this.request(`/conversations/foreman/${confabId}/resume`, { method: 'POST' });
  }

  /**
   * Start a runtime conversation with a published confab.
   * @param {number} confabId
   */
  async startRuntimeConversation(confabId) {
    return this.request(`/conversations/runtime/${confabId}/start`, { method: 'POST' });
  }

  /**
   * Send a message using the high-level conversation endpoint.
   * Routes to the correct orchestrator automatically.
   * @param {number} threadId
   * @param {string} content
   * @param {object} options - { addressedTo, inReplyTo }
   */
  async sendConversationMessage(threadId, content, options = {}) {
    const body = { content };
    if (options.addressedTo) body.addressed_to = options.addressedTo;
    if (options.inReplyTo) body.in_reply_to = options.inReplyTo;
    return this.request(`/conversations/${threadId}/messages`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
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

  // Version endpoint (no auth required)
  async getApiVersion() {
    const url = `${this.baseURL}/`;
    try {
      const response = await fetch(url);
      if (!response.ok) {
        return { version: 'unknown' };
      }
      const data = await response.json();
      return { version: data.version || 'unknown' };
    } catch (error) {
      console.error('API Client: Failed to fetch API version:', error);
      return { version: 'unavailable' };
    }
  }

}

// Create a singleton instance
export const apiClient = new ApiClient();
