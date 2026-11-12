# Frontend UX Audit

## Summary

The current React frontend already has the right product logic and route structure, but the experience feels unfinished and inconsistent. The main issues are not in the prediction engine or backend APIs—they are in hierarchy, messaging, visual polish, and the way each page guides first-time users.

## Major UX problems

### 1) Typography feels inconsistent and under-designed
- The app mixes generic system fonts without a clear English/Persian strategy.
- Heading scale is uneven across landing, dashboard, and workspace pages.
- Several labels and callouts feel visually noisy or too small for a premium product.
- Numeric information, especially prices and model metadata, does not consistently use a consistent reading rhythm.

### 2) Navigation is functional but not intuitive
- The workspace sidebar contains a reasonable structure but the active state and calling hierarchy are not strong enough.
- The "chat" feature is present as a navigation item even though it is unavailable, which creates false expectations.
- The top bar and page titles are usable but do not clearly reinforce the product's primary task: creating and understanding estimates.

### 3) First-time user guidance is weak
- A new visitor can understand the app only after reading multiple sections.
- The product promise is not immediate enough on first load.
- The user is not clearly told what is required, what a model estimate means, or where the saved results appear.

### 4) Visual hierarchy does not emphasize the core task
- The dashboard and prediction screens contain a lot of content, but the primary action and the estimate itself are not always the strongest focal point.
- Secondary information competes with the main estimate rather than supporting it.
- The MAE reference range is important, but it needs clearer emphasis and explanation.

### 5) The design system is too loose and inconsistent
- Inputs, cards, buttons, and neutral surfaces vary in tone and spacing.
- The app has the right warm palette, but it needs more deliberate semantic styling and clearer interaction states.
- Several cards do not feel premium; they read more like a generic dashboard demo than a serious automotive platform.

### 6) Mobile usability needs refinement
- The workspace and auth layouts work, but the mobile experience still feels more crowded than necessary.
- Compact forms and dense tables can become harder to scan on narrow screens.
- The mobile drawer needs clearer spacing and stronger visual feedback.

### 7) Accessibility and clarity are mostly good but need stronger polish
- The app already has focus states and form labels, which is a strong start.
- However, several text patterns and status messages need better clarity and stronger contrast in dense UI contexts.
- The system should avoid assuming currency or prediction guarantees; the UI should keep uncertainty visible and readable.

## Redesign priorities

1. Establish a stronger premium automotive visual language with a clear design system.
2. Improve typography and spacing consistency across every page and component.
3. Simplify the user journey: landing -> sign in -> create estimate -> understand result -> save/history review.
4. Make the estimate the dominant object in both dashboard and prediction flows.
5. Clarify the product scope: Peugeot 206 only, six inputs, result is an estimate, not a guarantee.
6. Make the mobile experience more breathable without removing functionality.
7. Keep the unavailable chat feature explicitly coming soon, without misrepresenting AI availability.

## Planned improvements implemented

- Unified typography with Inter + Vazirmatn.
- Centralized semantic color tokens and more consistent focus, hover, and state styling.
- Stronger landing-page messaging and clearer call-to-action flow.
- More consistent workspace navigation and stronger page hierarchy.
- Improved input form clarity and result emphasis.
- Cleaner dashboard and prediction result presentation while preserving the existing model behavior.
- Better mobile spacing and responsive behavior.
- Clearer product caveats for the estimate and reference range. 

