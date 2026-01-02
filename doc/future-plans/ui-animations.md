# UI Animation Plan - Gemma Admin

> **Status**: Future Enhancement
> **Created**: 2025-12-28
> **Library**: [Motion](https://motion.dev) + [Fancy Components](https://www.fancycomponents.dev)

---

## Overview

Transform Gemma Admin into a polished, animated experience using Motion (formerly Framer Motion) and Fancy Components. This document catalogs animation patterns and their intended use cases.

---

## Animation Categories

### 1. Number & Counter Animations

| Use Case | Resource | Notes |
|----------|----------|-------|
| Metric cards (SUTs, Queue, etc.) | [Count Animation](https://motion.dev/examples/react-html-content?tutorial=true) | Animate numbers on load/update |
| Duration displays | [Number Formatting](https://motion.dev/examples/react-number-formatting) | Format with animations |
| Price/stat switcher | [Price Switcher](https://motion.dev/examples/react-number-price-switcher) | For toggling between metrics |
| Simple counter | [Number Counter](https://motion.dev/examples/react-number-counter) | Basic counting animation |
| Rapid stat changes | [Engagement Stats](https://motion.dev/examples/react-number-engagement-stats) | For live run counts |
| Number ticker | [Basic Number Ticker](https://www.fancycomponents.dev/docs/components/text/basic-number-ticker) | Alternative ticker style |

### 2. Entry/Exit Animations

| Use Case | Resource | Notes |
|----------|----------|-------|
| Component unmounting | [Exit Animation](https://motion.dev/examples/react-exit-animation) | Smooth hide animations |
| Page transitions | [Transition](https://motion.dev/examples/react-transition) | Route change animations |
| Modal/dialog | [Modal Shared Layout](https://motion.dev/examples/react-modal-shared-layout) | For screenshot viewer |
| Staggered lists | [Staggered Grid](https://motion.dev/examples/react-staggered-grid) | SUTs, games, runs lists |
| Theme switching | [Variants](https://motion.dev/examples/react-variants) | Future light/dark toggle |

### 3. Interactive Elements

| Use Case | Resource | Notes |
|----------|----------|-------|
| Drag to reorder | [Drag](https://motion.dev/examples/react-drag) | Reorder games, workflows |
| Hover/tap gestures | [Gestures](https://motion.dev/examples/react-gestures) | Button interactions |
| Bouncing toggle | [Bounce Easing](https://motion.dev/examples/react-bounce-easing) | Toggle switches |
| Hold to confirm | [Hold to Confirm](https://motion.dev/examples/react-hold-to-confirm) | Dangerous actions (stop all) |
| Color picker | [Color Picker](https://motion.dev/examples/react-color-picker) | Theme customization |

### 4. Navigation & Tabs

| Use Case | Resource | Notes |
|----------|----------|-------|
| Tab switching | [Smooth Tabs](https://motion.dev/examples/react-smooth-tabs) | Main navigation |
| Toggle groups | [Base Toggle Group](https://motion.dev/examples/react-base-toggle-group) | Filter toggles |
| Toolbar | [Radix Toolbar](https://motion.dev/examples/react-radix-toolbar) | Action toolbars |

### 5. Loading & Progress

| Use Case | Resource | Notes |
|----------|----------|-------|
| Game running animation | [Motion Path](https://motion.dev/examples/react-motion-path) | Replace squircle with game image |
| Reorder loading | [Reorder Items](https://motion.dev/examples/react-reorder-items) | Random reorder effect |
| Progress bars | [Base Progress](https://motion.dev/examples/react-base-progress) | Run progress, queue depth |

### 6. Scrolling & Lists

| Use Case | Resource | Notes |
|----------|----------|-------|
| Horizontal scroll buttons | [Use Presence Data](https://motion.dev/examples/react-use-presence-data) | Game carousel navigation |
| Scroll-linked logs | [Scroll Linked](https://motion.dev/examples/react-scroll-linked) | Log viewer enhancements |
| Infinite scroll | [Infinite Loading](https://motion.dev/examples/react-infinite-loading) | Run history pagination |

### 7. Dialogs & Notifications

| Use Case | Resource | Notes |
|----------|----------|-------|
| Confirm dialogs | [Family Dialog](https://motion.dev/examples/react-family-dialog) | Delete, stop confirmations |
| Toast notifications | [Base Toast](https://motion.dev/examples/react-base-toast) | Scheduled run alerts |
| Multi-state badge | [Multi-State Badge](https://motion.dev/examples/react-multi-state-badge) | Start automation button |

### 8. Text Effects

| Use Case | Resource | Notes |
|----------|----------|-------|
| Log highlighting | [Text Highlighter](https://www.fancycomponents.dev/docs/components/text/text-highlighter) | Highlight errors in logs |
| Character counter | [Characters Remaining](https://motion.dev/examples/react-characters-remaining) | Input fields |
| Variable font hover | [Variable Font Hover](https://www.fancycomponents.dev/docs/components/text/variable-font-hover-by-random-letter) | Alternative start button |
| Font size settings | [Variable Font Cursor](https://www.fancycomponents.dev/docs/components/text/variable-font-and-cursor) | Accessibility settings |
| Rotating text | [Text Rotate](https://www.fancycomponents.dev/docs/components/text/text-rotate) | Dashboard hero text |

### 9. Layout & Containers

| Use Case | Resource | Notes |
|----------|----------|-------|
| Aspect ratio | [Aspect Ratio](https://motion.dev/examples/react-aspect-ratio) | Screenshot containers |

### 10. Showcase & Marketing

For gaming-dashboard or marketing pages:

| Use Case | Resource | Notes |
|----------|----------|-------|
| Game grid (Apple Watch style) | [Apple Watch Home](https://motion.dev/examples/react-apple-watch-home-screen) | Supported games showcase |
| Parallax floating | [Parallax Floating](https://www.fancycomponents.dev/docs/components/image/parallax-floating) | Game artwork display |
| Marquee scroll | [Simple Marquee](https://www.fancycomponents.dev/docs/components/blocks/simple-marquee) | Game logos carousel |
| Pixel trail | [Pixel Trail](https://www.fancycomponents.dev/docs/components/background/pixel-trail) | Fun background effect |

---

## Implementation Priority

### Phase 1: Core Interactions
1. Number animations for metric cards
2. Entry/exit animations for lists
3. Smooth tab navigation
4. Progress bar animations

### Phase 2: Enhanced UX
1. Hold-to-confirm for dangerous actions
2. Toast notifications
3. Modal animations for screenshot viewer
4. Staggered grid for game/SUT lists

### Phase 3: Polish
1. Scroll-linked log viewer
2. Text highlighting in logs
3. Infinite scroll for history
4. Drag-to-reorder workflows

### Phase 4: Delight
1. Loading animations with game images
2. Theme transition effects
3. Pixel trail backgrounds
4. Variable font effects

---

## Installation

```bash
# Motion (primary animation library)
npm install motion

# For React components
npm install framer-motion

# Fancy Components (copy from website - no npm package)
# Components are copy-paste from https://www.fancycomponents.dev
```

---

## Notes

- Motion.dev examples are React-focused and work well with our stack
- Fancy Components provides copy-paste code snippets
- Consider performance impact of complex animations
- Test on lower-end hardware before deployment
- Animations should enhance, not distract from functionality
