import { Autocomplete } from '@base-ui/react/autocomplete'
import { MapPinIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'

import { searchPlaces } from '@/api/client'
import type { Place } from '@/api/types'
import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group'
import type { PlaceValue } from '@/lib/place'

const MIN_CHARS = 2
const DEBOUNCE_MS = 250

interface Props {
  id: string
  icon: ReactNode
  value: PlaceValue
  onChange: (value: PlaceValue) => void
  invalid?: boolean
}

/** A place input that suggests matching addresses as you type. */
export function PlaceField({ id, icon, value, onChange, invalid }: Props) {
  const [results, setResults] = useState<Place[]>([])
  const [loading, setLoading] = useState(false)
  const query = value.point ? '' : value.text.trim()
  const searching = query.length >= MIN_CHARS
  const suggestions = searching ? results : []

  useEffect(() => {
    if (!searching) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      setLoading(true)
      searchPlaces(query, controller.signal)
        .then(setResults)
        .catch(() => {
          if (!controller.signal.aborted) setResults([])
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false)
        })
    }, DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query, searching])

  function handleValueChange(text: string) {
    const picked = suggestions.find((place) => place.name === text)
    onChange(picked ? { text, point: { lat: picked.lat, lon: picked.lon } } : { text })
  }

  return (
    <Autocomplete.Root
      items={suggestions}
      mode="none"
      value={value.text}
      onValueChange={handleValueChange}
      itemToStringValue={(place: Place) => place.name}
    >
      <InputGroup>
        <InputGroupAddon>{icon}</InputGroupAddon>
        <Autocomplete.Input
          render={
            <InputGroupInput
              id={id}
              placeholder="City or address"
              required
              aria-invalid={invalid || undefined}
            />
          }
        />
        {value.point && (
          <InputGroupAddon align="inline-end" title="Exact point chosen">
            <MapPinIcon className="text-primary" aria-label="Exact point chosen" />
          </InputGroupAddon>
        )}
      </InputGroup>
      <Autocomplete.Portal>
        <Autocomplete.Positioner sideOffset={4} className="isolate z-1100">
          <Autocomplete.Popup className="max-h-72 w-(--anchor-width) overflow-y-auto rounded-lg bg-popover p-1 text-sm text-popover-foreground shadow-md ring-1 ring-foreground/10 outline-hidden">
            <Autocomplete.Empty className="px-2 py-1.5 text-muted-foreground empty:hidden">
              {searching && !loading && 'No matching places'}
            </Autocomplete.Empty>
            <Autocomplete.List>
              {(place: Place) => (
                <Autocomplete.Item
                  key={`${place.name}-${place.lat}-${place.lon}`}
                  value={place}
                  className="flex cursor-default items-center gap-2 rounded-md px-2 py-1.5 outline-none select-none data-highlighted:bg-accent data-highlighted:text-accent-foreground"
                >
                  <MapPinIcon className="size-3.5 shrink-0 text-muted-foreground" />
                  <span className="truncate">{place.name}</span>
                </Autocomplete.Item>
              )}
            </Autocomplete.List>
          </Autocomplete.Popup>
        </Autocomplete.Positioner>
      </Autocomplete.Portal>
    </Autocomplete.Root>
  )
}
