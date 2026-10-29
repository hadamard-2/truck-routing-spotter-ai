import { CalendarIcon, FlagIcon, MapPinIcon } from 'lucide-react'
import { useState } from 'react'
import type { SubmitEvent } from 'react'

import type { PlanRequest } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from '@/components/ui/input-group'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Spinner } from '@/components/ui/spinner'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { formatDate, nextHour, toUtcIso } from '@/format'

interface Props {
  busy: boolean
  fieldError?: { field: string; message: string }
  onSubmit: (request: PlanRequest) => void
}

const INTERVALS = [10, 25, 50] as const

function startOfToday() {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d
}
type Interval = (typeof INTERVALS)[number]

export function TripForm({ busy, fieldError, onSubmit }: Props) {
  const [origin, setOrigin] = useState('Dallas, TX')
  const [destination, setDestination] = useState('Denver, CO')
  const [date, setDate] = useState(() => nextHour().date)
  const [time, setTime] = useState(() => nextHour().time)
  const [dateOpen, setDateOpen] = useState(false)
  const [today] = useState(startOfToday)
  const [weight, setWeight] = useState('42000')
  const [interval, setInterval] = useState<Interval>(25)

  function submit(event: SubmitEvent) {
    event.preventDefault()
    onSubmit({
      origin: origin.trim(),
      destination: destination.trim(),
      departure_time: toUtcIso(date, time),
      load_weight_lb: Number.parseInt(weight, 10),
      sample_interval_mi: interval,
    })
  }

  const invalid = (field: string) => fieldError?.field === field
  const errorFor = (field: string) => (invalid(field) ? <FieldError>{fieldError?.message}</FieldError> : null)

  return (
    <form onSubmit={submit}>
      <FieldGroup className="gap-5">
        <Field data-invalid={invalid('origin') || undefined}>
          <FieldLabel htmlFor="origin">From</FieldLabel>
          <InputGroup>
            <InputGroupAddon>
              <MapPinIcon />
            </InputGroupAddon>
            <InputGroupInput
              id="origin"
              value={origin}
              onChange={(e) => setOrigin(e.target.value)}
              placeholder="City or address"
              autoComplete="off"
              required
              aria-invalid={invalid('origin') || undefined}
            />
          </InputGroup>
          {errorFor('origin')}
        </Field>

        <Field data-invalid={invalid('destination') || undefined}>
          <FieldLabel htmlFor="destination">To</FieldLabel>
          <InputGroup>
            <InputGroupAddon>
              <FlagIcon />
            </InputGroupAddon>
            <InputGroupInput
              id="destination"
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              placeholder="City or address"
              autoComplete="off"
              required
              aria-invalid={invalid('destination') || undefined}
            />
          </InputGroup>
          {errorFor('destination')}
        </Field>

        <Field data-invalid={invalid('departure_time') || undefined}>
          <FieldLabel htmlFor="departure-date">Departure</FieldLabel>
          <div className="flex gap-2">
            <Popover open={dateOpen} onOpenChange={setDateOpen}>
              <PopoverTrigger
                render={<Button id="departure-date" variant="outline" className="flex-1 justify-start font-normal" />}
              >
                <CalendarIcon data-icon="inline-start" />
                {formatDate(date)}
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="single"
                  selected={date}
                  defaultMonth={date}
                  disabled={{ before: today }}
                  onSelect={(next) => {
                    if (next) {
                      setDate(next)
                      setDateOpen(false)
                    }
                  }}
                />
              </PopoverContent>
            </Popover>
            <Input
              type="time"
              aria-label="Departure time"
              className="w-36"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              required
              aria-invalid={invalid('departure_time') || undefined}
            />
          </div>
          {errorFor('departure_time')}
        </Field>

        <Field data-invalid={invalid('load_weight_lb') || undefined}>
          <FieldLabel htmlFor="load">Load weight</FieldLabel>
          <InputGroup>
            <InputGroupInput
              id="load"
              type="number"
              inputMode="numeric"
              min={1}
              step={1}
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              required
              aria-invalid={invalid('load_weight_lb') || undefined}
            />
            <InputGroupAddon align="inline-end">
              <InputGroupText>lb</InputGroupText>
            </InputGroupAddon>
          </InputGroup>
          {errorFor('load_weight_lb')}
        </Field>

        <Field data-invalid={invalid('sample_interval_mi') || undefined}>
          <FieldLabel id="interval-label">Check weather every</FieldLabel>
          <ToggleGroup
            aria-labelledby="interval-label"
            variant="outline"
            className="w-full"
            spacing={0}
            value={[String(interval)]}
            onValueChange={(value) => {
              const next = Number(value[0]) as Interval
              if (INTERVALS.includes(next)) setInterval(next)
            }}
          >
            {INTERVALS.map((value) => (
              <ToggleGroupItem key={value} value={String(value)} className="flex-1">
                {value} mi
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <FieldDescription>Shorter intervals catch narrow bands of weather.</FieldDescription>
          {errorFor('sample_interval_mi')}
        </Field>

        <Button type="submit" size="lg" disabled={busy}>
          {busy && <Spinner data-icon="inline-start" />}
          {busy ? 'Planning routes' : 'Plan routes'}
        </Button>
      </FieldGroup>
    </form>
  )
}
