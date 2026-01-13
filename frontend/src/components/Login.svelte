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
      <img
        src="/logo-primary.png"
        alt="THEO"
        class="login-logo"
      />
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
          on:keydown={(e) => e.key === 'Enter' && handleLogin(e)}
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
      <p class="hint-secondary">Multi-Modal Artificial Intelligence Project</p><p></p>
      <a
        href="https://github.com/dannxevans/theo"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="View THEO on GitHub"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="currentColor"
          style="vertical-align: middle;"
        >
          <path d="M12 0.5C5.37 0.5 0 5.87 0 12.5c0 5.29 3.438 9.773 8.205 11.364.6.113.82-.26.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.387-1.333-1.757-1.333-1.757-1.09-.745.083-.73.083-.73 1.205.085 1.84 1.237 1.84 1.237 1.07 1.835 2.807 1.305 3.492.998.108-.776.418-1.305.762-1.605-2.665-.303-5.466-1.332-5.466-5.93 0-1.31.468-2.382 1.235-3.222-.124-.303-.535-1.523.117-3.176 0 0 1.008-.322 3.3 1.23a11.5 11.5 0 0 1 3.003-.404c1.02.005 2.047.138 3.003.404 2.29-1.552 3.296-1.23 3.296-1.23.653 1.653.242 2.873.118 3.176.77.84 1.233 1.912 1.233 3.222 0 4.61-2.807 5.624-5.48 5.92.43.37.823 1.096.823 2.21 0 1.595-.015 2.88-.015 3.27 0 .32.218.694.825.576C20.565 22.27 24 17.787 24 12.5 24 5.87 18.63 0.5 12 0.5z"/>
        </svg>
      </a>
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
    max-width: 400px;
  }

  .login-header {
    text-align: center;
    margin-bottom: var(--space-6);
  }

  .login-logo {
    text-align: center;
    height: 60px;
    width: auto;
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
    box-sizing: border-box;
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

  .hint-secondary {
    font-size: var(--font-size-xs);
    color: var(--gray-500);
    margin: 0;
  }

  @media (max-width: 768px) {
    .login-box {
      padding: var(--space-6);
    }
  }
</style>
