import type { Route } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Item, ItemContent, ItemDescription, ItemGroup, ItemMedia, ItemTitle } from '@/components/ui/item'
import { formatDuration, formatMiles, formatTime } from '@/format'
import { cn } from '@/lib/utils'
import { LEVEL_BG, LEVEL_LABEL, LEVELS } from '@/risk'
import { RiskStrip } from './RiskStrip'

interface Props {
  routes: Route[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export function RouteList({ routes, selectedId, onSelect }: Props) {
  return (
    <ItemGroup className="gap-2">
      {routes.map((route) => {
        const selected = route.id === selectedId
        const miles = route.summary.miles_by_level
        const risky = [...LEVELS].reverse().filter((level) => level !== 'low' && miles[level] > 0)
        return (
          <Item
            key={route.id}
            variant={selected ? 'outline' : 'muted'}
            className={cn('cursor-pointer items-start text-left', selected ? 'border-primary/40 bg-card shadow-sm' : 'hover:bg-muted')}
            render={<button type="button" aria-pressed={selected} onClick={() => onSelect(route.id)} />}
          >
            <ItemMedia
              className={cn(
                'size-7 rounded-full text-xs font-semibold tabular-nums',
                selected ? 'bg-primary text-primary-foreground' : 'bg-background text-muted-foreground',
              )}
            >
              {route.rank}
            </ItemMedia>
            <ItemContent className="min-w-0 gap-2">
              <div className="flex items-center justify-between gap-2">
                <ItemTitle className="text-sm">{route.label}</ItemTitle>
                {route.recommended && <Badge>Recommended</Badge>}
              </div>
              <ItemDescription className="flex flex-wrap gap-x-3 tabular-nums">
                <span>{formatMiles(route.distance_mi)}</span>
                <span>{formatDuration(route.duration_s)}</span>
                <span>Arrives {formatTime(route.arrival_time)}</span>
              </ItemDescription>
              <RiskStrip checkpoints={route.checkpoints} distance={route.distance_mi} />
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs tabular-nums">
                {risky.length === 0 ? (
                  <span className="text-muted-foreground">Low risk the whole way</span>
                ) : (
                  risky.map((level) => (
                    <span key={level} className="inline-flex items-center gap-1.5">
                      <span className={cn('size-2 rounded-full', LEVEL_BG[level])} aria-hidden />
                      {formatMiles(miles[level])} {LEVEL_LABEL[level].toLowerCase()}
                    </span>
                  ))
                )}
              </div>
              <p className="text-xs text-muted-foreground">{route.summary.rank_reason}</p>
            </ItemContent>
          </Item>
        )
      })}
    </ItemGroup>
  )
}
