# Frontend and UI/UX Context for AI Assistants

This document is a handoff for ChatGPT or another AI assistant helping with the **frontend, product design, or UI/UX** of this project. It describes the current interface and technical context so future prompts can refer to the real application instead of a generic car-pricing website.

## Copy-and-paste prompt

Attach or paste this document into a new conversation, then use:

```text
I am working on the existing Peugeot 206 Price Prediction Platform described in the attached Frontend and UI/UX Context document. Read it first and use it as the source of truth for the current interface, routes, design system, and product limitations.

My task is:
[Describe the exact page, user problem, and desired outcome.]

Before changing anything:
- Inspect the relevant existing React components, styles, tests, and current behavior.
- Keep the requested work focused; do not redesign unrelated screens or remove working features.
- Reuse the current design tokens, components, icons, and dependencies where practical.
- Preserve existing routes, authentication, API behavior, form validation, and prediction calculations unless I explicitly request a behavior change.
- Do not imply that the model supports other cars, that its output unit is known, or that its estimate is guaranteed.
- Check keyboard and screen-reader accessibility, English/Persian readability, and responsive layouts.
- Run the relevant frontend tests, lint, and build; report any limitation if a check cannot run.

At the end, summarize the visible result, files changed, and checks performed.
```

## The product and its UI goal

This is a web application for estimating the numeric `price` field of used **Peugeot 206** listings. A signed-in user enters vehicle details and receives an estimate from a saved Linear Regression model. The central product task is creating and understanding an estimate—not browsing a broad inventory marketplace.

The interface also supports account access, personal prediction history, comparing saved predictions, and profile management. A conversation destination is visible, but the frontend currently treats AI conversations as **coming soon**. It must not look like a functioning chatbot or invent assistant responses.

Design priorities, in order:

1. Make the prediction result and its context easy to find and understand.
2. Make navigation, forms, and all text comfortable to read and operate.
3. Keep the product feeling like a polished, trustworthy automotive tool.
4. Preserve clarity and accessibility across desktop and small mobile screens.

## Frontend technology and files

The frontend is a Vite application using React 19 and TypeScript. It uses React Router for routes, TanStack Query for server state, React Hook Form and Zod for forms/validation, Recharts for the prediction history chart, and Lucide React for icons. Tailwind CSS v4 is installed, while most current page styling is expressed in the shared CSS files.

| File/location | Purpose |
|---|---|
| `frontend/src/App.tsx` | Route definitions, auth context, desktop/mobile workspace shell, and the page components. |
| `frontend/src/App.css` | Main component styles, layouts, visual states, and responsive breakpoints. |
| `frontend/src/index.css` | Global styles, theme tokens, font stack, and keyboard focus styles. |
| `frontend/src/components/PredictionHistoryChart.tsx` | Lazy-loaded prediction history chart. |
| `frontend/src/services/api.ts` | Frontend API client and in-memory access-token handling. |
| `frontend/src/services/featureValidation.ts` | Validation schema derived from model-provided feature metadata. |
| `frontend/src/types.ts` | Frontend API and domain types. |
| `frontend/src/App.test.tsx` | Frontend route, authentication, chat-unavailable, and prediction-flow tests. |
| `frontend/public/peugeot-206-model.webp` | Local WebP photograph used on the model-information page. |

The root `README.md` documents how to run the frontend and the project. Make changes in the existing frontend structure; do not add packages or move to another framework for ordinary design tasks.

## Current pages and user journeys

### Public pages

- **`/` — Landing page.** Public brand/navigation bar, a two-column hero, estimator positioning and calls to action, a stylized “206 / Peugeot” scope graphic, three short process steps, and a footer. The landing visual is a graphic, **not a car photograph**.
- **`/model` — Model information.** Public navigation, a photo-led Peugeot 206 hero, scope/model summary cards, inference-flow steps, historical evaluation caveats, verified input reference, and limitations. The real vehicle photo is stored locally as WebP and visibly credited to Vauxford under CC BY-SA 4.0.
- **`/login` and `/register` — Authentication.** Shared form and an editorial two-column layout. The green aside uses a large typographic “206” motif and model facts; it is **not currently a car photograph**. Registration does not automatically sign in.

### Authenticated workspace

Unauthenticated users are redirected from workspace pages to `/login`. Authenticated pages share the `AppShell`:

- Desktop: fixed left sidebar with brand, workspace links, “How it works,” privacy note, signed-in user, and logout; top bar with breadcrumb, active-model badge, and profile shortcut.
- Mobile: collapsible sidebar opened by a menu button, with a backdrop and close-on-navigation behavior; the full desktop sidebar becomes a drawer.
- **`/dashboard` — Dashboard.** Welcome/action row, large “Latest estimate” panel, account/model summary cards, prediction history chart, recent estimates, and scope/conversation notices. The estimate card is intended to be a focal point. It also labels AI chat unavailable.
- **`/predict` — Prediction form and result.** Inputs are created dynamically from model feature metadata. The user submits the six verified fields. The result view prominently presents the estimate, the MAE-based reference range, source-unit caveat, saved status, timestamp, history link, and appraisal disclaimer.
- **`/predictions/history` — History.** Sortable/paginated personal predictions with vehicle details and actions to inspect, reuse inputs, delete an item, or clear history.
- **`/compare` — Comparison.** Compare selected saved estimates and their vehicle inputs.
- **`/profile` — Profile.** User information and account/security controls.
- **`/chat` and `/chat/:conversationId` — Unavailable conversation feature.** Show an explicit coming-soon state rather than a chat transcript/composer or simulated AI.

Page components currently live in `App.tsx`; inspect their implementation before extracting or redesigning them. Prefer focused changes over an application-wide rewrite.

## Current visual system

The interface uses a restrained warm-neutral and forest-green palette. Reuse the CSS custom properties defined in `frontend/src/index.css`:

| Token | Current value | Typical role |
|---|---|---|
| `--ink` | `#1d2722` | Primary text |
| `--text-muted` | `#4c5a51` | Secondary text |
| `--text-subtle` | `#5a665e` | Subtle text |
| `--line` | `#dedbd2` | Borders and separators |
| `--surface` | `#fffdfa` | Cards and form surfaces |
| `--surface-soft` | `#f0ede6` | Soft backgrounds |
| `--surface-hover` | `#e9e4da` | Hover surfaces |
| `--page` | `#f5f2eb` | Warm page background |
| `--forest` | `#183b32` | Primary brand/action color |
| `--forest-hover` | `#244e41` | Primary hover |
| `--forest-muted` | `#355548` | Secondary green text/icons |
| `--accent` | `#bd7040` | Restrained bronze accent/focus |
| `--accent-soft` | `#f5e8dc` | Soft accent surface |

Typography currently uses `Inter, "Segoe UI", Tahoma, "Noto Sans Arabic", system-ui, sans-serif`, with a global 16px base size and 1.6 line height. There are no bundled font files. Preserve natural Persian shaping and use appropriate RTL direction/alignment when working with Persian content; do not assume that English-only letter spacing looks good on Persian text.

The design uses clear headings, quiet borders, moderate corner radii, green primary buttons, bronze focus indicators, subtle hover/motion, and reduced-motion support. Keep the visual language consistent; avoid excessive gradients, heavy shadows, tiny labels, decorative card proliferation, or overly bold type.

## Prediction UX and important product caveat

The estimate is the application's primary output. Keep it visually dominant on dashboard and prediction screens, with the horizontal reference bar immediately below the estimated value. The bar communicates lower and upper MAE reference values around the prediction and includes a caption saying it is not a guaranteed prediction interval.

The current frontend constant is `PRICE_REFERENCE_MAE_TOMAN = 116_716_294` in `frontend/src/App.tsx`. This was supplied as the initial MAE reference by the project owner. **The source data/backend do not document the target currency denomination**, while the current range caption and endpoint labels say “Toman.” Treat that as a known product-content discrepancy: do not silently change prediction logic or claim the backend verified the unit. If a task asks to change displayed currency or resolve this discrepancy, call it out and make the requested content decision explicitly.

The model uses six raw fields: `year`, `mileage`, `trim`, `transmission`, `body_status`, and `color`. Feature labels/options are fetched from the API, and some values are Persian. The current model is trained on 764 historical Peugeot 206 listings; this does not establish support for other cars or current-market accuracy. Year calendar, mileage unit, and source price denomination are unspecified. Do not frame the result as a guaranteed market price, professional appraisal, confidence score, or confidence interval.

## Responsive layout and accessibility

`App.css` has responsive breakpoints around 1100px, 920px, 800px, 600px, and 380px. Important behavior includes the mobile workspace drawer, stacked landing/auth layouts, reduced-column summary cards, full-width mobile forms, and the model hero photo moving into a content image on small screens.

When modifying UI:

- Check the actual relevant screen at desktop and narrow mobile widths; aim for no horizontal page overflow or clipped navigation/content.
- Keep controls comfortable to tap and text readable without forcing a desktop layout into a narrow viewport.
- Preserve semantic elements, accessible labels, focus-visible outlines, keyboard access, and reduced-motion support.
- Give images meaningful alt text (or mark them decorative when appropriate); keep the model photo credit visible and linked.
- Use active, hover, disabled, loading, error, and empty states consistently.
- Preserve Persian values exactly when they are form values sent to the API. Apply directionality to the appropriate text instead of changing data.

## Small amount of backend/model context that affects the UI

The UI talks to a FastAPI backend through `frontend/src/services/api.ts`. Protected routes rely on account authentication; predictions and history are per-user. The prediction form's labels, supported values, and observed numeric bounds come from the model feature metadata endpoint. Inspect the existing client/service/types before changing request or response behavior.

The saved Linear Regression estimator is paired with a fitted preprocessor in `ml/artifacts/`; the backend applies that preprocessing for the UI's six raw fields. Frontend design work should not modify model artifacts or prediction calculations. Alembic files under `backend/migrations/versions/` are persistent schema history: never rewrite an applied migration or reset/delete database volumes for a UI request.

## Prompt examples

Use the context above, then describe one concrete task:

- “Improve the dashboard's latest-estimate panel at mobile widths. Keep the estimate largest, retain its range and caveat, and do not alter its calculation.”
- “Review the sidebar and mobile navigation for spacing, active states, keyboard access, and overflow. Make focused changes using the current palette.”
- “Improve readability of the dynamic prediction form, including Persian select options. Preserve feature values sent to the API.”
- “Improve the model-page photo hero on phones. Keep the local image and visible attribution.”
- “Make the coming-soon conversation state clearer without adding chat controls or suggesting an AI is connected.”

Always include the specific page, desired behavior/visual outcome, viewport or accessibility requirements, and anything that must remain unchanged.
