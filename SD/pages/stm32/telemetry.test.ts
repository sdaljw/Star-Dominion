import { describe, expect, it } from 'vitest';
import { isValidMessage, parseGnggaMessage } from './telemetry';

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
});
