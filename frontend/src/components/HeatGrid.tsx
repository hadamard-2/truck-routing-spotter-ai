import L from 'leaflet'
import { useEffect, useMemo, useRef } from 'react'
import { useMap } from 'react-leaflet'

import type { Heatmap, HeatmapFrame } from '@/api/types'
import type { Playhead } from '@/lib/playhead'
import { usePlayhead } from '@/lib/playhead'
import { LEVEL_COLOR, LEVELS } from '@/risk'

// Its own pane between the basemap (200) and the routes (400), so routes always draw on top.
const PANE = 'heatmap'
const PANE_Z_INDEX = '350'
// Low is a faint tint so the area with a forecast shows; each level above it is more opaque.
const LOW_ALPHA = 0.12
const BASE_ALPHA = 0.3
const ALPHA_PER_LEVEL = 0.12

const LEVEL_RGB = LEVELS.map((level) => {
  const hex = LEVEL_COLOR[level]
  return [1, 3, 5].map((i) => Number.parseInt(hex.slice(i, i + 2), 16))
})

interface Layout {
  cols: number
  rows: number
  /** Pixel of each point in the image, aligned with `points`. */
  pixels: number[]
  bounds: L.LatLngBoundsLiteral
}

/** One image pixel per grid cell, north at the top. */
function layout({ points, step_deg: step }: Heatmap): Layout {
  const lons = points.map((p) => p.lon)
  const lats = points.map((p) => p.lat)
  const [minLon, maxLon, minLat, maxLat] = [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)]
  const cols = Math.round((maxLon - minLon) / step) + 1
  const rows = Math.round((maxLat - minLat) / step) + 1
  const half = step / 2
  return {
    cols,
    rows,
    pixels: points.map((p) => Math.round((maxLat - p.lat) / step) * cols + Math.round((p.lon - minLon) / step)),
    bounds: [
      [minLat - half, minLon - half],
      [maxLat + half, maxLon + half],
    ],
  }
}

/** RGBA per point (alpha 0–1); a point with no forecast is transparent. */
function frameColors(frame: HeatmapFrame): Float32Array {
  const colors = new Float32Array(frame.score.length * 4)
  frame.score.forEach((score, i) => {
    const [r, g, b] = LEVEL_RGB[score ?? 0]
    const alpha = score == null ? 0 : score === 0 ? LOW_ALPHA : BASE_ALPHA + score * ALPHA_PER_LEVEL
    colors.set([r, g, b, alpha], i * 4)
  })
  return colors
}

/** Paints `hour`, blending the frames either side of it so the map changes smoothly between hours. */
function paint(canvas: HTMLCanvasElement, { cols, rows, pixels }: Layout, frames: Float32Array[], hour: number) {
  const last = frames.length - 1
  const h = Math.min(Math.max(hour, 0), last)
  const before = frames[Math.floor(h)]
  const after = frames[Math.min(Math.floor(h) + 1, last)]
  const t = h - Math.floor(h)
  const context = canvas.getContext('2d')
  if (!context) return
  const image = context.createImageData(cols, rows)
  pixels.forEach((pixel, i) => {
    for (let k = 0; k < 4; k++) {
      const value = before[i * 4 + k] * (1 - t) + after[i * 4 + k] * t
      image.data[pixel * 4 + k] = k < 3 ? value : value * 255
    }
  })
  context.putImageData(image, 0, 0)
}

interface Props {
  heatmap: Heatmap
  playhead: Playhead
}

/**
 * Corridor weather as one small image, a pixel per forecast point, that the browser smooths as it
 * scales it over the map. Moving the slider repaints only those few hundred pixels.
 */
export function HeatGrid({ heatmap, playhead }: Props) {
  const map = useMap()
  const hour = usePlayhead(playhead)
  const grid = useMemo(() => layout(heatmap), [heatmap])
  const frames = useMemo(() => heatmap.frames.map(frameColors), [heatmap])
  const canvas = useMemo(() => Object.assign(document.createElement('canvas'), { width: grid.cols, height: grid.rows }), [grid])
  const overlay = useRef<L.ImageOverlay | null>(null)

  useEffect(() => {
    if (!map.getPane(PANE)) {
      const pane = map.createPane(PANE)
      pane.style.zIndex = PANE_Z_INDEX
      pane.style.pointerEvents = 'none'
    }
    const layer = L.imageOverlay(canvas.toDataURL(), grid.bounds, { pane: PANE, interactive: false }).addTo(map)
    overlay.current = layer
    return () => {
      layer.remove()
      overlay.current = null
    }
  }, [map, grid, canvas])

  useEffect(() => {
    paint(canvas, grid, frames, hour)
    overlay.current?.setUrl(canvas.toDataURL())
  }, [canvas, grid, frames, hour])

  return null
}
