import L from 'leaflet'
import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'

import type { Heatmap } from '@/api/types'
import { LEVEL_COLOR, LEVELS, MAP_COLORS } from '@/risk'

const AREA_OUTLINE = MAP_COLORS.otherRoute

interface Props {
  heatmap: Heatmap
  hour: number
}

/**
 * Corridor weather as a grid of cells, one per forecast point. Cells are drawn once
 * per heatmap and only restyled when the hour changes, so dragging the slider stays cheap.
 */
export function HeatGrid({ heatmap, hour }: Props) {
  const map = useMap()
  const cells = useRef<L.Rectangle[]>([])

  useEffect(() => {
    const { points } = heatmap
    const lons = [...new Set(points.map((p) => p.lon))].sort((a, b) => a - b)
    const lats = [...new Set(points.map((p) => p.lat))].sort((a, b) => a - b)
    const half = Math.min(lons[1] - lons[0] || 0.4, lats[1] - lats[0] || 0.4) / 2

    const group = L.layerGroup()
    cells.current = points.map((p) =>
      L.rectangle(
        [
          [p.lat - half, p.lon - half],
          [p.lat + half, p.lon + half],
        ],
        { stroke: false, fillOpacity: 0, interactive: false },
      ).addTo(group),
    )
    group.addTo(map)
    return () => {
      group.remove()
      cells.current = []
    }
  }, [map, heatmap])

  // Outline where forecast data exists, so a storm cut off at the edge reads as "no data beyond here".
  useEffect(() => {
    const lons = heatmap.points.map((p) => p.lon)
    const lats = heatmap.points.map((p) => p.lat)
    const uniqueLons = [...new Set(lons)].sort((a, b) => a - b)
    const uniqueLats = [...new Set(lats)].sort((a, b) => a - b)
    const half = Math.min(uniqueLons[1] - uniqueLons[0] || 0.4, uniqueLats[1] - uniqueLats[0] || 0.4) / 2
    const outline = L.rectangle(
      [
        [uniqueLats[0] - half, uniqueLons[0] - half],
        [uniqueLats[uniqueLats.length - 1] + half, uniqueLons[uniqueLons.length - 1] + half],
      ],
      { color: AREA_OUTLINE, weight: 1.5, opacity: 0.7, dashArray: '6 6', fill: false, interactive: false },
    ).addTo(map)
    return () => {
      outline.remove()
    }
  }, [map, heatmap])

  useEffect(() => {
    const frame = heatmap.frames[hour]
    if (!frame) return
    cells.current.forEach((cell, i) => {
      const score = frame.score[i]
      cell.setStyle(
        score > 0
          ? { fillColor: LEVEL_COLOR[LEVELS[score]], fillOpacity: 0.18 + score * 0.08 }
          : { fillOpacity: 0 },
      )
    })
  }, [heatmap, hour])

  return null
}
