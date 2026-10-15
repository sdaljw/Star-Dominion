import type { AlarmSettings } from './types';

export const ALARM_SETTING_KEYS: (keyof AlarmSettings)[] = [
  'acc_x',
  'acc_y',
  'angle_x',
  'angle_y',
  'angle_z',
];

export const EMPTY_ALARM_SETTINGS: AlarmSettings = {
  acc_x: null,
  acc_y: null,
  angle_x: null,
  angle_y: null,
  angle_z: null,
};

export function normalizeAlarmSettings(value: unknown): AlarmSettings {
  const source = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  return ALARM_SETTING_KEYS.reduce<AlarmSettings>((result, key) => {
    const raw = source[key];
    result[key] = typeof raw === 'number' && Number.isFinite(raw) && raw >= 0 ? raw : null;
    return result;
  }, { ...EMPTY_ALARM_SETTINGS });
}

export function countEnabledAlarmSettings(settings: AlarmSettings): number {
  return ALARM_SETTING_KEYS.filter((key) => settings[key] !== null).length;
}
