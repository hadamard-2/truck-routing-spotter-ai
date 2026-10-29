import type { Heatmap } from '@/api/types'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { formatTime } from '@/format'
import { cn } from '@/lib/utils'
import { LEVEL_BG, LEVEL_LABEL, LEVELS } from '@/risk'

interface Props {
  heatmap: Heatmap
  hour: number
  onHourChange: (hour: number) => void
  showHeatmap: boolean
  onShowHeatmapChange: (show: boolean) => void
  className?: string
}

export function TimeSlider({
  heatmap,
  hour,
  onHourChange,
  showHeatmap,
  onShowHeatmapChange,
  className,
}: Props) {
  const last = heatmap.frames.length - 1
  const frame = heatmap.frames[hour]

  return (
    <div className={cn('flex flex-col gap-3 rounded-xl bg-card p-4 text-card-foreground ring-1 ring-foreground/10', className)}>
      <div className="flex items-center justify-between gap-4">
        <div className="flex min-w-0 flex-col">
          <span className="text-sm font-medium tabular-nums">
            {hour === 0 ? 'At departure' : `${hour} h after departure`}
          </span>
          <span className="truncate text-xs text-muted-foreground">{frame && formatTime(frame.time)}</span>
        </div>
        <div className="flex items-center gap-2">
          <Switch id="weather-layer" checked={showHeatmap} onCheckedChange={onShowHeatmapChange} />
          <Label htmlFor="weather-layer" className="text-xs font-normal">
            Weather
          </Label>
        </div>
      </div>
      <Slider
        min={0}
        max={last}
        step={1}
        value={[hour]}
        onValueChange={(value) => onHourChange(Array.isArray(value) ? value[0] : value)}
        thumbProps={{
          'aria-label': 'Forecast hour',
          getAriaValueText: (_, value) => `${value} hours after departure`,
        }}
      />
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
        {LEVELS.map((level) => (
          <span key={level} className="inline-flex items-center gap-1.5">
            <span className={cn('size-2 rounded-full', LEVEL_BG[level])} aria-hidden />
            {LEVEL_LABEL[level]}
          </span>
        ))}
        {showHeatmap && (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-3 rounded-[2px] border border-dashed border-muted-foreground" aria-hidden />
            Forecast area
          </span>
        )}
      </div>
    </div>
  )
}
