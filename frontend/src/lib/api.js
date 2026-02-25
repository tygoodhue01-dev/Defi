import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API_BASE = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ====================
// Vault APIs
// ====================

export const vaultApi = {
  // Get all vaults
  getVaults: async () => {
    const response = await api.get('/vaults');
    return response.data;
  },
  
  // Get single vault
  getVault: async (id) => {
    const response = await api.get(`/vaults/${id}`);
    return response.data;
  },
  
  // Create vault (admin only)
  createVault: async (data) => {
    const response = await api.post('/vaults', data);
    return response.data;
  },
  
  // Update vault (admin only)
  updateVault: async (id, data) => {
    const response = await api.put(`/vaults/${id}`, data);
    return response.data;
  },
  
  // Delete vault (admin only)
  deleteVault: async (id) => {
    const response = await api.delete(`/vaults/${id}`);
    return response.data;
  },
};

// ====================
// Metrics APIs
// ====================

export const metricsApi = {
  // Get vault metrics
  getMetrics: async (vaultId) => {
    const response = await api.get(`/vaults/${vaultId}/metrics`);
    return response.data;
  },
  
  // Refresh vault metrics
  refreshMetrics: async (vaultId) => {
    const response = await api.post(`/vaults/${vaultId}/metrics/refresh`);
    return response.data;
  },
};

// ====================
// Harvest APIs
// ====================

export const harvestApi = {
  // Get harvest history
  getHarvests: async (vaultId, limit = 20) => {
    const response = await api.get(`/vaults/${vaultId}/harvests`, { params: { limit } });
    return response.data;
  },
  
  // Record harvest event
  recordHarvest: async (vaultId, txHash, profit = '0') => {
    const response = await api.post(`/vaults/${vaultId}/harvests`, null, {
      params: { txHash, profit },
    });
    return response.data;
  },
};

// ====================
// User Action APIs
// ====================

export const userActionApi = {
  // Record user action (deposit/withdraw)
  recordAction: async (data) => {
    const response = await api.post('/user-actions', data);
    return response.data;
  },
  
  // Get user actions
  getUserActions: async (userAddress, vaultId = null, limit = 50) => {
    const params = { limit };
    if (vaultId) params.vault_id = vaultId;
    const response = await api.get(`/user-actions/${userAddress}`, { params });
    return response.data;
  },
};

// ====================
// Beefy-style APIs
// ====================

export const beefyApi = {
  // Get all token prices
  getPrices: async (chainId = 8453) => {
    const response = await api.get('/prices', { params: { chain_id: chainId } });
    return response.data;
  },

  // Get all LP prices
  getLps: async (chainId = 8453) => {
    const response = await api.get('/lps', { params: { chain_id: chainId } });
    return response.data;
  },

  // Get TVL for all vaults
  getTvl: async () => {
    const response = await api.get('/tvl');
    return response.data;
  },

  // Get APY for all vaults
  getApy: async () => {
    const response = await api.get('/apy');
    return response.data;
  },

  // Get APY breakdown for a specific vault
  getVaultApy: async (vaultId) => {
    const response = await api.get(`/apy/${vaultId}`);
    return response.data;
  },
};

// ====================
// Auth APIs
// ====================

export const authApi = {
  // Admin login
  login: async (password) => {
    const response = await api.post('/admin/login', { password });
    return response.data;
  },
  
  // Admin logout
  logout: async () => {
    const response = await api.post('/admin/logout');
    return response.data;
  },
  
  // Check auth status
  checkAuth: async () => {
    const response = await api.get('/admin/check');
    return response.data;
  },
};

export default api;
