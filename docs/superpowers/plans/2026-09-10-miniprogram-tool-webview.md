# 工具站微信小程序 WebView Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有逐梦工具箱以移动端工具模式接入微信小程序，复用网站工具逻辑，同时隐藏个人项目页面。

**Architecture:** 小程序只提供 TypeScript WebView 壳，打开 `https://zhumenggy.top/?mini=1`；`SD` 网站通过会话级 mini 模式渲染工具专用首页、紧凑布局和路由保护。工具继续由现有 React 注册表与后端接口提供，复杂浏览器能力先给出兼容性提示，不在首版重复原生重写。

**Tech Stack:** 微信原生小程序 TypeScript/WXML/WXSS、React 18、React Router、Vite、Vitest、现有 `SD` CSS 变量与工具注册表。

---

## 文件结构与职责

### 网站 `SD`

- Create: `SD/lib/miniMode.ts` — 读取 `?mini=1`、保存会话状态、判断当前是否为小程序工具模式。
- Test: `SD/lib/miniMode.test.ts` — 覆盖入口参数、会话延续、普通访问和显式退出。
- Create: `SD/pages/MiniToolsPage.tsx` — 不含个人项目的移动工具首页，提供搜索、分类和全部工具入口。
- Test: `SD/pages/MiniToolsPage.test.tsx` — 验证工具首页内容与个人项目隔离。
- Create: `SD/layouts/MiniToolLayout.tsx` — WebView 内使用的紧凑顶部栏、内容区和简化页脚。
- Test: `SD/layouts/MiniToolLayout.test.tsx` — 验证标题、返回入口和 Outlet 渲染。
- Test: `SD/App.miniMode.test.tsx` — 验证个人项目路由在 mini 模式下回到工具首页。
- Create: `SD/components/MiniCompatibilityNotice.tsx` — 对明显依赖鼠标/桌面输入的工具显示移动端兼容性提示。
- Test: `SD/components/MiniCompatibilityNotice.test.tsx` — 验证提示只在指定工具上显示。
- Modify: `SD/App.tsx` — 根据 mini 模式选择首页，并保护个人项目、报告、登录和独立工作区路由。
- Modify: `SD/layouts/AppLayout.tsx` — 在普通桌面布局与 `MiniToolLayout` 之间分派。
- Modify: `SD/components/ToolWindow.tsx` — 在工具内容上方挂载兼容性提示。
- Modify: `SD/pages/ToolboxPage.tsx` — mini 模式下隐藏广告位和桌面专属留白。
- Modify: `SD/index.css` — 增加 mini 工具首页、工具壳层、窄屏卡片和安全区样式。
- Create: `SD/miniprogramContract.test.ts` — 检查小程序配置、WebView 标记和错误重试契约。

### 小程序 `xiaochengxu`

- Modify: `xiaochengxu/miniprogram/app.json` — 只保留正式首页并设置产品标题。
- Modify: `xiaochengxu/miniprogram/app.ts` — 移除官方示例日志和用户资料登录逻辑。
- Modify: `xiaochengxu/miniprogram/app.wxss` — 设置 WebView 页面基础背景。
- Modify: `xiaochengxu/miniprogram/pages/index/index.ts` — WebView 加载、错误、重试和分享逻辑。
- Modify: `xiaochengxu/miniprogram/pages/index/index.wxml` — WebView 与 `cover-view` 状态层。
- Modify: `xiaochengxu/miniprogram/pages/index/index.wxss` — 加载失败面板与安全区适配。
- Create: `xiaochengxu/miniprogram/config.ts` — 线上入口地址和重试 URL 构造函数。
- Create: `xiaochengxu/README.md` — 微信开发者工具、业务域名和发布前检查说明。

---

### Task 1: 建立可持久化的 mini 模式判断

**Files:**
- Create: `SD/lib/miniMode.test.ts`
- Create: `SD/lib/miniMode.ts`

- [ ] **Step 1: Write the failing tests**

```ts
import { describe, expect, it } from 'vitest';
import { readMiniMode, MINI_MODE_STORAGE_KEY } from './miniMode';

function createStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
    value: (key: string) => values.get(key),
  };
}

describe('mini mode', () => {
  it('enables and remembers mini mode from the entry query', () => {
    const storage = createStorage();

    expect(readMiniMode('?mini=1', storage)).toBe(true);
    expect(storage.value(MINI_MODE_STORAGE_KEY)).toBe('1');
    expect(readMiniMode('', storage)).toBe(true);
  });

  it('does not enable mini mode for an ordinary website visit', () => {
    const storage = createStorage();

    expect(readMiniMode('', storage)).toBe(false);
    expect(readMiniMode('?mini=0', storage)).toBe(false);
  });

  it('clears a previous mini session when mini=0 is explicit', () => {
    const storage = createStorage({ [MINI_MODE_STORAGE_KEY]: '1' });

    expect(readMiniMode('?mini=0', storage)).toBe(false);
    expect(storage.value(MINI_MODE_STORAGE_KEY)).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run the focused test and verify it fails for the missing module**

Run: `npm test -- lib/miniMode.test.ts`

Expected: FAIL because `SD/lib/miniMode.ts` does not exist yet; do not change the test to make an existing implementation pass.

- [ ] **Step 3: Implement the smallest pure utility**

```ts
export const MINI_MODE_STORAGE_KEY = 'sd-mini-mode';

export interface MiniModeStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export function readMiniMode(search: string, storage: MiniModeStorage | null = null): boolean {
  const requestedMode = new URLSearchParams(search).get('mini');

  if (requestedMode === '1') {
    storage?.setItem(MINI_MODE_STORAGE_KEY, '1');
    return true;
  }

  if (requestedMode === '0') {
    storage?.removeItem(MINI_MODE_STORAGE_KEY);
    return false;
  }

  return storage?.getItem(MINI_MODE_STORAGE_KEY) === '1';
}

export function getMiniMode(): boolean {
  if (typeof window === 'undefined') return false;

  try {
    return readMiniMode(window.location.search, window.sessionStorage);
  } catch {
    return readMiniMode(window.location.search);
  }
}
```

- [ ] **Step 4: Run the focused test and the existing utility tests**

Run: `npm test -- lib/miniMode.test.ts`

Expected: 3 mini-mode tests PASS with no errors.

- [ ] **Step 5: Commit the utility**

```bash
git add SD/lib/miniMode.ts SD/lib/miniMode.test.ts
git commit -m "feat: add persistent mini program mode detection"
```

### Task 2: Build the tool-only mini homepage

**Files:**
- Create: `SD/pages/MiniToolsPage.test.tsx`
- Create: `SD/pages/MiniToolsPage.tsx`

- [ ] **Step 1: Write the failing page tests**

```tsx
import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MiniToolsPage } from './MiniToolsPage';

describe('MiniToolsPage', () => {
  it('shows search, categories, and tool entries without personal project content', () => {
    render(
      <MemoryRouter>
        <MiniToolsPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: '工具箱' })).toBeTruthy();
    expect(screen.getByRole('searchbox', { name: '搜索工具' })).toBeTruthy();
    expect(screen.getByText('PDF 工具')).toBeTruthy();
    expect(screen.getByRole('link', { name: /打开 JSON 格式化/ })).toBeTruthy();
    expect(screen.getByRole('link', { name: /股票研究/ })).toBeTruthy();
    expect(screen.getByRole('link', { name: /趣味游戏/ })).toBeTruthy();
    expect(screen.queryByText('研报中心')).toBeNull();
    expect(screen.queryByText('个人项目')).toBeNull();
  });

  it('filters the tool list by search text', async () => {
    const userEvent = (await import('@testing-library/user-event')).default;
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <MiniToolsPage />
      </MemoryRouter>,
    );

    await user.type(screen.getByRole('searchbox', { name: '搜索工具' }), 'JSON');

    expect(screen.getByRole('link', { name: /打开 JSON 格式化/ })).toBeTruthy();
    expect(screen.queryByRole('link', { name: /打开 BMI/ })).toBeNull();
  });
});
```

- [ ] **Step 2: Run the page tests and verify they fail because the page is missing**

Run: `npm test -- pages/MiniToolsPage.test.tsx`

Expected: FAIL with an import/module error for `./MiniToolsPage`.

- [ ] **Step 3: Implement the tool-only page**

```tsx
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search } from 'lucide-react';
import { CATEGORIES, TOOLS } from '../tools/registry';
import { getIcon } from '../lib/iconMap';
import { ToolLink } from '../components/ToolLink';

const normalize = (value: string) => value.trim().toLocaleLowerCase();

export function MiniToolsPage() {
  const [query, setQuery] = useState('');
  const needle = normalize(query);
  const filteredTools = useMemo(() => {
    if (!needle) return TOOLS;
    return TOOLS.filter((tool) => normalize([tool.name, tool.description, ...(tool.tags ?? [])].join(' ')).includes(needle));
  }, [needle]);

  const visibleCategories = needle
    ? CATEGORIES.filter((category) => filteredTools.some((tool) => tool.category === category.id))
    : CATEGORIES;

  const specialEntries = [
    { href: '/stock/', name: '股票研究', description: '股票行情、策略和研究工具', icon: 'TrendingUp', external: true },
    { href: '/games', name: '趣味游戏', description: '小游戏和本地 AI 对战', icon: 'Gamepad2', external: false },
  ] as const;

  return (
    <div className="mini-tools-home">
      <section className="mini-tools-home__hero" aria-labelledby="mini-tools-title">
        <p className="mini-tools-home__eyebrow">逐梦工具箱 · 小程序工具版</p>
        <h1 id="mini-tools-title">工具箱</h1>
        <p>常用 PDF、图片、开发、计算和生活工具，打开即用。</p>
        <label className="mini-tools-home__search">
          <span className="sr-only">搜索工具</span>
          <Search aria-hidden="true" />
          <input
            type="search"
            aria-label="搜索工具"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索工具名称或关键词"
          />
        </label>
      </section>

      <section className="mini-tools-home__categories" aria-labelledby="mini-category-title">
        <div className="mini-section-heading">
          <h2 id="mini-category-title">工具分类</h2>
          <span>{filteredTools.length} 个工具</span>
        </div>
        <div className="mini-category-scroller">
          {visibleCategories.map((category) => {
            const Icon = getIcon(category.icon);
            const count = filteredTools.filter((tool) => tool.category === category.id).length;
            return (
              <Link key={category.id} to={`/gj?category=${encodeURIComponent(category.id)}`} className="mini-category-chip">
                <Icon aria-hidden="true" />
                <span>{category.name}</span>
                <small>{count}</small>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="mini-tools-home__list" aria-labelledby="mini-tool-list-title">
        <div className="mini-section-heading">
          <h2 id="mini-tool-list-title">全部工具</h2>
          <span>本地优先</span>
        </div>
        <div className="mini-special-grid" aria-label="其他工具入口">
          {specialEntries.map((entry) => {
            const Icon = getIcon(entry.icon);
            const content = (
              <>
                <span className="mini-tool-card__icon bg-gradient-to-br from-[#5f6f42] to-[#9a5a28]"><Icon aria-hidden="true" /></span>
                <span className="mini-tool-card__name">{entry.name}</span>
                <span className="mini-tool-card__description">{entry.description}</span>
              </>
            );
            return entry.external
              ? <a key={entry.href} href={entry.href} className="mini-tool-card">{content}</a>
              : <Link key={entry.href} to={entry.href} className="mini-tool-card">{content}</Link>;
          })}
        </div>
        <div className="mini-tool-grid">
          {filteredTools.map((tool) => {
            const Icon = getIcon(tool.icon);
            return (
              <ToolLink key={tool.id} toolId={tool.id} aria-label={`打开 ${tool.name}`} className="mini-tool-card">
                <span className={`mini-tool-card__icon bg-gradient-to-br ${tool.gradient}`}><Icon aria-hidden="true" /></span>
                <span className="mini-tool-card__name">{tool.name}</span>
                <span className="mini-tool-card__description">{tool.description}</span>
              </ToolLink>
            );
          })}
        </div>
        {filteredTools.length === 0 && <p className="mini-tools-home__empty">没有找到匹配工具，换个关键词试试。</p>}
      </section>
    </div>
  );
}

export default MiniToolsPage;
```

- [ ] **Step 4: Run the page tests and all existing website tests**

Run: `npm test -- pages/MiniToolsPage.test.tsx && npm test`

Expected: the new page tests and the existing suite PASS.

- [ ] **Step 5: Commit the mini homepage**

```bash
git add SD/pages/MiniToolsPage.tsx SD/pages/MiniToolsPage.test.tsx
git commit -m "feat: add tool-only mini program homepage"
```

### Task 3: Add route protection and the compact WebView layout

**Files:**
- Create: `SD/layouts/MiniToolLayout.test.tsx`
- Create: `SD/App.miniMode.test.tsx`
- Create: `SD/layouts/MiniToolLayout.tsx`
- Modify: `SD/App.tsx`
- Modify: `SD/layouts/AppLayout.tsx`

- [ ] **Step 1: Write the failing compact-layout test**

```tsx
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MiniToolLayout } from './MiniToolLayout';

describe('MiniToolLayout', () => {
  it('renders a compact title bar and the current tool outlet', () => {
    render(
      <MemoryRouter initialEntries={['/tool/json-format']}>
        <Routes>
          <Route element={<MiniToolLayout />}>
            <Route path="/tool/:toolId" element={<h1>JSON 格式化</h1>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: '逐梦工具箱' })).toBeTruthy();
    expect(screen.getByRole('link', { name: '返回工具箱' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'JSON 格式化' })).toBeTruthy();
  });
});
```

Add the route-boundary regression test in `SD/App.miniMode.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import App from './App';

describe('App mini mode routing', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    window.history.pushState({}, '', '/wuwa?mini=1');
  });

  afterEach(() => {
    window.history.pushState({}, '', '/');
    window.sessionStorage.clear();
  });

  it('redirects a personal project route to the mini tool home', async () => {
    render(<App />);

    expect(await screen.findByRole('heading', { name: '工具箱' })).toBeTruthy();
    expect(screen.queryByText('AI 伴侣')).toBeNull();
  });
});
```

- [ ] **Step 2: Run the focused tests and verify they fail because the new layout is missing**

Run: `npm test -- layouts/MiniToolLayout.test.tsx App.miniMode.test.tsx`

Expected: FAIL with an import/module error for `./MiniToolLayout`; the route-boundary test is also red because the new mini route is not implemented.

- [ ] **Step 3: Implement the compact layout**

```tsx
import { ArrowLeft, Wrench } from 'lucide-react';
import { Link, Outlet, useLocation } from 'react-router-dom';

export function MiniToolLayout() {
  const location = useLocation();
  const isHome = location.pathname === '/';

  return (
    <div className="mini-tool-shell">
      <header className="mini-tool-shell__header">
        <Link to="/" className="mini-tool-shell__brand" aria-label="逐梦工具箱">
          <span className="mini-tool-shell__brand-icon"><Wrench aria-hidden="true" /></span>
          <span>逐梦工具箱</span>
        </Link>
        {!isHome && (
          <Link to="/" className="mini-tool-shell__back" aria-label="返回工具箱">
            <ArrowLeft aria-hidden="true" />
            <span>工具箱</span>
          </Link>
        )}
      </header>
      <main id="main-content" className="mini-tool-shell__main"><Outlet /></main>
      <footer className="mini-tool-shell__footer">本地优先 · 工具结果留在当前设备</footer>
    </div>
  );
}

export default MiniToolLayout;
```

- [ ] **Step 4: Split the existing desktop layout behind a mode switch**

In `SD/layouts/AppLayout.tsx`, rename the current exported implementation to `DesktopAppLayout`, import `MiniToolLayout` and `getMiniMode`, then use this exact wrapper:

```tsx
export const AppLayout: React.FC = () => (
  getMiniMode() ? <MiniToolLayout /> : <DesktopAppLayout />
);

export default AppLayout;
```

Keep the current desktop JSX unchanged inside `DesktopAppLayout` so ordinary website users retain the existing sidebar, account menu, theme control, footer, and desktop navigation.

- [ ] **Step 5: Integrate the mini home and protect non-tool routes**

In `SD/App.tsx`, import `Navigate`, `useParams`, `MiniToolsPage`, and `getMiniMode`, and import `type ReactNode` with the existing React imports. Then use these route helpers before the default component:

```tsx
function MiniModeBlocked({ children }: { children: ReactNode }) {
  return getMiniMode() ? <Navigate replace to="/?mini=1" /> : <>{children}</>;
}

function CategoryEntry() {
  const { categoryId = '' } = useParams();
  return getMiniMode()
    ? <Navigate replace to={`/gj?category=${encodeURIComponent(categoryId)}`} />
    : <CategoryPage />;
}
```

Change the route table as follows:

```tsx
<Route element={<AppLayout />}>
  <Route index element={getMiniMode() ? <MiniToolsPage /> : <HomePage />} />
  <Route path="/gj" element={<ToolboxPage />} />
  <Route path="/fy" element={<TranslationPage />} />
  <Route path="/games" element={<GamesPage />} />
  <Route path="/games/:gameId" element={<GamePage />} />
  <Route path="/tool/:toolId" element={<ToolWindow />} />
  <Route path="/bp" element={<MiniModeBlocked><Stm32Page /></MiniModeBlocked>} />
  <Route path="/ai" element={<MiniModeBlocked><AIAgentPage /></MiniModeBlocked>} />
  <Route path="/wuwa" element={<MiniModeBlocked><ShouAnRenPage /></MiniModeBlocked>} />
  <Route path="/reports" element={<MiniModeBlocked><ReportsPage /></MiniModeBlocked>} />
  <Route path="/reports/github" element={<MiniModeBlocked><GitHubReportsPage /></MiniModeBlocked>} />
  <Route path="/reports/ai" element={<MiniModeBlocked><AIReportsPage /></MiniModeBlocked>} />
  <Route path="/reports/news" element={<MiniModeBlocked><NewsEventsPage /></MiniModeBlocked>} />
  <Route path="/reports/briefing" element={<MiniModeBlocked><AIBriefingPage /></MiniModeBlocked>} />
  <Route path="/auth/login" element={<MiniModeBlocked><LoginPage /></MiniModeBlocked>} />
</Route>
<Route path="/category/:categoryId" element={<CategoryEntry />} />
<Route path="/stm32/*" element={<MiniModeBlocked><Stm32Window /></MiniModeBlocked>} />
```

Do not add a stock route to this table because the stock frontend is an independent application reached through its existing `/stock/` entry. The mini homepage uses a normal same-domain anchor for that independent frontend and a React Router link for `/games`.

- [ ] **Step 6: Run focused layout and routing tests**

Run: `npm test -- layouts/MiniToolLayout.test.tsx App.miniMode.test.tsx pages/MiniToolsPage.test.tsx && npm run lint`

Expected: new layout/page tests PASS and TypeScript reports no errors.

- [ ] **Step 7: Commit the layout and route integration**

```bash
git add SD/App.tsx SD/App.miniMode.test.tsx SD/layouts/AppLayout.tsx SD/layouts/MiniToolLayout.tsx SD/layouts/MiniToolLayout.test.tsx
git commit -m "feat: route website through compact mini tool layout"
```

### Task 4: Add mobile-first tool mode styling and hide desktop-only blocks

**Files:**
- Modify: `SD/pages/ToolboxPage.tsx`
- Modify: `SD/index.css`

- [ ] **Step 1: Add the mini-mode condition to the toolbox page**

Import `getMiniMode` into `SD/pages/ToolboxPage.tsx`, read it once inside `ToolboxPage`, and keep the existing inline ad out of the mini view:

```tsx
// At the start of the existing ToolboxPage component body:
const miniMode = getMiniMode();

// At the current tools-inline AdSlot location:
{!miniMode && <AdSlot name="tools-inline" className="mt-8" />}
```

There is one `AdSlot` in the current file (`tools-inline` near the bottom). Do not remove the tool filters or user-local recent/favorite logic.

- [ ] **Step 2: Add the compact shell and tool-card CSS**

Append the following CSS to `SD/index.css`:

```css
.mini-tool-shell {
  min-height: 100vh;
  color: var(--text);
  background: var(--page-bg);
}

.mini-tool-shell__header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  min-height: 52px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: calc(8px + env(safe-area-inset-top)) 16px 8px;
  border-bottom: 1px solid var(--border);
  background: color-mix(in srgb, var(--surface) 92%, transparent);
  backdrop-filter: blur(16px);
}

.mini-tool-shell__brand,
.mini-tool-shell__back {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text);
  font-weight: 700;
  text-decoration: none;
}

.mini-tool-shell__brand-icon {
  display: inline-grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 9px;
  color: #fff;
  background: linear-gradient(135deg, #9a5a28, #5f6f42);
}

.mini-tool-shell__brand-icon svg,
.mini-tool-shell__back svg {
  width: 16px;
  height: 16px;
}

.mini-tool-shell__back {
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 600;
}

.mini-tool-shell__main {
  width: min(100%, 760px);
  min-height: calc(100vh - 53px);
  margin: 0 auto;
  padding: 16px 14px calc(28px + env(safe-area-inset-bottom));
}

.mini-tool-shell__footer {
  padding: 12px 16px calc(16px + env(safe-area-inset-bottom));
  color: var(--text-soft);
  font-size: 12px;
  text-align: center;
}

.mini-tools-home {
  display: grid;
  gap: 18px;
}

.mini-tools-home__hero,
.mini-tools-home__categories,
.mini-tools-home__list {
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: 20px;
  background: color-mix(in srgb, var(--surface) 94%, transparent);
  box-shadow: var(--shadow-sm);
}

.mini-tools-home__eyebrow {
  margin: 0 0 6px;
  color: var(--accent-strong);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .08em;
}

.mini-tools-home h1,
.mini-tools-home h2 {
  margin: 0;
  color: var(--text);
}

.mini-tools-home h1 { font-size: clamp(28px, 8vw, 42px); }
.mini-tools-home h2 { font-size: 18px; }
.mini-tools-home__hero > p:not(.mini-tools-home__eyebrow) { margin: 8px 0 16px; color: var(--text-muted); }

.mini-tools-home__search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  border: 1px solid var(--border-strong);
  border-radius: 14px;
  background: var(--surface-raised);
}

.mini-tools-home__search svg { flex: 0 0 auto; width: 18px; color: var(--text-soft); }
.mini-tools-home__search input { width: 100%; min-height: 46px; border: 0; outline: 0; color: var(--text); background: transparent; }

.mini-section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.mini-section-heading span { color: var(--text-soft); font-size: 12px; }

.mini-category-scroller { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 3px; scrollbar-width: none; }
.mini-category-scroller::-webkit-scrollbar { display: none; }

.mini-category-chip { display: inline-flex; flex: 0 0 auto; align-items: center; gap: 6px; padding: 9px 11px; border: 1px solid var(--border); border-radius: 999px; color: var(--text-muted); background: var(--surface-raised); font-size: 12px; text-decoration: none; }
.mini-category-chip svg { width: 15px; height: 15px; color: var(--accent-strong); }
.mini-category-chip small { color: var(--text-soft); }

.mini-tool-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.mini-special-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }
.mini-tool-card { display: grid; min-width: 0; gap: 7px; padding: 13px; border: 1px solid var(--border); border-radius: 16px; color: var(--text); background: var(--surface-raised); text-decoration: none; }
.mini-tool-card:active { transform: translateY(1px); }
.mini-tool-card__icon { display: inline-grid; width: 32px; height: 32px; place-items: center; border-radius: 10px; color: #fff; }
.mini-tool-card__icon svg { width: 17px; height: 17px; }
.mini-tool-card__name { overflow: hidden; font-size: 14px; font-weight: 800; text-overflow: ellipsis; white-space: nowrap; }
.mini-tool-card__description { display: -webkit-box; overflow: hidden; color: var(--text-soft); font-size: 11px; line-height: 1.45; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.mini-tools-home__empty { margin: 0; padding: 20px 0; color: var(--text-muted); text-align: center; }

.mini-tool-shell .tool-window-footer,
.mini-tool-shell .tool-window-related,
.mini-tool-shell .desktop-only { display: none; }

@media (min-width: 560px) {
  .mini-tool-shell__main { padding-right: 20px; padding-left: 20px; }
  .mini-tool-grid, .mini-special-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
```

- [ ] **Step 3: Run the website tests and type check**

Run: `npm test && npm run lint`

Expected: existing tests pass and no TypeScript errors are introduced.

- [ ] **Step 4: Commit mobile tool mode styling**

```bash
git add SD/pages/ToolboxPage.tsx SD/index.css
git commit -m "feat: add mobile tool mode styling"
```

### Task 5: Add WebView compatibility notices for desktop-only tools

**Files:**
- Create: `SD/components/MiniCompatibilityNotice.test.tsx`
- Create: `SD/components/MiniCompatibilityNotice.tsx`
- Modify: `SD/components/ToolWindow.tsx`
- Modify: `SD/index.css`

- [ ] **Step 1: Write the failing notice tests**

```tsx
import { beforeEach, afterEach, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MiniCompatibilityNotice } from './MiniCompatibilityNotice';

describe('MiniCompatibilityNotice', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/?mini=1');
  });

  afterEach(() => {
    window.history.pushState({}, '', '/');
    window.sessionStorage.clear();
  });

  it('explains mouse-tool limitations in mini mode', () => {
    render(<MiniCompatibilityNotice toolId="cps-test" />);

    expect(screen.getByRole('note')).toHaveTextContent('手机触控');
  });

  it('does not render for ordinary tools', () => {
    render(<MiniCompatibilityNotice toolId="json-format" />);

    expect(screen.queryByRole('note')).toBeNull();
  });
});
```

The focused test file runs with the normal website test setup, where the test URL is initialized to `/?mini=1`; the component must still be safe to render without a Router.

- [ ] **Step 2: Run the notice tests and verify they fail because the component is missing**

Run: `npm test -- components/MiniCompatibilityNotice.test.tsx`

Expected: FAIL with an import/module error for `./MiniCompatibilityNotice`.

- [ ] **Step 3: Implement the explicit desktop-input notice**

```tsx
import { getMiniMode } from '../lib/miniMode';

const DESKTOP_INPUT_TOOL_IDS = new Set([
  'cps-test', 'reaction-test', 'dpi-analyzer', 'double-click-test',
  'mouse-button-test', 'scroll-test', 'mouse-trail', 'polling-rate',
  'jitter-test', 'drag-test',
]);

export function MiniCompatibilityNotice({ toolId }: { toolId: string }) {
  if (!getMiniMode() || !DESKTOP_INPUT_TOOL_IDS.has(toolId)) return null;

  return (
    <aside className="mini-compatibility-notice" role="note">
      手机触控可以打开此工具，但它主要针对鼠标/桌面输入设计，手机上可能无法得到完整结果。
    </aside>
  );
}
```

- [ ] **Step 4: Mount the notice in `ToolWindow`**

Import `MiniCompatibilityNotice` and place it immediately before the tool component shell, after the tool title/description block:

```tsx
<MiniCompatibilityNotice toolId={tool.id} />
<div className={getToolComponentShellClass(tool.category)}>
  <ToolErrorBoundary toolName={tool.name} onClose={handleClose}>
    <tool.component onClose={handleClose} />
  </ToolErrorBoundary>
</div>
```

Add this mini-only style to `SD/index.css`:

```css
.mini-tool-shell .mini-compatibility-notice {
  margin: 0 0 14px;
  padding: 10px 12px;
  border: 1px solid #e5c98f;
  border-radius: 12px;
  color: #78551d;
  background: #fff7df;
  font-size: 13px;
  line-height: 1.5;
}
```

- [ ] **Step 5: Run the focused and full website tests**

Run: `npm test -- components/MiniCompatibilityNotice.test.tsx && npm test && npm run lint`

Expected: the notice appears only for the listed desktop-input tools in mini mode and all tests/type checks pass.

- [ ] **Step 6: Commit the compatibility boundary**

```bash
git add SD/components/MiniCompatibilityNotice.tsx SD/components/MiniCompatibilityNotice.test.tsx SD/components/ToolWindow.tsx SD/index.css
git commit -m "feat: explain desktop-only tool limits in mini mode"
```

### Task 6: Add the native TypeScript WebView shell

**Files:**
- Create: `SD/miniprogramContract.test.ts`
- Create: `xiaochengxu/miniprogram/config.ts`
- Modify: `xiaochengxu/miniprogram/app.json`
- Modify: `xiaochengxu/miniprogram/app.ts`
- Modify: `xiaochengxu/miniprogram/app.wxss`
- Modify: `xiaochengxu/miniprogram/pages/index/index.ts`
- Modify: `xiaochengxu/miniprogram/pages/index/index.wxml`
- Modify: `xiaochengxu/miniprogram/pages/index/index.wxss`

- [ ] **Step 1: Write the failing contract test**

```ts
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
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
```

- [ ] **Step 2: Run the contract test and verify it fails against the starter template**

Run from `E:\AI\gp\SD`: `npm test -- miniprogramContract.test.ts`

Expected: FAIL because the starter `app.json` still includes `pages/logs/logs` and the index WXML contains the Hello World profile form instead of `<web-view>`.

- [ ] **Step 3: Add the URL configuration**

Create `xiaochengxu/miniprogram/config.ts`:

```ts
export const WEB_ENTRY_URL = 'https://zhumenggy.top/?mini=1';

export function buildRetryUrl(timestamp: number): string {
  return `${WEB_ENTRY_URL}&retry=${timestamp}`;
}
```

- [ ] **Step 4: Replace the starter app and page logic**

Use the following `xiaochengxu/miniprogram/app.ts`:

```ts
App<IAppOption>({
  globalData: {},
});
```

Use the following `xiaochengxu/miniprogram/app.json`:

```json
{
  "pages": ["pages/index/index"],
  "window": {
    "navigationBarTextStyle": "black",
    "navigationBarTitleText": "逐梦工具箱",
    "navigationBarBackgroundColor": "#fffaf2",
    "backgroundColor": "#fffaf2",
    "backgroundTextStyle": "light"
  },
  "style": "v2",
  "componentFramework": "glass-easel",
  "lazyCodeLoading": "requiredComponents"
}
```

Use the following `xiaochengxu/miniprogram/pages/index/index.ts`:

```ts
import { buildRetryUrl, WEB_ENTRY_URL } from '../../config';

type WebViewStatus = 'loading' | 'ready' | 'error';

Page({
  data: {
    src: WEB_ENTRY_URL,
    status: 'loading' as WebViewStatus,
  },

  onWebViewLoad() {
    this.setData({ status: 'ready' as WebViewStatus });
  },

  onWebViewError() {
    this.setData({ status: 'error' as WebViewStatus });
  },

  retry() {
    this.setData({
      src: buildRetryUrl(Date.now()),
      status: 'loading' as WebViewStatus,
    });
  },

  onShareAppMessage() {
    return {
      title: '逐梦工具箱｜常用在线工具',
      path: '/pages/index/index',
    };
  },
});
```

Use the following `xiaochengxu/miniprogram/pages/index/index.wxml`:

```xml
<view class="webview-page">
  <web-view
    wx:if="{{status !== 'error'}}"
    src="{{src}}"
    bindload="onWebViewLoad"
    binderror="onWebViewError"
  ></web-view>

  <cover-view wx:if="{{status === 'loading'}}" class="state-mask">
    <cover-view class="state-card">
      <cover-view class="state-title">工具箱加载中</cover-view>
      <cover-view class="state-description">正在打开工具界面，请稍候</cover-view>
    </cover-view>
  </cover-view>

  <cover-view wx:if="{{status === 'error'}}" class="state-mask">
    <cover-view class="state-card">
      <cover-view class="state-title">页面加载失败</cover-view>
      <cover-view class="state-description">请检查网络或稍后重试</cover-view>
      <cover-view class="retry-button" bindtap="retry">重新加载</cover-view>
    </cover-view>
  </cover-view>
</view>
```

Use the following `xiaochengxu/miniprogram/pages/index/index.wxss`:

```css
page {
  height: 100%;
  background: #fffaf2;
}

.webview-page {
  position: relative;
  width: 100%;
  height: 100vh;
  background: #fffaf2;
}

.state-mask {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40rpx;
  background: #fffaf2;
}

.state-card {
  width: 100%;
  max-width: 620rpx;
  padding: 48rpx 36rpx;
  border: 1rpx solid #ead9c3;
  border-radius: 28rpx;
  box-sizing: border-box;
  color: #2f241b;
  background: #fff;
  text-align: center;
}

.state-title {
  font-size: 36rpx;
  font-weight: 700;
}

.state-description {
  margin-top: 18rpx;
  color: #806b59;
  font-size: 26rpx;
  line-height: 1.6;
}

.retry-button {
  margin: 32rpx auto 0;
  padding: 18rpx 30rpx;
  border-radius: 999rpx;
  color: #fff;
  background: #7a421b;
  font-size: 28rpx;
}
```

Use the following `xiaochengxu/miniprogram/app.wxss`:

```css
page {
  background: #fffaf2;
}
```

- [ ] **Step 5: Run the contract test and both TypeScript checks**

Run from `E:\AI\gp\SD`: `npm test -- miniprogramContract.test.ts && npm run lint`

Run from `E:\AI\gp`: `npx tsc --noEmit -p xiaochengxu/tsconfig.json`

Expected: the contract tests, SD type check, and mini-program type check PASS.

- [ ] **Step 6: Commit the native WebView shell**

```bash
git add SD/miniprogramContract.test.ts xiaochengxu/miniprogram/app.json xiaochengxu/miniprogram/app.ts xiaochengxu/miniprogram/app.wxss xiaochengxu/miniprogram/config.ts xiaochengxu/miniprogram/pages/index/index.ts xiaochengxu/miniprogram/pages/index/index.wxml xiaochengxu/miniprogram/pages/index/index.wxss
git commit -m "feat: add mini program webview shell"
```

### Task 7: Document domain setup and run full verification

**Files:**
- Create: `xiaochengxu/README.md`

- [ ] **Step 1: Write the release checklist**

Create `xiaochengxu/README.md` with the following complete instructions:

```md
# 逐梦工具箱微信小程序

这是工具站的微信小程序 WebView 壳，工具逻辑继续运行在 `https://zhumenggy.top/?mini=1`。

## 开发者工具

1. 用微信开发者工具打开本目录。
2. 使用项目配置中的 AppID。
3. 开发阶段可以在开发者工具的本地设置中临时关闭合法域名校验；真机预览和发布前必须恢复校验。

## 发布前配置

1. 确认 `zhumenggy.top` 使用 HTTPS，并能正常打开 `https://zhumenggy.top/?mini=1`。
2. 在小程序后台的开发设置中添加 WebView 业务域名。
3. 按后台要求下载域名校验文件，并把文件原样放到网站域名根目录。
4. 完成校验后再进行真机预览和提审。
5. 网站中需要调用后端的工具必须使用线上 HTTPS API，不能保留 `localhost`、局域网 IP 或本地端口。

## 首版边界

首版展示工具首页、分类、搜索、工具详情、股票入口和小游戏；个人项目、研报展示、登录管理和独立工作区不会进入小程序工具模式。依赖桌面鼠标、浏览器下载或高级文件 API 的工具按 WebView 能力显示提示或后续单独适配。
```

- [ ] **Step 2: Run repository verification**

Run from `E:\AI\gp\SD`:

```bash
npm test
npm run lint
npm run build:app
```

Run from `E:\AI\gp`:

```bash
npx tsc --noEmit -p xiaochengxu/tsconfig.json
git diff --check
```

Expected: all commands exit with code 0 and no whitespace errors are reported.

- [ ] **Step 3: Manually verify the mobile website mode**

Run: `npm run dev` in `E:\AI\gp\SD`, then open `http://127.0.0.1:8013/?mini=1` in the browser.

Verify visibly:

- the compact top bar and “工具箱” heading are present;
- search and category chips fit within a narrow viewport;
- personal project/report cards are absent;
- clicking a tool opens `ToolWindow` in the same mini shell;
- opening `/wuwa`, `/reports`, or `/auth/login` while the mini session is active redirects to the mini tool home;
- ordinary `http://127.0.0.1:8013/` still shows the existing desktop homepage.

- [ ] **Step 4: Manually verify the WeChat developer tool flow**

Open `E:\AI\gp\xiaochengxu` in WeChat Developer Tools, compile the project, and confirm the page enters the HTTPS website. Temporarily simulate a failed network request to verify the error panel and “重新加载” action; restore the normal network setting before finishing.

- [ ] **Step 5: Commit the documentation**

```bash
git add xiaochengxu/README.md
git commit -m "docs: document mini program webview release setup"
```

## Final handoff

After all checks pass, report the changed files, verification commands, the required WeChat business-domain configuration, and any individual tools that still need native file/camera adaptation. Do not claim production release until the domain has been configured and real-device preview succeeds.
