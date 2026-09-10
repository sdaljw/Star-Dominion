import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const miniRoot = resolve(fileURLToPath(new URL('../xiaochengxu/miniprogram/', import.meta.url)));
const read = (relativePath: string) => readFileSync(resolve(miniRoot, relativePath), 'utf8');

describe('wechat mini program webview shell', () => {
  it('uses only the real index page', () => {
    const app = JSON.parse(read('app.json')) as { pages: string[] };
    expect(app.pages).toEqual(['pages/index/index']);
  });

  it('loads the HTTPS tool site and exposes load/error/retry behavior', () => {
    const markup = read('pages/index/index.wxml');
    const logic = read('pages/index/index.ts');

    expect(markup).toContain('<web-view');
    expect(markup).toContain('bindload="onWebViewLoad"');
    expect(markup).toContain('binderror="onWebViewError"');
    expect(markup).toContain('bindtap="retry"');
    expect(logic).toContain('WEB_ENTRY_URL');
    expect(logic).toContain('onShareAppMessage');
  });
});
