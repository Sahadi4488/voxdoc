# VoxDoc frontend

React 19 + Vite, styled with plain CSS: `src/styles/voxdoc.css` holds the design tokens
(light and dark) and every component style, all classes prefixed `vd-`. Fonts (Geist,
Newsreader) are self-hosted from `src/assets/fonts`.

```powershell
npm ci
npm run dev      # http://localhost:5173; Vite proxies /api to the backend on http://127.0.0.1:8000
npm run build
npm run lint
```

- `src/components/landing`: the landing page (navbar, hero, features, how it works, voices)
- `src/components/upload`: the floating upload sheet
- `src/components/reader`: the reader (layout, sidebar, document, player, summary, Ask panel)
- `src/hooks`: the app logic (player, document, voices and preferences, summary, theme)
