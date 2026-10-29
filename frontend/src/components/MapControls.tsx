import L from 'leaflet'
import { MaximizeIcon, MinimizeIcon, MinusIcon, PlusIcon } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'

import { Button } from '@/components/ui/button'
import { ButtonGroup } from '@/components/ui/button-group'

interface Props {
  isFullscreen: boolean
  onToggleFullscreen?: () => void
}

/** Floating zoom and full-screen buttons in the map's top-right corner. */
export function MapControls({ isFullscreen, onToggleFullscreen }: Props) {
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
      <ButtonGroup orientation="vertical" aria-label="Zoom" className="shadow-sm">
        <Button variant="outline" size="icon" aria-label="Zoom in" className="bg-background" onClick={() => map.zoomIn()}>
          <PlusIcon />
        </Button>
        <Button variant="outline" size="icon" aria-label="Zoom out" className="bg-background" onClick={() => map.zoomOut()}>
          <MinusIcon />
        </Button>
      </ButtonGroup>
      {onToggleFullscreen && (
        <Button
          variant="outline"
          size="icon"
          aria-label={isFullscreen ? 'Exit full screen' : 'Full screen'}
          aria-pressed={isFullscreen}
          className="bg-background shadow-sm"
          onClick={onToggleFullscreen}
        >
          {isFullscreen ? <MinimizeIcon /> : <MaximizeIcon />}
        </Button>
      )}
    </div>
  )
}
