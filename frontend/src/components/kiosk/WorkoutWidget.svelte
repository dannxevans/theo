<script>
  export let workout = null;
</script>

<div class="workout-widget widget-card">
  <div class="widget-header">
    <svg class="widget-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M6.5 6.5L17.5 17.5"/>
      <path d="M17.5 6.5L6.5 17.5"/>
      <circle cx="12" cy="12" r="10"/>
    </svg>
    <span class="widget-title">Workout</span>
  </div>
  {#if workout}
    <div class="widget-content">
      <div class="workout-type">{workout.type}</div>
      <div class="main-stat">{workout.duration_minutes}<span class="unit">min</span></div>
      <div class="workout-time">{workout.time_ago}</div>
    </div>
  {:else}
    <div class="widget-content not-connected">
      <div class="not-connected-text">Not Connected</div>
    </div>
  {/if}
</div>

<style>
  .workout-widget {
    min-height: 120px;
  }

  .workout-type {
    font-size: 1rem;
    font-weight: 500;
    color: var(--kiosk-text-primary, #e0e0e0);
    margin-bottom: 0.5rem;
  }

  .main-stat {
    font-size: 3rem;
    font-weight: 300;
    font-family: 'Aptos Display', 'Aptos', sans-serif;
    color: var(--kiosk-accent-purple, #a855f7);
    line-height: 1;
    margin-bottom: 0.5rem;
  }

  .unit {
    font-size: 1.2rem;
    opacity: 0.6;
    margin-left: 0.25rem;
  }

  .workout-time {
    font-size: 0.9rem;
    color: var(--kiosk-text-secondary, #9ca3af);
    opacity: 0.7;
  }

  /* Responsive scaling */
  @media (max-width: 1024px) {
    .workout-widget {
      min-height: 100px;
    }

    .workout-type {
      font-size: 0.9rem;
    }

    .main-stat {
      font-size: 2.5rem;
    }

    .unit {
      font-size: 1rem;
    }

    .workout-time {
      font-size: 0.8rem;
    }
  }

  @media (max-width: 768px) {
    .workout-widget {
      min-height: 80px;
    }

    .workout-type {
      font-size: 0.8rem;
    }

    .main-stat {
      font-size: 2rem;
    }

    .unit {
      font-size: 0.9rem;
    }

    .workout-time {
      font-size: 0.75rem;
    }
  }
</style>
