<script>
  import { onMount } from "svelte";
  import { login } from "../lib/api.js";

  export let onLogin;

  let username = "";
  let password = "";
  let error = "";
  let loading = false;

  async function handleLogin(e) {
    e.preventDefault();
    error = "";
    loading = true;

    try {
      const data = await login(username, password);

      // Store token and user info
      localStorage.setItem("auth_token", data.token);
      localStorage.setItem("user", JSON.stringify(data.user));

      // Call parent callback
      onLogin(data.token, data.user);
    } catch (err) {
      error = err.message || "Login failed";
      loading = false;
    }
  }

  onMount(() => {
    // Clear any existing auth on mount
    username = "";
    password = "";
  });
</script>

<div class="login-container">
  <div class="login-box">
    <div class="login-header">
      <h1>THEO</h1>
      <p>Personal AI Assistant</p>
    </div>

    <form on:submit={handleLogin}>
      <div class="form-group">
        <label for="username">Username</label>
        <input
          id="username"
          type="text"
          bind:value={username}
          placeholder="Enter username"
          disabled={loading}
          autocomplete="username"
          required
        />
      </div>

      <div class="form-group">
        <label for="password">Password</label>
        <input
          id="password"
          type="password"
          bind:value={password}
          placeholder="Enter password"
          disabled={loading}
          autocomplete="current-password"
          required
        />
      </div>

      {#if error}
        <div class="error-message">
          {error}
        </div>
      {/if}

      <button type="submit" class="btn-login" disabled={loading}>
        {loading ? "Logging in..." : "Login"}
      </button>
    </form>

    <div class="login-footer">
      <p class="hint">Default: username <strong>admin</strong>, password <strong>admin</strong></p>
      <p class="hint-secondary">Change your password after logging in for the first time</p>
    </div>
  </div>
</div>

<style>
  .login-container {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: var(--space-4);
  }

  .login-box {
    background: white;
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-xl);
    padding: var(--space-8);
    width: 100%;
    max-width: 420px;
  }

  .login-header {
    text-align: center;
    margin-bottom: var(--space-6);
  }

  .login-header h1 {
    font-size: var(--font-size-3xl);
    font-weight: 700;
    color: var(--gray-900);
    margin: 0 0 var(--space-2) 0;
  }

  .login-header p {
    font-size: var(--font-size-base);
    color: var(--gray-600);
    margin: 0;
  }

  .form-group {
    margin-bottom: var(--space-4);
  }

  .form-group label {
    display: block;
    font-size: var(--font-size-sm);
    font-weight: 600;
    color: var(--gray-700);
    margin-bottom: var(--space-2);
  }

  .form-group input {
    width: 100%;
    padding: var(--space-3);
    border: 1px solid var(--gray-300);
    border-radius: var(--radius-md);
    font-size: var(--font-size-base);
    transition: border-color 0.2s, box-shadow 0.2s;
  }

  .form-group input:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
  }

  .form-group input:disabled {
    background-color: var(--gray-100);
    cursor: not-allowed;
  }

  .error-message {
    padding: var(--space-3);
    background: #fee;
    border: 1px solid #fcc;
    border-radius: var(--radius-md);
    color: #c33;
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-4);
  }

  .btn-login {
    width: 100%;
    padding: var(--space-3);
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    border-radius: var(--radius-md);
    font-size: var(--font-size-base);
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
  }

  .btn-login:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
  }

  .btn-login:active:not(:disabled) {
    transform: translateY(0);
  }

  .btn-login:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .login-footer {
    margin-top: var(--space-6);
    padding-top: var(--space-4);
    border-top: 1px solid var(--gray-200);
    text-align: center;
  }

  .hint {
    font-size: var(--font-size-sm);
    color: var(--gray-600);
    margin: 0 0 var(--space-2) 0;
  }

  .hint-secondary {
    font-size: var(--font-size-xs);
    color: var(--gray-500);
    margin: 0;
  }

  .hint strong {
    color: var(--gray-700);
    font-weight: 600;
  }

  @media (max-width: 768px) {
    .login-box {
      padding: var(--space-6);
    }

    .login-header h1 {
      font-size: var(--font-size-2xl);
    }
  }
</style>
