import { useSyncExternalStore } from 'react'

/**
 * The time slider's position, in hours after departure. The slider, heatmap and truck marker
 * subscribe to it directly, so moving it re-renders only them, not the whole app.
 */
export interface Playhead {
  get: () => number
  set: (hour: number) => void
  subscribe: (listener: () => void) => () => void
}

export function createPlayhead(): Playhead {
  let hour = 0
  const listeners = new Set<() => void>()
  return {
    get: () => hour,
    set: (next) => {
      if (next === hour) return
      hour = next
      listeners.forEach((listener) => listener())
    },
    subscribe: (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
  }
}

export function usePlayhead(playhead: Playhead): number {
  return useSyncExternalStore(playhead.subscribe, playhead.get)
}
