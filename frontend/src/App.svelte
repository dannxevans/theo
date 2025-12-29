<script>
  import { onMount } from "svelte";
  import Chat from "./components/Chat.svelte";
  import Settings from "./components/Settings.svelte";
  import Login from "./components/Login.svelte";
  import { getSessions, deleteSessionApi, verifySession, logout, getUserMode, setUserMode, getWorkSubtabConfig } from "./lib/api.js";

  let isAuthenticated = false;
  let currentUser = null;
  let showSettings = false;
  let currentMode = "personal"; // "work" or "personal"
  let activeWorkSubtab = "conversation"; // "conversation" | "email" | "code"

  // Dropdown state
  let modeDropdownOpen = false;
  let settingsDropdownOpen = false;

  // Mobile sidebar toggle state
  let sidebarOpen = false;
  $: {
    if (typeof document !== "undefined") {
      document.body.classList.toggle("no-scroll", sidebarOpen);
    }
  }

  // Close dropdowns when clicking outside
  function handleClickOutside(event) {
    const target = event.target;
    if (!target.closest('.dropdown')) {
      modeDropdownOpen = false;
      settingsDropdownOpen = false;
    }
  }

  // Session timeout management
  let sessionTimeoutId = null;
  const DEFAULT_TIMEOUT_HOURS = 8;

  function startSessionTimeout() {
    // Clear any existing timeout
    if (sessionTimeoutId) {
      clearTimeout(sessionTimeoutId);
    }

    // Get timeout setting from localStorage (in hours)
    const timeoutHours = parseInt(localStorage.getItem("theo.sessionTimeout")) || DEFAULT_TIMEOUT_HOURS;
    const timeoutMs = timeoutHours * 60 * 60 * 1000;

    sessionTimeoutId = setTimeout(async () => {
      alert(`Your session has expired after ${timeoutHours} hours of inactivity. Please log in again.`);
      await handleLogout();
    }, timeoutMs);
  }

  function resetSessionTimeout() {
    if (isAuthenticated) {
      startSessionTimeout();
    }
  }

  // Reset timeout on user activity
  function handleUserActivity() {
    resetSessionTimeout();
  }

  onMount(() => {
    document.addEventListener('click', handleClickOutside);
    document.addEventListener('mousemove', handleUserActivity);
    document.addEventListener('keypress', handleUserActivity);

    // Start timeout if authenticated
    if (isAuthenticated) {
      startSessionTimeout();
    }

    return () => {
      document.removeEventListener('click', handleClickOutside);
      document.removeEventListener('mousemove', handleUserActivity);
      document.removeEventListener('keypress', handleUserActivity);
      if (sessionTimeoutId) {
        clearTimeout(sessionTimeoutId);
      }
    };
  });
  function openSidebar() {
    sidebarOpen = true;
  }
  function closeSidebar() {
    sidebarOpen = false;
  }

  // Theme loading function (for new multi-theme system)
  function loadTheme() {
    if (typeof document === "undefined") return;

    // Get theme from localStorage (set by ThemeSettings.svelte)
    const savedTheme = localStorage.getItem("theme") || "light";

    // Apply theme using the new system
    if (savedTheme === "dark") {
      document.documentElement.classList.add("dark");
      document.documentElement.removeAttribute("data-theme");
    } else if (savedTheme === "light") {
      document.documentElement.classList.remove("dark");
      document.documentElement.removeAttribute("data-theme");
    } else {
      // Custom themes (cyberpunk, nature, corporate)
      document.documentElement.classList.remove("dark");
      document.documentElement.setAttribute("data-theme", savedTheme);
    }
  }

  let sessions = [];
  let activeSessionId = null;
  const MAX_SESSIONS = 20;

  const SESSION_STORAGE_KEY = "theo.activeSessionId";

  let confirmDeleteId = null;

  let sessionQuery = "";

  function generateUUID() {
    if (crypto && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
    // Fallback RFC4122 v4
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => {
      const r = Math.random() * 16 | 0;
      const v = c === "x" ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

onMount(async () => {
  // Load theme preference (new multi-theme system)
  loadTheme();

  // Check authentication first
  try {
    const result = await verifySession();
    if (result.valid) {
      isAuthenticated = true;
      currentUser = result.user;
      await loadSessions();
      await loadUserMode();
    }
  } catch (err) {
    console.error("Session verification failed", err);
    isAuthenticated = false;
  }

  // Listen for session title generation events
  window.addEventListener("sessionTitleGenerated", async (e) => {
    const { sessionId, title } = e.detail;
    // Refresh sessions list to show new title
    try {
      const updatedSessions = await getSessions();
      sessions = updatedSessions.filter(hasContent);
    } catch (err) {
      console.error("Failed to refresh sessions after title generation:", err);
    }
  });

  // Listen for work subtab changes from Chat component
  window.addEventListener("workSubtabChanged", (e) => {
    activeWorkSubtab = e.detail.subtab;
  });
});

async function loadSessions() {
  try {
    const stored = localStorage.getItem(SESSION_STORAGE_KEY);
    if (stored) {
      activeSessionId = stored;
    }

    sessions = await getSessions();
    sessions = sessions.filter(hasContent);

    if (!activeSessionId || !sessions.find(s => s.id === activeSessionId)) {
      activeSessionId = sessions.length
        ? sessions[0].id
        : generateUUID();
    }

    localStorage.setItem(SESSION_STORAGE_KEY, activeSessionId);
  } catch (err) {
    console.error("Failed to load sessions", err);
    sessions = [];
  }
}

async function loadUserMode() {
  try {
    const modeConfig = await getUserMode();
    currentMode = modeConfig.active_mode || "personal";
  } catch (err) {
    console.error("Failed to load user mode", err);
    currentMode = "personal";
  }
}

async function setMode(mode) {
  if (mode === currentMode) return; // Already in this mode

  const previousMode = currentMode;

  try {
    // Notify old chat BEFORE switching
    window.dispatchEvent(new CustomEvent("modeSwitching", {
      detail: { fromMode: previousMode, toMode: mode }
    }));

    await setUserMode(mode);
    currentMode = mode;

    // Brief delay for notification to render
    await new Promise(resolve => setTimeout(resolve, 500));

    // Create a new session when switching modes to separate contexts
    newSession();

    // Reload sessions (backend auto-filters by new mode)
    loadSessions();

    // Load last active subtab from localStorage when switching to work mode
    if (mode === "work") {
      const savedSubtab = localStorage.getItem("theo.activeWorkSubtab");
      if (savedSubtab && ["conversation", "email", "code"].includes(savedSubtab)) {
        activeWorkSubtab = savedSubtab;
      }
    }
  } catch (err) {
    console.error("Failed to switch mode", err);
  }
}

function handleLogin(token, user) {
  isAuthenticated = true;
  currentUser = user;
  loadSessions();
  loadUserMode();

  // Start session timeout
  startSessionTimeout();

  // Load last active work subtab
  const savedSubtab = localStorage.getItem("theo.activeWorkSubtab");
  if (savedSubtab && ["conversation", "email", "code"].includes(savedSubtab)) {
    activeWorkSubtab = savedSubtab;
  }
}

async function handleLogout() {
  try {
    await logout();
  } catch (err) {
    console.error("Logout failed", err);
  } finally {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("user");
    isAuthenticated = false;
    currentUser = null;
    sessions = [];
  }
}

  function selectSession(id) {
    const session = sessions.find(s => s.id === id);

    // Check mode mismatch - select the session but it will be locked
    if (session && session.mode && session.mode !== currentMode) {
      // Still select it, but Chat.svelte will show it as locked
      activeSessionId = id;
      localStorage.setItem(SESSION_STORAGE_KEY, id);
      sidebarOpen = false;
      // Chat will detect mode mismatch and disable input
      return;
    }

    // Normal selection
    activeSessionId = id;
    localStorage.setItem(SESSION_STORAGE_KEY, id);
    sidebarOpen = false;
  }

  function newSession() {
    const id = generateUUID();
    activeSessionId = id;
    localStorage.setItem(SESSION_STORAGE_KEY, id);
    // Optimistically add to top of list
    sessions = [{ id, title: "New chat", summary: "" }, ...sessions].slice(0, MAX_SESSIONS);
  }

  async function deleteSession(id) {
    try {
      await deleteSessionApi(id);

      sessions = sessions.filter(s => s.id !== id);

      if (activeSessionId === id) {
        if (sessions.length) {
          activeSessionId = sessions[0].id;
        } else {
          activeSessionId = generateUUID();
          sessions = [{ id: activeSessionId, title: "New chat", summary: "" }];
        }
        localStorage.setItem(SESSION_STORAGE_KEY, activeSessionId);
      }

      confirmDeleteId = null;
    } catch (err) {
      console.error("Failed to delete session", err);
      confirmDeleteId = null;
    }
  }

  function sessionLabel(session) {
    if (session.title && session.title.trim()) {
      return session.title.slice(0, 60);
    }
    if (session.summary && session.summary.trim()) {
      return session.summary.slice(0, 60);
    }
    return "New chat";
  }

  function sessionMatches(session) {
    if (!sessionQuery.trim()) return true;
    const q = sessionQuery.toLowerCase();
    return sessionLabel(session).toLowerCase().includes(q);
  }

  function hasContent(session) {
    return (
      (session.title && session.title.trim()) ||
      (session.summary && session.summary.trim())
    );
  }

  function dayGroup(dateStr) {
    const d = new Date(dateStr);
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);

    const sameDay = (a, b) =>
      a.getFullYear() === b.getFullYear() &&
      a.getMonth() === b.getMonth() &&
      a.getDate() === b.getDate();

    if (sameDay(d, today)) return "Today";
    if (sameDay(d, yesterday)) return "Yesterday";
    return "Earlier";
  }
</script>

<main class="app-layout app-root">
  {#if !isAuthenticated}
    <Login onLogin={handleLogin} />
  {:else}
  <header class="header">
    <div class="header-left">
      <button class="hamburger" on:click={openSidebar}>☰</button>
      <img
        src="/logo.svg"
        alt="THEO"
        class="logo"
        on:click={() => { showSettings = false; }}
        style="cursor: pointer;"
        title="Go to Chat"
      />
    </div>

    <div class="header-right">
      <div class="dropdown" class:open={modeDropdownOpen}>
        <button
          class="btn-pill btn-mode"
          class:mode-work={currentMode === "work"}
          class:mode-personal={currentMode === "personal"}
          on:click={() => { modeDropdownOpen = !modeDropdownOpen; }}
        >
          {currentMode === "work" ? "Work Mode" : "Personal Mode"}
        </button>
        {#if modeDropdownOpen}
          <div class="dropdown-content">
            <button
              class="dropdown-item"
              class:active={currentMode === "personal"}
              on:click={() => { setMode("personal"); modeDropdownOpen = false; }}
            >
              🏠 Personal
            </button>
            <button
              class="dropdown-item"
              class:active={currentMode === "work"}
              on:click={() => { setMode("work"); modeDropdownOpen = false; }}
            >
              💼 Work
            </button>
          </div>
        {/if}
      </div>

      <button
        class="btn-pill"
        class:active={!showSettings}
        on:click={() => { showSettings = false; }}
      >
        Home
      </button>

      <div class="dropdown" class:open={settingsDropdownOpen}>
        <button class="btn-pill" on:click={() => { settingsDropdownOpen = !settingsDropdownOpen; }}>
          Menu
        </button>
        {#if settingsDropdownOpen}
          <div class="dropdown-content">
            <button
              class="dropdown-item"
              on:click={() => { showSettings = true; settingsDropdownOpen = false; }}
            >
              Settings
            </button>
            <button
              class="dropdown-item"
              on:click={() => { handleLogout(); settingsDropdownOpen = false; }}
            >
              Logout
            </button>
          </div>
        {/if}
      </div>
    </div>
  </header>

<div class="app-body">

  <div class="shell layout-shell">
    <!-- Sidebar placeholder (sessions will move here later) -->
    <aside class="sidebar" class:open={sidebarOpen}>
      <div class="sidebar-title">Sessions</div>
      <button class="btn-pill new-session" on:click={newSession}>
        + New chat
      </button>

      <input
        class="session-search"
        type="text"
        placeholder="Search chats"
        bind:value={sessionQuery}
      />

      {#each ["Today", "Yesterday", "Earlier"] as group}
        {#if sessions.some(s => dayGroup(s.updated_at) === group && sessionMatches(s))}
          <div class="session-group">{group}</div>
        {/if}

        {#each sessions
          .filter(hasContent)
          .filter(s => dayGroup(s.updated_at) === group)
          .filter(sessionMatches)
          .slice(0, MAX_SESSIONS) as s}

          <div class="session-row" class:active={s.id === activeSessionId}>
            <button
              class="session-item"
              on:click={() => selectSession(s.id)}
            >
              {sessionLabel(s)}
            </button>

            {#if confirmDeleteId === s.id}
              <div class="confirm">
                <button class="danger" on:click={() => deleteSession(s.id)}>Delete</button>
                <button on:click={() => confirmDeleteId = null}>Cancel</button>
              </div>
            {:else}
              <button
                class="delete-btn"
                title="Delete chat"
                on:click={() => confirmDeleteId = s.id}
              >
                ×
              </button>
            {/if}
          </div>
        {/each}
      {/each}
    </aside>
    {#if sidebarOpen}
      <div class="sidebar-backdrop" on:click={closeSidebar}></div>
    {/if}

    <section class="main">
      <div class="chat-main">
        {#if showSettings}
          <Settings />
        {:else}
          <Chat
            sessionId={activeSessionId}
            currentMode={currentMode}
            sessionMode={sessions.find(s => s.id === activeSessionId)?.mode}
            activeWorkSubtab={activeWorkSubtab}
          />
        {/if}
      </div>
    </section>
  </div>
  </div>
  {/if}
</main>
