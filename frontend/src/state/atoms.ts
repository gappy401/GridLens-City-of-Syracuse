import { atom } from 'jotai'

export interface MapBounds {
  min_lon: number
  min_lat: number
  max_lon: number
  max_lat: number
}

export interface FilterState {
  fuelType: string | null
  minScore: number | null
  minCapacityMw: number | null
}

// The currently selected project ID (for scorecard panel)
export const selectedProjectIdAtom = atom<number | null>(null)

// Current map viewport bounds (drives API query)
export const mapBoundsAtom = atom<MapBounds | null>(null)

// Active filters from the filter panel
export const filtersAtom = atom<FilterState>({
  fuelType: null,
  minScore: null,
  minCapacityMw: null,
})

// Whether the scorecard side panel is open
export const scorecardOpenAtom = atom<boolean>(false)
