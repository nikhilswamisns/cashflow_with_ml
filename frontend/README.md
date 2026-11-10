# Gutster cash flow: `/ui2`

React 19 + Vite + TypeScript. Built to `frontend/dist`; FastAPI serves it at `/ui2/` (see `app/main.py`).
Same login and same API as `/ui`. It replaced the older `static_v2/` page at this URL. The server only needs the built files, not Node.

```
npm install
npm run dev          # Vite dev server (API calls need the FastAPI server running)
npm run check        # type-check + lint + tests + build. Run before every commit.
npm run build        # -> dist/
python ../scripts/check_ui2_parity.py [base_url] [runs]   # figures on screen == API, every matrix cell
```

## Layout

```
src/
  main.tsx              bootstrap: fonts, styles, <App/>
  app/                  App.tsx (providers + lazy routes), ErrorBoundary
  shared/               no feature imports allowed (lint enforces it)
    api.ts format.ts theme.tsx toast.tsx
    chart/              Chart.js defaults (base.ts) and colour tokens (tokens.ts)
    styles/             tokens.css (light/dark), base.css, ui.css (card, button, dialog...), index.css (import order)
  features/<name>/      one folder per area of the product
    types.ts            shapes the components use
    api.ts              the ONLY place that knows the server's JSON; maps it to types.ts
    hooks.ts            TanStack Query hooks over api.ts
    *Page.tsx, *.tsx    screens and parts
    <name>.css          styles for this feature only
    runs/               which forecast run is selected (?run=<id> in the URL) + the run list
    shell/              rail, top bar, health banner, layout, nav.ts
    dashboard/ matrix/ revenue/ sync/ config/ chat/
  test/                 setup + renderApp()/stubApi() helpers
```

## Rules

1. **Server shapes stop at `api.ts`.** Components never call `fetch` and never see raw responses.
2. **Server state = TanStack Query.** No `useEffect` + `setState` to load data (the linter blocks it). Use a query and, if a form needs initial values, mount the form once data is in (`key=` or an inner component).
3. **The selected run is the URL.** Read it with `useRun()`; create runs through `afterRun(id)`. Don't keep a copy of it in component state.
4. **Imports:** `@/…` across folders, `./…` inside one. `shared/` never imports from `features/` or `app/`. A feature may use another feature's `types.ts`, `hooks.ts`, `api.ts` and providers, not its internals.
5. **New page:** add `features/<name>/<Name>Page.tsx`, a lazy route in `app/App.tsx`, an entry in `features/shell/nav.ts`. Pages load as separate chunks.
6. **Styles:** shared look goes in `shared/styles`; page-specific CSS lives beside the feature and is imported in `shared/styles/index.css`. Use the CSS variables (`--brand`, `--surface`, `--c-cash`...), never raw colours, so dark mode works. New components may use `*.module.css` (Vite supports it).
7. **Charts:** colour means one thing everywhere (blue cash/rules, amber ML/forecast, green in, rose out). Take colours from `useChartTokens()`. No `any`: Chart.js types are used, and `src/types/chartjs.d.ts` adds our `hideTip` dataset flag.
8. **Never say "Builderflow lacks"-style absolutes about data:** if the server has no value (e.g. a minimum cash floor), the field is `null` and the UI hides the feature instead of inventing one.
9. **Writes need care:** sync, upload, snapshot re-run, opening cash and config save change server data. Test them with a stubbed `fetch` unless you mean to change data.
10. **Tests:** pure logic and mapping (`api.ts`, hooks) get unit tests; interactive pieces get a Testing Library test. `stubApi({'GET /runs': [...]})` fakes the server.

## Known gaps

- The Ask Gutster chat is a placeholder (`features/chat/api.ts`). The AI backend is a separate track.
- `Lowest cash ahead` reads the saved run, as the old page did; on ML-timed runs it can differ from the rules-only low shown in the chart (the parity script prints a NOTE).
