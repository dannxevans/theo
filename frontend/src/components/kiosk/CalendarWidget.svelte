<script>
  export let calendar = null;
</script>

<div class="calendar-widget widget-card">
  <div class="widget-header">
    <svg class="widget-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
      <line x1="16" y1="2" x2="16" y2="6"/>
      <line x1="8" y1="2" x2="8" y2="6"/>
      <line x1="3" y1="10" x2="21" y2="10"/>
    </svg>
    <span class="widget-title">Calendar</span>
  </div>
  {#if calendar}
    <div class="widget-content">
      {#if calendar.count > 0}
        <div class="main-stat">{calendar.count}<span class="unit">events</span></div>
        {#if calendar.next_event}
          <div class="next-event">
            <div class="event-title">{calendar.next_event.title}</div>
            <div class="event-time">{calendar.next_event.relative}</div>
          </div>
        {/if}
      {:else}
        <div class="no-events">No upcoming events</div>
      {/if}
    </div>
  {:else}
    <div class="widget-content not-connected">
      <div class="not-connected-text">Not Connected</div>
    </div>
  {/if}
</div>

<style>
  .calendar-widget {
    min-height: 120px;
  }

  .main-stat {
    font-size: 3rem;
    font-weight: 300;
    font-family: 'Aptos Display', 'Aptos', sans-serif;
    color: var(--kiosk-accent-purple, #a855f7);
    line-height: 1;
    margin-bottom: 0.75rem;
  }

  .unit {
    font-size: 1rem;
    opacity: 0.6;
    margin-left: 0.5rem;
  }

  .next-event {
    padding-top: 0.75rem;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
  }

  .event-title {
    font-size: 0.95rem;
    color: var(--kiosk-text-primary, #e0e0e0);
    font-weight: 500;
    margin-bottom: 0.25rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .event-time {
    font-size: 0.85rem;
    color: var(--kiosk-text-secondary, #9ca3af);
  }

  .no-events {
    font-size: 1rem;
    color: var(--kiosk-text-secondary, #9ca3af);
    padding: 1rem 0;
  }

  /* Responsive scaling */
  @media (max-width: 1024px) {
    .calendar-widget {
      min-height: 100px;
    }

    .main-stat {
      font-size: 2.5rem;
    }

    .unit {
      font-size: 0.9rem;
    }

    .event-title {
      font-size: 0.85rem;
    }

    .event-time {
      font-size: 0.75rem;
    }

    .no-events {
      font-size: 0.9rem;
      padding: 0.75rem 0;
    }
  }

  @media (max-width: 768px) {
    .calendar-widget {
      min-height: 80px;
    }

    .main-stat {
      font-size: 2rem;
    }

    .unit {
      font-size: 0.8rem;
    }

    .event-title {
      font-size: 0.75rem;
    }

    .event-time {
      font-size: 0.7rem;
    }

    .no-events {
      font-size: 0.8rem;
      padding: 0.5rem 0;
    }
  }
</style>
