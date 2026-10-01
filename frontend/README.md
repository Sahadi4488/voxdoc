# VoxDoc frontend

React 19 + Vite + Tailwind CSS v4 (configured in `src/index.css` via `@theme`, no config file).

```powershell
npm install
npm run dev      # http://localhost:5173 - needs the backend on http://127.0.0.1:8000
npm run build
npm run lint
```

The API URL for development lives in `.env.development` (`VITE_API_URL`).
