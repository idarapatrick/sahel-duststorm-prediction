/**
 * Baseline SahelWatch place catalogue.
 *
 * PostgreSQL remains the live source of truth and replaces this list after the
 * application starts. Keeping the same public seed catalogue in the client
 * prevents a slow catalogue request from reducing the location picker to one
 * city.
 */
import type { Location } from './types';

const place = (
	name: string,
	country: string,
	lat: number,
	lon: number,
	coverageStatus: Location['coverageStatus'] = 'provisional',
	placeType: Location['placeType'] = 'town',
	forecastLat = lat,
	forecastLon = lon
): Location => ({ name, country, lat, lon, coverageStatus, placeType, forecastLat, forecastLon });

export const locations: Location[] = [
	place('Niamey', 'Niger', 13.51, 2.11, 'operational', 'city'),
	place('Sokoto', 'Nigeria', 13.06, 5.24, 'operational', 'city'),
	place('Kano', 'Nigeria', 12.00, 8.52, 'operational', 'city'),
	place('Maiduguri', 'Nigeria', 11.85, 13.16, 'operational', 'city'),
	place('Agadez', 'Niger', 16.97, 7.99, 'operational', 'city'),
	place("N'Djamena", 'Chad', 12.13, 15.06, 'operational', 'city'),
	place('Bamako', 'Mali', 12.64, -8.00, 'operational', 'city'),
	place('Timbuktu', 'Mali', 16.77, -3.01, 'operational'),
	place('Ouagadougou', 'Burkina Faso', 12.36, -1.48, 'operational', 'city'),
	place('Dakar', 'Senegal', 14.69, -17.44, 'operational', 'city'),
	place('Nouakchott', 'Mauritania', 18.09, -15.98, 'operational', 'city'),
	place('Tillaberi', 'Niger', 14.21, 1.45),
	place('Maradi', 'Niger', 13.50, 7.10, 'provisional', 'city'),
	place('Zinder', 'Niger', 13.81, 8.99, 'provisional', 'city'),
	place('Diffa', 'Niger', 13.32, 12.61),
	place('Tahoua', 'Niger', 14.89, 5.27),
	place('Katsina', 'Nigeria', 12.99, 7.60, 'provisional', 'city'),
	place('Gusau', 'Nigeria', 12.17, 6.66, 'provisional', 'city'),
	place('Damaturu', 'Nigeria', 11.75, 11.96),
	place('Gashua', 'Nigeria', 12.87, 11.04),
	place('Dori', 'Burkina Faso', 14.03, -0.03),
	place('Djibo', 'Burkina Faso', 14.10, -1.63),
	place('Gorom-Gorom', 'Burkina Faso', 14.44, -0.23),
	place('Gao', 'Mali', 16.27, -0.04, 'provisional', 'city'),
	place('Mopti', 'Mali', 14.49, -4.20, 'provisional', 'city'),
	place('Kidal', 'Mali', 18.44, 1.41),
	place('Menaka', 'Mali', 15.92, 2.40),
	place('Abeche', 'Chad', 13.83, 20.83, 'provisional', 'city'),
	place('Moussoro', 'Chad', 13.64, 16.49),
	place('Faya-Largeau', 'Chad', 17.93, 19.10),
	place('Podor', 'Senegal', 16.65, -14.96),
	place('Matam', 'Senegal', 15.66, -13.26),
	place('Linguere', 'Senegal', 15.40, -15.12),
	place('Nema', 'Mauritania', 16.62, -7.25),
	place('Atar', 'Mauritania', 20.52, -13.05),
	place('Kiffa', 'Mauritania', 16.62, -11.40),
	place('Libore', 'Niger', 13.41, 2.19, 'provisional', 'community', 13.51, 2.11),
	place('Wamakko', 'Nigeria', 13.04, 5.10, 'provisional', 'community', 13.06, 5.24),
	place('Kumbotso', 'Nigeria', 11.89, 8.50, 'provisional', 'community', 12.00, 8.52),
	place('Jere', 'Nigeria', 11.84, 13.10, 'provisional', 'community', 11.85, 13.16),
	place('Saaba', 'Burkina Faso', 12.38, -1.41, 'provisional', 'community', 12.36, -1.48)
];

export const DEFAULT_LOCATION = locations[0];
export const SAHEL_BOUNDS = { latMin: 10, latMax: 25, lonMin: -18, lonMax: 25 };
