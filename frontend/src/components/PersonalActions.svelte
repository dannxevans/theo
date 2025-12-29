<script>
  import { onMount } from "svelte";
  import {
    startM365Auth,
    pollM365Auth,
    getM365Status,
    disconnectM365,
    getPendingConfirmations,
    approveConfirmation,
    rejectConfirmation,
  } from "../lib/api.js";

  let m365Connected = false;
  let m365Status = null;
  let authInProgress = false;
  let deviceCode = null;
  let userCode = null;
  let verificationUrl = null;
  let pollingInterval = null;

  let pendingConfirmations = [];
  let confirmationsLoading = false;

  onMount(async () => {
    await checkM365Status();
    await loadPendingConfirmations();

    // Poll for confirmations every 10 seconds
    const confirmationInterval = setInterval(loadPendingConfirmations, 10000);

    return () => {
      if (pollingInterval) clearInterval(pollingInterval);
      clearInterval(confirmationInterval);
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
  <h2>Personal Assistant</h2>

  <!-- M365 Connection Section -->
  <div class="section">
    <h3>Microsoft 365 Connection</h3>

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
        <button class="btn-disconnect" on:click={handleDisconnect}>
          Disconnect
        </button>
      </div>
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
        <button class="btn-cancel" on:click={cancelAuth}>Cancel</button>
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
        <button class="btn-connect" on:click={handleConnect}>
          Connect Microsoft 365
        </button>
      </div>
    {/if}
  </div>

  <!-- Pending Actions Section -->
  {#if m365Connected}
    <div class="section">
      <h3>Pending Confirmations</h3>

      {#if pendingConfirmations.length === 0}
        <p class="no-confirmations">No pending actions</p>
      {:else}
        <div class="confirmations-list">
          {#each pendingConfirmations as confirmation}
            <div class="confirmation-card">
              <div class="confirmation-header">
                <span class="confirmation-type">{confirmation.category || confirmation.action_type}</span>
                <span class="confirmation-expires">
                  Expires in {formatExpiresAt(confirmation.expires_at)}
                </span>
              </div>

              <div class="confirmation-message">
                {confirmation.message}
              </div>

              <div class="confirmation-actions">
                <button
                  class="btn-approve"
                  on:click={() => handleApprove(confirmation.confirmation_id)}
                >
                  ✓ Approve
                </button>
                <button
                  class="btn-reject"
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

  .section {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }

  .connection-status {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .status-info {
    flex: 1;
  }

  .btn-connect,
  .btn-disconnect,
  .btn-cancel {
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font-weight: 500;
    cursor: pointer;
    border: none;
    transition: all 0.2s;
  }

  .btn-connect {
    background: #3b82f6;
    color: white;
  }

  .btn-connect:hover {
    background: #2563eb;
  }

  .btn-disconnect {
    background: #ef4444;
    color: white;
  }

  .btn-disconnect:hover {
    background: #dc2626;
  }

  .btn-cancel {
    background: #6b7280;
    color: white;
  }

  .btn-cancel:hover {
    background: #4b5563;
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
    color: #3b82f6;
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

  .no-confirmations {
    color: var(--text-secondary);
    font-style: italic;
    padding: 1rem;
    text-align: center;
  }

  .confirmations-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .confirmation-card {
    border: 1px solid var(--border-primary);
    border-radius: 6px;
    padding: 1rem;
    background: var(--bg-secondary);
  }

  .confirmation-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
  }

  .confirmation-type {
    background: #3b82f6;
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
  }

  .confirmation-expires {
    font-size: 0.875rem;
    color: var(--text-secondary);
  }

  .confirmation-message {
    margin-bottom: 1rem;
    color: var(--text-primary);
    font-size: 1rem;
    line-height: 1.5;
  }

  .confirmation-actions {
    display: flex;
    gap: 0.75rem;
  }

  .btn-approve,
  .btn-reject {
    flex: 1;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font-weight: 500;
    cursor: pointer;
    border: none;
    transition: all 0.2s;
  }

  .btn-approve {
    background: #10b981;
    color: white;
  }

  .btn-approve:hover {
    background: #059669;
  }

  .btn-reject {
    background: #ef4444;
    color: white;
  }

  .btn-reject:hover {
    background: #dc2626;
  }
</style>
