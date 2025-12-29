<script>
  import { changePassword } from "../../lib/api";

  let passwordForm = {
    current: "",
    new: "",
    confirm: ""
  };
  let passwordError = null;
  let passwordSuccess = null;
  let changingPassword = false;

  let sessionTimeoutHours = parseInt(localStorage.getItem("theo.sessionTimeout")) || 8;
  let sessionTimeoutStatus = null;

  async function handleChangePassword() {
    passwordError = null;
    passwordSuccess = null;

    // Validation
    if (!passwordForm.current || !passwordForm.new || !passwordForm.confirm) {
      passwordError = "All fields are required";
      return;
    }

    if (passwordForm.new !== passwordForm.confirm) {
      passwordError = "New passwords do not match";
      return;
    }

    if (passwordForm.new.length < 4) {
      passwordError = "Password must be at least 4 characters";
      return;
    }

    changingPassword = true;

    try {
      await changePassword(passwordForm.current, passwordForm.new);
      passwordSuccess = "Password changed successfully!";
      passwordForm = { current: "", new: "", confirm: "" };
    } catch (err) {
      passwordError = err.message || "Failed to change password";
    } finally {
      changingPassword = false;
    }
  }

  function saveSessionTimeout() {
    sessionTimeoutStatus = null;

    // Validation
    if (!sessionTimeoutHours || sessionTimeoutHours < 1 || sessionTimeoutHours > 168) {
      sessionTimeoutStatus = "Please enter a timeout between 1 and 168 hours";
      return;
    }

    // Save to localStorage
    localStorage.setItem("theo.sessionTimeout", sessionTimeoutHours.toString());
    sessionTimeoutStatus = `Session timeout set to ${sessionTimeoutHours} hours. The new timeout will take effect on your next login.`;

    setTimeout(() => {
      sessionTimeoutStatus = null;
    }, 5000);
  }
</script>

<div class="tab-panel">
  <h2>Account & Security</h2>
  <p class="subtitle">Manage your password and security settings.</p>

  <!-- Change Password Section -->
  <div class="section">
    <h3>Change Password</h3>

    {#if passwordError}
      <div class="error-message">{passwordError}</div>
    {/if}

    {#if passwordSuccess}
      <div class="success-message">{passwordSuccess}</div>
    {/if}

    <div class="form-group">
      <label for="current-password">Current Password</label>
      <input
        id="current-password"
        type="password"
        bind:value={passwordForm.current}
        disabled={changingPassword}
        placeholder="Enter current password"
      />
    </div>

    <div class="form-group">
      <label for="new-password">New Password</label>
      <input
        id="new-password"
        type="password"
        bind:value={passwordForm.new}
        disabled={changingPassword}
        placeholder="Enter new password (min 4 characters)"
      />
    </div>

    <div class="form-group">
      <label for="confirm-password">Confirm New Password</label>
      <input
        id="confirm-password"
        type="password"
        bind:value={passwordForm.confirm}
        disabled={changingPassword}
        placeholder="Confirm new password"
      />
    </div>

    <button
      class="btn-primary"
      on:click={handleChangePassword}
      disabled={changingPassword}
    >
      {changingPassword ? "Changing Password..." : "Change Password"}
    </button>
  </div>

  <!-- Session Timeout Section -->
  <div class="section">
    <h3>Session Timeout</h3>
    <p class="hint">Configure automatic logout after a period of inactivity</p>

    <div class="form-group">
      <label for="session-timeout">Timeout Duration (hours)</label>
      <input
        id="session-timeout"
        type="number"
        min="1"
        max="168"
        bind:value={sessionTimeoutHours}
        placeholder="8"
      />
      <small>Default: 8 hours. Maximum: 168 hours (1 week)</small>
    </div>

    <button
      class="btn-primary"
      on:click={saveSessionTimeout}
    >
      Save Timeout Setting
    </button>

    {#if sessionTimeoutStatus}
      <div class="success-message">{sessionTimeoutStatus}</div>
    {/if}
  </div>
</div>

<style>
  .tab-panel {
    max-width: 900px;
    margin: 0 auto;
  }

  h2 {
    margin-top: 0;
    margin-bottom: var(--space-2);
  }

  .subtitle {
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-4);
  }

  .section {
    margin-bottom: var(--space-6);
    padding: var(--space-5);
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
  }

  .section:last-child {
    margin-bottom: 0;
  }

  .form-group {
    margin-bottom: var(--space-4);
  }

  .form-group label {
    display: block;
    width: auto;
    margin-bottom: var(--space-1);
    font-weight: 600;
    color: var(--text-primary);
  }

  .form-group input[type="password"],
  .form-group input[type="number"] {
    width: 100%;
    padding: var(--space-2);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-sm);
    font-family: inherit;
    background: var(--bg-primary);
    color: var(--text-primary);
  }

  .form-group input[type="password"]:focus,
  .form-group input[type="number"]:focus {
    outline: none;
    border-color: var(--border-focus);
  }

  .form-group small {
    display: block;
    color: var(--text-tertiary);
    font-size: var(--font-size-xs);
    margin-top: var(--space-1);
  }

  .hint {
    color: var(--text-tertiary);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-4);
  }

  .error-message {
    padding: var(--space-3);
    background: var(--error-50);
    border: 1px solid var(--error-200);
    border-radius: var(--radius-md);
    color: var(--error-700);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-4);
  }

  .success-message {
    padding: var(--space-3);
    background: #d1fae5;
    border: 1px solid #6ee7b7;
    border-radius: var(--radius-md);
    color: #065f46;
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-4);
  }
</style>
