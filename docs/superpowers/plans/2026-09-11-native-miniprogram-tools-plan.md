# 原生小程序工具迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `xiaochengxu` 从 WebView 壳改为个人主体可发布的原生微信小程序，并分批迁移网站中可在手机微信环境运行的工具。

**Architecture:** 使用原生 WXML/TypeScript 页面、公共组件、工具注册表和能力适配服务。首页、分类和工具容器保持统一，轻量工具放主包，PDF/图片/办公等重型能力放分包；网站端 `SD` 不再是小程序运行时依赖。

**Tech Stack:** 微信小程序 TypeScript、WXML、WXSS、`miniprogram-api-typings`、Vitest 契约测试、现有 `SD` 网站纯逻辑模块（逐个去除 React/browser 依赖后复用）。

---

## 执行约束

- 先写失败测试，再修改小程序生产代码；每个迁移批次都必须看到 RED → GREEN。
- 不修改用户当前未提交的 `xiaochengxu/project.config.json` AppID 修改，也不提交 `xiaochengxu/project.private.config.json`。
- 不把股票入口、个人项目、研报、登录管理和独立工作区加入原生小程序。
- 不使用 `<web-view>`、`window`、`document`、`navigator`、浏览器 `File/Blob/URL` 或 React 运行时。
- 需要网络的原生 API 统一使用 `https://zhumenggy.top`；不写入 AppSecret、第三方 API Key 或内部端口。
- 每完成一个任务提交一次，提交只包含该任务的文件。

## 文件结构目标

```text
xiaochengxu/miniprogram/
├─ app.ts / app.json / app.wxss
├─ data/toolRegistry.ts / data/categories.ts
├─ types/tool.ts
├─ pages/home/ / pages/category/ / pages/tool/
├─ components/common/
├─ components/tools/
├─ packages/
├─ services/http.ts / file.ts / storage.ts
└─ utils/
```

测试继续放在网站项目的 Vitest 环境中，因为 `xiaochengxu` 当前只有微信编译器，没有独立的 Node 测试运行器；测试通过读取小程序源码和导入无平台依赖的纯函数完成契约验证。

### Task 1: 移除 WebView 壳并建立原生页面骨架

**Files:**
- Create: `SD/nativeMiniProgramContract.test.ts`
- Create: `xiaochengxu/miniprogram/pages/home/index.json`
- Create: `xiaochengxu/miniprogram/pages/home/index.ts`
- Create: `xiaochengxu/miniprogram/pages/home/index.wxml`
- Create: `xiaochengxu/miniprogram/pages/home/index.wxss`
- Create: `xiaochengxu/miniprogram/pages/category/index.json`
- Create: `xiaochengxu/miniprogram/pages/category/index.ts`
- Create: `xiaochengxu/miniprogram/pages/category/index.wxml`
- Create: `xiaochengxu/miniprogram/pages/category/index.wxss`
- Create: `xiaochengxu/miniprogram/pages/tool/index.json`
- Create: `xiaochengxu/miniprogram/pages/tool/index.ts`
- Create: `xiaochengxu/miniprogram/pages/tool/index.wxml`
- Create: `xiaochengxu/miniprogram/pages/tool/index.wxss`
- Modify: `xiaochengxu/miniprogram/app.json`
- Modify: `xiaochengxu/miniprogram/app.wxss`
- Modify: `xiaochengxu/miniprogram/app.ts`
- Delete: `xiaochengxu/miniprogram/config.ts`
- Delete: `xiaochengxu/miniprogram/pages/index/index.json`
- Delete: `xiaochengxu/miniprogram/pages/index/index.ts`
- Delete: `xiaochengxu/miniprogram/pages/index/index.wxml`
- Delete: `xiaochengxu/miniprogram/pages/index/index.wxss`

- [ ] **Step 1: Write the failing contract test**

  Add assertions that `app.json` declares `pages/home/index`, `pages/category/index`, and `pages/tool/index`, and that no file under `xiaochengxu/miniprogram` contains `<web-view`, `WEB_ENTRY_URL`, or `?mini=1`.

- [ ] **Step 2: Run the contract test and verify RED**

  Run from `E:\AI\gp\SD`:

  ```powershell
  npm test -- nativeMiniProgramContract.test.ts
  ```

  Expected: FAIL because the existing `pages/index` WebView shell and `config.ts` are still present.

- [ ] **Step 3: Implement the minimal native shell**

  Use a three-page `app.json` with `pages/home/index` as the launch page. Replace the old page with native WXML migration screens that render a title, a category entry area, and a tool-list area. `pages/tool/index` initially renders the selected tool title and a “工具正在迁移” state; it must not reference WebView.

- [ ] **Step 4: Run the contract and TypeScript checks**

  ```powershell
  npm test -- nativeMiniProgramContract.test.ts
  & 'E:\AI\gp\SD\node_modules\.bin\tsc.cmd' --noEmit -p ..\xiaochengxu\tsconfig.json
  ```

  Expected: contract tests pass and the WeChat TypeScript compiler exits with code 0.

- [ ] **Step 5: Commit**

  ```powershell
  git add SD/nativeMiniProgramContract.test.ts xiaochengxu/miniprogram
  git commit -m "feat: replace mini program webview shell with native pages"
  ```

  Do not stage `xiaochengxu/project.config.json` or `xiaochengxu/project.private.config.json`; both contain user-specific AppID/developer settings.

### Task 2: 建立原生注册表、公共组件和首页搜索

**Files:**
- Create: `SD/nativeToolRegistry.test.ts`
- Create: `xiaochengxu/miniprogram/types/tool.ts`
- Create: `xiaochengxu/miniprogram/data/toolRegistry.ts`
- Create: `xiaochengxu/miniprogram/data/categories.ts`
- Create: `xiaochengxu/miniprogram/components/common/tool-card/tool-card.json`
- Create: `xiaochengxu/miniprogram/components/common/tool-card/tool-card.ts`
- Create: `xiaochengxu/miniprogram/components/common/tool-card/tool-card.wxml`
- Create: `xiaochengxu/miniprogram/components/common/tool-card/tool-card.wxss`
- Create: `xiaochengxu/miniprogram/components/common/search-bar/search-bar.json`
- Create: `xiaochengxu/miniprogram/components/common/search-bar/search-bar.ts`
- Create: `xiaochengxu/miniprogram/components/common/search-bar/search-bar.wxml`
- Create: `xiaochengxu/miniprogram/components/common/search-bar/search-bar.wxss`
- Modify: `xiaochengxu/miniprogram/pages/home/*`
- Modify: `xiaochengxu/miniprogram/pages/category/*`

- [ ] **Step 1: Write failing registry tests**

  Test that every ready tool has a unique ID, non-empty name/category/route, that categories referenced by tools exist, that `stock` is absent, and that desktop-only mouse tools are not marked ready. Test the initial core entries `json-format`, `json-minify`, `bmi`, `percentage`, `random-number`, `password-gen`, and `word-count`.

- [ ] **Step 2: Run registry tests and verify RED**

  ```powershell
  npm test -- nativeToolRegistry.test.ts
  ```

  Expected: FAIL because the native registry does not exist.

- [ ] **Step 3: Add typed metadata and public components**

  Define `NativeToolCapability` as `local | request | file | camera | audio | unsupported` and `NativeToolStatus` as `ready | adapting | desktop-only`. Add category metadata and an initial registry that is data-only and free of React imports. Tool cards emit `tap` with the tool ID; search emits `input` with normalized text.

- [ ] **Step 4: Wire home/category filtering**

  `pages/home` loads category and ready-tool data, filters name/description/tags, and uses `wx.navigateTo` with an encoded `id`. `pages/category` reads `category` from query, filters the same registry, and handles an empty state. Use only WXML bindings and `setData`; no DOM APIs.

- [ ] **Step 5: Verify and commit**

  ```powershell
  npm test -- nativeToolRegistry.test.ts
  npm test -- nativeMiniProgramContract.test.ts nativeToolRegistry.test.ts
  & 'E:\AI\gp\SD\node_modules\.bin\tsc.cmd' --noEmit -p ..\xiaochengxu\tsconfig.json
  git add SD/nativeToolRegistry.test.ts xiaochengxu/miniprogram
  git commit -m "feat: add native tool registry and mini program home"
  ```

### Task 3: 工具容器、缓存和通用反馈

**Files:**
- Create: `xiaochengxu/miniprogram/services/storage.ts`
- Create: `xiaochengxu/miniprogram/services/http.ts`
- Create: `xiaochengxu/miniprogram/components/common/tool-header/*`
- Create: `xiaochengxu/miniprogram/components/common/result-panel/*`
- Create: `xiaochengxu/miniprogram/components/common/empty-state/*`
- Modify: `xiaochengxu/miniprogram/pages/tool/*`
- Create: `SD/nativeToolPageContract.test.ts`

- [ ] **Step 1: Write failing page contract tests**

  Assert that the tool page reads an `id` query, renders a title from the registry, has a back action, and displays a consistent unsupported/error state. Assert that `http.ts` uses a single HTTPS base URL and rejects URLs containing localhost, loopback addresses, or internal ports.

- [ ] **Step 2: Run tests and verify RED**

  ```powershell
  npm test -- nativeToolPageContract.test.ts
  ```

- [ ] **Step 3: Implement service and shell components**

  `storage.ts` wraps `wx.getStorageSync`, `wx.setStorageSync`, and `wx.removeStorageSync` with a namespaced key. `http.ts` wraps `wx.request`, sets a 15-second timeout, normalizes status errors, and exposes `requestJson<T>(path, options)`. The tool page resolves the registry item and exposes `onBack`, `onCopy`, and `onClear` events through common components.

- [ ] **Step 4: Verify and commit**

  ```powershell
  npm test -- nativeToolPageContract.test.ts
  & 'E:\AI\gp\SD\node_modules\.bin\tsc.cmd' --noEmit -p ..\xiaochengxu\tsconfig.json
  git add SD/nativeToolPageContract.test.ts xiaochengxu/miniprogram
  git commit -m "feat: add native tool page shell and services"
  ```

### Task 4: 迁移纯文本、开发者和计算器工具

**Files:**
- Create: `xiaochengxu/miniprogram/utils/json.ts`
- Create: `xiaochengxu/miniprogram/utils/encoding.ts`
- Create: `xiaochengxu/miniprogram/utils/calculator.ts`
- Create: `xiaochengxu/miniprogram/utils/text.ts`
- Create: `xiaochengxu/miniprogram/components/tools/text-workbench/*`
- Create: `xiaochengxu/miniprogram/components/tools/dev-workbench/*`
- Create: `xiaochengxu/miniprogram/components/tools/calculator-workbench/*`
- Create: `SD/nativeCoreTools.test.ts`
- Modify: `xiaochengxu/miniprogram/data/toolRegistry.ts`
- Modify: `xiaochengxu/miniprogram/pages/tool/*`

- [ ] **Step 1: Write failing pure-logic tests**

  Cover JSON format/minify/validation, URL encode/decode, Base64 text conversion, word count, case conversion, percentage calculation, discount calculation, BMI classification, age/date difference, and unit conversion. Include empty input and invalid numeric input.

- [ ] **Step 2: Run tests and verify RED**

  ```powershell
  npm test -- nativeCoreTools.test.ts
  ```

- [ ] **Step 3: Implement pure functions**

  Implement deterministic functions with explicit result/error return values. Do not use `window`, `document`, browser `btoa/atob`, or `Intl` features unavailable in the configured mini program runtime; use UTF-8-safe helpers and the existing TypeScript target.

- [ ] **Step 4: Implement native workbench components**

  Text and developer workbenches use `<textarea>`, `bindinput`, and action buttons. Calculator workbench uses numeric inputs and a result card. `pages/tool` selects the workbench by tool ID and passes the initial values from page state.

- [ ] **Step 5: Verify and commit**

  ```powershell
  npm test -- nativeCoreTools.test.ts
  npm test -- nativeMiniProgramContract.test.ts nativeToolRegistry.test.ts nativeToolPageContract.test.ts nativeCoreTools.test.ts
  & 'E:\AI\gp\SD\node_modules\.bin\tsc.cmd' --noEmit -p ..\xiaochengxu\tsconfig.json
  git add SD/nativeCoreTools.test.ts xiaochengxu/miniprogram
  git commit -m "feat: migrate native text developer and calculator tools"
  ```

### Task 5: 迁移趣味、测评、塔罗和星座工具

**Files:**
- Create: `xiaochengxu/miniprogram/utils/random.ts`
- Create: `xiaochengxu/miniprogram/data/assessmentData.ts`
- Create: `xiaochengxu/miniprogram/data/tarotData.ts`
- Create: `xiaochengxu/miniprogram/components/tools/fun-workbench/*`
- Create: `xiaochengxu/miniprogram/components/tools/assessment-workbench/*`
- Create: `xiaochengxu/miniprogram/components/tools/tarot-workbench/*`
- Create: `SD/nativeFunTools.test.ts`
- Create: `SD/nativeAssessmentTools.test.ts`
- Modify: `xiaochengxu/miniprogram/data/toolRegistry.ts`
- Modify: `xiaochengxu/miniprogram/pages/tool/*`

- [ ] **Step 1: Write failing tests**

  Test seeded/random number bounds, password requirements, lottery selection without duplicate winners, dice results, assessment scoring, unanswered-question handling, tarot draw uniqueness, and deterministic zodiac/name helper behavior where the website already defines it.

- [ ] **Step 2: Run RED, then port data and pure logic**

  ```powershell
  npm test -- nativeFunTools.test.ts nativeAssessmentTools.test.ts
  ```

  Move only data and pure scoring/draw functions from the website; do not copy React components or browser-only charting.

- [ ] **Step 3: Implement native interaction**

  Use `radio`, `checkbox`, `picker`, and `button` controls. Preserve progress, previous/next navigation, restart, and result copy. Store only an in-progress local draft when needed; do not add account history.

- [ ] **Step 4: Verify and commit**

  ```powershell
  npm test -- nativeFunTools.test.ts nativeAssessmentTools.test.ts
  & 'E:\AI\gp\SD\node_modules\.bin\tsc.cmd' --noEmit -p ..\xiaochengxu\tsconfig.json
  git add SD/nativeFunTools.test.ts SD/nativeAssessmentTools.test.ts xiaochengxu/miniprogram
  git commit -m "feat: migrate native fun assessment and tarot tools"
  ```

### Task 6: 文件、图片和格式转换基础能力

**Files:**
- Create: `xiaochengxu/miniprogram/services/file.ts`
- Create: `xiaochengxu/miniprogram/services/canvas.ts`
- Create: `xiaochengxu/miniprogram/components/tools/file-picker/*`
- Create: `xiaochengxu/miniprogram/components/tools/image-workbench/*`
- Create: `xiaochengxu/miniprogram/components/tools/converter-workbench/*`
- Create: `SD/nativeFileTools.test.ts`
- Modify: `xiaochengxu/miniprogram/app.json`
- Modify: `xiaochengxu/miniprogram/data/toolRegistry.ts`

- [ ] **Step 1: Write failing adapter and logic tests**

  Test extension/type validation, file-size rejection, image dimension calculations, aspect-ratio crop math, color conversion, and supported image conversion mappings without invoking `wx` in unit tests.

- [ ] **Step 2: Implement file and Canvas adapters**

  `file.ts` exposes `chooseFile`, `readText`, `readBinary`, `saveTempFile`, and `openDocument` with typed errors. `canvas.ts` isolates `wx.createOffscreenCanvas`/canvas context calls behind operations that can be mocked by contract tests.

- [ ] **Step 3: Implement image and converter workbenches**

  Migrate image resize/crop/base64/color/merge/split and JPG/PNG/WebP/SVG/ICO conversion where supported by the native Canvas/runtime. Each unsupported format returns a visible “当前微信版本不支持” message rather than silently producing a bad file.

- [ ] **Step 4: Put heavy components in a media subpackage**

  Register a `packages/media` subpackage and route image/file tools there. Keep only shared metadata in the main package.

- [ ] **Step 5: Verify and commit**

  ```powershell
  npm test -- nativeFileTools.test.ts
  & 'E:\AI\gp\SD\node_modules\.bin\tsc.cmd' --noEmit -p ..\xiaochengxu\tsconfig.json
  git add SD/nativeFileTools.test.ts xiaochengxu/miniprogram
  git commit -m "feat: add native file image and converter tools"
  ```

### Task 7: PDF、文档、数据、办公和学术分包

**Files:**
- Create: `xiaochengxu/miniprogram/packages/pdf/*`
- Create: `xiaochengxu/miniprogram/packages/document/*`
- Create: `xiaochengxu/miniprogram/packages/office/*`
- Create: `xiaochengxu/miniprogram/packages/academic/*`
- Create: `SD/nativeDocumentTools.test.ts`
- Modify: `xiaochengxu/miniprogram/app.json`
- Modify: `xiaochengxu/miniprogram/data/toolRegistry.ts`

- [ ] **Step 1: Write failing pure-logic tests**

  Cover PDF page selection/range parsing, metadata validation, CSV delimiter detection, table diff keys, reference formatting, Markdown/HTML conversion, Word/Excel type validation, and privacy-cleaning field selection.

- [ ] **Step 2: Implement the smallest local paths first**

  Port operations that can run on local bytes. Use `file.ts` for input and `openDocument`/temporary file handling for output. Do not assume the browser `File` API exists.

- [ ] **Step 3: Adapt or replace heavy libraries**

  Each library must be compatible with the mini program bundler and the package size budget. If a library needs DOM/canvas APIs unavailable in the target runtime, move that operation to a backend endpoint and mark the tool as `request`; do not ship a broken import in the main package.

- [ ] **Step 4: Add subpackage routes and user-facing limitations**

  PDF/office/OCR tools show file type, size and page limits before processing. A failed conversion preserves the selected file metadata and offers retry.

- [ ] **Step 5: Verify and commit**

  ```powershell
  npm test -- nativeDocumentTools.test.ts
  & 'E:\AI\gp\SD\node_modules\.bin\tsc.cmd' --noEmit -p ..\xiaochengxu\tsconfig.json
  git add SD/nativeDocumentTools.test.ts xiaochengxu/miniprogram
  git commit -m "feat: add native document office academic and pdf packages"
  ```

### Task 8: 音频、视频、站长和其他后端工具

**Files:**
- Create: `xiaochengxu/miniprogram/components/tools/request-workbench/*`
- Create: `xiaochengxu/miniprogram/components/tools/audio-workbench/*`
- Create: `xiaochengxu/miniprogram/components/tools/video-workbench/*`
- Create: `xiaochengxu/miniprogram/components/tools/webmaster-workbench/*`
- Create: `SD/nativeRequestTools.test.ts`
- Modify: `xiaochengxu/miniprogram/services/http.ts`
- Modify: `xiaochengxu/miniprogram/data/toolRegistry.ts`

- [ ] **Step 1: Write failing request contract tests**

  Assert endpoint paths are relative to `https://zhumenggy.top`, that user-provided URLs are validated before sending, that non-2xx responses become typed errors, and that request tools never embed a secret.

- [ ] **Step 2: Implement request workbench**

  Add loading, timeout, retry, server-error and empty-result states. Keep user input after failure. Only use APIs already exposed through the website’s public reverse proxy; do not expose 8000/8012/etc. to the client.

- [ ] **Step 3: Implement audio/video capability checks**

  Use only supported `wx.chooseMedia`, file and audio APIs. Tools requiring a remote parser or download service call the backend; tools requiring desktop browser download behavior are marked desktop-only.

- [ ] **Step 4: Verify and commit**

  ```powershell
  npm test -- nativeRequestTools.test.ts
  & 'E:\AI\gp\SD\node_modules\.bin\tsc.cmd' --noEmit -p ..\xiaochengxu\tsconfig.json
  git add SD/nativeRequestTools.test.ts xiaochengxu/miniprogram
  git commit -m "feat: add native request media and webmaster tools"
  ```

### Task 9: 完成全量注册表、桌面端标记和兼容性提示

**Files:**
- Modify: `xiaochengxu/miniprogram/data/toolRegistry.ts`
- Create: `xiaochengxu/miniprogram/components/common/compatibility-notice/*`
- Create: `SD/nativeRegistryCompleteness.test.ts`
- Modify: `xiaochengxu/README.md`

- [ ] **Step 1: Write failing completeness tests**

  Compare the native metadata IDs with the 233 tool IDs in `SD/tools/registry.tsx`, allowing only the explicit stock/personal-project exclusions and desktop-only mouse entries. Require every remaining ID to be `ready`, `adapting` with a visible limitation, or `desktop-only` with a reason.

- [ ] **Step 2: Complete registry and limitations**

  Add every migrated tool’s native route and capability. Add a compatibility notice component that names the limitation and tells tools that only run on desktop to use the website电脑版.

- [ ] **Step 3: Update README**

  Document native mode, personal主体限制、request合法域名、分包、测试命令和当前明确不支持的桌面能力。删除旧的 WebView 发布说明，避免后续再次按业务域名配置。

- [ ] **Step 4: Verify and commit**

  ```powershell
  npm test -- nativeRegistryCompleteness.test.ts
  & 'E:\AI\gp\SD\node_modules\.bin\tsc.cmd' --noEmit -p ..\xiaochengxu\tsconfig.json
  git add SD/nativeRegistryCompleteness.test.ts xiaochengxu/README.md xiaochengxu/miniprogram/data xiaochengxu/miniprogram/components
  git commit -m "feat: complete native tool registry and compatibility states"
  ```

### Task 10: 全量验证和发布检查

**Files:**
- Modify: `SD/miniprogramContract.test.ts`
- Modify: `xiaochengxu/README.md`
- Test only: all files changed in Tasks 1–9

- [ ] **Step 1: Add final no-WebView and package contract assertions**

  Assert no native source contains `<web-view` or `WEB_ENTRY_URL`, app routes contain home/category/tool, every ready route resolves, and all request base URLs are HTTPS public URLs.

- [ ] **Step 2: Run focused native tests**

  ```powershell
  npm test -- nativeMiniProgramContract.test.ts nativeToolRegistry.test.ts nativeToolPageContract.test.ts nativeCoreTools.test.ts nativeFunTools.test.ts nativeAssessmentTools.test.ts nativeFileTools.test.ts nativeDocumentTools.test.ts nativeRequestTools.test.ts nativeRegistryCompleteness.test.ts miniprogramContract.test.ts
  ```

  Expected: all native contract and pure-logic tests pass.

- [ ] **Step 3: Run website regression checks**

  ```powershell
  npm test
  npm run lint
  npm run build
  git diff --check
  ```

  Expected: the existing website test suite, TypeScript build, static generation and native TypeScript compilation remain green.

- [ ] **Step 4: Run the WeChat compiler check**

  ```powershell
  & 'E:\AI\gp\SD\node_modules\.bin\tsc.cmd' --noEmit -p ..\xiaochengxu\tsconfig.json
  ```

- [ ] **Step 5: Manual acceptance in WeChat Developer Tools**

  Open `E:\AI\gp\xiaochengxu`, compile with the user’s existing AppID, verify home/category/search/tool navigation, then test representative local, file, permission and request tools. The existing user-specific AppID/private config stays uncommitted.

- [ ] **Step 6: Commit release documentation only after all checks pass**

  ```powershell
  git status --short --untracked-files=all
  git log -1 --oneline
  ```

  Confirm that only the intentionally untracked user config remains and that no AppID change has been staged by the migration.
