<script>
  import { onMount } from "svelte";
  import { createApiKey, listApiKeys, revokeApiKey } from "../../lib/api";

  let keys = [];
  let loading = true;
  let error = null;

  // Create form
  let newKeyName = "";
  let newKeyExpiration = null;
  let creating = false;

  // One-time display modal
  let showKeyModal = false;
  let newlyCreatedKey = null;
  let keyCopied = false;
  let keyConfirmed = false;

  onMount(async () => {
    await loadKeys();
  });

  async function loadKeys() {
    loading = true;
    error = null;
    try {
      keys = await listApiKeys();
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  async function handleCreateKey() {
    if (!newKeyName.trim()) {
      error = "Please enter a key name";
      return;
    }

    creating = true;
    error = null;

    try {
      const result = await createApiKey(newKeyName, newKeyExpiration);
      newlyCreatedKey = result;
      showKeyModal = true;
      keyCopied = false;
      keyConfirmed = false;
      newKeyName = "";
      newKeyExpiration = null;
      await loadKeys();
    } catch (err) {
      error = err.message;
    } finally {
      creating = false;
    }
  }

  function copyToClipboard() {
    if (newlyCreatedKey && newlyCreatedKey.key) {
      navigator.clipboard.writeText(newlyCreatedKey.key);
      keyCopied = true;
    }
  }

  function closeModal() {
    if (!keyConfirmed) {
      if (!confirm("Have you saved this key? It will never be shown again.")) {
        return;
      }
    }
    showKeyModal = false;
    newlyCreatedKey = null;
  }

  async function handleRevokeKey(keyId, keyName) {
    if (!confirm(`Revoke API key "${keyName}"? This cannot be undone and will immediately invalidate the key.`)) {
      return;
    }

    error = null;
    try {
      await revokeApiKey(keyId);
      await loadKeys();
    } catch (err) {
      error = err.message;
    }
  }

  function formatDate(dateString) {
    if (!dateString) return "Never";
    const date = new Date(dateString);
    return date.toLocaleDateString() + " " + date.toLocaleTimeString();
  }

  function isExpired(expiresAt) {
    if (!expiresAt) return false;
    return new Date(expiresAt) < new Date();
  }

  function getStatusBadge(key) {
    if (key.is_revoked) {
      return { text: "Revoked", class: "status-revoked" };
    }
    if (isExpired(key.expires_at)) {
      return { text: "Expired", class: "status-expired" };
    }
    return { text: "Active", class: "status-active" };
  }
</script>

<div class="tab-panel">
  <h2>API Keys</h2>
  <p class="subtitle">
    Create API keys for programmatic access to THEO via Siri Shortcuts, iOS automation, and external tools.
  </p>

  <!-- Error Display -->
  {#if error}
    <div class="error-message">{error}</div>
  {/if}

  <!-- Create API Key Section -->
  <div class="section">
    <h3>Generate New API Key</h3>
    <p class="hint">
      API keys provide programmatic access to THEO. They will only be displayed once upon creation.
    </p>

    <div class="form-group">
      <label for="key-name">Key Name</label>
      <input
        id="key-name"
        type="text"
        bind:value={newKeyName}
        disabled={creating}
        placeholder="e.g., My iPhone, Siri Shortcuts, Home Automation"
        maxlength="100"
      />
      <small>A descriptive name to help you identify this key</small>
    </div>

    <div class="form-group">
      <label for="key-expiration">Expiration (Optional)</label>
      <select id="key-expiration" bind:value={newKeyExpiration} disabled={creating}>
        <option value={null}>Never expires</option>
        <option value={30}>30 days</option>
        <option value={90}>90 days</option>
        <option value={180}>180 days</option>
        <option value={365}>1 year</option>
      </select>
      <small>Keys can be manually revoked at any time</small>
    </div>

    <button
      class="btn-primary"
      on:click={handleCreateKey}
      disabled={creating || !newKeyName.trim()}
    >
      {creating ? "Generating..." : "Generate API Key"}
    </button>

    <div class="security-warning">
      <strong>Security Warning:</strong> API keys provide full access to your account.
      Treat them like passwords and never share them publicly. Store them securely.
    </div>
  </div>

  <!-- API Keys List -->
  <div class="section">
    <h3>Your API Keys</h3>

    {#if loading}
      <p class="loading">Loading API keys...</p>
    {:else if keys.length === 0}
      <p class="empty-state">
        No API keys yet. Create one above to get started with programmatic access.
      </p>
    {:else}
      <div class="keys-table-container">
        <table class="keys-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Created</th>
              <th>Last Used</th>
              <th>Expires</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each keys as key (key.id)}
              <tr class={key.is_revoked ? "revoked-row" : ""}>
                <td class="key-name">{key.name || "Untitled"}</td>
                <td>
                  <span class="status-badge {getStatusBadge(key).class}">
                    {getStatusBadge(key).text}
                  </span>
                </td>
                <td class="date-cell">{formatDate(key.created_at)}</td>
                <td class="date-cell">{formatDate(key.last_used_at)}</td>
                <td class="date-cell">
                  {#if key.expires_at}
                    {formatDate(key.expires_at)}
                    {#if isExpired(key.expires_at)}
                      <span class="expired-indicator"> (Expired)</span>
                    {/if}
                  {:else}
                    Never
                  {/if}
                </td>
                <td>
                  {#if !key.is_revoked}
                    <button
                      class="btn-danger btn-small"
                      on:click={() => handleRevokeKey(key.id, key.name)}
                    >
                      Revoke
                    </button>
                  {:else}
                    <span class="revoked-label">—</span>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</div>

<!-- One-Time Key Display Modal -->
{#if showKeyModal && newlyCreatedKey}
  <div class="modal-overlay" on:click={closeModal}>
    <div class="modal-content" on:click|stopPropagation>
      <h2>API Key Created Successfully</h2>

      <div class="warning-box">
        <strong>⚠️ Important:</strong> This key will only be shown once.
        Copy it now and store it securely.
      </div>

      <div class="key-display-box">
        <code class="api-key-code">{newlyCreatedKey.key}</code>
        <button class="btn-copy" on:click={copyToClipboard}>
          {keyCopied ? "✓ Copied!" : "Copy to Clipboard"}
        </button>
      </div>

      <div class="key-info">
        <p><strong>Name:</strong> {newlyCreatedKey.name}</p>
        <p><strong>Created:</strong> {formatDate(newlyCreatedKey.created_at)}</p>
        {#if newlyCreatedKey.expires_at}
          <p><strong>Expires:</strong> {formatDate(newlyCreatedKey.expires_at)}</p>
        {:else}
          <p><strong>Expires:</strong> Never</p>
        {/if}
      </div>

      <div class="confirmation-group">
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={keyConfirmed} />
          I have saved this key securely
        </label>
      </div>

      <button
        class="btn-primary btn-large"
        on:click={closeModal}
        disabled={!keyConfirmed}
      >
        {keyConfirmed ? "Close" : "Check the box above to continue"}
      </button>
    </div>
  </div>
{/if}

<style>
  .security-warning {
    margin-top: 1rem;
    padding: 1rem;
    background: #fff3cd;
    border: 1px solid #ffc107;
    border-radius: 4px;
    color: #856404;
    font-size: 0.9rem;
  }

  .keys-table-container {
    overflow-x: auto;
    margin-top: 1rem;
  }

  .keys-table {
    width: 100%;
    border-collapse: collapse;
    background: white;
    border-radius: 8px;
    overflow: hidden;
  }

  .keys-table thead {
    background: #f8f9fa;
  }

  .keys-table th {
    text-align: left;
    padding: 0.75rem 1rem;
    font-weight: 600;
    color: #495057;
    font-size: 0.9rem;
    border-bottom: 2px solid #dee2e6;
  }

  .keys-table td {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #dee2e6;
  }

  .keys-table tr:hover:not(.revoked-row) {
    background: #f8f9fa;
  }

  .revoked-row {
    opacity: 0.6;
    background: #f8f9fa;
  }

  .key-name {
    font-weight: 500;
  }

  .date-cell {
    font-size: 0.85rem;
    color: #6c757d;
  }

  .status-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
  }

  .status-active {
    background: #d4edda;
    color: #155724;
  }

  .status-expired {
    background: #f8d7da;
    color: #721c24;
  }

  .status-revoked {
    background: #e2e3e5;
    color: #383d41;
  }

  .expired-indicator {
    color: #dc3545;
    font-size: 0.85rem;
  }

  .revoked-label {
    color: #6c757d;
  }

  .empty-state {
    text-align: center;
    padding: 2rem;
    color: #6c757d;
    font-style: italic;
  }

  .loading {
    text-align: center;
    padding: 1rem;
    color: #6c757d;
  }

  /* Modal Styles */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal-content {
    background: white;
    padding: 2rem;
    border-radius: 12px;
    max-width: 600px;
    width: 90%;
    max-height: 90vh;
    overflow-y: auto;
  }

  .modal-content h2 {
    margin-top: 0;
    color: #28a745;
  }

  .warning-box {
    background: #fff3cd;
    border: 1px solid #ffc107;
    padding: 1rem;
    border-radius: 6px;
    margin: 1rem 0;
    color: #856404;
  }

  .key-display-box {
    background: #f8f9fa;
    border: 2px solid #007bff;
    padding: 1.5rem;
    border-radius: 8px;
    margin: 1.5rem 0;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .api-key-code {
    font-family: 'Monaco', 'Courier New', monospace;
    font-size: 0.9rem;
    word-break: break-all;
    background: white;
    padding: 1rem;
    border-radius: 4px;
    border: 1px solid #dee2e6;
    color: #007bff;
  }

  .btn-copy {
    background: #007bff;
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 500;
  }

  .btn-copy:hover {
    background: #0056b3;
  }

  .key-info {
    margin: 1rem 0;
    padding: 1rem;
    background: #f8f9fa;
    border-radius: 6px;
  }

  .key-info p {
    margin: 0.5rem 0;
  }

  .confirmation-group {
    margin: 1.5rem 0;
    padding: 1rem;
    background: #e7f3ff;
    border-radius: 6px;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    font-weight: 500;
  }

  .checkbox-label input[type="checkbox"] {
    width: 18px;
    height: 18px;
    cursor: pointer;
  }

  .btn-large {
    width: 100%;
    padding: 0.75rem;
    font-size: 1rem;
  }

  .btn-small {
    padding: 0.25rem 0.75rem;
    font-size: 0.85rem;
  }
</style>
