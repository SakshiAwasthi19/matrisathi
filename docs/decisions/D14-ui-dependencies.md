# D14: UI dependencies

**Status:** Approved by the developer on 2026-11-07 (as `CLAUDE.md` requires for new dependencies). **Manager:** informed at the Saturday 14 Nov review. **Written:** 2026-11-07 (W1-B8).
**Used by:** W1-B7 (UI foundation), and W5-B2 for the PWA plugin.

## The question

Which libraries does the web app adopt for its UI foundation?

## Today

`apps/web/package.json` has only `react` and `react-dom` at runtime. Routing is hand-written hash routing in `App.tsx`. Styling is inline. There is no translation setup.

## Approved list (build plan Part G)

| Library | Purpose | When |
|---|---|---|
| Tailwind CSS | Styling and design tokens | W1-B7 |
| shadcn/ui components, built on Radix | Accessible form, dialog and menu components | W1-B7 |
| react-router | Real URLs instead of hash routing | W1-B7 |
| @tanstack/react-query | Server data caching, wrapping the existing `api/client.ts` | W1-B7 |
| react-i18next | All screen text in translation files; English plus one more language | W1-B7 |
| lucide-react | Icons (every status shows an icon plus a word) | W1-B7 |
| Noto Sans fonts | One font family covering Indian scripts | W1-B7 |
| vite-plugin-pwa | Installable app with offline drafts | W5-B2 only |

## Conditions

- **Exact versions** pinned in `package.json` (no `^` or `~`), recorded in the W1-B7 PR.
- **Bundle size** reported in W1-B7 (main JS, gzipped). Flag anything over 250 KB.
- **Second language:** D02 is open, so W1-B7 sets up English plus one **empty** locale file. No language is assumed.
- The existing API client behaviour (retries, idempotency keys, session refresh) and its tests stay unchanged.

## Companion packages (approved by the developer on 2026-11-07)

These come with the approved items in practice. Listed so nothing is installed silently. The developer approved items 1–4, including bundling the font files, on 2026-11-07:

1. **shadcn/ui helper packages.** shadcn/ui is not a package; its generated components import small helpers: `class-variance-authority`, `clsx`, `tailwind-merge`, plus one `@radix-ui/react-*` package per component used.
2. **Tailwind's Vite plugin** (`@tailwindcss/vite`), the standard way to wire Tailwind into Vite.
3. **`i18next`** itself, which `react-i18next` requires.
4. **How the Noto Sans fonts are delivered.** Recommended: bundle the font files with the app (for example the `@fontsource` packages) rather than loading them from Google's servers, so the app makes no third-party request and works on weak networks once cached.
5. Anything else that turns up during W1-B7: it stops and asks.

## Recommendation

Keep the approval, including items 1–4.

## For the manager

Nothing to decide unless you object. Raise any objection at the 14 Nov review, before W1-B7 merges.
