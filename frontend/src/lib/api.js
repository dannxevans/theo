const API_BASE = "";

export async function sendMessage({ text, sessionId }) {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      session_id: sessionId,
      text
    })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Request failed");
  }

  return response.json();
}

export async function fetchSessionSummary(sessionId) {
  const response = await fetch(`${API_BASE}/api/session/${sessionId}`);

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to load session summary");
  }

  return response.json();
}

export async function getSessions() {
  try {
    const response = await fetch(`${API_BASE}/api/sessions`);

    if (!response.ok) {
      console.error("Failed to load sessions:", response.status);
      return [];
    }

    const data = await response.json();
    return Array.isArray(data) ? data : [];
  } catch (err) {
    // This catches CORS, network failures, backend restarts, etc.
    console.error("Session fetch failed:", err);
    return [];
  }
}

export async function rememberMemory(key, value) {
  const response = await fetch(`${API_BASE}/api/memory/remember`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      key,
      value
    })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to remember value");
  }

  return response.json();
}

export async function forgetMemory(key) {
  const response = await fetch(`${API_BASE}/api/memory/forget`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      key
    })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to forget value");
  }

  return response.json();
}

// =============================
// Providers API
// =============================

export async function listProviders() {
  const response = await fetch(`${API_BASE}/api/providers`);

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to load providers");
  }

  return response.json();
}

export async function getProviders() {
  return listProviders();
}

export async function upsertProvider(provider) {
  const response = await fetch(`${API_BASE}/api/providers`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(provider)
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to save provider");
  }

  return response.json();
}

export async function deleteProvider(providerId) {
  const response = await fetch(`${API_BASE}/api/providers/${providerId}`, {
    method: "DELETE"
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to delete provider");
  }

  return response.json();
}
// =============================
// Sessions API
// =============================

export async function deleteSessionApi(sessionId) {
  const response = await fetch(
    `${API_BASE}/api/sessions/${sessionId}`,
    {
      method: "DELETE"
    }
  );

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to delete session");
  }

  return response.json();
}

export async function getSessionMessages(sessionId) {
  // Add cache-busting timestamp to prevent browser caching
  const timestamp = Date.now();
  const response = await fetch(
    `${API_BASE}/api/sessions/${sessionId}/messages?_=${timestamp}`,
    {
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
      }
    }
  );

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to load session messages");
  }

  const data = await response.json();
  return Array.isArray(data) ? data : [];
}

export async function exportSession(sessionId, format = "json") {
  const response = await fetch(
    `${API_BASE}/api/sessions/${sessionId}/export?format=${format}`
  );

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to export session");
  }

  // Trigger download
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `conversation_${sessionId}.${format === "markdown" ? "md" : "json"}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

export async function forkSession(sessionId, turnIndex = null, title = null) {
  const response = await fetch(
    `${API_BASE}/api/sessions/${sessionId}/fork`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        turn_index: turnIndex,
        title: title
      })
    }
  );

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to fork session");
  }

  return response.json();
}

export async function generateSessionTitle(sessionId) {
  const response = await fetch(
    `${API_BASE}/api/sessions/${sessionId}/generate-title`,
    {
      method: "POST"
    }
  );

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to generate session title");
  }

  return response.json();
}

export async function regenerateMessage(sessionId, turnId) {
  const response = await fetch(
    `${API_BASE}/api/sessions/${sessionId}/regenerate/${turnId}`,
    {
      method: "POST"
    }
  );

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to regenerate message");
  }

  return response.json();
}

// =============================
// Intent Management API
// =============================

export async function getIntents() {
  const response = await fetch(`${API_BASE}/api/intents`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to load intents");
  }

  return response.json();
}

export async function getIntent(intentId) {
  const response = await fetch(`${API_BASE}/api/intents/${intentId}`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to load intent");
  }

  return response.json();
}

export async function createIntent(intent) {
  const response = await fetch(`${API_BASE}/api/intents`, {
    method: "POST",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json"
    },
    body: JSON.stringify(intent)
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to create intent");
  }

  return response.json();
}

export async function updateIntent(intentId, updates) {
  const response = await fetch(`${API_BASE}/api/intents/${intentId}`, {
    method: "PUT",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json"
    },
    body: JSON.stringify(updates)
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to update intent");
  }

  return response.json();
}

export async function deleteIntent(intentId) {
  const response = await fetch(`${API_BASE}/api/intents/${intentId}`, {
    method: "DELETE",
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to delete intent");
  }

  return response.json();
}

// =============================
// Routing Preferences API
// =============================

export async function getRoutingRules() {
  const response = await fetch(`${API_BASE}/api/routing`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to load routing rules");
  }

  return response.json();
}

export async function setRoutingRule(intent, providerId, fallbackProviderId = null) {
  const response = await fetch(`${API_BASE}/api/routing`, {
    method: "POST",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      intent,
      provider_id: providerId,
      fallback_provider_id: fallbackProviderId
    })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to save routing rule");
  }

  return response.json();
}

export async function deleteRoutingRule(intent) {
  const response = await fetch(`${API_BASE}/api/routing/${intent}`, {
    method: "DELETE",
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to delete routing rule");
  }

  return response.json();
}

// =============================
// Debug / Logging API
// =============================

export async function getDebugFlag() {
  const response = await fetch(`${API_BASE}/api/settings/debug`);

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to load debug flag");
  }

  const data = await response.json();
  return Boolean(data.enabled);
}

export async function setDebugFlag(enabled) {
  const response = await fetch(`${API_BASE}/api/settings/debug`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      enabled: Boolean(enabled)
    })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to save debug flag");
  }

  return response.json();
}

export async function getMessageDebugFlag() {
  const response = await fetch(`${API_BASE}/api/settings/message-debug`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to get message debug flag");
  }

  return response.json();
}

export async function setMessageDebugFlag(enabled) {
  const response = await fetch(`${API_BASE}/api/settings/message-debug`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders()
    },
    body: JSON.stringify({
      enabled: Boolean(enabled)
    })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to save message debug flag");
  }

  return response.json();
}

// =============================
// System Prompt Configuration API
// =============================

export async function getSystemPromptConfig() {
  const response = await fetch(`${API_BASE}/api/settings/system-prompt`);

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to load system prompt config");
  }

  return response.json();
}

export async function updateSystemPromptConfig(config) {
  const response = await fetch(`${API_BASE}/api/settings/system-prompt`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(config)
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to update system prompt config");
  }

  return response.json();
}

/**
 * Stream a chat response via Server-Sent Events (SSE).
 * This is intentionally separate from sendMessage() so we can
 * run Socket.IO and SSE side-by-side during migration.
 */
export function streamMessage({ text, sessionId, forcedProvider, workSubtab, onToken, onEnd, onError }) {
  const params = new URLSearchParams({ text });
  if (forcedProvider) {
    params.append("forced_provider", forcedProvider);
  }
  if (workSubtab) {
    params.append("work_subtab", workSubtab);
  }
  // Add auth token to query params since EventSource doesn't support custom headers
  const token = getAuthToken();
  if (token) {
    params.append("token", token);
  }
  const url = `${API_BASE}/api/stream/${sessionId}?${params.toString()}`;

  const source = new EventSource(url);

  source.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.token && onToken) {
        onToken(data.token);
      }
    } catch (err) {
      console.error("Failed to parse SSE message:", err);
    }
  };

  source.addEventListener("end", (event) => {
    let meta = {};

    try {
      if (event.data) {
        meta = JSON.parse(event.data);
      }
    } catch (err) {
      console.warn("Failed to parse end-event metadata:", err);
    }

    source.close();
    if (onEnd) onEnd(meta);
  });

  source.onerror = (err) => {
    console.error("SSE error:", err);
    source.close();
    if (onError) onError(err);
  };

  return () => {
    source.close();
  };
}

// =============================
// Step 2: Structured Memory API
// =============================

export async function getMemories(params = {}) {
  const queryString = new URLSearchParams();
  if (params.type) queryString.append("type", params.type);
  if (params.limit) queryString.append("limit", params.limit);

  const url = `${API_BASE}/api/memories${queryString.toString() ? "?" + queryString.toString() : ""}`;
  const response = await fetch(url);

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to load memories");
  }

  return response.json();
}

export async function createMemory({ type, key, value, pinned }) {
  const response = await fetch(`${API_BASE}/api/memories`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      type,
      key,
      value,
      pinned
    })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to create memory");
  }

  return response.json();
}

export async function deleteMemory(memoryId) {
  const response = await fetch(`${API_BASE}/api/memories/${memoryId}`, {
    method: "DELETE"
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to delete memory");
  }

  return response.json();
}

export async function updateMemory(memoryId, { type, key, value }) {
  const response = await fetch(`${API_BASE}/api/memories/${memoryId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      type,
      key,
      value
    })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to update memory");
  }

  return response.json();
}

export async function pinMemory(memoryId, pinned) {
  const response = await fetch(`${API_BASE}/api/memories/${memoryId}/pin`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      pinned
    })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to pin memory");
  }

  return response.json();
}

export async function getRelevantMemories(query) {
  const response = await fetch(`${API_BASE}/api/memories/relevant?q=${encodeURIComponent(query)}`);

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to get relevant memories");
  }

  return response.json();
}

// =============================
// Step 3: Provider Intelligence API
// =============================

export async function getProviderHealth() {
  const response = await fetch(`${API_BASE}/api/providers/health`);

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to get provider health");
  }

  return response.json();
}

export async function resetProviderHealth(providerId) {
  const response = await fetch(`${API_BASE}/api/providers/${providerId}/health/reset`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    }
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to reset provider health");
  }

  return response.json();
}

export async function getProviderCosts(days = 30) {
  const params = new URLSearchParams();
  if (days !== null) {
    params.append("days", days.toString());
  }

  const response = await fetch(`${API_BASE}/api/providers/costs?${params}`);

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to get provider costs");
  }

  return response.json();
}

export async function getVoiceCosts(days = 30) {
  const params = new URLSearchParams();
  if (days !== null) {
    params.append("days", days.toString());
  }

  const response = await fetch(`${API_BASE}/api/providers/voice-costs?${params}`);

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to get voice costs");
  }

  return response.json();
}

export async function resetProviderUsage() {
  const response = await fetch(`${API_BASE}/api/providers/usage/reset`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    }
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to reset provider usage");
  }

  return response.json();
}

// =============================
// Authentication API
// =============================

function getAuthToken() {
  return localStorage.getItem("auth_token");
}

function getAuthHeaders() {
  const token = getAuthToken();
  return token ? { "Authorization": `Bearer ${token}` } : {};
}

export async function login(username, password) {
  const response = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ username, password })
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.error || "Login failed");
  }

  return response.json();
}

export async function logout() {
  const response = await fetch(`${API_BASE}/api/auth/logout`, {
    method: "POST",
    headers: {
      ...getAuthHeaders()
    }
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Logout failed");
  }

  return response.json();
}

export async function verifySession() {
  const response = await fetch(`${API_BASE}/api/auth/verify`, {
    headers: {
      ...getAuthHeaders()
    }
  });

  if (!response.ok) {
    return { valid: false };
  }

  return response.json();
}

export async function changePassword(currentPassword, newPassword) {
  const response = await fetch(`${API_BASE}/api/auth/change-password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders()
    },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword
    })
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.error || "Failed to change password");
  }

  return response.json();
}

// =============================
// API Key Management
// =============================

export async function createApiKey(name, expiresInDays = null) {
  const response = await fetch(`${API_BASE}/api/api-keys`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders()
    },
    body: JSON.stringify({
      name,
      expires_in_days: expiresInDays
    })
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.error || "Failed to create API key");
  }

  return response.json();
}

export async function listApiKeys() {
  const response = await fetch(`${API_BASE}/api/api-keys`, {
    method: "GET",
    headers: {
      ...getAuthHeaders()
    }
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.error || "Failed to list API keys");
  }

  return response.json();
}

export async function revokeApiKey(keyId) {
  const response = await fetch(`${API_BASE}/api/api-keys/${keyId}`, {
    method: "DELETE",
    headers: {
      ...getAuthHeaders()
    }
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.error || "Failed to revoke API key");
  }

  return response.json();
}

export async function updateApiKey(keyId, updates) {
  const response = await fetch(`${API_BASE}/api/api-keys/${keyId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders()
    },
    body: JSON.stringify(updates)
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.error || "Failed to update API key");
  }

  return response.json();
}

// =============================
// Mode Management
// =============================

export async function getUserMode() {
  const response = await fetch(`${API_BASE}/api/mode`, {
    headers: {
      ...getAuthHeaders()
    }
  });

  if (!response.ok) {
    throw new Error("Failed to get user mode");
  }

  return response.json();
}

export async function setUserMode(mode) {
  const response = await fetch(`${API_BASE}/api/mode`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders()
    },
    body: JSON.stringify({ mode })
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.error || "Failed to set mode");
  }

  return response.json();
}

export async function getAllModeSettings() {
  const response = await fetch(`${API_BASE}/api/mode/settings`, {
    headers: {
      ...getAuthHeaders()
    }
  });

  if (!response.ok) {
    throw new Error("Failed to get mode settings");
  }

  return response.json();
}

export async function getModeSettings(mode) {
  const response = await fetch(`${API_BASE}/api/mode/settings/${mode}`, {
    headers: {
      ...getAuthHeaders()
    }
  });

  if (!response.ok) {
    throw new Error("Failed to get mode settings");
  }

  return response.json();
}

export async function updateModeSettings(mode, settings) {
  const response = await fetch(`${API_BASE}/api/mode/settings/${mode}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders()
    },
    body: JSON.stringify(settings)
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.error || "Failed to update mode settings");
  }

  return response.json();
}

// =============================
// Work Mode Sub-Tab Management
// =============================

export async function getWorkSubtabConfig(subtab) {
  const response = await fetch(`${API_BASE}/api/mode/work/subtab/${subtab}`, {
    headers: {
      ...getAuthHeaders()
    }
  });

  if (!response.ok) {
    throw new Error("Failed to get work subtab config");
  }

  return response.json();
}

export async function updateWorkSubtabConfig(subtab, config) {
  const response = await fetch(`${API_BASE}/api/mode/work/subtab/${subtab}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders()
    },
    body: JSON.stringify(config)
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.error || "Failed to update work subtab config");
  }

  return response.json();
}

export async function getAllWorkSubtabConfigs() {
  const response = await fetch(`${API_BASE}/api/mode/work/subtabs`, {
    headers: {
      ...getAuthHeaders()
    }
  });

  if (!response.ok) {
    throw new Error("Failed to get all work subtab configs");
  }

  return response.json();
}

// =============================
// M365 Integration
// =============================

export async function startM365Auth() {
  const response = await fetch(`${API_BASE}/api/m365/auth/start`, {
    method: "POST",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json"
    }
  });

  // Return JSON even on error so we can show configuration instructions
  const data = await response.json();

  if (!response.ok) {
    return data; // Return error object with instructions
  }

  return data;
}

export async function pollM365Auth(deviceCode) {
  const response = await fetch(`${API_BASE}/api/m365/auth/poll`, {
    method: "POST",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ device_code: deviceCode })
  });

  const data = await response.json();

  // Backend returns 200 for success, 202 for pending, 400+ for errors
  if (response.ok || response.status === 202) {
    return data;
  }

  // Error case
  throw new Error(data.error || "Failed to poll M365 authentication");
}

export async function getM365Status() {
  const response = await fetch(`${API_BASE}/api/m365/status`, {
    headers: {
      ...getAuthHeaders()
    }
  });

  if (!response.ok) {
    throw new Error("Failed to get M365 status");
  }

  return response.json();
}

export async function disconnectM365() {
  const response = await fetch(`${API_BASE}/api/m365/disconnect`, {
    method: "POST",
    headers: {
      ...getAuthHeaders()
    }
  });

  if (!response.ok) {
    throw new Error("Failed to disconnect M365");
  }

  return response.json();
}

// =============================
// Confirmation Workflow
// =============================

export async function getPendingConfirmations() {
  const response = await fetch(`${API_BASE}/api/confirmations/pending`, {
    headers: {
      ...getAuthHeaders()
    }
  });

  if (!response.ok) {
    throw new Error("Failed to get pending confirmations");
  }

  return response.json();
}

export async function approveConfirmation(confirmationId) {
  const response = await fetch(`${API_BASE}/api/confirmations/${confirmationId}/approve`, {
    method: "POST",
    headers: {
      ...getAuthHeaders()
    }
  });

  if (!response.ok) {
    throw new Error("Failed to approve confirmation");
  }

  return response.json();
}

export async function rejectConfirmation(confirmationId, reason = null) {
  const response = await fetch(`${API_BASE}/api/confirmations/${confirmationId}/reject`, {
    method: "POST",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ reason })
  });

  if (!response.ok) {
    throw new Error("Failed to reject confirmation");
  }

  return response.json();
}

export async function dismissProactiveNotification(turnId) {
  const response = await fetch(`${API_BASE}/api/proactive/dismiss/${turnId}`, {
    method: "POST",
    headers: {
      ...getAuthHeaders()
    }
  });

  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.message || "Failed to dismiss notification");
  }

  return response.json();
}

// =============================
// Session Mode API
// =============================

export async function getSessionMode(sessionId) {
  const response = await fetch(`${API_BASE}/api/sessions/${sessionId}/mode`, {
    headers: { ...getAuthHeaders() }
  });

  if (!response.ok) {
    throw new Error("Failed to get session mode");
  }

  const data = await response.json();
  return data.mode;
}

// =============================
// PII Configuration API
// =============================

export async function getPIIConfig() {
  const response = await fetch(`${API_BASE}/api/mode/settings/work/pii-config`, {
    headers: { ...getAuthHeaders() }
  });

  if (!response.ok) {
    throw new Error("Failed to get PII config");
  }

  return response.json();
}

export async function updatePIIConfig(config) {
  const response = await fetch(`${API_BASE}/api/mode/settings/work/pii-config`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders()
    },
    body: JSON.stringify(config)
  });

  if (!response.ok) {
    throw new Error("Failed to update PII config");
  }

  return response.json();
}

// ========================================
// Voice API (TTS & STT)
// ========================================

/**
 * Convert text to speech audio.
 * @param {string} text - Text to convert to speech
 * @param {string} voice - Voice ID (alloy, echo, fable, onyx, nova, shimmer)
 * @param {number} speed - Speech speed (0.25 to 4.0)
 * @returns {Promise<Blob>} Audio blob (MP3)
 */
export async function textToSpeech(text, voice = "alloy", speed = 1.0) {
  const response = await fetch(`${API_BASE}/api/voice/tts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders()
    },
    body: JSON.stringify({ text, voice, speed })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || "TTS failed");
  }

  return response.blob();
}

/**
 * Convert speech audio to text.
 * @param {Blob} audioBlob - Audio data
 * @param {string} format - Audio format (webm, mp3, wav, etc.)
 * @param {string} language - Optional language code (e.g., 'en', 'es')
 * @returns {Promise<Object>} Transcription result { text, language }
 */
export async function speechToText(audioBlob, format = "webm", language = null) {
  const formData = new FormData();
  formData.append("audio", audioBlob, `recording.${format}`);
  formData.append("format", format);
  if (language) {
    formData.append("language", language);
  }

  const response = await fetch(`${API_BASE}/api/voice/stt`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: formData
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || "STT failed");
  }

  return response.json();
}

/**
 * Get list of available TTS voices.
 * @returns {Promise<Array>} List of voice objects
 */
export async function getVoices() {
  const response = await fetch(`${API_BASE}/api/voice/voices`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    throw new Error("Failed to fetch voices");
  }

  const data = await response.json();
  return data.voices || [];
}

/**
 * Get user preference by key
 */
export async function getUserPreference(key) {
  const response = await fetch(`${API_BASE}/api/settings/preference/${key}`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    throw new Error(`Failed to get preference: ${key}`);
  }

  const data = await response.json();
  return data.value;
}

/**
 * Set user preference by key
 */
export async function setUserPreference(key, value) {
  const response = await fetch(`${API_BASE}/api/settings/preference/${key}`, {
    method: "POST",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ value })
  });

  if (!response.ok) {
    throw new Error(`Failed to set preference: ${key}`);
  }

  return await response.json();
}

// =============================
// Feature Providers API
// =============================

/**
 * Get all feature providers
 */
export async function getFeatureProviders() {
  const response = await fetch(`${API_BASE}/api/feature-providers`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to get feature providers");
  }

  return response.json();
}

/**
 * Get a specific feature provider
 */
export async function getFeatureProvider(providerType) {
  const response = await fetch(`${API_BASE}/api/feature-providers/${providerType}`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    if (response.status === 404) {
      return null;
    }
    const err = await response.text();
    throw new Error(err || "Failed to get feature provider");
  }

  return response.json();
}

/**
 * Configure or update a feature provider
 */
export async function configureFeatureProvider(providerType, config) {
  const response = await fetch(`${API_BASE}/api/feature-providers/${providerType}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders()
    },
    body: JSON.stringify(config)
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to configure feature provider");
  }

  return response.json();
}

/**
 * Delete a feature provider
 */
export async function deleteFeatureProvider(providerType) {
  const response = await fetch(`${API_BASE}/api/feature-providers/${providerType}`, {
    method: "DELETE",
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to delete feature provider");
  }

  return response.json();
}

// Proactive Notification Settings
export async function getProactiveSettings() {
  const response = await fetch(`${API_BASE}/api/settings/proactive`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to fetch proactive settings");
  }

  return response.json();
}

export async function updateProactiveSettings(settings) {
  const response = await fetch(`${API_BASE}/api/settings/proactive`, {
    method: "POST",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json"
    },
    body: JSON.stringify(settings)
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to update proactive settings");
  }

  return response.json();
}

// =============================
// Debug Console
// =============================

/**
 * Fetch historical debug logs with filtering and pagination
 */
export async function fetchDebugLogs(filters = {}) {
  const params = new URLSearchParams(filters);
  const response = await fetch(`${API_BASE}/api/debug/logs?${params}`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to fetch debug logs");
  }

  return response.json();
}

/**
 * Stream debug logs in real-time using Server-Sent Events
 */
export function streamDebugLogs(onMessage, filters = {}) {
  const token = localStorage.getItem('auth_token');
  if (!token) {
    throw new Error('No authentication token found');
  }

  const params = new URLSearchParams({ ...filters, token });
  const eventSource = new EventSource(`${API_BASE}/api/debug/logs/stream?${params}`);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage({ data });
    } catch (e) {
      console.error('Failed to parse log event:', e);
    }
  };

  eventSource.onerror = (error) => {
    console.error('Debug log stream error:', error);
  };

  return eventSource;
}

/**
 * Toggle debug mode on/off
 */
export async function toggleDebugMode(enabled) {
  const response = await fetch(`${API_BASE}/api/debug/toggle`, {
    method: "POST",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ enabled })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to toggle debug mode");
  }

  return response.json();
}

/**
 * Clear debug logs from database
 */
export async function clearDebugLogs(filters = {}) {
  const params = new URLSearchParams(filters);
  const response = await fetch(`${API_BASE}/api/debug/logs?${params}`, {
    method: "DELETE",
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to clear debug logs");
  }

  return response.json();
}

/**
 * Update debug logger filters
 */
export async function updateDebugFilters(filters) {
  const response = await fetch(`${API_BASE}/api/debug/filters`, {
    method: "POST",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ filters })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to update filters");
  }

  return response.json();
}

/**
 * Send a frontend log to the backend
 */
export async function logToBackend(level, message, component, sessionId = null) {
  try {
    const response = await fetch(`${API_BASE}/api/debug/log`, {
      method: "POST",
      headers: {
        ...getAuthHeaders(),
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        level,
        message,
        component,
        session_id: sessionId
      })
    });

    // Don't throw on error for logging - just log to console
    if (!response.ok) {
      console.warn('Failed to send log to backend');
    }
  } catch (e) {
    console.warn('Failed to send log to backend:', e);
  }
}