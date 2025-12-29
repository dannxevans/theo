<script>
  import { onMount } from "svelte";

  const themes = [
    { id: "light", name: "Light", description: "Clean and bright interface" },
    { id: "dark", name: "Dark", description: "Easy on the eyes" },
    { id: "cyberpunk", name: "Cyberpunk", description: "Neon and high contrast" },
    { id: "nature", name: "Nature", description: "Earthy greens and natural tones" },
    { id: "corporate", name: "Corporate", description: "Professional blues and grays" }
  ];

  let currentTheme = "light";
  let previewTheme = null;

  onMount(() => {
    // Get current theme from document or localStorage
    const savedTheme = localStorage.getItem("theme") || "light";
    currentTheme = savedTheme;

    // Apply saved theme
    if (savedTheme === "dark") {
      document.documentElement.classList.add("dark");
      document.documentElement.removeAttribute("data-theme");
    } else if (savedTheme === "light") {
      document.documentElement.classList.remove("dark");
      document.documentElement.removeAttribute("data-theme");
    } else {
      document.documentElement.classList.remove("dark");
      document.documentElement.setAttribute("data-theme", savedTheme);
    }
  });

  function applyTheme(themeId) {
    currentTheme = themeId;
    localStorage.setItem("theme", themeId);

    if (themeId === "dark") {
      document.documentElement.classList.add("dark");
      document.documentElement.removeAttribute("data-theme");
    } else if (themeId === "light") {
      document.documentElement.classList.remove("dark");
      document.documentElement.removeAttribute("data-theme");
    } else {
      document.documentElement.classList.remove("dark");
      document.documentElement.setAttribute("data-theme", themeId);
    }
  }

  function startPreview(themeId) {
    previewTheme = themeId;

    if (themeId === "dark") {
      document.documentElement.classList.add("dark");
      document.documentElement.removeAttribute("data-theme");
    } else if (themeId === "light") {
      document.documentElement.classList.remove("dark");
      document.documentElement.removeAttribute("data-theme");
    } else {
      document.documentElement.classList.remove("dark");
      document.documentElement.setAttribute("data-theme", themeId);
    }
  }

  function endPreview() {
    if (previewTheme) {
      previewTheme = null;
      // Restore current theme
      applyTheme(currentTheme);
    }
  }
</script>

<div class="tab-panel">
  <h2>Theme Settings</h2>
  <p class="subtitle">Choose your preferred color scheme and visual style.</p>

  {#if previewTheme}
    <div class="alert alert--info preview-banner">
      <span class="alert__icon">👁️</span>
      <div class="alert__content">
        <div class="alert__title">Previewing: {themes.find(t => t.id === previewTheme)?.name}</div>
        <div class="alert__message">
          This is a live preview. Click "Apply Theme" to save or "Cancel" to return.
        </div>
      </div>
    </div>
  {/if}

  <div class="current-theme-section">
    <h3>Current Theme</h3>
    <div class="current-theme-card">
      <div class="theme-info">
        <h4>{themes.find(t => t.id === currentTheme)?.name}</h4>
        <p>{themes.find(t => t.id === currentTheme)?.description}</p>
      </div>
      <div class="theme-preview-mini">
        <div class="preview-colors">
          <span class="color-dot" style="background: var(--theo-gradient);"></span>
          <span class="color-dot" style="background: var(--bg-tertiary);"></span>
          <span class="color-dot" style="background: var(--text-primary);"></span>
        </div>
      </div>
    </div>
  </div>

  <div class="themes-grid">
    {#each themes as theme}
      <div
        class="theme-card"
        class:active={currentTheme === theme.id}
        class:previewing={previewTheme === theme.id}
      >
        <div class="theme-preview" data-theme={theme.id}>
          <div class="preview-header">
            <div class="preview-logo"></div>
            <div class="preview-badge">AI</div>
          </div>
          <div class="preview-content">
            <div class="preview-card">
              <div class="preview-card-header">
                <span class="preview-status status-success">Success</span>
                <span class="preview-status status-info">Info</span>
              </div>
              <div class="preview-text">Sample text content</div>
            </div>
            <div class="preview-button-group">
              <div class="preview-button preview-button-primary">Primary</div>
              <div class="preview-button preview-button-secondary">Secondary</div>
            </div>
          </div>
        </div>

        <div class="theme-details">
          <h4>{theme.name}</h4>
          <p>{theme.description}</p>

          <div class="theme-actions">
            {#if previewTheme === theme.id}
              <button class="btn-success" on:click={() => applyTheme(theme.id)}>
                ✓ Apply Theme
              </button>
              <button class="btn-secondary" on:click={endPreview}>
                Cancel
              </button>
            {:else if currentTheme === theme.id}
              <div class="active-badge">
                <span class="status-badge status-badge--success">Active</span>
              </div>
            {:else}
              <button class="btn-primary" on:click={() => startPreview(theme.id)}>
                Preview
              </button>
              <button class="btn-secondary" on:click={() => applyTheme(theme.id)}>
                Apply
              </button>
            {/if}
          </div>
        </div>
      </div>
    {/each}
  </div>

  <div class="theme-tips">
    <h3>💡 Theme Tips</h3>
    <ul>
      <li><strong>Light:</strong> Best for well-lit environments and daytime use</li>
      <li><strong>Dark:</strong> Reduces eye strain in low-light conditions</li>
      <li><strong>Cyberpunk:</strong> High contrast with neon accents for a futuristic feel</li>
      <li><strong>Nature:</strong> Calming earth tones inspired by natural environments</li>
      <li><strong>Corporate:</strong> Professional appearance suitable for business settings</li>
    </ul>
  </div>
</div>

<style>
  .current-theme-section {
    margin-bottom: var(--space-6);
  }

  .current-theme-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-5);
    background: var(--bg-tertiary);
    border: 2px solid var(--border-focus);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-md);
  }

  .theme-info h4 {
    margin: 0 0 var(--space-1) 0;
    font-size: var(--font-size-lg);
    color: var(--text-primary);
  }

  .theme-info p {
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
  }

  .preview-colors {
    display: flex;
    gap: var(--space-2);
  }

  .color-dot {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: 2px solid var(--border-primary);
    box-shadow: var(--shadow-sm);
  }

  .preview-banner {
    margin-bottom: var(--space-6);
  }

  .themes-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: var(--space-6);
    margin-bottom: var(--space-8);
  }

  .theme-card {
    border: 2px solid var(--border-primary);
    border-radius: var(--radius-lg);
    overflow: hidden;
    transition: all 0.3s;
    background: var(--bg-tertiary);
  }

  .theme-card:hover {
    box-shadow: var(--shadow-lg);
    transform: translateY(-2px);
  }

  .theme-card.active {
    border-color: var(--success-500);
    box-shadow: 0 0 0 3px var(--success-100);
  }

  .theme-card.previewing {
    border-color: var(--info-500);
    box-shadow: 0 0 0 3px var(--info-100);
  }

  .theme-preview {
    height: 200px;
    padding: var(--space-4);
    position: relative;
    overflow: hidden;
  }

  /* Theme-specific preview backgrounds */
  .theme-preview[data-theme="light"] {
    background: #ffffff;
    color: #1f2937;
  }

  .theme-preview[data-theme="dark"] {
    background: #1a1d2e;
    color: #e5e7eb;
  }

  .theme-preview[data-theme="cyberpunk"] {
    background: #0a0e27;
    color: #e0f2fe;
  }

  .theme-preview[data-theme="nature"] {
    background: #f8faf7;
    color: #1b4332;
  }

  .theme-preview[data-theme="corporate"] {
    background: #ffffff;
    color: #0f172a;
  }

  .preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-3);
  }

  .preview-logo {
    width: 40px;
    height: 40px;
    border-radius: var(--radius-md);
  }

  .theme-preview[data-theme="light"] .preview-logo {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  }

  .theme-preview[data-theme="dark"] .preview-logo {
    background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
  }

  .theme-preview[data-theme="cyberpunk"] .preview-logo {
    background: linear-gradient(135deg, #00f0ff 0%, #ff00ff 100%);
  }

  .theme-preview[data-theme="nature"] .preview-logo {
    background: linear-gradient(135deg, #2d6a4f 0%, #52b788 100%);
  }

  .theme-preview[data-theme="corporate"] .preview-logo {
    background: linear-gradient(135deg, #1e3a8a 0%, #3730a3 100%);
  }

  .preview-badge {
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 10px;
    font-weight: 600;
  }

  .theme-preview[data-theme="light"] .preview-badge {
    background: #dbeafe;
    color: #1e40af;
  }

  .theme-preview[data-theme="dark"] .preview-badge {
    background: #1e3a5f;
    color: #93c5fd;
  }

  .theme-preview[data-theme="cyberpunk"] .preview-badge {
    background: #0a1f2a;
    color: #00d9ff;
  }

  .theme-preview[data-theme="nature"] .preview-badge {
    background: #d8f3dc;
    color: #1b4332;
  }

  .theme-preview[data-theme="corporate"] .preview-badge {
    background: #dbeafe;
    color: #1e40af;
  }

  .preview-content {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .preview-card {
    padding: var(--space-3);
    border-radius: var(--radius-sm);
    font-size: 11px;
  }

  .theme-preview[data-theme="light"] .preview-card {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
  }

  .theme-preview[data-theme="dark"] .preview-card {
    background: #242940;
    border: 1px solid #2e3451;
  }

  .theme-preview[data-theme="cyberpunk"] .preview-card {
    background: #151937;
    border: 1px solid #2d3459;
  }

  .theme-preview[data-theme="nature"] .preview-card {
    background: #e8f3ea;
    border: 1px solid #b7e4c7;
  }

  .theme-preview[data-theme="corporate"] .preview-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
  }

  .preview-card-header {
    display: flex;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }

  .preview-status {
    padding: 2px 6px;
    border-radius: 10px;
    font-size: 9px;
    font-weight: 600;
  }

  .preview-status.status-success {
    background: #dcfce7;
    color: #166534;
  }

  .theme-preview[data-theme="cyberpunk"] .preview-status.status-success {
    background: #0d1f1a;
    color: #00ff9f;
  }

  .preview-status.status-info {
    background: #dbeafe;
    color: #1e40af;
  }

  .theme-preview[data-theme="cyberpunk"] .preview-status.status-info {
    background: #0a1f2a;
    color: #00d9ff;
  }

  .preview-text {
    opacity: 0.7;
    line-height: 1.4;
  }

  .preview-button-group {
    display: flex;
    gap: var(--space-2);
  }

  .preview-button {
    flex: 1;
    padding: 6px;
    border-radius: 4px;
    text-align: center;
    font-size: 10px;
    font-weight: 600;
  }

  .preview-button-primary {
    color: white;
  }

  .theme-preview[data-theme="light"] .preview-button-primary {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  }

  .theme-preview[data-theme="dark"] .preview-button-primary {
    background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
  }

  .theme-preview[data-theme="cyberpunk"] .preview-button-primary {
    background: linear-gradient(135deg, #00f0ff 0%, #ff00ff 100%);
  }

  .theme-preview[data-theme="nature"] .preview-button-primary {
    background: linear-gradient(135deg, #2d6a4f 0%, #52b788 100%);
  }

  .theme-preview[data-theme="corporate"] .preview-button-primary {
    background: linear-gradient(135deg, #1e3a8a 0%, #3730a3 100%);
  }

  .preview-button-secondary {
    border: 1px solid;
  }

  .theme-preview[data-theme="light"] .preview-button-secondary {
    border-color: #d1d5db;
    background: #ffffff;
    color: #374151;
  }

  .theme-preview[data-theme="dark"] .preview-button-secondary {
    border-color: #2e3451;
    background: #1a1d2e;
    color: #e5e7eb;
  }

  .theme-preview[data-theme="cyberpunk"] .preview-button-secondary {
    border-color: #252b4f;
    background: #0a0e27;
    color: #e0f2fe;
  }

  .theme-preview[data-theme="nature"] .preview-button-secondary {
    border-color: #c7e9c0;
    background: #f8faf7;
    color: #1b4332;
  }

  .theme-preview[data-theme="corporate"] .preview-button-secondary {
    border-color: #cbd5e1;
    background: #ffffff;
    color: #0f172a;
  }

  .theme-details {
    padding: var(--space-4);
  }

  .theme-details h4 {
    margin: 0 0 var(--space-1) 0;
    font-size: var(--font-size-base);
    color: var(--text-primary);
  }

  .theme-details p {
    margin: 0 0 var(--space-4) 0;
    font-size: var(--font-size-sm);
    color: var(--text-secondary);
  }

  .theme-actions {
    display: flex;
    gap: var(--space-2);
  }

  .theme-actions button {
    flex: 1;
  }

  .active-badge {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-2);
  }

  .theme-tips {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
  }

  .theme-tips h3 {
    margin-top: 0;
    margin-bottom: var(--space-3);
    color: var(--text-primary);
  }

  .theme-tips ul {
    margin: 0;
    padding-left: var(--space-6);
  }

  .theme-tips li {
    margin-bottom: var(--space-2);
    color: var(--text-secondary);
    line-height: 1.6;
  }

  .theme-tips li strong {
    color: var(--text-primary);
  }

  /* Use global utilities:
     - .tab-panel from settings.css
     - .subtitle from global
     - .btn-primary, .btn-secondary, .btn-success from buttons.css
     - .status-badge--success from utilities.css
     - .alert variants from utilities.css
  */
</style>
