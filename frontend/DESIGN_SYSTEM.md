# THEO Design System

This document outlines the design system used across the THEO application. All design tokens are defined as CSS custom properties in `/frontend/src/styles/variables.css`.

## CSS Architecture

The THEO application uses a modular CSS architecture:

- **`/frontend/src/styles/index.css`** - Main entry point that imports all modules
- **`/frontend/src/styles/variables.css`** - Design tokens (colors, spacing, typography)
- **`/frontend/src/styles/global.css`** - Global styles, resets, and layout
- **`/frontend/src/styles/components/`** - Component-specific styles:
  - `buttons.css` - Button variants and styles
  - `forms.css` - Form inputs, selects, textareas
  - `cards.css` - Card components and badges
  - `modals.css` - Dropdowns, modals, tabs
  - `sidebar.css` - Sidebar navigation
  - `chat.css` - Chat layout and messages
  - `health-monitor.css` - Health monitoring components
- **`/frontend/src/styles/utilities.css`** - Utility classes

## Colors

### Brand Colors
```css
--theo-blue: #38BDF8
--theo-indigo: #6366F1
--theo-violet: #A855F7
--theo-gradient: linear-gradient(90deg, var(--theo-blue) 0%, var(--theo-indigo) 50%, var(--theo-violet) 100%)
```

### Neutral Colors (Gray Scale)
```css
--gray-50: #f9fafb    /* Lightest backgrounds */
--gray-100: #f3f4f6   /* Light backgrounds */
--gray-200: #e5e7eb   /* Borders */
--gray-300: #d1d5db   /* Form borders */
--gray-400: #9ca3af   /* Muted text */
--gray-500: #6b7280   /* Secondary text */
--gray-600: #4b5563   /* Primary text */
--gray-700: #374151   /* Dark text */
--gray-800: #1f2937   /* Darkest text */
--gray-900: #111827   /* Almost black */
```

### Semantic Colors

**Success (Green)**
```css
--success-50: #f0fdf4    /* Success backgrounds */
--success-500: #10b981   /* Success primary */
--success-600: #059669   /* Success dark */
```

**Warning (Orange)**
```css
--warning-50: #fffbeb    /* Warning backgrounds */
--warning-500: #f59e0b   /* Warning primary */
--warning-600: #d97706   /* Warning dark */
```

**Error (Red)**
```css
--error-50: #fef2f2      /* Error backgrounds */
--error-500: #ef4444     /* Error primary */
--error-600: #dc2626     /* Error dark */
```

**Info (Blue)**
```css
--info-50: #eff6ff       /* Info backgrounds */
--info-500: #3b82f6      /* Info primary */
--info-600: #2563eb      /* Info dark */
```

## Spacing

Based on a **4px grid system**:

```css
--space-1: 0.25rem   /* 4px */
--space-2: 0.5rem    /* 8px */
--space-3: 0.75rem   /* 12px */
--space-4: 1rem      /* 16px */
--space-5: 1.25rem   /* 20px */
--space-6: 1.5rem    /* 24px */
--space-8: 2rem      /* 32px */
--space-10: 2.5rem   /* 40px */
--space-12: 3rem     /* 48px */
```

### Usage Guidelines
- Use `--space-1` for tight spacing (badges, small gaps)
- Use `--space-2` to `--space-4` for component internal spacing
- Use `--space-5` to `--space-6` for section spacing
- Use `--space-8` and above for large layout gaps

## Typography

### Font Sizes
```css
--font-size-xs: 0.75rem    /* 12px - Small labels, badges */
--font-size-sm: 0.875rem   /* 14px - Body text, buttons */
--font-size-base: 1rem     /* 16px - Default text */
--font-size-lg: 1.125rem   /* 18px - Subheadings */
--font-size-xl: 1.25rem    /* 20px - Small headings */
--font-size-2xl: 1.5rem    /* 24px - Large headings */
```

### Usage
- **xs**: Badges, timestamps, metadata
- **sm**: Button text, form labels, secondary text
- **base**: Body text, default paragraph text
- **lg**: Card titles, section subheadings
- **xl**: Component headings
- **2xl**: Page headings (h1)

## Border Radius

```css
--radius-sm: 4px     /* Small elements */
--radius-md: 6px     /* Medium elements */
--radius-lg: 8px     /* Large containers */
--radius-xl: 12px    /* Extra large containers */
--radius-full: 999px /* Pills, rounded buttons */
```

## Shadows

```css
--shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05)            /* Subtle depth */
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1)          /* Standard elevation */
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1)        /* High elevation */
--shadow-brand: 0 4px 12px rgba(99, 102, 241, 0.35)     /* Brand glow */
```

## Z-Index Scale

```css
--z-dropdown: 10      /* Dropdowns */
--z-sticky: 20        /* Sticky headers */
--z-modal-backdrop: 30 /* Modal backgrounds */
--z-modal: 40         /* Modal content */
--z-toast: 50         /* Notifications */
```

## Components

### Buttons

#### Primary Button
- **Use for**: Main actions, form submissions
- **Colors**: `--theo-gradient` background, white text
- **Size**: 40px height, `--space-4` horizontal padding
- **Shadow**: `--shadow-brand`
```html
<button class="btn-primary">Save</button>
```

#### Secondary Button
- **Use for**: Alternative actions, cancels
- **Colors**: White background, `--gray-900` text, `--gray-300` border
- **Size**: 40px height, `--space-3` horizontal padding
```html
<button class="btn-secondary">Cancel</button>
```

#### Danger Button
- **Use for**: Destructive actions
- **Colors**: `--error-500` background, white text
- **Size**: 40px height, `--space-3` horizontal padding
```html
<button class="btn-danger">Delete</button>
```

#### Small Button
- **Use for**: Inline actions, list items
- **Colors**: White background, `--gray-700` text, `--gray-300` border
- **Size**: 32px height, `--space-3` horizontal padding
- **Font**: `--font-size-xs`
```html
<button class="btn-small">Edit</button>
```

### Forms

#### Text Inputs
```css
padding: var(--space-2);
border: 1px solid var(--gray-300);
border-radius: var(--radius-sm);
font-size: var(--font-size-sm);
```

#### Select Dropdowns
Same styling as text inputs

#### Form Labels
```css
font-size: var(--font-size-sm);
font-weight: 500;
margin-bottom: var(--space-1);
```

#### Form Help Text
```css
font-size: var(--font-size-xs);
color: var(--gray-500);
margin-top: var(--space-1);
```

### Cards

#### Standard Card
```css
border: 1px solid var(--gray-200);
border-radius: var(--radius-lg);
padding: var(--space-4);
background: white;
```

#### Form Container
```css
background: var(--gray-50);
border: 1px solid var(--gray-200);
border-radius: var(--radius-lg);
padding: var(--space-5) to var(--space-6);
```

### Badges

#### Status Badges
- **Padding**: `--space-1` vertical, `--space-2` to `--space-3` horizontal
- **Border Radius**: `--radius-sm`
- **Font Size**: `--font-size-xs`
- **Font Weight**: 500

**Success Badge**: `background: var(--success-500)`, `color: white`
**Warning Badge**: `background: var(--warning-500)`, `color: white`
**Error Badge**: `background: var(--error-500)`, `color: white`
**Info Badge**: `background: var(--info-500)`, `color: white`

### Empty States

```css
text-align: center;
padding: var(--space-12) var(--space-4);
color: var(--gray-500);
```

## Best Practices

1. **Always use CSS variables** instead of hard-coded values
2. **Follow the spacing scale** - don't create custom spacing values
3. **Use semantic colors** for success/warning/error states
4. **Maintain consistent border radius** across similar components
5. **Keep z-index values** from the defined scale
6. **Use design tokens** for all new components

## Migration Checklist

When adding new components or updating existing ones:

- [ ] Replace all color hex codes with `var(--color-name)`
- [ ] Replace spacing px values with `var(--space-N)`
- [ ] Replace font sizes with `var(--font-size-name)`
- [ ] Replace border radius with `var(--radius-name)`
- [ ] Replace shadows with `var(--shadow-name)`
- [ ] Use standard button classes instead of custom styles
- [ ] Follow the semantic color naming for states
