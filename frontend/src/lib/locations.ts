import type { Location } from './types';

// The complete catalogue comes from PostgreSQL through /api/v1/coverage/places.
// This single default keeps the first render usable while that request completes.
export const DEFAULT_LOCATION: Location = {
	name: 'Niamey', country: 'Niger', lat: 13.51, lon: 2.11,
	coverageStatus: 'operational'
};
export const locations: Location[] = [DEFAULT_LOCATION];
export const SAHEL_BOUNDS = { latMin: 10, latMax: 25, lonMin: -18, lonMax: 25 };
