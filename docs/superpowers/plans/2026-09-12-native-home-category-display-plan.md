# 原生小程序首页分类展示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复原生小程序分类数量统计并将首页改为完整分类入口页。

**Architecture:** 分类数量由 `data/toolRegistry.ts` 统一计算，首页只消费分类摘要；首页无搜索词时渲染完整分类卡片，有搜索词时渲染现有搜索结果。工具状态和分类页路由保持不变。

**Tech Stack:** 微信小程序 WXML/TS/WXSS、TypeScript、Vitest。

---

### Task 1: 锁定分类统计和首页展示契约

**Files:**
- Modify: `SD/nativeToolRegistry.test.ts`
- Modify: `SD/nativeMiniProgramContract.test.ts`

- [x] **Step 1: Write the failing tests**

在 `nativeToolRegistry.test.ts` 引入 `getNativeCategorySummaries`，增加断言：摘要数量等于分类数量，`pdf` 和 `audio` 的数量大于 0，并且数量包含适配中工具。

在 `nativeMiniProgramContract.test.ts` 读取 `pages/home/index.ts` 和 `pages/home/index.wxml`，断言首页不再使用 `featuredTools`、`slice(0, 8)` 或“常用工具”，并包含“全部分类”和分类简介绑定。

- [x] **Step 2: Run tests to verify they fail**

Run: `npm test -- nativeToolRegistry.test.ts nativeMiniProgramContract.test.ts`

Expected: FAIL because `getNativeCategorySummaries` 尚未导出，当前首页仍使用前 8 个分类和 `featuredTools`。

### Task 2: 统一分类摘要数据

**Files:**
- Modify: `xiaochengxu/miniprogram/data/toolRegistry.ts`

- [x] **Step 1: Add the minimal registry helper**

新增：

```ts
export type NativeCategorySummary = NativeCategoryDefinition & { count: number };

export function getNativeCategorySummaries(): NativeCategorySummary[] {
  return NATIVE_CATEGORIES.map((category) => ({
    ...category,
    count: NATIVE_TOOLS.filter((tool) => tool.category === category.id).length,
  }));
}
```

该函数不筛选 `status`，使首页数量与分类页登记工具口径一致。

- [x] **Step 2: Run the registry tests**

Run: `npm test -- nativeToolRegistry.test.ts`

Expected: PASS。

### Task 3: 将首页改为完整分类卡片

**Files:**
- Modify: `xiaochengxu/miniprogram/pages/home/index.ts`
- Modify: `xiaochengxu/miniprogram/pages/home/index.wxml`
- Modify: `xiaochengxu/miniprogram/pages/home/index.wxss`

- [x] **Step 1: Consume all category summaries**

将首页 `data.categories` 改为 `getNativeCategorySummaries()`，删除 `featuredTools`，不再切片或按 `ready` 筛选。

- [x] **Step 2: Replace the home content section**

将“工具分类”标题改为“全部分类”，数量绑定 `categories.length`；将横向 `category-scroller/category-chip` 改为两列 `category-grid/category-card`，卡片展示 `item.name`、`item.description` 和 `item.count`，继续绑定 `openCategory`。删除无搜索词时的“常用工具”和 `tool-card` 循环，保留搜索结果区域。

- [x] **Step 3: Add mobile-first card styles**

使用两列自适应网格、原有暖色边框和圆角卡片风格；小屏保持两列，分类名称和简介允许换行，数量使用次要文字样式。

### Task 4: 回归验证

**Files:**
- No additional files.

- [x] **Step 1: Run focused tests**

Run: `npm test -- nativeToolRegistry.test.ts nativeMiniProgramContract.test.ts`

Expected: PASS。

- [x] **Step 2: Run project verification**

Run: `npm test`

Expected: all test files and tests pass。

Run: `npm run lint`

Expected: TypeScript check passes。

Run: `& 'E:\\AI\\gp\\SD\\node_modules\\.bin\\tsc.cmd' --noEmit -p ..\\xiaochengxu\\tsconfig.json`

Expected: mini program TypeScript check passes。

- [x] **Step 3: Review the final diff**

Run: `git diff --check` and `git status --short`。

Expected: only the intended mini program, test, spec and plan files are staged; existing stock-module and AppID/private-config changes remain untouched。
