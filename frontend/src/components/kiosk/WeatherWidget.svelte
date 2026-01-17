<script>
  export let weather = null;
</script>

<div class="weather-widget widget-card">
  <div class="widget-header">
    <svg class="widget-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/>
    </svg>
    <span class="widget-title">Weather</span>
  </div>
  {#if weather}
    <div class="widget-content">
      <div class="main-stat">{weather.temperature}<span class="unit">°C</span></div>
      <div class="condition">{weather.condition}</div>
      <div class="location">{weather.location}</div>
    </div>
  {:else}
    <div class="widget-content not-connected">
      <div class="not-connected-text">Not Connected</div>
    </div>
  {/if}
</div>

<style>
  .weather-widget {
    min-height: 120px;
  }

  .main-stat {
    font-size: 3.5rem;
    font-weight: 300;
    font-family: 'Aptos Display', 'Aptos', sans-serif;
    color: var(--kiosk-accent-cyan, #00ffff);
    line-height: 1;
    margin-bottom: 0.5rem;
  }

  .unit {
    font-size: 1.5rem;
    opacity: 0.6;
    margin-left: 0.25rem;
  }

  .condition {
    font-size: 1rem;
    color: var(--kiosk-text-primary, #e0e0e0);
    font-weight: 500;
    margin-bottom: 0.25rem;
  }

  .location {
    font-size: 0.9rem;
    color: var(--kiosk-text-secondary, #9ca3af);
    opacity: 0.7;
  }

  /* Responsive scaling */
  @media (max-width: 1024px) {
    .weather-widget {
      min-height: 100px;
    }

    .main-stat {
      font-size: 2.75rem;
    }

    .unit {
      font-size: 1.2rem;
    }

    .condition {
      font-size: 0.9rem;
    }

    .location {
      font-size: 0.8rem;
    }
  }

  @media (max-width: 768px) {
    .weather-widget {
      min-height: 80px;
    }

    .main-stat {
      font-size: 2.25rem;
    }

    .unit {
      font-size: 1rem;
    }

    .condition {
      font-size: 0.8rem;
    }

    .location {
      font-size: 0.7rem;
    }
  }
</style>
