/** "7 seconds", "1 second", "3 minutes": how long a 429 says to wait. */
export function formatWait(seconds) {
  if (seconds < 90) return `${seconds} second${seconds === 1 ? '' : 's'}`
  return formatMinutes(seconds)
}

/** Always in minutes, rounded up: "1 minute", "10 minutes". */
export function formatMinutes(seconds) {
  const minutes = Math.max(1, Math.ceil(seconds / 60))
  return `${minutes} minute${minutes === 1 ? '' : 's'}`
}
