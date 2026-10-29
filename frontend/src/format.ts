const timeFormats = new Map<string | undefined, Intl.DateTimeFormat>()

const dateFormat = new Intl.DateTimeFormat(undefined, { weekday: 'short', month: 'short', day: 'numeric' })

/** "Fri, 9:00 AM CDT", in `timeZone` (an IANA zone) or the browser's own zone. */
export function formatTime(iso: string, timeZone?: string): string {
  let format = timeFormats.get(timeZone)
  if (!format) {
    format = new Intl.DateTimeFormat(undefined, {
      weekday: 'short',
      hour: 'numeric',
      minute: '2-digit',
      timeZoneName: 'short',
      timeZone,
    })
    timeFormats.set(timeZone, format)
  }
  return format.format(new Date(iso))
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

/** Combines a calendar date and an `HH:MM` time into a wall-clock ISO time with no zone, e.g. "2026-10-30T09:00:00". */
export function toWallClockIso(date: Date, time: string): string {
  const day = [date.getFullYear(), date.getMonth() + 1, date.getDate()].map((n) => String(n).padStart(2, '0'))
  return `${day.join('-')}T${time}:00`
}

/** Splits a wall-clock ISO time with no zone back into a calendar date and an `HH:MM` time. */
export function fromWallClockIso(iso: string): { date: Date; time: string } {
  const [day, clock] = iso.split('T')
  const [y, m, d] = day.split('-').map(Number)
  return { date: new Date(y, m - 1, d), time: clock.slice(0, 5) }
}
