import { PauseIcon, PlayIcon } from 'lucide-react'
import { useEffect, useState } from 'react'

import type { Heatmap } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { formatDuration, formatTime } from '@/format'
import type { Playhead } from '@/lib/playhead'
import { usePlayhead } from '@/lib/playhead'
import { cn } from '@/lib/utils'
import { LEVEL_BG, LEVEL_LABEL, LEVELS } from '@/risk'

// Playing runs the 48 hours in 12 seconds.
const HOURS_PER_SECOND = 4
const STEP_HOURS = 0.25

interface Props {
  heatmap: Heatmap
  /** IANA zone the frame's time is shown in. */
  timeZone?: string
  playhead: Playhead
  showHeatmap: boolean
  onShowHeatmapChange: (show: boolean) => void
  className?: string
}

export function TimeSlider({ heatmap, timeZone, playhead, showHeatmap, onShowHeatmapChange, className }: Props) {
  const hour = usePlayhead(playhead)
  const [playing, setPlaying] = useState(false)
  const last = heatmap.frames.length - 1
  const time = new Date(Date.parse(heatmap.start) + hour * 3_600_000).toISOString()

  useEffect(() => {
    if (!playing) return
    let request = 0
    let previous = performance.now()
    const tick = (now: number) => {
      const next = playhead.get() + ((now - previous) / 1000) * HOURS_PER_SECOND
      previous = now
      if (next >= last) {
        playhead.set(last)
        setPlaying(false)
        return
      }
      playhead.set(next)
      request = requestAnimationFrame(tick)
    }
    request = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(request)
  }, [playing, playhead, last])

  function togglePlaying() {
    if (!playing && playhead.get() >= last) playhead.set(0)
    setPlaying(!playing)
  }

  return (
    <div className={cn('flex flex-col gap-3 rounded-xl bg-card p-4 text-card-foreground ring-1 ring-foreground/10', className)}>
      <div className="flex items-center justify-between gap-4">
        <div className="flex min-w-0 flex-col">
          <span className="text-sm font-medium tabular-nums">
            {hour === 0 ? 'At departure' : `${formatDuration(hour * 3600)} after departure`}
          </span>
          <span className="truncate text-xs text-muted-foreground">{formatTime(time, timeZone)}</span>
        </div>
        <div className="flex items-center gap-2">
          <Switch id="weather-layer" checked={showHeatmap} onCheckedChange={onShowHeatmapChange} />
          <Label htmlFor="weather-layer" className="text-xs font-normal">
            Weather
          </Label>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="icon-sm"
          className="rounded-full"
          aria-label={playing ? 'Pause' : 'Play the next 48 hours'}
          onClick={togglePlaying}
        >
          {playing ? <PauseIcon /> : <PlayIcon />}
        </Button>
        <Slider
          className="flex-1"
          min={0}
          max={last}
          step={STEP_HOURS}
          value={[hour]}
          onValueChange={(value) => {
            setPlaying(false)
            playhead.set(Array.isArray(value) ? value[0] : value)
          }}
          thumbProps={{
            'aria-label': 'Forecast hour',
            getAriaValueText: (_, value) => `${formatDuration(value * 3600)} after departure`,
          }}
        />
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
        {LEVELS.map((level) => (
          <span key={level} className="inline-flex items-center gap-1.5">
            <span className={cn('size-2 rounded-full', LEVEL_BG[level])} aria-hidden />
            {LEVEL_LABEL[level]}
          </span>
        ))}
      </div>
    </div>
  )
}
