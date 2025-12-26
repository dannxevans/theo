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
  const response = await fetch(
    `${API_BASE}/api/sessions/${sessionId}/messages`
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

// =============================
// Intent Management API
// =============================

export async function getIntents() {
  const response = await fetch(`${API_BASE}/api/intents`);

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to load intents");
  }

  return response.json();
}

export async function getIntent(intentId) {
  const response = await fetch(`${API_BASE}/api/intents/${intentId}`);

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
    method: "DELETE"
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
  const response = await fetch(`${API_BASE}/api/routing`);

  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || "Failed to load routing rules");
  }

  return response.json();
}

export async function setRoutingRule(intent, providerId) {
  const response = await fetch(`${API_BASE}/api/routing`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      intent,
      provider_id: providerId
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
    method: "DELETE"
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
export function streamMessage({ text, sessionId, forcedProvider, onToken, onEnd, onError }) {
  const params = new URLSearchParams({ text });
  if (forcedProvider) {
    params.append("forced_provider", forcedProvider);
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