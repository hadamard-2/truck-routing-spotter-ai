import { AlertCircleIcon, ArrowRightIcon, InfoIcon, PencilIcon, RouteIcon, TruckIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { ApiError, getHeatmap, planTrip } from '@/api/client'
import type { Heatmap, Plan, PlanRequest } from '@/api/types'
import { MapView } from '@/components/MapView'
import { RouteList } from '@/components/RouteList'
import { TimeSlider } from '@/components/TimeSlider'
import { TripForm } from '@/components/TripForm'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { Skeleton } from '@/components/ui/skeleton'
import { formatTime, formatWeight } from '@/format'
import { cn } from '@/lib/utils'

function placeName(name: string) {
  return name.split(',')[0]
}

function TripSummary({ plan, onEdit }: { plan: Plan; onEdit: () => void }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5">
          {placeName(plan.origin.name)}
          <ArrowRightIcon className="size-3.5 text-muted-foreground" aria-label="to" />
          {placeName(plan.destination.name)}
        </CardTitle>
        <CardDescription className="flex flex-wrap gap-x-3 tabular-nums">
          <span>Leaves {formatTime(plan.departure_time)}</span>
          <span>{formatWeight(plan.load_weight_lb)}</span>
          <span>Every {plan.sample_interval_mi} mi</span>
        </CardDescription>
        <CardAction>
          <Button variant="outline" size="sm" onClick={onEdit}>
            <PencilIcon data-icon="inline-start" />
            Edit
          </Button>
        </CardAction>
      </CardHeader>
    </Card>
  )
}

export default function App() {
  const [plan, setPlan] = useState<Plan | null>(null)
  const [heatmap, setHeatmap] = useState<Heatmap | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [hour, setHour] = useState(0)
  const [showHeatmap, setShowHeatmap] = useState(true)
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)
  const mapRef = useRef<HTMLDivElement>(null)
  const [isExpanded, setIsExpanded] = useState(false)

  // Esc leaves the expanded map, like closing a full-screen view.
  useEffect(() => {
    if (!isExpanded) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setIsExpanded(false)
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [isExpanded])

  async function handlePlan(request: PlanRequest) {
    setBusy(true)
    setError(null)
    try {
      const next = await planTrip(request)
      setPlan(next)
      setSelectedId(next.recommended_route_id)
      setHour(0)
      setHeatmap(null)
      setEditing(false)
      getHeatmap(next)
        .then(setHeatmap)
        .catch((e: ApiError) => toast.error('Weather layer unavailable', { description: e.message }))
      if (!window.matchMedia('(min-width: 1024px)').matches) {
        requestAnimationFrame(() => mapRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
      }
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError('unknown', 'Something went wrong while planning.'))
    } finally {
      setBusy(false)
    }
  }

  const fieldError = error?.field ? { field: error.field, message: error.message } : undefined

  return (
    <div className="flex min-h-svh flex-col bg-muted/40 lg:grid lg:h-svh lg:grid-cols-[minmax(360px,420px)_1fr] lg:grid-rows-[auto_1fr]">
      <header className="flex flex-col gap-5 bg-background p-4 lg:col-start-1 lg:row-start-1 lg:border-r lg:p-6 lg:pb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 items-center justify-center rounded-lg bg-brand text-brand-foreground">
            <TruckIcon className="size-4" />
          </div>
          <div className="flex flex-col">
            <h1 className="text-sm font-semibold">Truck Routr</h1>
            <p className="text-xs text-muted-foreground">The safest route for your load and departure</p>
          </div>
        </div>

        {plan && !editing && <TripSummary plan={plan} onEdit={() => setEditing(true)} />}
        <div className={cn(plan && !editing && 'hidden')}>
          <TripForm busy={busy} fieldError={fieldError} onSubmit={handlePlan} />
        </div>
      </header>

      <main
        ref={mapRef}
        className={cn(
          'relative isolate scroll-mt-4 flex-col gap-3 px-4 pt-4 lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:flex lg:p-0',
          plan ? 'flex' : 'hidden',
          isExpanded && 'fixed inset-0 z-40 flex bg-background p-0 lg:p-0',
        )}
      >
        <div
          className={cn(
            'h-[60svh] overflow-hidden rounded-xl ring-1 ring-foreground/10 lg:h-full lg:rounded-none lg:ring-0',
            isExpanded && 'h-full rounded-none ring-0',
          )}
        >
          <MapView
            plan={plan}
            selectedId={selectedId}
            onSelect={setSelectedId}
            heatmap={heatmap}
            showHeatmap={showHeatmap}
            hour={hour}
            isExpanded={isExpanded}
            onToggleExpanded={() => setIsExpanded((v) => !v)}
          />
        </div>
        {heatmap ? (
          <TimeSlider
            heatmap={heatmap}
            hour={hour}
            onHourChange={setHour}
            showHeatmap={showHeatmap}
            onShowHeatmapChange={setShowHeatmap}
            className={cn(
              'lg:absolute lg:inset-x-6 lg:bottom-6 lg:z-1000 lg:mx-auto lg:max-w-xl lg:shadow-lg',
              isExpanded && 'absolute inset-x-3 bottom-3 z-1000 mx-auto max-w-xl shadow-lg',
            )}
          />
        ) : (
          plan && <Skeleton className="h-28 rounded-xl lg:hidden" />
        )}
      </main>

      <section
        aria-live="polite"
        className="flex flex-1 flex-col gap-4 bg-background p-4 lg:col-start-1 lg:row-start-2 lg:overflow-y-auto lg:border-r lg:bg-muted/40 lg:p-6 lg:pt-4"
      >
        {error && !error.field && (
          <Alert variant="destructive">
            <AlertCircleIcon />
            <AlertTitle>Couldn't plan this trip</AlertTitle>
            <AlertDescription>{error.message}</AlertDescription>
          </Alert>
        )}

        {plan?.warnings.map((w) => (
          <Alert key={w.code}>
            <InfoIcon />
            <AlertDescription>{w.message}</AlertDescription>
          </Alert>
        ))}

        {busy && !plan ? (
          <div className="flex flex-col gap-2">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-32 rounded-lg" />
            ))}
          </div>
        ) : plan ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <h2 className="text-sm font-semibold">
                {plan.routes.length} routes, safest first
              </h2>
              <p className="text-xs text-muted-foreground">
                Ranked by miles of no-travel, severe and high weather, then average risk, then drive time.
              </p>
            </div>
            <RouteList routes={plan.routes} selectedId={selectedId} onSelect={setSelectedId} />
          </div>
        ) : (
          !error && (
            <Empty className="border border-dashed">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <RouteIcon />
                </EmptyMedia>
                <EmptyTitle>No trip planned yet</EmptyTitle>
                <EmptyDescription>
                  Compare three routes by the weather the truck meets on each, at the hour it gets there.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          )
        )}
      </section>
    </div>
  )
}
