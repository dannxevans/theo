# Utility Classes Quick Reference
**THEO AI Assistant - CSS Utilities Cheat Sheet**

## 🎨 Status Badges

```html
<!-- Inline status indicators -->
<span class="status-badge status-badge--success">Active</span>
<span class="status-badge status-badge--warning">Pending</span>
<span class="status-badge status-badge--error">Failed</span>
<span class="status-badge status-badge--info">Processing</span>
```

**Variants**: `--success`, `--warning`, `--error`, `--info`

---

## 📦 Cards

```html
<!-- Basic card -->
<div class="card">
  <div class="card__header">
    Header content
  </div>
  <div class="card__body">
    Main content
  </div>
  <div class="card__footer">
    Footer actions
  </div>
</div>

<!-- Status card -->
<div class="status-card status-card--success">
  <span class="status-card__icon">✓</span>
  <div class="status-card__title">Connected</div>
  <div class="status-card__text">All systems operational</div>
</div>
```

**Card Variants**: `.card`, `.status-card`
**Status Card Variants**: `--success`, `--warning`, `--error`, `--info`

---

## 🚨 Alerts

```html
<!-- Success alert -->
<div class="alert alert--success">
  <span class="alert__icon">✓</span>
  <div class="alert__content">
    <div class="alert__title">Success!</div>
    <div class="alert__message">Your changes have been saved.</div>
  </div>
</div>

<!-- Warning alert -->
<div class="alert alert--warning">
  <span class="alert__icon">⚠</span>
  <div class="alert__content">
    <div class="alert__title">Warning</div>
    <div class="alert__message">Please review before proceeding.</div>
  </div>
</div>

<!-- Error alert -->
<div class="alert alert--error">
  <span class="alert__icon">✕</span>
  <div class="alert__content">
    <div class="alert__title">Error</div>
    <div class="alert__message">Something went wrong.</div>
  </div>
</div>

<!-- Info alert -->
<div class="alert alert--info">
  <span class="alert__icon">ℹ</span>
  <div class="alert__content">
    <div class="alert__title">Info</div>
    <div class="alert__message">Helpful information here.</div>
  </div>
</div>
```

**Variants**: `--success`, `--warning`, `--error`, `--info`

---

## 🔘 Buttons

```html
<!-- Primary action -->
<button class="btn-primary">Save Changes</button>

<!-- Secondary action -->
<button class="btn-secondary">Cancel</button>

<!-- Destructive action -->
<button class="btn-danger">Delete</button>

<!-- Success action -->
<button class="btn-success">Approve</button>

<!-- Info/Neutral action -->
<button class="btn-info">Learn More</button>

<!-- Small variant -->
<button class="btn-small">Edit</button>

<!-- Pill style navigation -->
<button class="btn-pill active">Active Tab</button>
<button class="btn-pill">Inactive Tab</button>
```

**Available**: `.btn-primary`, `.btn-secondary`, `.btn-danger`, `.btn-success`, `.btn-info`, `.btn-small`, `.btn-pill`

---

## 📝 Forms

```html
<!-- Form group (label + input + hint) -->
<div class="form-group">
  <label for="username">Username</label>
  <input type="text" id="username" placeholder="Enter username">
  <small>Choose a unique username</small>
</div>

<!-- Form actions -->
<div class="form-actions">
  <button class="btn-primary">Submit</button>
  <button class="btn-secondary">Cancel</button>
</div>

<!-- Save status messages -->
<div class="save-status success">Settings saved!</div>
<div class="success-message">Operation completed successfully</div>
<div class="error-message">Something went wrong</div>
```

**Available**: `.form-group`, `.form-actions`, `.save-status`, `.success-message`, `.error-message`

---

## 🪟 Modals

```html
<div class="modal-overlay">
  <div class="modal">
    <div class="modal__header">
      <h2 class="modal__title">Edit Settings</h2>
      <button class="modal__close">×</button>
    </div>

    <div class="modal__body">
      <!-- Form content here -->
    </div>

    <div class="modal__footer">
      <button class="btn-secondary">Cancel</button>
      <button class="btn-primary">Save</button>
    </div>
  </div>
</div>
```

**Available**: `.modal__header`, `.modal__title`, `.modal__close`, `.modal__body`, `.modal__footer`

---

## 📐 Layout

```html
<!-- Settings section wrapper -->
<div class="section">
  <h3>Section Title</h3>
  <!-- Content -->
</div>

<!-- Tab panel container -->
<div class="tab-panel">
  <h2>Tab Content</h2>
  <!-- Tab content -->
</div>

<!-- Empty state -->
<div class="empty-state">
  <p>No items found</p>
  <button class="btn-primary">Create New</button>
</div>
```

**Available**: `.section`, `.tab-panel`, `.empty-state`

---

## 🏷️ Provider Badges

```html
<!-- AI provider labels -->
<span class="provider-badge provider-badge--ai">GPT-4</span>
<span class="provider-badge provider-badge--action">Email Sent</span>
<span class="provider-badge provider-badge--error">Failed</span>
<span class="provider-badge provider-badge--default">System</span>
```

**Variants**: `--ai`, `--action`, `--error`, `--default`

---

## 🎨 CSS Variables (Semantic Tokens)

### Colors
```css
/* Text colors */
var(--text-primary)      /* Main text color */
var(--text-secondary)    /* Secondary text */
var(--text-tertiary)     /* Tertiary/muted text */

/* Background colors */
var(--bg-primary)        /* Main background */
var(--bg-secondary)      /* Secondary surfaces */
var(--bg-tertiary)       /* Elevated surfaces */
var(--bg-hover)          /* Hover state background */
var(--bg-active)         /* Active state background */

/* Border colors */
var(--border-primary)    /* Main borders */
var(--border-secondary)  /* Secondary borders */
var(--border-focus)      /* Focus state borders */

/* Brand colors */
var(--theo-indigo)       /* Primary brand */
var(--theo-purple)       /* Secondary brand */
var(--theo-blue)         /* Accent brand */
var(--theo-gradient)     /* Brand gradient */
```

### Status Colors
```css
/* Success */
var(--success-50)        /* Lightest */
var(--success-500)       /* Base */
var(--success-600)       /* Darker */

/* Warning */
var(--warning-50)
var(--warning-500)
var(--warning-600)

/* Error */
var(--error-50)
var(--error-500)
var(--error-600)

/* Info */
var(--info-50)
var(--info-500)
var(--info-600)

/* Semantic status tokens */
var(--status-success-bg)
var(--status-success-border)
var(--status-success-text)
/* ... same for warning, error, info */
```

### Spacing
```css
var(--space-1)   /* 4px */
var(--space-2)   /* 8px */
var(--space-3)   /* 12px */
var(--space-4)   /* 16px */
var(--space-5)   /* 20px */
var(--space-6)   /* 24px */
var(--space-8)   /* 32px */
var(--space-12)  /* 48px */
```

### Border Radius
```css
var(--radius-sm)    /* Small radius */
var(--radius-md)    /* Medium radius */
var(--radius-lg)    /* Large radius */
var(--radius-full)  /* Pill shape */
```

### Shadows
```css
var(--shadow-sm)      /* Subtle shadow */
var(--shadow-md)      /* Medium shadow */
var(--shadow-lg)      /* Large shadow */
var(--shadow-brand)   /* Brand-colored shadow */
```

---

## 📋 Common Patterns

### Success Message with Action
```html
<div class="alert alert--success">
  <span class="alert__icon">✓</span>
  <div class="alert__content">
    <div class="alert__title">Profile Updated</div>
    <div class="alert__message">Your profile has been successfully updated.</div>
  </div>
</div>
```

### Card with Status Badge
```html
<div class="card">
  <div class="card__header">
    <h4>User Account</h4>
    <span class="status-badge status-badge--success">Active</span>
  </div>
  <div class="card__body">
    Account details here
  </div>
</div>
```

### Form with Validation
```html
<div class="form-group">
  <label for="email">Email Address</label>
  <input type="email" id="email" placeholder="you@example.com">
  <small>We'll never share your email</small>
</div>

<div class="error-message">
  Please enter a valid email address
</div>

<div class="form-actions">
  <button class="btn-primary">Save</button>
  <button class="btn-secondary">Cancel</button>
</div>
```

### Modal Dialog
```html
<div class="modal-overlay">
  <div class="modal">
    <div class="modal__header">
      <h2 class="modal__title">Confirm Delete</h2>
      <button class="modal__close" onclick="closeModal()">×</button>
    </div>

    <div class="modal__body">
      <p>Are you sure you want to delete this item? This action cannot be undone.</p>
    </div>

    <div class="modal__footer">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-danger" onclick="confirmDelete()">Delete</button>
    </div>
  </div>
</div>
```

---

## ✅ Best Practices

### DO ✓
- Use semantic tokens for all colors
- Use utility classes for common patterns
- Test components with all themes
- Keep component-specific CSS minimal
- Use BEM naming for custom classes

### DON'T ✗
- Hardcode color values (#ffffff, rgb(), etc.)
- Duplicate existing utilities
- Use direct color names (color: red)
- Override utility classes with !important
- Create one-off utilities in components

---

## 🔍 Quick Lookup

**Need to display success?**
- Small inline: `.status-badge--success`
- Card: `.status-card--success`
- Alert: `.alert--success`
- Button: `.btn-success`

**Need a button?**
- Primary action: `.btn-primary`
- Cancel/Close: `.btn-secondary`
- Delete/Remove: `.btn-danger`
- Approve/Confirm: `.btn-success`
- Info/Learn More: `.btn-info`
- Compact: `.btn-small`

**Need a message?**
- Success: `.success-message` or `.alert--success`
- Error: `.error-message` or `.alert--error`
- Warning: `.alert--warning`
- Info: `.alert--info`

**Need spacing?**
- Tiny: `var(--space-1)` or `var(--space-2)`
- Small: `var(--space-3)`
- Medium: `var(--space-4)` or `var(--space-5)`
- Large: `var(--space-6)` or `var(--space-8)`
- Extra large: `var(--space-12)`

---

## 📚 Full Documentation

For complete documentation, see:
- **Architecture**: `/frontend/src/styles/README.md`
- **Theme System**: `/COMPLETE_THEME_SYSTEM_SUMMARY.md`
- **Migration Guide**: `/UTILITY_CLASS_MIGRATION.md`
- **Theme Presets**: `/THEME_PRESETS_IMPLEMENTATION.md`

---

**Last Updated**: December 29, 2025
**Version**: 1.0.0
**Source**: `/frontend/src/styles/utilities.css`
