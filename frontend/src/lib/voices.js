const ACCENTS = { US: 'American', UK: 'British' }

/** "Everyday reading · American": a preset's character, short enough for a menu row */
export function voiceDescription(preset) {
  return [preset.use, ACCENTS[preset.accent] ?? preset.accent].filter(Boolean).join(' · ')
}
