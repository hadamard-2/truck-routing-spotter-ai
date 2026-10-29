import L from 'leaflet'
import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'

import type { Heatmap } from '@/api/types'
import { LEVEL_COLOR, LEVELS } from '@/risk'

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
    const half = heatmap.step_deg / 2

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

  useEffect(() => {
    const frame = heatmap.frames[hour]
    if (!frame) return
    cells.current.forEach((cell, i) => {
      const score = frame.score[i]
      cell.setStyle(
        score != null && score > 0
          ? { fillColor: LEVEL_COLOR[LEVELS[score]], fillOpacity: 0.18 + score * 0.08 }
          : { fillOpacity: 0 },
      )
    })
  }, [heatmap, hour])

  return null
}
