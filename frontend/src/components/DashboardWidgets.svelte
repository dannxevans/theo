<script>
  import { onMount, onDestroy } from "svelte";
  import { fetchKioskDashboard } from "../lib/api.js";
  import TimeWidget from "./kiosk/TimeWidget.svelte";
  import SleepWidget from "./kiosk/SleepWidget.svelte";
  import WorkoutWidget from "./kiosk/WorkoutWidget.svelte";
  import WeatherWidget from "./kiosk/WeatherWidget.svelte";
  import CalendarWidget from "./kiosk/CalendarWidget.svelte";
  import EmailBadge from "./kiosk/EmailBadge.svelte";

  export let paused = false; // Pause polling during active conversation
  export let emailData = null; // Export email data to parent

  let dashboardData = null;
  let pollInterval = null;
  let isLoading = true;

  async function loadDashboard() {
    if (paused) return;

    try {
      console.log("[DASHBOARD] Fetching dashboard data...");
      dashboardData = await fetchKioskDashboard();
      console.log("[DASHBOARD] Data received:", dashboardData);

      // Update email data for parent component
      emailData = dashboardData?.email || null;

      isLoading = false;
    } catch (error) {
      console.error("[DASHBOARD] Failed to fetch dashboard data:", error);
      console.error("[DASHBOARD] Error details:", error.message);
      isLoading = false;
    }
  }

  onMount(() => {
    // Initial load
    loadDashboard();

    // Poll every 60 seconds
    pollInterval = setInterval(() => {
      loadDashboard();
    }, 60000);
  });

  onDestroy(() => {
    if (pollInterval) {
      clearInterval(pollInterval);
    }
  });

  // Reload when unpaused
  $: if (!paused && pollInterval) {
    loadDashboard();
  }
</script>

<div class="dashboard-widgets">
  <!-- Time Widget (full width) -->
  <div class="time-section">
    <TimeWidget time={dashboardData?.time} />
  </div>

  <!-- Widget Grid (2 columns) -->
  <div class="widget-grid">
    <SleepWidget sleep={dashboardData?.sleep} />
    <WorkoutWidget workout={dashboardData?.workout} />
    <WeatherWidget weather={dashboardData?.weather} />
    <CalendarWidget calendar={dashboardData?.calendar} />
  </div>
</div>

<style>
  .dashboard-widgets {
    display: flex;
    flex-direction: column;
    gap: 2rem;
    height: 100%;
  }

  .time-section {
    width: 100%;
  }

  .widget-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
  }

  /* Shared widget card styles (applied globally via CSS variables) */
  :global(.widget-card) {
    background: var(--kiosk-card-bg);
    border: 1px solid var(--kiosk-card-border);
    border-radius: 16px;
    padding: 1.25rem;
    backdrop-filter: blur(10px);
    transition: all 0.3s ease;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  }

  :global(.widget-card:hover) {
    border-color: rgba(100, 255, 255, 0.4);
    box-shadow: var(--kiosk-glow);
  }

  :global(.widget-header) {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  :global(.widget-icon) {
    font-size: 1.5rem;
  }

  :global(.widget-title) {
    font-size: 0.9rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--kiosk-text-secondary);
  }

  :global(.widget-content) {
    display: flex;
    flex-direction: column;
  }

  :global(.not-connected) {
    padding: 1.5rem 0;
    text-align: center;
  }

  :global(.not-connected-text) {
    font-size: 0.9rem;
    color: var(--kiosk-text-secondary);
    opacity: 0.6;
  }

  /* Responsive scaling for smaller screens - shrink proportionally */
  @media (max-width: 1024px) {
    .dashboard-widgets {
      gap: 1.5rem;
    }

    .widget-grid {
      gap: 1rem;
    }

    :global(.widget-card) {
      padding: 1rem;
      border-radius: 12px;
    }

    :global(.widget-header) {
      margin-bottom: 0.75rem;
      padding-bottom: 0.5rem;
    }

    :global(.widget-icon) {
      font-size: 1.2rem;
    }

    :global(.widget-title) {
      font-size: 0.75rem;
    }
  }

  @media (max-width: 768px) {
    .dashboard-widgets {
      gap: 1rem;
    }

    .widget-grid {
      gap: 0.75rem;
    }

    :global(.widget-card) {
      padding: 0.75rem;
      border-radius: 10px;
    }

    :global(.widget-header) {
      margin-bottom: 0.5rem;
      padding-bottom: 0.4rem;
    }

    :global(.widget-icon) {
      font-size: 1rem;
    }

    :global(.widget-title) {
      font-size: 0.65rem;
    }
  }

  /* Responsive scaling for short screens (vertical constraint) */
  @media (max-height: 700px) {
    .dashboard-widgets {
      gap: 1.25rem;
    }

    .widget-grid {
      gap: 1rem;
    }

    :global(.widget-card) {
      padding: 0.9rem;
      min-height: 90px;
    }
  }

  @media (max-height: 600px) {
    .dashboard-widgets {
      gap: 0.75rem;
    }

    .widget-grid {
      gap: 0.5rem;
    }

    :global(.widget-card) {
      padding: 0.65rem;
      min-height: 70px;
    }

    :global(.widget-header) {
      margin-bottom: 0.4rem;
      padding-bottom: 0.3rem;
    }

    :global(.widget-icon) {
      font-size: 0.9rem;
    }

    :global(.widget-title) {
      font-size: 0.6rem;
    }
  }
</style>
