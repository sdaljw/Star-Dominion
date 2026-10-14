export type LngLat = [number, number];

const PI = Math.PI;
const EARTH_RADIUS = 6378245.0;
const ECCENTRICITY_SQUARED = 0.00669342162296594323;

function isOutsideChina(latitude: number, longitude: number): boolean {
  return longitude < 72.004 || longitude > 137.8347 || latitude < 0.8293 || latitude > 55.8271;
}

function transformLatitude(x: number, y: number): number {
  let value = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
  value += (20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0 / 3.0;
  value += (20.0 * Math.sin(y * PI) + 40.0 * Math.sin(y / 3.0 * PI)) * 2.0 / 3.0;
  value += (160.0 * Math.sin(y / 12.0 * PI) + 320.0 * Math.sin(y * PI / 30.0)) * 2.0 / 3.0;
  return value;
}

function transformLongitude(x: number, y: number): number {
  let value = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
  value += (20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0 / 3.0;
  value += (20.0 * Math.sin(x * PI) + 40.0 * Math.sin(x / 3.0 * PI)) * 2.0 / 3.0;
  value += (150.0 * Math.sin(x / 12.0 * PI) + 300.0 * Math.sin(x / 30.0 * PI)) * 2.0 / 3.0;
  return value;
}

export function wgs84ToGcj02(position: LngLat): LngLat {
  const [longitude, latitude] = position;
  if (!Number.isFinite(longitude) || !Number.isFinite(latitude) || isOutsideChina(latitude, longitude)) {
    return position;
  }

  const offsetLatitude = transformLatitude(longitude - 105.0, latitude - 35.0);
  const offsetLongitude = transformLongitude(longitude - 105.0, latitude - 35.0);
  const latitudeRadians = latitude / 180.0 * PI;
  const sine = Math.sin(latitudeRadians);
  const magic = 1.0 - ECCENTRICITY_SQUARED * sine * sine;
  const sqrtMagic = Math.sqrt(magic);
  const latitudeDelta = offsetLatitude * 180.0 / ((EARTH_RADIUS * (1.0 - ECCENTRICITY_SQUARED)) / (magic * sqrtMagic) * PI);
  const longitudeDelta = offsetLongitude * 180.0 / (EARTH_RADIUS / sqrtMagic * Math.cos(latitudeRadians) * PI);

  return [longitude + longitudeDelta, latitude + latitudeDelta];
}
