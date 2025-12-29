# THEO Theme System

This document explains the theme architecture and how to use it consistently across the application.

## Architecture Overview

The theme system is built on CSS custom properties (variables) with semantic naming conventions. This allows:
- Easy theme switching (light/dark and future themes)
- Consistent color usage across components
- Single source of truth for design tokens
- Automatic color adjustments when themes change

## File Structure

```
frontend/src/styles/
├── variables.css      # Theme tokens and color definitions
├── utilities.css      # Reusable component classes
├── components/        # Component-specific styles
│   ├── buttons.css
│   ├── cards.css
│   ├── chat.css
│   ├── forms.css
│   └── modals.css
└── README.md         # This file
```

## Theme Variables

### Background Colors
Use these for component backgrounds:

```css
--bg-primary      /* Main background (white in light, dark in dark) */
--bg-secondary    /* Subtle contrast background */
--bg-tertiary     /* Medium contrast background */
--bg-elevated     /* Elevated surfaces (modals, dropdowns) */
--bg-hover        /* Hover state background */
--bg-active       /* Active/selected state background */
```

### Text Colors
Use these for text content:

```css
--text-primary    /* Primary text (high contrast) */
--text-secondary  /* Secondary text (medium contrast) */
--text-tertiary   /* Tertiary text (low contrast, hints) */
--text-inverse    /* Inverse text (for dark backgrounds) */
```

### Border Colors
Use these for borders and dividers:

```css
--border-primary    /* Default borders */
--border-secondary  /* Subtle borders */
--border-focus      /* Focus state (usually brand color) */
```

### Status Colors (Semantic)
**Always use the semantic tokens, not the base palette:**

```css
/* Success states */
--status-success-bg      /* Light green background */
--status-success-border  /* Green border */
--status-success-text    /* Dark green text */

/* Error states */
--status-error-bg        /* Light red background */
--status-error-border    /* Red border */
--status-error-text      /* Dark red text */

/* Warning states */
--status-warning-bg      /* Light yellow background */
--status-warning-border  /* Yellow border */
--status-warning-text    /* Dark yellow/orange text */

/* Info states */
--status-info-bg         /* Light blue background */
--status-info-border     /* Blue border */
--status-info-text       /* Dark blue text */
```

## Utility Classes

Instead of writing inline styles or scoped component styles, use these reusable classes:

### Status Badges

```html
<!-- Success badge -->
<span class="status-badge status-badge--success">Connected</span>

<!-- Error badge -->
<span class="status-badge status-badge--error">Failed</span>

<!-- Warning badge -->
<span class="status-badge status-badge--warning">Degraded</span>

<!-- Info badge -->
<span class="status-badge status-badge--info">Processing</span>
```

### Status Cards

```html
<div class="status-card status-card--success">
  <div class="status-card__icon">✓</div>
  <div class="status-card__title">Connected</div>
  <div class="status-card__text">Token expires: 12/30/2025</div>
</div>
```

### Form Inputs

```html
<div class="form-group">
  <label class="form-group__label" for="email">Email</label>
  <input
    type="email"
    id="email"
    class="input-field"
    placeholder="Enter your email"
  />
  <span class="form-group__hint">We'll never share your email</span>
</div>
```

### Cards

```html
<div class="card">
  <div class="card__header">
    <h3 class="card__title">Provider Settings</h3>
    <button>Edit</button>
  </div>
  <div class="card__body">
    <p>Configure your AI providers here...</p>
  </div>
</div>
```

### Sections (Settings Pages)

```html
<div class="section">
  <h2 class="section__title">General Settings</h2>
  <p class="section__subtitle">Configure system-wide preferences</p>
  <!-- Form content here -->
</div>
```

## Adding a New Theme

To add a new theme (e.g., "high-contrast"):

1. **Add theme selector in variables.css:**

```css
[data-theme="high-contrast"] {
  /* Backgrounds */
  --bg-primary: #000000;
  --bg-secondary: #1a1a1a;
  --bg-tertiary: #2d2d2d;

  /* Text */
  --text-primary: #ffffff;
  --text-secondary: #cccccc;
  --text-tertiary: #999999;

  /* Borders */
  --border-primary: #ffffff;
  --border-secondary: #cccccc;

  /* Status colors stay the same or adjust if needed */
  --status-success-text: #00ff00;  /* Brighter green */
  --status-error-text: #ff0000;    /* Brighter red */
}
```

2. **Update theme switcher to include new option** (in Settings or wherever theme is selected)

3. **No component changes needed!** All components using the semantic tokens will automatically adapt.

## Best Practices

### ✅ DO

```css
/* Use semantic tokens */
.my-component {
  background: var(--bg-tertiary);
  color: var(--text-primary);
  border: 1px solid var(--border-primary);
}

/* Use utility classes */
<div class="status-card status-card--success">...</div>

/* Use status tokens for state-based colors */
.success-message {
  background: var(--status-success-bg);
  color: var(--status-success-text);
  border: 1px solid var(--status-success-border);
}
```

### ❌ DON'T

```css
/* Don't use hardcoded colors */
.my-component {
  background: #f3f4f6;  /* ❌ Won't change with theme */
  color: #111827;       /* ❌ Won't change with theme */
}

/* Don't use base palette directly in components */
.success-message {
  background: var(--success-50);   /* ❌ Use --status-success-bg instead */
  color: var(--success-600);       /* ❌ Use --status-success-text instead */
}

/* Don't duplicate utility classes */
.my-custom-badge {  /* ❌ Use .status-badge instead */
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  /* ... */
}
```

## Component Style Guidelines

When creating new components:

1. **Check utilities.css first** - Can you use existing classes?
2. **Use semantic tokens** - Always use `--bg-*`, `--text-*`, `--border-*`, `--status-*`
3. **Avoid scoped styles** - Prefer global utility classes for consistency
4. **Document new patterns** - If you create a new reusable pattern, add it to utilities.css

## Migration Guide

To migrate existing components to use the new system:

1. **Replace hardcoded colors:**
   ```css
   /* Before */
   background: #ffffff;
   color: #111827;

   /* After */
   background: var(--bg-primary);
   color: var(--text-primary);
   ```

2. **Replace base palette variables:**
   ```css
   /* Before */
   background: var(--success-50);
   color: var(--success-600);

   /* After */
   background: var(--status-success-bg);
   color: var(--status-success-text);
   ```

3. **Use utility classes:**
   ```html
   <!-- Before -->
   <div style="background: var(--success-50); padding: 1rem;">
     Success!
   </div>

   <!-- After -->
   <div class="status-card status-card--success">
     <div class="status-card__text">Success!</div>
   </div>
   ```

## Testing Themes

To test your component in both themes:

1. Toggle between light/dark mode using the theme switcher
2. Verify text is readable (sufficient contrast)
3. Check all interactive states (hover, focus, active)
4. Verify borders and dividers are visible

## Questions?

If you're unsure which variable to use:
- Backgrounds → `--bg-*`
- Text → `--text-*`
- Borders → `--border-*`
- Status/state indicators → `--status-*`

When in doubt, check utilities.css for existing patterns!
