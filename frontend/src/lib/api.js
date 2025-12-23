const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:1066';

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

/**
 * Stream a chat response via Server-Sent Events (SSE).
 * This is intentionally separate from sendMessage() so we can
 * run Socket.IO and SSE side-by-side during migration.
 */
export function streamMessage({ text, sessionId, onToken, onEnd, onError }) {
  const params = new URLSearchParams({ text });
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

  source.addEventListener("end", () => {
    source.close();
    if (onEnd) onEnd();
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