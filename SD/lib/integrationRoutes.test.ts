import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const source = (relativePath: string) =>
  readFileSync(new URL(relativePath, import.meta.url), 'utf8');

describe('independent module integration', () => {
  it('proxies all ShouAnRen root assets to the ShouAnRen service', () => {
    const configSource = source('../vite.config.ts');
    for (const assetRoot of ['/css', '/js', '/static', '/avatars', '/audio']) {
      expect(configSource).toContain(`'${assetRoot}':`);
    }
  });

  it('registers the standalone STM32 page route', () => {
    expect(source('../App.tsx')).toContain('path="/stm32/*"');
  });

  it('does not open the STM32 page automatically', () => {
    expect(source('../pages/Stm32Page.tsx')).not.toContain('window.open(');
  });

  it('reports a missing STM32 map configuration only once in StrictMode', () => {
    const mapSource = source('../pages/stm32/MapSurface.tsx');
    expect(mapSource).toContain('mapConfigurationReportedRef.current');
  });

  it('converts WGS-84 coordinates before rendering them on AMap', () => {
    const mapSource = source('../pages/stm32/MapSurface.tsx');
    expect(mapSource).toContain("from '../../lib/geo'");
    expect(mapSource).toContain('wgs84ToGcj02');
  });

  it('does not render the obsolete top-left alarm overlay', () => {
    const stm32Source = source('../pages/Stm32Window.tsx');
    expect(stm32Source).not.toContain("from './stm32/AlertStack'");
    expect(stm32Source).not.toContain('<AlertStack');
  });

  it('keeps the left telemetry dock within one viewport without the title block', () => {
    const dockSource = source('../pages/stm32/LeftTelemetryDock.tsx');
    expect(dockSource).not.toContain('Telemetry deck');
    expect(dockSource).not.toContain('边坡监测数据');
    expect(dockSource).toContain('h-screen');
    expect(dockSource).toContain('overflow-hidden');
    expect(dockSource).not.toContain('overflow-y-auto');
  });
});
