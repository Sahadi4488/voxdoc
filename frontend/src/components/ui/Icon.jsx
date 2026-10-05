// Monochrome line icons (1.5px stroke), inline SVG: no icon dependency.
const PATHS = {
  arrowRight: <path d="M5 12h14M13 6l6 6-6 6" />,
  arrowUp: <path d="M12 19V5M6 11l6-6 6 6" />,
  arrowDown: <path d="M12 5v14M6 13l6 6 6-6" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  play: (
    <path
      d="M8 5.5v13a.5.5 0 0 0 .77.42l10-6.5a.5.5 0 0 0 0-.84l-10-6.5A.5.5 0 0 0 8 5.5z"
      fill="currentColor"
      stroke="none"
    />
  ),
  pause: (
    <>
      <rect x="6.5" y="5" width="3.5" height="14" rx="1" fill="currentColor" stroke="none" />
      <rect x="14" y="5" width="3.5" height="14" rx="1" fill="currentColor" stroke="none" />
    </>
  ),
  stop: <rect x="7" y="7" width="10" height="10" rx="1.5" fill="currentColor" stroke="none" />,
  prev: <path d="M6 5v14M19 5.8v12.4a.6.6 0 0 1-.92.5L9.5 12.5a.6.6 0 0 1 0-1L18.08 5.3a.6.6 0 0 1 .92.5z" />,
  next: <path d="M18 5v14M5 5.8v12.4a.6.6 0 0 0 .92.5l8.58-6.2a.6.6 0 0 0 0-1L5.92 5.3a.6.6 0 0 0-.92.5z" />,
  doc: (
    <>
      <path d="M7 3.5h7l4.5 4.5v12a.5.5 0 0 1-.5.5H7a.5.5 0 0 1-.5-.5V4a.5.5 0 0 1 .5-.5z" />
      <path d="M13.5 3.5V8.5h5M9.5 13h6M9.5 16.5h4" />
    </>
  ),
  summary: <path d="M5 6h14M5 10h14M5 14h9M5 18h6" />,
  ask: <path d="M5 18.5V7a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H8.5L5 18.5zM9 9.5h6M9 12.5h4" />,
  settings: (
    <>
      <path d="M4 7h10M18 7h2M4 17h2M10 17h10" />
      <circle cx="16" cy="7" r="2" />
      <circle cx="8" cy="17" r="2" />
    </>
  ),
  sidebar: (
    <>
      <rect x="3.5" y="5" width="17" height="14" rx="2.5" />
      <path d="M9.5 5v14" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4" />
    </>
  ),
  moon: <path d="M19 14.5A7.5 7.5 0 0 1 9.5 5a7.5 7.5 0 1 0 9.5 9.5z" />,
  plus: <path d="M12 5v14M5 12h14" />,
  wave: <path d="M4 12h1M7.5 9v6M11 6v12M14.5 8.5v7M18 10.5v3M20.5 12h-.5" />,
  speaker: (
    <>
      <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" />
      <path d="M15.5 9a4.5 4.5 0 0 1 0 6M18 6.5a8 8 0 0 1 0 11" />
    </>
  ),
  voice: <path d="M12 4a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V7a3 3 0 0 1 3-3zM6 11.5a6 6 0 0 0 12 0M12 17.5V20" />,
  book: <path d="M12 6.5C10.5 5.3 8.3 4.8 5 5v13c3.3-.2 5.5.3 7 1.5 1.5-1.2 3.7-1.7 7-1.5V5c-3.3-.2-5.5.3-7 1.5zM12 6.5v13" />,
  spark: <path d="M12 4v4M12 16v4M4 12h4M16 12h4M7 7l2 2M15 15l2 2M7 17l2-2M15 9l2-2" />,
  send: <path d="M12 19V6M6.5 11.5L12 6l5.5 5.5" />,
}

export default function Icon({ name, size, className = '', ...rest }) {
  const sizeClass = size === 'sm' ? 'vd-icon--sm' : size === 'lg' ? 'vd-icon--lg' : ''
  return (
    <svg
      className={`vd-icon ${sizeClass} ${className}`.trim()}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {PATHS[name]}
    </svg>
  )
}
