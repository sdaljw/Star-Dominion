import { describe, expect, it } from 'vitest';
import { isValidMessage, normalizeAlarm, parseGnggaMessage } from './telemetry';

describe('STM32 NMEA telemetry', () => {
  it('accepts the GBGGA sentence emitted by the device', () => {
    const payload = '$GBGGA,121520.00,3648.62646082,N,11759.61107990,E,7,09,1.5,33.4547,M';

    expect(isValidMessage(payload)).toBe(true);
    expect(parseGnggaMessage(payload)).toMatchObject({
      quality_code: '7',
      satellites: 9,
      altitude: 33.4547,
    });
  });

  it('preserves cloud alarm trigger details in a device snapshot', () => {
    const alarm = normalizeAlarm({
      level: 'RED',
      source: 'cloud',
      metric: 'acc_x',
      label: '加速度 X',
      value: -0.85,
      absolute_value: 0.85,
      threshold: 0.8,
      message: '加速度 X 达到 0.850 g，阈值 0.800 g',
      triggered_at_ms: 1000,
      conditions: [{
        metric: 'acc_x',
        label: '加速度 X',
        value: -0.85,
        absolute_value: 0.85,
        threshold: 0.8,
      }],
    });

    expect(alarm?.source).toBe('cloud');
    expect(alarm?.conditions).toHaveLength(1);
    expect(alarm?.absolute_value).toBe(0.85);
  });
});
