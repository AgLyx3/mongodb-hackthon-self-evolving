---
paths:
  - "apps/web/**/*.ts"
  - "apps/web/**/*.tsx"
  - "apps/web/**/*.css"
---

# Frontend: apps/web

This file is the source of truth for tokens and contracts below. If a value you
need is not here, it does not exist yet. Propose adding it rather than
inventing a one-off.

The app is a dense, data-heavy console for an FDE: agent runs, recalled
memories with provenance, proposal diffs, eval deltas, versions, rollback. The
target is the feel of a well-made developer tool (Linear, Vercel, PlanetScale,
Sentry), not a landing page.

---

## Design tokens

Defined once in `apps/web/styles/tokens.css` on `:root` and `[data-theme="dark"]`.
Consume as `var(--token)`. Never redefine a token outside that file.

### Color

**This file defines token names and meanings only, never values.** Concrete
colors live in the theme layer (`apps/web/styles/themes/*.css`). A rebrand or a
high-contrast mode is then a new theme file, not a code change.

A theme derives every value from three inputs (base, accent, contrast) in
OKLCH, so equal lightness looks equally light (Linear's approach). No
gradients anywhere in chrome.

**One accent.** `--color-primary` marks interactive and active state only:
links, focus, the selected row, the primary button. It is never decoration.
Status colors (`alarm`, `warning`, `success`) are a separate semantic set and
never decorative either.

#### Intent

Each intent ships a triad: the base, `-hover`, and `-fg` (text readable on the
base).

| Token | Means |
| --- | --- |
| `--color-primary` | Primary action, active state |
| `--color-secondary` | Secondary action, lower-emphasis controls |
| `--color-neutral` | Inert controls, unselected toggles |
| `--color-alarm` | Destructive action, errors |
| `--color-warning` | Degraded state, unsaved changes |
| `--color-success` | Saved, connected, resolved |

Adding an intent means adding all three of its triad.

#### Surface and content

| Token | Means |
| --- | --- |
| `--color-surface` | Page background |
| `--color-surface-raised` | Cards, toolbars, menus |
| `--color-surface-sunken` | Wells, code blocks |
| `--color-content` | Primary text |
| `--color-content-muted` | Secondary text, captions |
| `--color-content-subtle` | Placeholders, disabled |
| `--color-border` | Default dividers |
| `--color-border-strong` | Inputs, focus outlines |

No palette primitives (`--color-blue-500`) are exposed to components. Roles only.

### Spacing (4px base)

`--space-1` 4px · `--space-2` 8px · `--space-3` 12px · `--space-4` 16px ·
`--space-6` 24px · `--space-8` 32px · `--space-12` 48px · `--space-16` 64px

No `5`, `7`, `9`. If a gap needs an off-scale value, the layout is wrong.

### Typography

| Token | Value |
| --- | --- |
| `--font-sans` | `ui-sans-serif, system-ui, sans-serif` |
| `--font-mono` | `ui-monospace, "SF Mono", monospace` |
| `--text-xs` / `--text-sm` / `--text-base` / `--text-lg` / `--text-xl` / `--text-2xl` | 12 / 14 / 16 / 18 / 20 / 24 px |
| `--leading-ui` | 1.4 |
| `--leading-prose` | 1.45 — memory text, run summaries, proposal rationale |
| `--measure-prose` | 70ch — max width for prose blocks |

- `--text-sm` (14px) is the default for both labels and body copy in the app.
  Headings come from `--text-lg` and up. **At most four sizes on one screen.**
- Emphasis (bold, muted) is a modifier on an existing size, not a new token.
- `--font-mono` is **only** for literal machine text: IDs, content hashes,
  prompt bodies, diffs, logs, JSON. Never for labels, headings, or buttons.
- Every numeric column (scores, deltas, latency, tokens, counts) uses
  `font-variant-numeric: tabular-nums` and is right-aligned.

### Radius, elevation, motion

`--radius-sm` 4px · `--radius-md` 6px · `--radius-full` 9999px (avatars only)

Nothing is rounder than 6px except avatars.

`--shadow-sm` · `--shadow-md` · `--shadow-overlay`

`--duration-fast` 100ms · `--duration-base` 150ms · `--duration-slow` 250ms ·
`--ease-out` `cubic-bezier(0.16, 1, 0.3, 1)`

### Z-index: the full ladder

| Token | Value | Layer |
| --- | --- | --- |
| `--z-base` | 0 | Page content |
| `--z-sticky` | 10 | Sticky headers |
| `--z-toolbar` | 20 | Floating toolbars |
| `--z-popover` | 30 | Menus, popovers |
| `--z-modal` | 40 | Dialogs |
| `--z-toast` | 50 | Notifications |

This is the complete set. A raw numeric `z-index` anywhere is a defect.

### Breakpoints

`--bp-sm` 640px · `--bp-md` 768px · `--bp-lg` 1024px · `--bp-xl` 1280px

---

## Contracts

**Color.** Applied only via `var(--color-*)`. Hex literals, `rgb()`, named CSS
colors, and Tailwind arbitrary values (`text-[#2563eb]`) are never written in a
component. The only files that may contain a literal color value are themes
under `styles/themes/`.

**Spacing and radius.** Applied only via `var(--space-*)` / `var(--radius-*)`.
No `px` literals in component styles except `1px` hairline borders.

**Stacking.** Applied only via `var(--z-*)`. No numeric `z-index`.

---

## Design defaults to avoid

Without direction, generated UIs fall back to the same few styles. A general
"avoid a generic look" just swaps one default for another, so the patterns are
named here. Don't use these unless a design explicitly asks for them:

- Cream or off-white page backgrounds
- Italic accent words in headings
- Numbered "01 / 02 / 03" section labels
- Monospace labels on non-code UI
- Pill-shaped buttons
- Emoji as section headers or status markers
- Everything wrapped in rounded cards. Lists of runs, versions, memories,
  and proposals are **rows** (tables or hairline-divided lists). Cards are
  only for unlike content placed side by side.
- Illustrations, emoji, or exclamation marks in empty or error states

When a result still looks generic, name the pattern it fell back on and add it
here.

---

## Patterns for this app

Each maps to a reference page. Open it before building the screen.

| Screen | Pattern | Reference |
| --- | --- | --- |
| **Run detail** | Main column is one run; a chronological timeline of tool calls and recalled memories leads to the outcome; a right sidebar holds provenance and aggregates. Latest / previous run navigation. | Sentry issue details: docs.sentry.io/product/issues/issue-details |
| **Proposal review** | Header shows whether it can be promoted and why (gate results). "Changes" tab has the diff; a Summary shows hypothesis, falsification criterion, fix/forget counts. Accept / Edit / Reject. | PlanetScale deploy requests: planetscale.com/docs/vitess/schema-changes/deploy-requests |
| **Diff view** | Unified/split toggle that persists across visits; unchanged context collapsed; `+`/`−` gutters; line-level comments; "reviewed" checkbox that collapses a file. | GitHub PR review: docs.github.com (reviewing proposed changes in a PR) |
| **Eval comparison** | Baseline, delta, and regression count always shown; sortable by regressions; filter improved/regressed with counts; noise band shown next to the delta; deltas carry sign and arrow (`▲ +0.04`), not color alone. | Braintrust compare experiments: braintrust.dev/docs/evaluate/compare-experiments |
| **Version history** | Rows with the date as anchor; big changes get a sentence of why, small ones one line. Every version has an immutable ID and exactly these actions: View diff / Promote / Roll back. | Linear changelog: linear.app/changelog; Vercel deployments: vercel.com/docs/deployments |
| **Memory detail** | Two columns: readable summary left, raw stored document right; nested provenance fields collapsed with deep links. | Stripe API reference: docs.stripe.com/api |

Typography and voice outside the tool category: oxide.computer/blog (sober
palette, clear metadata, but use rows, not its card grid). Numbers:
practicaltypography.com (body 15–25px, 45–90 characters per line).

## Contracts, continued

**Status.** Every status is text plus an icon or sign, never color alone:
`▲ +0.04`, `▼ −0.02`, `unresolved (within ±0.05 noise)`, `2 forgotten`.

**Dates.** Absolute and unambiguous: `26 Sep 2026 14:02`. Relative time
("3m ago") only as secondary text or a tooltip.

**Rollback and promote.** The confirmation says what will change and what
won't (which version becomes live, what memory stays). The action fires only
after confirmation completes. The copy names the target version ID.

**Empty and error states.** One plain sentence plus the next action: "No
proposals yet. They appear after a run with at least three failures in the
same category." No illustrations.

**Motion.** Frequent actions (command menu, tab switch, row select) are
instant, with no animation. Animate only to show where something came from.

## Real-UI galleries

When a screen has no reference above, look at real products, not generated
mockups: mobbin.com (flows and patterns), refero.design (web SaaS dashboards).

---

## Naming

- Components: `PascalCase.tsx`, one component per file, filename equals export.
- Hooks: `useThing.ts`, always prefixed `use`.
- Route segments: `kebab-case/`.
- Boolean props: `is*` / `has*` / `can*`. Handler props: `on*`. Handler
  implementations: `handle*`.
- Imports use the `@/` alias. No `../../` beyond one level.

---

## Rendering and data

- Server Components by default. `"use client"` only for genuine interactivity.
- The browser never talks to MongoDB directly. Data goes through the backend.
- Colocate a component with its only consumer. Promote to shared on the second
  use, not in anticipation of one.
- Props explicitly typed. No `any`, no `object`, no untyped spread onto DOM nodes.
- Loading and error states are part of the component, not an afterthought.

---

## Accessibility

- Interactive elements have an accessible name. Tests query by role and name.
- Focus outlines use `--color-border-strong` and are never removed without a
  visible replacement.
- State is never conveyed by color alone.
- Honor `prefers-reduced-motion`.
