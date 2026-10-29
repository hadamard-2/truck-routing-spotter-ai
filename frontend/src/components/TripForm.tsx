import { CalendarIcon, FlagIcon, MapPinIcon } from 'lucide-react'
import { useState } from 'react'
import type { SubmitEvent } from 'react'

import type { Place, PlanRequest } from '@/api/types'
import { PlaceField } from '@/components/PlaceField'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from '@/components/ui/input-group'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { TimePicker, TimePickerContent, TimePickerPanel, TimePickerTrigger } from '@/components/reui/time-picker'
import { Spinner } from '@/components/ui/spinner'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { formatDate, fromUtcIso, nextHour, toUtcIso } from '@/format'
import { fromRequestPlace, toRequestPlace } from '@/lib/place'
import type { PlaceValue } from '@/lib/place'

interface Props {
  busy: boolean
  fieldError?: { field: string; message: string }
  onSubmit: (request: PlanRequest) => void
  /** Values to start from, e.g. the last submitted trip. */
  initial?: PlanRequest
  /** When set, shows a Cancel button that leaves the form without planning. */
  onCancel?: () => void
  /** A place chosen on the map; each new `id` fills that field. */
  picked?: PickedPlace
  /** The field the map is waiting to set, if any. */
  pickingField: PickedPlace['field'] | null
  /** Arms or disarms picking a field on the map. */
  onPickOnMap: (field: PickedPlace['field']) => void
}

export interface PickedPlace {
  id: number
  field: 'origin' | 'destination'
  place: Place
}

const INTERVALS = [10, 25, 50] as const

function startOfToday() {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d
}
type Interval = (typeof INTERVALS)[number]

export function TripForm({ busy, fieldError, onSubmit, initial, onCancel, picked, pickingField, onPickOnMap }: Props) {
  const [origin, setOrigin] = useState<PlaceValue>(() => fromRequestPlace(initial?.origin ?? 'Dallas, TX'))
  const [destination, setDestination] = useState<PlaceValue>(() =>
    fromRequestPlace(initial?.destination ?? 'Denver, CO'),
  )
  const [date, setDate] = useState(() => (initial ? fromUtcIso(initial.departure_time) : nextHour()).date)
  const [time, setTime] = useState(() => (initial ? fromUtcIso(initial.departure_time) : nextHour()).time)
  const [dateOpen, setDateOpen] = useState(false)
  const [today] = useState(startOfToday)
  const [weight, setWeight] = useState(String(initial?.load_weight_lb ?? 42000))
  const [interval, setInterval] = useState<Interval>(initial?.sample_interval_mi ?? 25)

  // Apply each new map pick once, while rendering, so the field updates in the same pass.
  const [appliedPick, setAppliedPick] = useState(picked?.id)
  if (picked && picked.id !== appliedPick) {
    setAppliedPick(picked.id)
    const value = { text: picked.place.name, point: { lat: picked.place.lat, lon: picked.place.lon } }
    if (picked.field === 'origin') setOrigin(value)
    else setDestination(value)
  }

  function submit(event: SubmitEvent) {
    event.preventDefault()
    onSubmit({
      origin: toRequestPlace(origin),
      destination: toRequestPlace(destination),
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
          <PlaceField
            id="origin"
            pickLabel="start"
            picking={pickingField === 'origin'}
            onPickOnMap={() => onPickOnMap('origin')}
            icon={<MapPinIcon />}
            value={origin}
            onChange={setOrigin}
            invalid={invalid('origin')}
          />
          {errorFor('origin')}
        </Field>

        <Field data-invalid={invalid('destination') || undefined}>
          <FieldLabel htmlFor="destination">To</FieldLabel>
          <PlaceField
            id="destination"
            pickLabel="end"
            picking={pickingField === 'destination'}
            onPickOnMap={() => onPickOnMap('destination')}
            icon={<FlagIcon />}
            value={destination}
            onChange={setDestination}
            invalid={invalid('destination')}
          />
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
            <TimePicker
              value={time}
              onValueChange={(next) => next && setTime(next)}
              hourCycle={12}
              minuteStep={5}
              required
              invalid={invalid('departure_time')}
              aria-label="Departure time"
            >
              <TimePickerTrigger className="w-36" />
              <TimePickerContent>
                <TimePickerPanel />
              </TimePickerContent>
            </TimePicker>
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
              <ToggleGroupItem
                key={value}
                value={String(value)}
                className="flex-1 aria-pressed:border-primary aria-pressed:bg-primary aria-pressed:text-primary-foreground aria-pressed:hover:bg-primary/90 aria-pressed:hover:text-primary-foreground"
              >
                {value} mi
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <FieldDescription>Shorter intervals catch narrow bands of weather.</FieldDescription>
          {errorFor('sample_interval_mi')}
        </Field>

        <div className="flex gap-2">
          {onCancel && (
            <Button type="button" variant="outline" size="lg" onClick={onCancel} disabled={busy}>
              Cancel
            </Button>
          )}
          <Button type="submit" size="lg" className="flex-1" disabled={busy}>
            {busy && <Spinner data-icon="inline-start" />}
            {busy ? 'Planning routes' : 'Plan routes'}
          </Button>
        </div>
      </FieldGroup>
    </form>
  )
}
