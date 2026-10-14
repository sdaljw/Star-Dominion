export type MapTheme = 'dark' | 'normal' | 'satellite';

export interface GnggaData {
  latitude: number | null;
  longitude: number | null;
  altitude: number | null;
  quality: string;
  qualityCode: string;
  satellites: number;
  raw: string;
}

export interface ImuData {
  acc: [number, number, number];
  gyro: [number, number, number];
  angle: [number, number, number];
}

export interface AlarmData {
  level: string;
  score: number;
  D: number;
  V: number;
  E: number;
  N: number;
  U: number;
  tilt: number;
  accDyn: number;
  q: number;
  sats: number;
}

export interface DeviceMessage {
  seq: number;
  message: string;
  raw?: string;
  device_id?: string;
  server_timestamp?: number;
}

export interface LogEntry {
  deviceId: string;
  seq: number;
  text: string;
  timestamp: number;
}

export interface DisplacementPoint {
  time: string;
  x: number;
  y: number;
  z: number;
}

export interface NotificationItem {
  msg: string;
  type: 'success' | 'error' | 'info' | 'warning';
  time: string;
}

export interface DeviceRecord {
  device_id: string;
  online: boolean;
  data_age_ms: number;
  latitude: number | null;
  longitude: number | null;
  altitude: number | null;
  quality_code: string;
  quality: string;
  satellites: number;
  temperature: number | null;
  humidity: number | null;
  rtk_status: string;
  message: string;
  last_message: string;
  raw: string;
  server_timestamp: number;
  message_seq: number;
  imu: ImuData;
  alarm: AlarmData | null;
  messages: DeviceMessage[];
}

export interface DeviceSnapshot {
  devices: Record<string, Partial<DeviceRecord>>;
  server_timestamp?: number;
}
