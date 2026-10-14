import { describe, expect, it } from 'vitest';

import { alarmToDisplacementPoint, parseAlarmPayload } from './displacement';

describe('ALARM displacement data', () => {
  it('preserves signed E/N/U values when parsing an ALARM payload', () => {
    const alarm = parseAlarmPayload(
      'ALARM: level=YELLOW score=30.0 D=10.52mm V=20.74mm/min E=7.62mm N=-6.12mm U=-3.90mm tilt=1.28deg accDyn=0.001g q=4 sats=18',
    );

    expect(alarm).toMatchObject({ E: 7.62, N: -6.12, U: -3.9 });
  });

  it('converts ALARM millimetres to chart metres', () => {
    const point = alarmToDisplacementPoint(
      { E: 7.62, N: -6.12, U: -3.9 },
      '12:06:19',
    );

    expect(point.time).toBe('12:06:19');
    expect(point.x).toBeCloseTo(0.00762, 8);
    expect(point.y).toBeCloseTo(-0.00612, 8);
    expect(point.z).toBeCloseTo(-0.0039, 8);
  });
});
