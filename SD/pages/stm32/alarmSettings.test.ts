import { describe, expect, it } from 'vitest';
import {
  countEnabledAlarmSettings,
  EMPTY_ALARM_SETTINGS,
  normalizeAlarmSettings,
} from './alarmSettings';

describe('cloud alarm settings', () => {
  it('normalizes the five server fields and counts enabled values', () => {
    const settings = normalizeAlarmSettings({ acc_x: 0.8, angle_z: 30 });

    expect(settings).toEqual({
      acc_x: 0.8,
      acc_y: null,
      angle_x: null,
      angle_y: null,
      angle_z: 30,
    });
    expect(countEnabledAlarmSettings(settings)).toBe(2);
    expect(countEnabledAlarmSettings(EMPTY_ALARM_SETTINGS)).toBe(0);
  });
});
