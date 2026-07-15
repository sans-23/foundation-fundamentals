import keycloak from './keycloak';

/**
 * API Client with Automatic Bearer Token Injection
 * 
 * This module wraps the native `fetch` API to automatically attach
 * the Keycloak Access Token as an Authorization header on every request.
 * 
 * Flow:
 * 1. Before each request, call `keycloak.updateToken(30)` to ensure the
 *    access token is valid for at least 30 more seconds.
 * 2. If the token is about to expire, the adapter silently refreshes it
 *    using the Refresh Token (no user interaction required).
 * 3. Attach the fresh token as `Authorization: Bearer <token>`.
 * 
 * This means our backend services NEVER see an expired token, and the user
 * never gets randomly logged out mid-session.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:4000';

async function apiFetch(endpoint, options = {}) {
  try {
    // Silently refresh token if it expires within 30 seconds
    await keycloak.updateToken(30);
  } catch (err) {
    // If refresh fails (e.g., refresh token expired), force re-login
    console.error('Token refresh failed, redirecting to login...', err);
    keycloak.login();
    return;
  }

  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${keycloak.token}`,
    ...options.headers,
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`API Error ${response.status}: ${errorBody}`);
  }

  return response.json();
}

// Convenience methods
export const api = {
  get: (endpoint) => apiFetch(endpoint, { method: 'GET' }),
  post: (endpoint, data) => apiFetch(endpoint, { method: 'POST', body: JSON.stringify(data) }),
};
