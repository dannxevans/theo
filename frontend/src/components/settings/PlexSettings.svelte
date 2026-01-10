<script>
  import { onMount, onDestroy } from "svelte";

  const API_BASE_URL = "";

  let status = {
    connected: false,
    server_name: "",
    server_url: "",
    plex_username: "",
    is_valid: true
  };

  let settings = {
    new_episode_notifications_enabled: false,
    new_season_notifications_enabled: false,
    new_movie_notifications_enabled: false,
    check_frequency_minutes: 15,
    quiet_hours_start: "",
    quiet_hours_end: ""
  };

  let loading = false;
  let connecting = false;
  let polling = false;
  let saveMessage = "";
  let errorMessage = "";
  let settingsExpanded = false;

  // Server URL override
  let customServerUrl = "";
  let updatingServerUrl = false;
  let serverUrlMessage = "";

  // OAuth flow state
  let pinCode = "";
  let pinId = null;
  let authUrl = "";
  let pollInterval = null;

  onMount(async () => {
    await loadStatus();
    if (status.connected) {
      await loadSettings();
    }
  });

  onDestroy(() => {
    if (pollInterval) {
      clearInterval(pollInterval);
    }
  });

  async function loadStatus() {
    try {
      loading = true;
      errorMessage = "";

      const token = localStorage.getItem("auth_token");
      const response = await fetch(`${API_BASE_URL}/api/plex/status`, {
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });

      if (response.status === 401) {
        // Not authenticated - silently fail
        console.warn("Not authenticated for Plex status");
        return;
      }

      if (response.ok) {
        const text = await response.text();
        if (text) {
          const data = JSON.parse(text);
          status = data;
        }
      } else {
        console.error("Failed to load Plex status:", response.status);
      }
    } catch (err) {
      console.error("Failed to load Plex status:", err);
      errorMessage = "Failed to load Plex status";
    } finally {
      loading = false;
    }
  }

  async function loadSettings() {
    try {
      const token = localStorage.getItem("auth_token");
      const response = await fetch(`${API_BASE_URL}/api/plex/settings`, {
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });

      if (response.status === 401) {
        console.warn("Not authenticated for Plex settings");
        return;
      }

      if (response.ok) {
        const text = await response.text();
        if (text) {
          const data = JSON.parse(text);
          settings = data;
        }
      }
    } catch (err) {
      console.error("Failed to load Plex settings:", err);
    }
  }

  async function startConnection() {
    try {
      connecting = true;
      errorMessage = "";
      pinCode = "";
      pinId = null;

      const token = localStorage.getItem("auth_token");
      const response = await fetch(`${API_BASE_URL}/api/plex/auth/start`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });

      if (!response.ok) {
        const text = await response.text();
        if (text) {
          try {
            const error = JSON.parse(text);
            throw new Error(error.error || "Failed to start Plex authentication");
          } catch (e) {
            if (e.message !== "Failed to start Plex authentication") {
              // JSON parse failed
              throw new Error("Failed to start Plex authentication");
            }
            throw e;
          }
        }
        throw new Error("Failed to start Plex authentication");
      }

      const text = await response.text();
      if (!text) {
        throw new Error("Empty response from server");
      }
      const data = JSON.parse(text);
      pinCode = data.code;
      pinId = data.pin_id;
      authUrl = data.auth_url;

      // Open auth URL in popup
      const width = 600;
      const height = 700;
      const left = (screen.width / 2) - (width / 2);
      const top = (screen.height / 2) - (height / 2);

      window.open(
        authUrl,
        "PlexAuth",
        `width=${width},height=${height},left=${left},top=${top}`
      );

      // Start polling
      startPolling();
    } catch (err) {
      console.error("Failed to start Plex connection:", err);
      errorMessage = err.message;
      connecting = false;
    }
  }

  function startPolling() {
    polling = true;
    pollInterval = setInterval(async () => {
      await checkAuthStatus();
    }, 2500); // Poll every 2.5 seconds
  }

  async function checkAuthStatus() {
    try {
      const token = localStorage.getItem("auth_token");
      const response = await fetch(`${API_BASE_URL}/api/plex/auth/poll`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ pin_id: pinId })
      });

      if (!response.ok) {
        throw new Error("Poll request failed");
      }

      const text = await response.text();
      if (!text) {
        return;
      }

      const data = JSON.parse(text);

      if (data.status === "authorized") {
        // Success!
        clearInterval(pollInterval);
        pollInterval = null;
        polling = false;
        connecting = false;
        pinCode = "";
        pinId = null;

        // Reload status and settings
        await loadStatus();
        await loadSettings();

        saveMessage = "Plex connected successfully!";
        setTimeout(() => {
          saveMessage = "";
        }, 3000);
      }
      // If status is "pending", keep polling
    } catch (err) {
      console.error("Error polling auth status:", err);
      // Don't stop polling on error, might be transient
    }
  }

  function cancelConnection() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    polling = false;
    connecting = false;
    pinCode = "";
    pinId = null;
    errorMessage = "";
  }

  async function disconnect() {
    if (!confirm("Are you sure you want to disconnect your Plex account? This will delete all Plex settings and notification tracking.")) {
      return;
    }

    try {
      loading = true;
      errorMessage = "";

      const token = localStorage.getItem("auth_token");
      const response = await fetch(`${API_BASE_URL}/api/plex/disconnect`, {
        method: "DELETE",
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error("Failed to disconnect Plex");
      }

      status = {
        connected: false,
        server_name: "",
        server_url: "",
        plex_username: "",
        is_valid: true
      };

      saveMessage = "Plex disconnected successfully";
      setTimeout(() => {
        saveMessage = "";
      }, 3000);
    } catch (err) {
      console.error("Failed to disconnect Plex:", err);
      errorMessage = "Failed to disconnect Plex";
    } finally {
      loading = false;
    }
  }

  async function updateServerUrl() {
    try {
      updatingServerUrl = true;
      serverUrlMessage = "";
      errorMessage = "";

      if (!customServerUrl.trim()) {
        errorMessage = "Please enter a server URL";
        return;
      }

      const token = localStorage.getItem("auth_token");
      const response = await fetch(`${API_BASE_URL}/api/plex/server-url`, {
        method: "PUT",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ server_url: customServerUrl.trim() })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Failed to update server URL");
      }

      await loadStatus();
      serverUrlMessage = "Server URL updated successfully";
      customServerUrl = "";
      setTimeout(() => {
        serverUrlMessage = "";
      }, 3000);
    } catch (err) {
      console.error("Failed to update server URL:", err);
      errorMessage = err.message || "Failed to update server URL";
    } finally {
      updatingServerUrl = false;
    }
  }

  async function saveSettings() {
    try {
      loading = true;
      errorMessage = "";
      saveMessage = "";

      const token = localStorage.getItem("auth_token");
      const response = await fetch(`${API_BASE_URL}/api/plex/settings`, {
        method: "PUT",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify(settings)
      });

      if (!response.ok) {
        const text = await response.text();
        if (text) {
          const error = JSON.parse(text);
          throw new Error(error.error || "Failed to save settings");
        }
        throw new Error("Failed to save settings");
      }

      const text = await response.text();
      if (text) {
        const data = JSON.parse(text);
        settings = data.settings;
      }

      saveMessage = "Settings saved successfully";
      setTimeout(() => {
        saveMessage = "";
        settingsExpanded = false;
      }, 2000);
    } catch (err) {
      console.error("Failed to save Plex settings:", err);
      errorMessage = err.message;
    } finally {
      loading = false;
    }
  }
</script>

<div>
  <h3>Plex Media Server</h3>

  {#if errorMessage}
    <div class="alert alert--error">{errorMessage}</div>
  {/if}

  {#if saveMessage}
    <div class="alert alert--success">{saveMessage}</div>
  {/if}

  {#if status.connected}
    <div class="status-card status-card--success connection-status">
      <span class="status-card__icon">✓</span>
      <div class="status-info">
        <div class="status-card__title">Connected to Plex</div>
        <div class="status-card__text">
          Server: {status.server_name} • Username: {status.plex_username}
        </div>
      </div>
      <button class="btn-danger" on:click={disconnect}>
        Disconnect
      </button>
    </div>

    <!-- Server URL Override -->
    <div class="whoop-settings-panel" style="margin-top: 1rem;">
      <h4>Server Connection</h4>
      <p style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 0.5rem;">
        Current server URL: <code style="background: var(--bg-tertiary); padding: 2px 6px; border-radius: 4px;">{status.server_url}</code>
      </p>

      {#if serverUrlMessage}
        <div class="alert alert--success" style="margin-bottom: 1rem;">{serverUrlMessage}</div>
      {/if}

      <p style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 1rem;">
        If the auto-detected URL doesn't work, manually specify your server URL below:
      </p>

      <div class="form-group">
        <label for="custom-server-url">Custom Server URL:</label>
        <input
          id="custom-server-url"
          type="text"
          bind:value={customServerUrl}
          placeholder="http://192.168.1.100:32400 or http://193.237.209.39:32400"
          style="width: 100%; max-width: 500px;"
        />
        <small style="display: block; margin-top: 0.25rem; color: var(--text-secondary);">
          Use your local IP (192.168.x.x) or public IP address with port 32400
        </small>
      </div>

      <button class="btn-primary" on:click={updateServerUrl} disabled={updatingServerUrl || !customServerUrl.trim()}>
        {updatingServerUrl ? "Updating..." : "Update Server URL"}
      </button>
    </div>

    <!-- Notification Settings Panel -->
    {#if settingsExpanded}
      <div class="whoop-settings-panel">
        <h4>Notification Settings</h4>
        <p style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 1rem;">
          All notifications are <strong>disabled by default</strong>. Choose which types of content updates you want to be notified about.
        </p>

        <label class="checkbox-label">
          <input type="checkbox" bind:checked={settings.new_episode_notifications_enabled} />
          <span>Enable new episode notifications</span>
        </label>

        <label class="checkbox-label">
          <input type="checkbox" bind:checked={settings.new_season_notifications_enabled} />
          <span>Enable new season notifications</span>
        </label>

        <label class="checkbox-label">
          <input type="checkbox" bind:checked={settings.new_movie_notifications_enabled} />
          <span>Enable new movie notifications</span>
        </label>

        {#if settings.new_episode_notifications_enabled || settings.new_season_notifications_enabled || settings.new_movie_notifications_enabled}
          <div class="form-group" style="margin-top: 1rem;">
            <label for="plex-check-frequency">Check frequency (minutes):</label>
            <input
              id="plex-check-frequency"
              type="number"
              bind:value={settings.check_frequency_minutes}
              min="5"
              max="120"
              step="5"
            />
          </div>

          <div class="form-group">
            <label for="plex-quiet-start">Quiet hours start:</label>
            <input
              id="plex-quiet-start"
              type="time"
              bind:value={settings.quiet_hours_start}
            />
          </div>

          <div class="form-group">
            <label for="plex-quiet-end">Quiet hours end:</label>
            <input
              id="plex-quiet-end"
              type="time"
              bind:value={settings.quiet_hours_end}
            />
          </div>
        {/if}

        <button class="btn-primary" on:click={saveSettings} disabled={loading}>
          {loading ? "Saving..." : "Save Settings"}
        </button>
      </div>
    {:else}
      <button class="btn-primary whoop-configure-btn" on:click={() => settingsExpanded = true}>
        Configure Notifications
      </button>
    {/if}

  {:else if pinCode && polling}
    <div class="auth-flow">
      <div class="auth-instructions">
        <h4>Connect Plex</h4>
        <p>Enter this PIN on Plex:</p>
        <code class="user-code">{pinCode}</code>
        <p style="margin-top: 1rem;">
          A popup window should have opened. If not,
          <a href={authUrl} target="_blank" rel="noopener noreferrer" class="verification-link">
            click here to open Plex authentication
          </a>.
        </p>
        <p class="auth-waiting">Waiting for authorization...</p>
      </div>
      <button class="btn-secondary" on:click={cancelConnection}>Cancel</button>
    </div>

  {:else}
    <div class="connection-status disconnected">
      <span class="status-icon">○</span>
      <div class="status-info">
        <div class="status-label">Not connected</div>
        <div class="status-detail">
          Connect your Plex Media Server to get viewing history insights and receive notifications about new content.
          <br />
          <small class="mode-notice">Available in Personal Mode only</small>
        </div>
      </div>
      <button class="btn-info" on:click={startConnection} disabled={loading || connecting}>
        {connecting ? "Connecting..." : "Connect Plex"}
      </button>
    </div>
  {/if}
</div>

<style>
  h3 {
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: 1rem;
    color: var(--text-primary);
  }

  h4 {
    margin-bottom: 1rem;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .alert {
    padding: 1rem;
    border-radius: 6px;
    margin-bottom: 1rem;
    font-size: 0.875rem;
  }

  .alert--error {
    background: var(--danger-100);
    border: 1px solid var(--danger-300);
    color: var(--danger-700);
  }

  .alert--success {
    background: var(--success-100);
    border: 1px solid var(--success-300);
    color: var(--success-700);
  }

  .connection-status {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .status-info {
    flex: 1;
  }

  .status-label {
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.25rem;
  }

  .status-detail {
    font-size: 0.875rem;
    color: var(--text-secondary);
    line-height: 1.5;
  }

  .status-icon {
    font-size: 1.5rem;
    color: var(--text-secondary);
  }

  .disconnected {
    padding: 1.5rem;
    background: var(--bg-secondary);
    border: 1px solid var(--border-primary);
    border-radius: 8px;
  }

  .mode-notice {
    color: var(--text-tertiary);
    font-style: italic;
  }

  .auth-flow {
    padding: 1.5rem;
    background: var(--bg-secondary);
    border: 1px solid var(--border-primary);
    border-radius: 8px;
  }

  .auth-instructions h4 {
    margin-bottom: 1rem;
  }

  .auth-instructions p {
    margin: 0.75rem 0;
    line-height: 1.5;
    color: var(--text-primary);
  }

  .verification-link {
    color: var(--info-500);
    text-decoration: underline;
    font-weight: 500;
  }

  .user-code {
    display: inline-block;
    background: var(--bg-tertiary);
    padding: 0.5rem 1rem;
    border-radius: 4px;
    font-family: monospace;
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: 0.2em;
    margin: 0.5rem 0;
  }

  .auth-waiting {
    margin-top: 1rem;
    font-style: italic;
    color: var(--text-secondary);
  }

  .whoop-settings-panel {
    margin-top: 1rem;
    padding: 1.5rem;
    background: var(--bg-primary);
    border: 1px solid var(--border-primary);
    border-radius: 8px;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
    cursor: pointer;
    color: var(--text-primary);
  }

  .checkbox-label input[type="checkbox"] {
    width: 18px;
    height: 18px;
    cursor: pointer;
  }

  .checkbox-label span {
    user-select: none;
  }

  .form-group {
    margin-bottom: 0.75rem;
  }

  .form-group label {
    display: block;
    margin-bottom: 0.25rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-secondary);
  }

  .form-group input[type="number"],
  .form-group input[type="time"] {
    width: 100%;
    max-width: 200px;
    padding: 0.5rem;
    border: 1px solid var(--border-secondary);
    border-radius: 4px;
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 0.875rem;
  }

  .whoop-configure-btn {
    margin-top: 1rem;
  }

  /* Use global styles from PersonalActions.svelte:
     - .status-card, .status-card--success from utilities.css
     - .btn-info, .btn-danger, .btn-primary, .btn-secondary from buttons.css
  */
</style>
