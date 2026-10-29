import L from 'leaflet'
import { MaximizeIcon, MinimizeIcon, MinusIcon, PlusIcon } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'

import { Button } from '@/components/ui/button'
import { ButtonGroup } from '@/components/ui/button-group'

interface Props {
  isExpanded: boolean
  onToggleExpanded: () => void
}

/** Floating zoom and expand buttons in the map's top-right corner. */
export function MapControls({ isExpanded, onToggleExpanded }: Props) {
  const map = useMap()
  const ref = useRef<HTMLDivElement>(null)

  // Clicks and scrolls on the controls must not pan or zoom the map underneath.
  useEffect(() => {
    if (!ref.current) return
    L.DomEvent.disableClickPropagation(ref.current)
    L.DomEvent.disableScrollPropagation(ref.current)
  }, [])

  return (
    <div ref={ref} className="absolute top-3 right-3 z-1000 flex flex-col gap-2">
      <ButtonGroup orientation="vertical" aria-label="Zoom" className="rounded-lg shadow-sm">
        <Button variant="outline" size="icon" aria-label="Zoom in" className="bg-background" onClick={() => map.zoomIn()}>
          <PlusIcon />
        </Button>
        <Button variant="outline" size="icon" aria-label="Zoom out" className="bg-background" onClick={() => map.zoomOut()}>
          <MinusIcon />
        </Button>
      </ButtonGroup>
      <Button
        variant="outline"
        size="icon"
        aria-label={isExpanded ? 'Exit full view' : 'Full view'}
        aria-pressed={isExpanded}
        className="bg-background shadow-sm"
        onClick={onToggleExpanded}
      >
        {isExpanded ? <MinimizeIcon /> : <MaximizeIcon />}
      </Button>
    </div>
  )
}
