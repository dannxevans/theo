<script>
  import { onMount } from "svelte";
  import {
    startM365Auth,
    pollM365Auth,
    getM365Status,
    disconnectM365,
    getM365OAuthConfig,
    saveM365OAuthConfig,
    startWhoopAuth,
    completeWhoopAuth,
    getWhoopStatus,
    disconnectWhoop,
    getWhoopSettings,
    updateWhoopSettings,
    getWhoopOAuthConfig,
    saveWhoopOAuthConfig,
    getPendingConfirmations,
    approveConfirmation,
    rejectConfirmation,
  } from "../lib/api.js";
  import ProactiveSettings from "./settings/ProactiveSettings.svelte";
  import PlexSettings from "./settings/PlexSettings.svelte";

  let m365Connected = false;
  let m365Status = null;
  let authInProgress = false;
  let deviceCode = null;
  let userCode = null;
  let verificationUrl = null;
  let pollingInterval = null;

  // WHOOP Integration State
  let whoopConnected = false;
  let whoopStatus = null;
  let whoopAuthInProgress = false;
  let whoopSettingsExpanded = false;
  let whoopSettings = {
    sleep_notifications_enabled: true,
    workout_notifications_enabled: true,
    stress_notifications_enabled: true,
    stress_notification_time: "14:00",
    check_frequency_minutes: 30,
    quiet_hours_enabled: false,
    quiet_hours_start: "22:00",
    quiet_hours_end: "07:00"
  };
  let whoopOAuthConfig = {
    client_id: '',
    client_secret: '',
    redirect_uri: 'http://localhost:1066/api/whoop/auth/callback',
    configured: false
  };
  let whoopOAuthExpanded = false;
  let whoopStatusCheckInterval = null;

  // M365 settings panel state
  let m365SettingsExpanded = false;
  let m365OAuthConfig = {
    client_id: '',
    tenant_id: '',
    configured: false
  };
  let m365OAuthExpanded = false;
  let proactiveSettingsComponent;

  let pendingConfirmations = [];
  let confirmationsLoading = false;

  onMount(async () => {
    await checkM365Status();
    await checkWhoopStatus();
    if (whoopConnected) {
      await loadWhoopSettings();
    }
    await loadWhoopOAuthConfig();
    await loadM365OAuthConfig();
    await loadPendingConfirmations();

    // Poll for confirmations every 10 seconds
    const confirmationInterval = setInterval(loadPendingConfirmations, 10000);

    // Listen for WHOOP OAuth completion messages
    window.addEventListener('message', handleWhoopAuthMessage);

    return () => {
      if (pollingInterval) clearInterval(pollingInterval);
      if (whoopStatusCheckInterval) clearInterval(whoopStatusCheckInterval);
      clearInterval(confirmationInterval);
      window.removeEventListener('message', handleWhoopAuthMessage);
    };
  });

  async function checkM365Status() {
    try {
      m365Status = await getM365Status();
      // Check both connected and is_valid (credentials might be marked invalid)
      m365Connected = m365Status.connected && m365Status.is_valid !== false;
    } catch (err) {
      console.error("Failed to check M365 status:", err);
      m365Connected = false;
    }
  }

  async function handleConnect() {
    try {
      authInProgress = true;
      const authData = await startM365Auth();

      if (authData.error) {
        throw new Error(authData.error + (authData.instructions ? "\n\n" + authData.instructions : ""));
      }

      deviceCode = authData.device_code;
      userCode = authData.user_code;
      verificationUrl = authData.verification_url;

      // Start polling for token
      pollingInterval = setInterval(async () => {
        try {
          const result = await pollM365Auth(deviceCode);
          if (result.status === "success") {
            // Success!
            clearInterval(pollingInterval);
            pollingInterval = null;
            authInProgress = false;
            deviceCode = null;
            userCode = null;
            verificationUrl = null;
            await checkM365Status();
          } else if (result.status === "pending") {
            // Still waiting
          } else if (result.status === "declined" || result.status === "failed") {
            // Error
            clearInterval(pollingInterval);
            pollingInterval = null;
            authInProgress = false;
            alert("Authentication failed: " + (result.error || result.message));
          }
        } catch (err) {
          console.error("Polling error:", err);
        }
      }, 5000); // Poll every 5 seconds
    } catch (err) {
      console.error("Failed to start M365 auth:", err);
      authInProgress = false;
      alert(err.message);
    }
  }

  async function handleDisconnect() {
    if (!confirm("Are you sure you want to disconnect Microsoft 365?")) {
      return;
    }

    try {
      await disconnectM365();
      m365Connected = false;
      m365Status = null;
    } catch (err) {
      console.error("Failed to disconnect M365:", err);
      alert("Failed to disconnect");
    }
  }

  function cancelAuth() {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
    authInProgress = false;
    deviceCode = null;
    userCode = null;
    verificationUrl = null;
  }

  // =============================
  // WHOOP Functions
  // =============================

  async function checkWhoopStatus() {
    try {
      whoopStatus = await getWhoopStatus();
      whoopConnected = whoopStatus.connected && whoopStatus.is_valid !== false;

      // Clear polling interval if connected (cleanup in case interval is still running)
      if (whoopConnected && whoopStatusCheckInterval) {
        clearInterval(whoopStatusCheckInterval);
        whoopStatusCheckInterval = null;
      }
    } catch (err) {
      console.error("Failed to check WHOOP status:", err);
      whoopConnected = false;
    }
  }

  async function loadWhoopSettings() {
    try {
      whoopSettings = await getWhoopSettings();
    } catch (err) {
      console.error("Failed to load WHOOP settings:", err);
    }
  }

  async function handleConnectWhoop() {
    try {
      whoopAuthInProgress = true;
      const result = await startWhoopAuth();

      if (result.error) {
        alert(`Failed to start WHOOP auth: ${result.error}`);
        whoopAuthInProgress = false;
        return;
      }

      // Open OAuth URL in popup
      const popup = window.open(
        result.authorization_url,
        "WHOOP Authorization",
        "width=600,height=700,scrollbars=yes"
      );

      if (!popup) {
        alert("Please allow popups for this site to connect WHOOP");
        whoopAuthInProgress = false;
        return;
      }

      // Start polling for status (fallback if message doesn't arrive)
      // Poll every 2 seconds during OAuth for responsive UX
      whoopStatusCheckInterval = setInterval(async () => {
        await checkWhoopStatus();
        if (whoopConnected) {
          clearInterval(whoopStatusCheckInterval);
          whoopStatusCheckInterval = null;
          whoopAuthInProgress = false;
          await loadWhoopSettings();
          if (popup && !popup.closed) {
            popup.close();
          }
        }
      }, 2000);

      // Stop polling after 5 minutes
      setTimeout(() => {
        if (whoopStatusCheckInterval) {
          clearInterval(whoopStatusCheckInterval);
          whoopStatusCheckInterval = null;
          whoopAuthInProgress = false;
        }
      }, 300000);

    } catch (err) {
      console.error("Failed to connect WHOOP:", err);
      alert(`Failed to connect WHOOP: ${err.message}`);
      whoopAuthInProgress = false;
    }
  }

  async function handleWhoopAuthMessage(event) {
    // Only accept messages from our OAuth callback
    if (event.data && event.data.type === 'whoop_auth_success') {
      try {
        // Complete auth by storing credentials
        await completeWhoopAuth(event.data.credentials);

        // Update status
        await checkWhoopStatus();
        await loadWhoopSettings();

        // Stop polling
        if (whoopStatusCheckInterval) {
          clearInterval(whoopStatusCheckInterval);
          whoopStatusCheckInterval = null;
        }

        whoopAuthInProgress = false;

      } catch (err) {
        console.error("Failed to complete WHOOP auth:", err);
        alert(`Failed to complete WHOOP auth: ${err.message}`);
        whoopAuthInProgress = false;
      }
    } else if (event.data && event.data.type === 'whoop_auth_error') {
      alert(`WHOOP authorization failed: ${event.data.error}`);
      whoopAuthInProgress = false;
      if (whoopStatusCheckInterval) {
        clearInterval(whoopStatusCheckInterval);
        whoopStatusCheckInterval = null;
      }
    }
  }

  async function handleDisconnectWhoop() {
    if (!confirm("Are you sure you want to disconnect WHOOP? This will stop all health notifications.")) {
      return;
    }

    try {
      await disconnectWhoop();
      whoopConnected = false;
      whoopStatus = null;
      whoopSettingsExpanded = false;
      // Refresh status to confirm disconnection
      await checkWhoopStatus();
    } catch (err) {
      console.error("Failed to disconnect WHOOP:", err);
      alert(`Failed to disconnect WHOOP: ${err.message}`);
    }
  }

  function cancelWhoopAuth() {
    if (whoopStatusCheckInterval) {
      clearInterval(whoopStatusCheckInterval);
      whoopStatusCheckInterval = null;
    }
    whoopAuthInProgress = false;
  }

  async function saveWhoopSettings() {
    try {
      await updateWhoopSettings(whoopSettings);
    } catch (err) {
      console.error("Failed to save WHOOP settings:", err);
      alert(`Failed to save settings: ${err.message}`);
    }
  }

  async function loadWhoopOAuthConfig() {
    try {
      const config = await getWhoopOAuthConfig();
      whoopOAuthConfig = {
        client_id: config.client_id || '',
        client_secret: '', // Never send back from server for security
        redirect_uri: config.redirect_uri || 'http://localhost:1066/api/whoop/auth/callback',
        configured: config.configured || false,
        has_client_secret: config.has_client_secret || false
      };
    } catch (err) {
      console.error("Failed to load WHOOP OAuth config:", err);
    }
  }

  async function loadM365OAuthConfig() {
    try {
      const config = await getM365OAuthConfig();
      m365OAuthConfig = {
        client_id: config.client_id || '',
        tenant_id: config.tenant_id || 'common',
        configured: config.configured || false
      };
    } catch (err) {
      console.error("Failed to load M365 OAuth config:", err);
    }
  }

  async function handleSaveM365OAuthConfig() {
    try {
      await saveM365OAuthConfig(m365OAuthConfig);
      alert("M365 OAuth configuration saved successfully!");
      await loadM365OAuthConfig(); // Reload to get updated status
    } catch (err) {
      console.error("Failed to save M365 OAuth config:", err);
      alert(`Failed to save M365 OAuth config: ${err.message}`);
    }
  }

  async function handleSaveWhoopOAuthConfig() {
    try {
      await saveWhoopOAuthConfig(whoopOAuthConfig);
      alert("WHOOP OAuth configuration saved successfully!");
      await loadWhoopOAuthConfig(); // Reload to get updated status
    } catch (err) {
      console.error("Failed to save WHOOP OAuth config:", err);
      alert(`Failed to save OAuth config: ${err.message}`);
    }
  }

  async function loadPendingConfirmations() {
    if (confirmationsLoading) return;

    try {
      confirmationsLoading = true;
      const result = await getPendingConfirmations();
      pendingConfirmations = result.confirmations || [];
    } catch (err) {
      console.error("Failed to load confirmations:", err);
    } finally {
      confirmationsLoading = false;
    }
  }

  async function handleApprove(confirmationId) {
    try {
      const result = await approveConfirmation(confirmationId);
      if (result.status === "approved") {
        alert("Action completed successfully!");
        await loadPendingConfirmations();
      } else {
        alert("Failed to approve: " + result.message);
      }
    } catch (err) {
      console.error("Failed to approve confirmation:", err);
      alert("Failed to approve action");
    }
  }

  async function handleReject(confirmationId) {
    const reason = prompt("Reason for rejection (optional):");

    try {
      await rejectConfirmation(confirmationId, reason);
      alert("Action rejected");
      await loadPendingConfirmations();
    } catch (err) {
      console.error("Failed to reject confirmation:", err);
      alert("Failed to reject action");
    }
  }

  function formatExpiresAt(isoString) {
    if (!isoString) return "";
    const date = new Date(isoString);
    const now = new Date();
    const diff = date - now;

    if (diff < 0) return "Expired";

    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    if (hours > 24) {
      return `${Math.floor(hours / 24)}d ${hours % 24}h`;
    } else if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else {
      return `${minutes}m`;
    }
  }
</script>

<div class="personal-actions">
  <h2>Integrations</h2>

  <!-- M365 Connection Section -->
  <div class="section">
    <h3>Microsoft 365 Connection</h3>

    <!-- OAuth Configuration (always visible) -->
    <div class="oauth-config-section">
      <div class="oauth-config-header" on:click={() => m365OAuthExpanded = !m365OAuthExpanded}>
        <h4>OAuth Configuration</h4>
        <span class="toggle-icon">{m365OAuthExpanded ? '▼' : '▶'}</span>
      </div>

      {#if m365OAuthExpanded}
        <div class="oauth-config-panel">
          <p class="oauth-help-text">
            Configure your Microsoft 365 OAuth credentials. Required to connect to M365.
            {#if m365OAuthConfig.configured}
              <span class="config-status config-status--ok">✓ Configured</span>
            {:else}
              <span class="config-status config-status--warning">⚠ Not configured</span>
            {/if}
          </p>

          <div class="form-group">
            <label for="m365-client-id">Client ID:</label>
            <input
              id="m365-client-id"
              type="text"
              bind:value={m365OAuthConfig.client_id}
              placeholder="Enter M365 Client ID"
            />
          </div>

          <div class="form-group">
            <label for="m365-tenant-id">Tenant ID:</label>
            <input
              id="m365-tenant-id"
              type="text"
              bind:value={m365OAuthConfig.tenant_id}
              placeholder="common (or your tenant ID)"
            />
            <p class="field-help-text">
              Use "common" for personal Microsoft accounts, or your specific tenant ID for organizational accounts.
            </p>
          </div>

          <button class="btn-primary" on:click={handleSaveM365OAuthConfig}>
            Save OAuth Configuration
          </button>
        </div>
      {/if}
    </div>

    {#if m365Connected}
      <div class="status-card status-card--success connection-status">
        <span class="status-card__icon">✓</span>
        <div class="status-info">
          <div class="status-card__title">Connected to Microsoft 365</div>
          {#if m365Status?.expires_at}
            <div class="status-card__text">
              Token expires: {new Date(m365Status.expires_at).toLocaleString()}
            </div>
          {/if}
        </div>
        <button class="btn-danger" on:click={handleDisconnect}>
          Disconnect
        </button>
      </div>

      <!-- M365 Proactive Notifications Panel -->
      {#if m365SettingsExpanded}
        <div class="whoop-settings-panel">
          <h4>Proactive Notifications</h4>
          <ProactiveSettings bind:this={proactiveSettingsComponent} hideActions={true} />
          <button class="btn-primary" on:click={async () => {
            if (proactiveSettingsComponent) {
              await proactiveSettingsComponent.saveSettings();
            }
            m365SettingsExpanded = false;
          }}>
            Save and Close
          </button>
        </div>
      {:else}
        <button class="btn-primary whoop-configure-btn" on:click={() => m365SettingsExpanded = true}>
          Configure Notifications
        </button>
      {/if}

    {:else if authInProgress}
      <div class="auth-flow">
        <div class="auth-instructions">
          <h4>Connect Microsoft 365</h4>
          <p>To connect your Microsoft 365 account:</p>
          <ol>
            <li>
              Go to:
              <a
                href={verificationUrl}
                target="_blank"
                rel="noopener noreferrer"
                class="verification-link"
              >
                {verificationUrl}
              </a>
            </li>
            <li>
              Enter this code: <code class="user-code">{userCode}</code>
            </li>
            <li>Sign in with your Microsoft account</li>
            <li>Return here after approving access</li>
          </ol>
          <p class="auth-waiting">Waiting for authorization...</p>
        </div>
        <button class="btn-secondary" on:click={cancelAuth}>Cancel</button>
      </div>
    {:else}
      <div class="connection-status disconnected">
        <span class="status-icon">○</span>
        <div class="status-info">
          <div class="status-label">Not connected</div>
          <div class="status-detail">
            Connect your Microsoft 365 account to access calendar and email
          </div>
        </div>
        <button class="btn-info" on:click={handleConnect}>
          Connect Microsoft 365
        </button>
      </div>
    {/if}
  </div>

  <!-- WHOOP Integration Section -->
  <div class="section">
    <h3>WHOOP Integration</h3>

    <!-- OAuth Configuration (always visible) -->
    <div class="oauth-config-section">
      <div class="oauth-config-header" on:click={() => whoopOAuthExpanded = !whoopOAuthExpanded}>
        <h4>OAuth Configuration</h4>
        <span class="toggle-icon">{whoopOAuthExpanded ? '▼' : '▶'}</span>
      </div>

      {#if whoopOAuthExpanded}
        <div class="oauth-config-panel">
          <p class="oauth-help-text">
            Configure your WHOOP OAuth credentials. Required to connect to WHOOP.
            {#if whoopOAuthConfig.configured}
              <span class="config-status config-status--ok">✓ Configured</span>
            {:else}
              <span class="config-status config-status--warning">⚠ Not configured</span>
            {/if}
          </p>

          <div class="form-group">
            <label for="whoop-client-id">Client ID:</label>
            <input
              id="whoop-client-id"
              type="text"
              bind:value={whoopOAuthConfig.client_id}
              placeholder="Enter WHOOP Client ID"
            />
          </div>

          <div class="form-group">
            <label for="whoop-client-secret">Client Secret:</label>
            <input
              id="whoop-client-secret"
              type="password"
              bind:value={whoopOAuthConfig.client_secret}
              placeholder={whoopOAuthConfig.has_client_secret ? "••••••••" : "Enter WHOOP Client Secret"}
            />
            {#if whoopOAuthConfig.has_client_secret}
              <small class="help-text">Leave blank to keep existing secret</small>
            {/if}
          </div>

          <div class="form-group">
            <label for="whoop-redirect-uri">Redirect URI:</label>
            <input
              id="whoop-redirect-uri"
              type="text"
              bind:value={whoopOAuthConfig.redirect_uri}
              placeholder="http://localhost:1066/api/whoop/auth/callback"
            />
          </div>

          <button class="btn-primary" on:click={handleSaveWhoopOAuthConfig}>
            Save OAuth Config
          </button>
        </div>
      {/if}
    </div>

    {#if whoopConnected}
      <div class="status-card status-card--success connection-status">
        <span class="status-card__icon">✓</span>
        <div class="status-info">
          <div class="status-card__title">Connected to WHOOP</div>
          {#if whoopStatus?.whoop_user_id}
            <div class="status-card__text">
              User ID: {whoopStatus.whoop_user_id}
            </div>
          {/if}
          {#if whoopStatus?.expires_at}
            <div class="status-card__text">
              Token expires: {new Date(whoopStatus.expires_at).toLocaleString()}
            </div>
          {/if}
        </div>
        <button class="btn-danger" on:click={handleDisconnectWhoop}>
          Disconnect
        </button>
      </div>

      <!-- WHOOP Settings Panel -->
      {#if whoopSettingsExpanded}
        <div class="whoop-settings-panel">
          <h4>Notification Settings</h4>

          <label class="checkbox-label">
            <input
              type="checkbox"
              bind:checked={whoopSettings.sleep_notifications_enabled}
              on:change={saveWhoopSettings}
            />
            <span>Enable post-sleep summaries</span>
          </label>

          <label class="checkbox-label">
            <input
              type="checkbox"
              bind:checked={whoopSettings.workout_notifications_enabled}
              on:change={saveWhoopSettings}
            />
            <span>Enable post-workout summaries</span>
          </label>

          <label class="checkbox-label">
            <input
              type="checkbox"
              bind:checked={whoopSettings.stress_notifications_enabled}
              on:change={saveWhoopSettings}
            />
            <span>Enable daily stress summaries</span>
          </label>

          {#if whoopSettings.stress_notifications_enabled}
            <div class="form-group indented">
              <label for="whoop-stress-time">Daily stress summary time:</label>
              <input
                id="whoop-stress-time"
                type="time"
                bind:value={whoopSettings.stress_notification_time}
                on:change={saveWhoopSettings}
              />
            </div>
          {/if}

          <div class="form-group">
            <label for="whoop-check-frequency">Check frequency (minutes):</label>
            <input
              id="whoop-check-frequency"
              type="number"
              min="1"
              max="120"
              bind:value={whoopSettings.check_frequency_minutes}
              on:change={saveWhoopSettings}
            />
          </div>

          <label class="checkbox-label">
            <input
              type="checkbox"
              bind:checked={whoopSettings.quiet_hours_enabled}
              on:change={saveWhoopSettings}
            />
            <span>Enable quiet hours</span>
          </label>

          {#if whoopSettings.quiet_hours_enabled}
            <div class="quiet-hours-group">
              <div class="form-group">
                <label for="whoop-quiet-start">Start:</label>
                <input
                  id="whoop-quiet-start"
                  type="time"
                  bind:value={whoopSettings.quiet_hours_start}
                  on:change={saveWhoopSettings}
                />
              </div>
              <div class="form-group">
                <label for="whoop-quiet-end">End:</label>
                <input
                  id="whoop-quiet-end"
                  type="time"
                  bind:value={whoopSettings.quiet_hours_end}
                  on:change={saveWhoopSettings}
                />
              </div>
            </div>
          {/if}

          <button class="btn-primary" on:click={() => whoopSettingsExpanded = false}>
            Close Settings
          </button>
        </div>
      {:else}
        <button class="btn-primary whoop-configure-btn" on:click={() => whoopSettingsExpanded = true}>
          Configure Notifications
        </button>
      {/if}

    {:else if whoopAuthInProgress}
      <div class="auth-flow">
        <div class="auth-instructions">
          <h4>Connecting to WHOOP</h4>
          <p>Please complete the authorization in the popup window.</p>
          <p class="auth-waiting">Waiting for authorization...</p>
        </div>
        <button class="btn-secondary" on:click={cancelWhoopAuth}>Cancel</button>
      </div>

    {:else}
      <div class="connection-status disconnected">
        <span class="status-icon">○</span>
        <div class="status-info">
          <div class="status-label">Not connected</div>
          <div class="status-detail">
            Connect your WHOOP account to receive personalized sleep and workout insights.
            <br />
            <small class="mode-notice">Available in Personal Mode only</small>
          </div>
        </div>
        <button class="btn-info" on:click={handleConnectWhoop}>
          Connect WHOOP
        </button>
      </div>
    {/if}
  </div>

  <!-- Plex Integration Section -->
  <div class="section">
    <PlexSettings />
  </div>

  <!-- Pending Actions Section -->
  {#if m365Connected}
    <div class="section">
      <h3>Pending Confirmations</h3>

      {#if pendingConfirmations.length === 0}
        <p class="empty-state">No pending actions</p>
      {:else}
        <div class="confirmations-list">
          {#each pendingConfirmations as confirmation}
            <div class="card">
              <div class="card__header">
                <span class="status-badge status-badge--info">{confirmation.category || confirmation.action_type}</span>
                <span class="confirmation-expires">
                  Expires in {formatExpiresAt(confirmation.expires_at)}
                </span>
              </div>

              <div class="card__body">
                {confirmation.message}
              </div>

              <div class="confirmation-actions">
                <button
                  class="btn-success"
                  on:click={() => handleApprove(confirmation.confirmation_id)}
                >
                  ✓ Approve
                </button>
                <button
                  class="btn-danger"
                  on:click={() => handleReject(confirmation.confirmation_id)}
                >
                  × Reject
                </button>
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .personal-actions {
    padding: 2rem;
    max-width: 800px;
    margin: 0 auto;
  }

  h2 {
    font-size: 1.75rem;
    font-weight: 600;
    margin-bottom: 2rem;
    color: var(--text-primary);
  }

  h3 {
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: 1rem;
    color: var(--text-primary);
  }

  /* Component-specific layout overrides */
  .connection-status {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .status-info {
    flex: 1;
  }

  .auth-flow {
    padding: 1rem;
  }

  .auth-instructions h4 {
    margin-bottom: 1rem;
    color: var(--text-primary);
  }

  .auth-instructions ol {
    margin: 1rem 0;
    padding-left: 1.5rem;
  }

  .auth-instructions li {
    margin-bottom: 0.75rem;
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
    background: var(--bg-secondary);
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-family: monospace;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: 0.1em;
  }

  .auth-waiting {
    margin-top: 1rem;
    font-style: italic;
    color: var(--text-secondary);
  }

  .confirmations-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .confirmation-expires {
    font-size: 0.875rem;
    color: var(--text-secondary);
  }

  .confirmation-actions {
    display: flex;
    gap: 0.75rem;
  }

  .confirmation-actions button {
    flex: 1;
  }

  /* WHOOP-specific styles */
  .whoop-settings-panel {
    margin-top: 1rem;
    padding: 1.5rem;
    background: var(--bg-primary);
    border: 1px solid var(--border-primary);
    border-radius: 8px;
  }

  .whoop-settings-panel h4 {
    margin-bottom: 1rem;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
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

  .quiet-hours-group {
    margin-left: 1.5rem;
    display: flex;
    gap: 1rem;
    margin-bottom: 0.75rem;
  }

  .form-group.indented {
    margin-left: 1.5rem;
  }

  .mode-notice {
    color: var(--text-tertiary);
    font-style: italic;
  }

  .whoop-configure-btn {
    margin-top: 1rem;
  }

  .oauth-config-section {
    margin-bottom: 1.5rem;
    padding: 1rem;
    background: var(--bg-secondary);
    border: 1px solid var(--border-secondary);
    border-radius: 6px;
  }

  .oauth-config-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    user-select: none;
  }

  .oauth-config-header:hover {
    opacity: 0.8;
  }

  .toggle-icon {
    font-size: 0.75rem;
    color: var(--text-secondary);
  }

  .oauth-config-panel {
    margin-top: 1rem;
  }

  .oauth-help-text {
    font-size: 0.875rem;
    color: var(--text-secondary);
    margin-bottom: 1rem;
    line-height: 1.5;
  }

  .config-status {
    display: inline-block;
    margin-left: 0.5rem;
    padding: 0.125rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .config-status--ok {
    background: var(--success-100);
    color: var(--success-700);
  }

  .config-status--warning {
    background: var(--warning-100);
    color: var(--warning-700);
  }

  .form-group input[type="text"],
  .form-group input[type="password"] {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid var(--border-secondary);
    border-radius: 4px;
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 0.875rem;
  }

  .help-text {
    display: block;
    margin-top: 0.25rem;
    font-size: 0.75rem;
    color: var(--text-tertiary);
    font-style: italic;
  }

  /* All other styles now imported from global CSS:
     - .section from settings.css
     - .status-card, .status-card--success from utilities.css
     - .card, .card__header, .card__body from utilities.css
     - .status-badge, .status-badge--info from utilities.css
     - .empty-state from utilities.css
     - .btn-info, .btn-danger, .btn-secondary, .btn-success from buttons.css
  */
</style>
