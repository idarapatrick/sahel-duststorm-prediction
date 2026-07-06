export interface KnownLocation {
  name: string;
  country: string;
  lat: number;
  lon: number;
}

export const KNOWN_LOCATIONS: KnownLocation[] = [
  { name: "Sokoto", country: "Nigeria", lat: 13.06, lon: 5.24 },
  { name: "Kano", country: "Nigeria", lat: 12.0, lon: 8.52 },
  { name: "Maiduguri", country: "Nigeria", lat: 11.85, lon: 13.16 },
  { name: "Niamey", country: "Niger", lat: 13.51, lon: 2.11 },
  { name: "Agadez", country: "Niger", lat: 16.97, lon: 7.99 },
  { name: "Zinder", country: "Niger", lat: 13.8, lon: 8.99 },
  { name: "N'Djamena", country: "Chad", lat: 12.13, lon: 15.06 },
  { name: "Bamako", country: "Mali", lat: 12.64, lon: -8.0 },
  { name: "Timbuktu", country: "Mali", lat: 16.77, lon: -3.01 },
  { name: "Ouagadougou", country: "Burkina Faso", lat: 12.36, lon: -1.48 },
  { name: "Dakar", country: "Senegal", lat: 14.69, lon: -17.44 },
  { name: "Nouakchott", country: "Mauritania", lat: 18.09, lon: -15.98 },
  { name: "Tamale", country: "Ghana", lat: 10.5, lon: -0.85 },
];
