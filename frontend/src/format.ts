const timeFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
})

const dateFormat = new Intl.DateTimeFormat(undefined, { weekday: 'short', month: 'short', day: 'numeric' })

export function formatTime(iso: string): string {
  return timeFormat.format(new Date(iso))
}

export function formatDate(date: Date): string {
  return dateFormat.format(date)
}

export function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h ? `${h} h ${m} min` : `${m} min`
}

export function formatMiles(miles: number): string {
  return `${Math.round(miles).toLocaleString()} mi`
}

export function formatWeight(lb: number): string {
  return `${lb.toLocaleString()} lb`
}

/** The next full hour in local time, split into a calendar date and an `HH:MM` time. */
export function nextHour(): { date: Date; time: string } {
  const d = new Date()
  d.setHours(d.getHours() + 1, 0, 0, 0)
  const time = `${String(d.getHours()).padStart(2, '0')}:00`
  d.setHours(0, 0, 0, 0)
  return { date: d, time }
}

/** Combines a local calendar date and an `HH:MM` local time into a UTC ISO string. */
export function toUtcIso(date: Date, time: string): string {
  const [h, m] = time.split(':').map(Number)
  const d = new Date(date)
  d.setHours(h, m, 0, 0)
  return d.toISOString().replace(/\.\d{3}Z$/, 'Z')
}
