import { describe, expect, it } from 'vitest';

import { wgs84ToGcj02 } from './geo';

describe('WGS-84 to GCJ-02 conversion', () => {
  it('converts mainland GPS coordinates before displaying them on AMap', () => {
    const [longitude, latitude] = wgs84ToGcj02([117.99347180316667, 36.81042920516667]);

    expect(longitude).toBeCloseTo(117.99937974104057, 6);
    expect(latitude).toBeCloseTo(36.81078642338471, 6);
  });

  it('leaves coordinates outside mainland China unchanged', () => {
    expect(wgs84ToGcj02([0, 0])).toEqual([0, 0]);
    expect(wgs84ToGcj02([-73.9857, 40.7484])).toEqual([-73.9857, 40.7484]);
  });
});
