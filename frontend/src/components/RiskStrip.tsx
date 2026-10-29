import type { Checkpoint, RiskLevel } from '@/api/types'
import { LEVEL_BG, LEVEL_LABEL } from '@/risk'
import { cn } from '@/lib/utils'

interface Props {
  checkpoints: Checkpoint[]
  distance: number
}

interface Run {
  level: RiskLevel | null
  from: number
  miles: number
}

/** Consecutive checkpoints at the same level, joined into one stretch of road. */
function toRuns(checkpoints: Checkpoint[]): Run[] {
  const runs: Run[] = []
  for (const c of checkpoints) {
    if (c.segment_mi <= 0) continue
    const last = runs[runs.length - 1]
    if (last && last.level === c.level) last.miles += c.segment_mi
    else runs.push({ level: c.level, from: c.mile, miles: c.segment_mi })
  }
  return runs
}

/** The route unrolled into a bar, each stretch coloured by its risk. */
export function RiskStrip({ checkpoints, distance }: Props) {
  return (
    <div
      className="flex h-1.5 w-full gap-0.5 overflow-hidden rounded-full"
      role="img"
      aria-label="Risk along the route, from start to finish"
    >
      {toRuns(checkpoints).map((run) => (
        <span
          key={run.from}
          className={cn('h-full first:rounded-l-full last:rounded-r-full', run.level ? LEVEL_BG[run.level] : 'bg-risk-unknown')}
          style={{ width: `${(run.miles / distance) * 100}%` }}
          title={`Miles ${Math.round(run.from)}–${Math.round(run.from + run.miles)}: ${run.level ? LEVEL_LABEL[run.level] : 'No forecast'}`}
        />
      ))}
    </div>
  )
}
