<script>
  import { onMount } from "svelte";
  import { changePassword, getUserPreference, setUserPreference } from "../../lib/api";

  let passwordForm = {
    current: "",
    new: "",
    confirm: ""
  };
  let passwordError = null;
  let passwordSuccess = null;
  let changingPassword = false;

  let sessionTimeoutHours = 8;
  let sessionTimeoutStatus = null;
  let loadingTimeout = true;

  onMount(async () => {
    // Load session timeout from backend
    try {
      const value = await getUserPreference("session_timeout");
      if (value) {
        sessionTimeoutHours = parseInt(value);
      } else {
        // Fallback to localStorage for migration
        const localValue = localStorage.getItem("theo.sessionTimeout");
        if (localValue) {
          sessionTimeoutHours = parseInt(localValue);
        }
      }
    } catch (err) {
      console.warn("Failed to load session timeout from backend:", err);
      // Fallback to localStorage
      const localValue = localStorage.getItem("theo.sessionTimeout");
      if (localValue) {
        sessionTimeoutHours = parseInt(localValue);
      }
    } finally {
      loadingTimeout = false;
    }
  });

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

  async function saveSessionTimeout() {
    sessionTimeoutStatus = null;

    // Validation
    if (!sessionTimeoutHours || sessionTimeoutHours < 1 || sessionTimeoutHours > 168) {
      sessionTimeoutStatus = "Please enter a timeout between 1 and 168 hours";
      return;
    }

    try {
      // Save to backend
      await setUserPreference("session_timeout", sessionTimeoutHours.toString());

      // Also save to localStorage for backward compatibility with frontend timeout
      localStorage.setItem("theo.sessionTimeout", sessionTimeoutHours.toString());

      sessionTimeoutStatus = `Session timeout set to ${sessionTimeoutHours} hours. This will take effect immediately for backend session validation.`;
    } catch (err) {
      sessionTimeoutStatus = `Error saving session timeout: ${err.message}`;
    }

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
  /* All styles imported from global CSS:
     - .tab-panel from settings.css
     - .section from settings.css
     - .form-group from forms.css
     - .success-message from forms.css
     - .error-message from forms.css
     - .hint from forms.css
  */
</style>
