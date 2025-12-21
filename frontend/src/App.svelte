<svelte:head>
  <link rel="stylesheet" href="/style.css" />
</svelte:head>

<script>
  import { onMount } from "svelte";
  import Chat from "./components/Chat.svelte";
  import Providers from "./components/Providers.svelte";
  import Settings from "./components/Settings.svelte";
  import { getSessions, deleteSessionApi } from "./lib/api.js";

  let showProviders = false;
  let showSettings = false;

  let sessions = [];
  let activeSessionId = null;
  const MAX_SESSIONS = 20;

  const SESSION_STORAGE_KEY = "theo.activeSessionId";

  let confirmDeleteId = null;

  let sessionQuery = "";

onMount(async () => {
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
        : crypto.randomUUID();
    }

    localStorage.setItem(SESSION_STORAGE_KEY, activeSessionId);
  } catch (err) {
    console.error("Failed to load sessions", err);
    sessions = [];
  }
});

  function selectSession(id) {
    activeSessionId = id;
    localStorage.setItem(SESSION_STORAGE_KEY, id);
  }

  function newSession() {
    const id = crypto.randomUUID();
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
          activeSessionId = crypto.randomUUID();
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

<main class="app">
  <header class="header">
    <div class="header-left">
      <img
        src="/logo.svg"
        alt="THEO"
        class="logo"
      />
    </div>

    <div class="header-right">
      <button
        class="btn-pill"
        class:active={!showProviders && !showSettings}
        on:click={() => { showProviders = false; showSettings = false; }}
      >
        Chat
      </button>

      <button
        class="btn-pill"
        class:active={showProviders}
        on:click={() => { showProviders = true; showSettings = false; }}
      >
        Providers
      </button>

      <button
        class="btn-pill"
        class:active={showSettings}
        on:click={() => { showSettings = true; showProviders = false; }}
      >
        Settings
      </button>
    </div>
  </header>

  <div class="shell">
    <!-- Sidebar placeholder (sessions will move here later) -->
    <aside class="sidebar">
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

    <section class="main">
      {#if showProviders}
        <Providers />
      {:else if showSettings}
        <Settings />
      {:else}
        <Chat sessionId={activeSessionId} />
      {/if}
    </section>
  </div>
</main>

<style>
:global(html, body) {
  height: 100%;
  margin: 0;
}

.app {
  height: 100vh;
  display: flex;
  flex-direction: column;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

/* ---------- Header ---------- */

.header {
  flex-shrink: 0;
  height: 56px;
  padding: 0 1rem;
  border-bottom: 1px solid #ddd;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header h1 {
  margin: 0;
  font-size: 1.1rem;
}

.header-right {
  display: flex;
  gap: 0.5rem;
}

.header button {
  padding: 0.35rem 0.75rem;
  font-size: 0.85rem;
  border: 1px solid #ccc;
  background: #f5f5f5;
  cursor: pointer;
}

.header button.active {
  background: #e5e7eb;
  font-weight: 600;
}

/* ---------- Shell ---------- */

.shell {
  flex: 1;
  display: grid;
  grid-template-columns: 260px 1fr;
  min-height: 0;
}

/* ---------- Main ---------- */

.main {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.session-row {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.session-row.active {
  background: #dbeafe;
  border-radius: 4px;
}

.delete-btn {
  background: transparent;
  border: none;
  color: #999;
  cursor: pointer;
  font-size: 0.9rem;
}

.delete-btn:hover {
  color: #c00;
}

.confirm {
  display: flex;
  gap: 0.25rem;
}

.confirm button {
  font-size: 0.7rem;
  padding: 0.2rem 0.35rem;
}

.confirm .danger {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fca5a5;
}

.logo {
  height: 28px;
  width: auto;
  display: block;
}
</style>
