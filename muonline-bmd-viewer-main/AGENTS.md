# Repository Guidelines

## Project Structure & Module Organization
`src/` contains the TypeScript application code for the viewer. Core loaders and app entrypoints live at the top level, while domain-specific logic is grouped in folders such as `src/terrain/`, `src/utils/`, `src/helpers/`, and `src/crypto/`. Desktop packaging code lives in `electron/` (`main.js`, `preload.js`). Tests live in `tests/` and include both `.test.ts` files and binary fixtures such as `.bmd` samples. Build output goes to `dist/`; installer artifacts go to `release/`. Reference material lives in `muonline/` and `docs/`.

## Build, Test, and Development Commands
Use `npm run dev` to start the Vite dev server for browser work. Use `npm run electron` to run the Electron shell against the local Vite server. Use `npm run build` to generate a production web build in `dist/`. Use `npm run electron:build` to package the desktop app with `electron-builder`. Run `npm test` to execute the Jest suite with `ts-jest`.

## Coding Style & Naming Conventions
This project uses strict TypeScript (`strict: true`) with CommonJS output for tests and tooling. Follow the existing style: 4-space indentation, semicolons, single quotes, and explicit type imports where helpful. Use `PascalCase` for classes and scene modules (`TerrainScene`), `camelCase` for functions and variables, and descriptive filenames ending in `.test.ts` for tests. Keep new code feature-focused; prefer adding logic to `src/terrain/` or `src/utils/` instead of growing `src/main.ts` unnecessarily. No formatter or linter is currently wired in, so match surrounding code closely.

## Testing Guidelines
Jest is the active test runner, configured in `jest.config.js` with the Node environment. Add unit tests alongside the existing patterns in `tests/`, for example `tests/TerrainExplorerUtils.test.ts`. Reuse fixture files in `tests/` for loader and parser coverage instead of duplicating binary assets. Target meaningful coverage for loaders, parsing, and state-management changes before opening a PR.

## Commit & Pull Request Guidelines
Recent history uses Conventional Commit style, especially `feat: ...`. Follow the same format for all changes, for example `fix: handle missing terrain texture fallback`. Keep pull requests focused and include: a short summary, testing notes (`npm test`, Electron smoke test), and screenshots or short recordings for viewer UI changes.

## Configuration & Asset Tips
Do not commit secrets or machine-specific absolute paths. Large MU Online assets should stay out of source unless they are required as small test fixtures. When adding new sample models or textures, document where they are used and keep names stable so tests and manual QA remain reproducible.
