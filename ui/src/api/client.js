const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

class ApiClient {
  constructor() {
    this.baseURL = API_BASE_URL;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    
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
      const response = await fetch(url, config);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.message || `HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        throw new Error('Network error. Please check your connection and ensure the backend server is running.');
      }
      throw error;
    }
  }

  // Auth endpoints
  async register(userData) {
    return this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
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

  async getGitHubAuthUrl() {
    return `${this.baseURL}/auth/github/authorize`;
  }

  async connectGitHub(githubData) {
    return this.request('/auth/github/connect', {
      method: 'POST',
      body: JSON.stringify(githubData),
    });
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

  clearToken() {
    localStorage.removeItem('access_token');
  }
}

// Create a singleton instance
export const apiClient = new ApiClient();
