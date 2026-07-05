export interface KnownLocation {
  name: string;
  country: string;
  lat: number;
  lon: number;
}

export const KNOWN_LOCATIONS: KnownLocation[] = [
  { name: "Niamey", country: "Niger", lat: 13.512, lon: 2.112 },
  { name: "Birnin Kebbi", country: "Nigeria", lat: 12.453, lon: 4.197 },
  { name: "Bamako", country: "Mali", lat: 12.639, lon: -8.0 },
  { name: "Ouagadougou", country: "Burkina Faso", lat: 12.371, lon: -1.519 },
  { name: "Dakar", country: "Senegal", lat: 14.716, lon: -17.467 },
  { name: "N'Djamena", country: "Chad", lat: 12.107, lon: 15.044 },
  { name: "Kano", country: "Nigeria", lat: 12.0, lon: 8.517 },
  { name: "Nouakchott", country: "Mauritania", lat: 18.086, lon: -15.975 },
  { name: "Zinder", country: "Niger", lat: 13.801, lon: 8.988 },
  { name: "Agadez", country: "Niger", lat: 16.973, lon: 7.99 },
  { name: "Timbuktu", country: "Mali", lat: 16.773, lon: -3.009 },
  { name: "Maiduguri", country: "Nigeria", lat: 11.846, lon: 13.16 },
];
