import L from 'leaflet'
import { FlagIcon, MapPinIcon } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  CircleMarker,
  MapContainer,
  Marker,
  Polyline,
  Popup,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from 'react-leaflet'

import { reversePlace } from '@/api/client'
import type { Checkpoint, Heatmap, Place, Plan } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { Separator } from '@/components/ui/separator'
import { formatTime } from '@/format'
import { cn } from '@/lib/utils'
import { LEVEL_BG, LEVEL_COLOR, LEVEL_LABEL, LOAD_RULE_TEXT, MAP_COLORS, UNKNOWN_COLOR, positionAt } from '@/risk'
import { HeatGrid } from './HeatGrid'
import { MapControls } from './MapControls'

interface Props {
  plan: Plan | null
  selectedId: string | null
  onSelect: (id: string) => void
  heatmap: Heatmap | null
  showHeatmap: boolean
  hour: number
  isExpanded: boolean
  onToggleExpanded: () => void
  /** Called when the user chooses a clicked point as the trip's start or end. */
  onPick: (field: PlaceField, place: Place) => void
  /** Points picked for the next plan, shown until it is planned. */
  draft: Partial<Record<PlaceField, Place>>
}

type PlaceField = 'origin' | 'destination'

const US_CENTER: [number, number] = [39.5, -98.35]
const truckIcon = L.divIcon({ className: 'truck-marker', html: '<span></span>', iconSize: [18, 18] })

/** Leaflet measures its container once; re-measure when the layout changes size or visibility. */
function TrackContainerSize() {
  const map = useMap()
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize())
    observer.observe(map.getContainer())
    return () => observer.disconnect()
  }, [map])
  return null
}

function FitToPlan({ plan }: { plan: Plan | null }) {
  const map = useMap()
  useEffect(() => {
    if (!plan) return
    const [minLon, minLat, maxLon, maxLat] = plan.corridor_bbox
    map.fitBounds(
      [
        [minLat, minLon],
        [maxLat, maxLon],
      ],
      // On wide screens the time slider floats over the bottom of the map.
      window.matchMedia('(min-width: 1024px)').matches
        ? { paddingTopLeft: [32, 32], paddingBottomRight: [32, 180] }
        : { padding: [16, 16] },
    )
  }, [map, plan])
  return null
}

/** Clicking the map offers to use that point as the start or end of the trip. */
function MapPicker({ onPick }: { onPick: Props['onPick'] }) {
  const [point, setPoint] = useState<L.LatLng | null>(null)
  const [busy, setBusy] = useState<PlaceField | null>(null)
  const lastPopupClose = useRef(0)

  useMapEvents({
    // A click that only closes an open popup should not open the picker as well.
    popupclose: () => {
      lastPopupClose.current = Date.now()
    },
    click: (e) => {
      if (Date.now() - lastPopupClose.current < 300) return
      setPoint(e.latlng)
    },
  })

  async function choose(field: PlaceField) {
    if (!point) return
    setBusy(field)
    const { lat, lng } = point
    const place = await reversePlace(lat, lng).catch(() => ({ name: `${lat.toFixed(4)}, ${lng.toFixed(4)}`, lat, lon: lng }))
    onPick(field, place)
    setBusy(null)
    setPoint(null)
  }

  if (!point) return null
  return (
    <Popup position={point} eventHandlers={{ remove: () => setPoint(null) }}>
      <div className="flex flex-col gap-2 font-sans">
        <span className="text-xs text-muted-foreground tabular-nums">
          {point.lat.toFixed(4)}, {point.lng.toFixed(4)}
        </span>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" disabled={busy !== null} onClick={() => choose('origin')}>
            {busy === 'origin' ? <Spinner data-icon="inline-start" /> : <MapPinIcon data-icon="inline-start" />}
            Start here
          </Button>
          <Button size="sm" variant="outline" disabled={busy !== null} onClick={() => choose('destination')}>
            {busy === 'destination' ? <Spinner data-icon="inline-start" /> : <FlagIcon data-icon="inline-start" />}
            End here
          </Button>
        </div>
      </div>
    </Popup>
  )
}

function CheckpointPopup({ checkpoint }: { checkpoint: Checkpoint }) {
  const { weather, levels, level, load_rule } = checkpoint
  const rows = weather && levels
    ? [
        { name: 'Wind', value: `${weather.wind_mph} mph, gusts ${weather.gust_mph}`, level: levels.wind },
        { name: 'Rain', value: `${weather.rain_in_hr} in/hr`, level: levels.rain },
        { name: 'Snow', value: `${weather.snow_in_hr} in/hr`, level: levels.snow },
      ]
    : []
  return (
    <div className="flex min-w-56 flex-col gap-2 font-sans text-xs text-foreground tabular-nums">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium">Mile {Math.round(checkpoint.mile)}</span>
        <Badge variant="outline" className="gap-1.5">
          <span className={cn('size-2 rounded-full', level ? LEVEL_BG[level] : 'bg-risk-unknown')} aria-hidden />
          {level ? LEVEL_LABEL[level] : 'No forecast'}
        </Badge>
      </div>
      <span className="text-muted-foreground">Arrive {formatTime(checkpoint.eta)}</span>
      <Separator />
      {rows.length > 0 ? (
        <dl className="grid grid-cols-[auto_1fr_auto] items-center gap-x-3 gap-y-1">
          {rows.map((row) => (
            <div key={row.name} className="contents">
              <dt className="text-muted-foreground">{row.name}</dt>
              <dd>{row.value}</dd>
              <dd className="flex items-center gap-1.5 text-muted-foreground">
                <span className={cn('size-1.5 rounded-full', LEVEL_BG[row.level])} aria-hidden />
                {LEVEL_LABEL[row.level]}
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <span>This checkpoint is past the end of the forecast.</span>
      )}
      {load_rule && <p className="font-medium text-destructive">{LOAD_RULE_TEXT[load_rule] ?? load_rule}</p>}
    </div>
  )
}

export function MapView({
  plan,
  selectedId,
  onSelect,
  heatmap,
  showHeatmap,
  hour,
  isExpanded,
  onToggleExpanded,
  onPick,
  draft,
}: Props) {
  const routes = plan?.routes ?? []
  const selected = routes.find((r) => r.id === selectedId) ?? null
  const others = routes.filter((r) => r.id !== selectedId)

  const lines = useMemo(
    () =>
      Object.fromEntries(
        (plan?.routes ?? []).map((r) => [r.id, r.geometry.coordinates.map(([lon, lat]) => [lat, lon])]),
      ) as Record<string, [number, number][]>,
    [plan],
  )

  const truck = useMemo(() => {
    if (!plan || !selected) return null
    return positionAt(selected.checkpoints, Date.parse(plan.departure_time) + hour * 3_600_000)
  }, [plan, selected, hour])

  return (
    <MapContainer
      center={US_CENTER}
      zoom={4}
      // Half-level steps for the buttons and slower wheel zoom, so zooming is easier to control.
      zoomSnap={0.25}
      zoomDelta={0.5}
      wheelPxPerZoomLevel={120}
      preferCanvas
      className="size-full"
      zoomControl={false}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <TrackContainerSize />
      <MapControls isExpanded={isExpanded} onToggleExpanded={onToggleExpanded} />
      <FitToPlan plan={plan} />
      <MapPicker onPick={onPick} />
      {heatmap && showHeatmap && <HeatGrid heatmap={heatmap} hour={hour} />}

      {others.map((r) => (
        <Polyline
          key={r.id}
          positions={lines[r.id]}
          pathOptions={{ color: MAP_COLORS.otherRoute, weight: 4, opacity: 0.5 }}
          bubblingMouseEvents={false}
          eventHandlers={{ click: () => onSelect(r.id) }}
        >
          <Tooltip sticky>{r.label}</Tooltip>
        </Polyline>
      ))}

      {selected && (
        <>
          <Polyline
            positions={lines[selected.id]}
            pathOptions={{ color: '#fff', weight: 8, opacity: 0.9 }}
            bubblingMouseEvents={false}
          />
          <Polyline positions={lines[selected.id]} pathOptions={{ color: MAP_COLORS.route, weight: 4 }} bubblingMouseEvents={false} />
          {selected.checkpoints.map((c) => (
            <CircleMarker
              key={`${selected.id}-${c.index}`}
              center={[c.lat, c.lon]}
              radius={c.level === 'low' ? 4 : 6}
              bubblingMouseEvents={false}
              pathOptions={{
                color: '#fff',
                weight: 1.5,
                fillColor: c.level ? LEVEL_COLOR[c.level] : UNKNOWN_COLOR,
                fillOpacity: 1,
              }}
            >
              <Popup>
                <CheckpointPopup checkpoint={c} />
              </Popup>
            </CircleMarker>
          ))}
        </>
      )}

      {plan && (
        <>
          <CircleMarker
            center={[plan.origin.lat, plan.origin.lon]}
            radius={7}
            pathOptions={{ color: MAP_COLORS.route, weight: 3, fillColor: '#fff', fillOpacity: 1 }}
            bubblingMouseEvents={false}
          >
            <Tooltip>{plan.origin.name}</Tooltip>
          </CircleMarker>
          <CircleMarker
            center={[plan.destination.lat, plan.destination.lon]}
            radius={7}
            pathOptions={{ color: '#fff', weight: 3, fillColor: MAP_COLORS.brand, fillOpacity: 1 }}
            bubblingMouseEvents={false}
          >
            <Tooltip>{plan.destination.name}</Tooltip>
          </CircleMarker>
        </>
      )}

      {draft.origin && (
        <CircleMarker
          center={[draft.origin.lat, draft.origin.lon]}
          radius={7}
          pathOptions={{ color: MAP_COLORS.route, weight: 3, fillColor: '#fff', fillOpacity: 1, dashArray: '3 3' }}
          bubblingMouseEvents={false}
        >
          <Tooltip>New start: {draft.origin.name}</Tooltip>
        </CircleMarker>
      )}
      {draft.destination && (
        <CircleMarker
          center={[draft.destination.lat, draft.destination.lon]}
          radius={7}
          pathOptions={{ color: MAP_COLORS.brand, weight: 3, fillColor: '#fff', fillOpacity: 1, dashArray: '3 3' }}
          bubblingMouseEvents={false}
        >
          <Tooltip>New end: {draft.destination.name}</Tooltip>
        </CircleMarker>
      )}

      {truck && (
        <Marker position={truck} icon={truckIcon} keyboard={false}>
          <Tooltip direction="top" offset={[0, -10]}>
            Truck at hour {hour}
          </Tooltip>
        </Marker>
      )}
    </MapContainer>
  )
}
