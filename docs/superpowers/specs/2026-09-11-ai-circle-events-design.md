# AI 圈大事接入设计

**日期：** 2026-09-11

**状态：** 已获用户确认，等待实施计划

## 目标

新增一个独立的 Cloudflare Workers 项目，运行在能够访问 X 和 Gemini 的网络环境中，完成：

```text
固定 AI 账号动态 → FxTwitter → 过滤/去重 → Gemini 2.5 Flash → 国内研报 HTTPS API
```

国内网站只负责安全接收、持久化和展示，不调用 FxTwitter，不调用 Gemini，也不保存 Gemini API Key。

## 当前项目背景

仓库已有独立的 `research-reports` FastAPI 服务和 `/reports` 前端页面。现有代码已经支持 RSS 新闻、`x_indexed` 社交新闻筛选和旧版 AI 早报，但没有外部 X 推送接口，也没有 X 专属动态/摘要存储模型。

本次改造在仓库顶层新建 `ai-circle-events/`，同时扩展现有 `research-reports` 和 SD 前端。已有 RSS、GitHub 榜单和旧版 AI 早报接口继续兼容。

## 范围与非目标

### 本次范围

- Cloudflare Worker 使用 TypeScript。
- 固定监控 `OpenAI`、`AnthropicAI`、`GoogleDeepMind`、`sama`、`demishassabis`、`huggingface`、`MistralAI`、`perplexity_ai`、`claudeai`。
- 使用 FxTwitter v2 profile statuses 接口获取公开动态。
- 使用 Cloudflare Cron Trigger 每 15 分钟执行一次。
- 提供受保护的手动 HTTP 触发接口。
- 使用 KV 保存每个账号最后成功处理的动态 ID。
- 每轮收集全部新动态，过滤后只调用一次 Gemini 2.5 Flash。
- Worker 内校验 Gemini 结构化 JSON，成功后推送到国内网站。
- 网站新增 Bearer Token 接收接口、X 动态与摘要存储和前端展示。
- 对数据源失败、超时、限流、模型失败和网站失败提供有限重试与日志。

### 非目标

- 不使用 X 官方付费 API。
- 不在国内服务器请求 X 或 Gemini。
- 不在第一版实现账号管理后台、登录 X、浏览器自动化或付费数据源。
- 不在本次改造中替换现有 RSS 新闻与 GitHub 榜单逻辑。
- 不自动部署到用户的 Cloudflare 账号；代码和部署说明先落库。

## 架构

### Cloudflare Worker

`ai-circle-events/` 是独立项目，包含以下边界清晰的模块：

- `providers/types.ts`：数据源 Provider 接口和标准化动态类型。
- `providers/fxtwitter.ts`：FxTwitter v2 实现。
- `filter.ts`：回复、广告和低价值内容过滤。
- `dedup.ts`：动态 ID、标准化正文和批次去重。
- `gemini.ts`：Gemini 2.5 Flash REST 客户端和结构化输出校验。
- `site-client.ts`：向国内研报服务推送的客户端。
- `pipeline.ts`：单轮抓取、合并、摘要、推送和游标提交。
- `index.ts`：`fetch`、`scheduled` 和手动触发路由。

### 国内研报服务

在 `research-reports/research_reports/` 增加 X 专属模型、迁移、接收路由、公开读取路由和配置项。Nginx 已有 `/reports-api/` 反向代理，因此 Worker 使用公开 HTTPS 地址访问新接口时不需要新增端口。

### 前端

复用现有 `/reports/news` 页面，把“社交大事”页签改为读取 X 专属最新摘要和动态；“AI 新闻”页签保持原行为。

## Worker 处理流程

1. Cron 或经过鉴权的 `POST /trigger` 创建一轮任务。
2. 对固定账号调用 Provider；每个账号独立设置超时并收集成功或失败结果。
3. 读取 `cursor:{handle}`，通过 Provider 分页读取到最后成功处理的 ID；只保留更新的动态，首次运行只取 Provider 返回的最新一页。
4. 将 FxTwitter 动态标准化为统一字段。
5. 过滤无意义回复、明显广告和无实质内容；按动态 ID、标准化正文和 URL 去重。
6. 没有任何新动态时直接结束，不调用 Gemini，不调用网站接口，也不改变无关账号游标。
7. 将本轮全部新动态合并成一次 Gemini 输入。
8. 调用 `gemini-2.5-flash`，要求中文总结并按 JSON Schema 返回动态重要度、摘要、事件和风险。
9. 在 Worker 内解析 JSON，并校验字段、动态 ID 集合、原文一致性、重要度范围和事件引用。
10. 使用由本轮动态 ID 排序后计算出的幂等键向网站推送。
11. 网站返回成功后，按账号分别写入本轮完整扫描到的最新 ID；请求失败或分页未完成的账号不推进游标。

KV 游标只代表“已经成功送达网站”的边界。Gemini 或网站失败时保留游标，下一轮可以安全重试；网站已成功但 KV 写入失败时，网站端幂等键保证重复推送不会重复入库。为避免手动触发和 Cron 的常见重叠，Worker 使用带 TTL 的 KV 运行租约；租约不是强一致分布式锁，最终幂等键仍是重复执行的安全边界。

## Provider 契约

Provider 对外只暴露：

```ts
interface TimelineProvider {
  fetchLatest(handle: string): Promise<NormalizedPost[]>;
}
```

第一版使用：

```text
GET https://api.fxtwitter.com/2/profile/{handle}/statuses
```

FxTwitter 返回的动态至少需要映射 `id`、`url`、`text`、`created_at` 和作者信息；互动数据只作为可选字段，不进入第一版网站契约。Provider 支持响应中的 `cursor` 分页：已有游标时持续读取，直到遇到 `last_post_id`、没有下一页或达到安全页数上限；达到上限时本账号本轮不推进游标，避免静默丢数据。Provider 失败必须抛出带有账号和错误类型的可记录错误，但不能阻止其他账号继续执行。

## 过滤与去重

### 过滤

- `replying_to` 存在且正文为空、只有表情、只有礼貌性短句或简单附和时丢弃。
- 命中明显广告/推广模式，且没有独立 AI 行业信息时丢弃。
- 正文只有链接、重复标签或无意义模板文本时丢弃。
- 原创动态默认保留。
- 转发只有在正文包含实质判断、产品/模型/研究/行业事件信息时保留。

过滤规则是确定性的，便于测试和调整；Gemini 负责总结和重要度评估，不负责替 Worker 猜测是否已经处理过动态。

### 去重

- 同一账号按 FxTwitter `post_id` 去重。
- 同一轮跨账号按标准化正文去重。
- 同一轮按标准化 URL 去重。
- 网站端按 `provider + external_id` 再做一次幂等保护。

## Gemini 契约

Worker 使用 Gemini `generateContent` REST 接口，模型固定为 `gemini-2.5-flash`。请求只包含本轮过滤后的动态和明确的“只基于输入资料、不得补写事实”的提示词。

期望输出：

```json
{
  "posts": [
    {
      "id": "原始动态 ID",
      "author": "显示名称",
      "username": "账号",
      "text": "原文",
      "url": "原文链接",
      "publishedAt": "ISO 时间",
      "importance": 0
    }
  ],
  "summary": {
    "title": "AI 圈大事",
    "summary": "中文总体摘要",
    "events": [
      {
        "title": "事件标题",
        "summary": "事件说明",
        "importance": 0,
        "postIds": ["对应动态 ID"]
      }
    ],
    "risks": ["需要关注的风险"]
  }
}
```

校验要求：

- 顶层必须包含 `posts` 和 `summary`。
- `posts` 的 ID 集合必须与 Gemini 输入完全一致。
- `author`、`username`、`text`、`url` 和 `publishedAt` 必须与输入原文一致，Worker 不接受模型改写来源字段。
- `importance` 和事件重要度必须是 `0–100` 的整数。
- `events[].postIds` 只能引用本轮输入动态。
- 标题、摘要、事件和风险必须是受长度限制的字符串或对象。
- JSON 解析或校验失败时不推送网站、不推进游标。

Gemini API Key 通过 Cloudflare Secret 的 `x-goog-api-key` 请求头发送，不出现在 URL、响应或日志中。

## 网站接收接口

### 写入接口

```text
POST /reports-api/api/v1/ingest/x
Authorization: Bearer <RESEARCH_REPORTS_X_INGEST_TOKEN>
Content-Type: application/json
X-Idempotency-Key: <本轮动态 ID 哈希>
```

接口行为：

- 缺少或错误 Token 返回 `401`。
- 未配置服务端 Token 返回 `503`，不允许意外开放写入。
- 请求体校验失败返回 `422`。
- `provider + external_id` 或幂等键重复时返回已接收结果，不重复插入。
- 校验通过后，在一个数据库事务内写入动态和本轮摘要。
- 成功返回 `200`，包含本轮接收数、重复数和报告 ID。

### 公开读取接口

```text
GET /reports-api/api/v1/x-events/latest
```

无数据时返回：

```json
{
  "report": null,
  "posts": []
}
```

有数据时返回最新成功报告及其关联动态。报告包含 `title`、`summary`、`events`、`risks`、`modelName` 和 `receivedAt`；动态包含账号、正文、链接、发布时间和重要度。

## 国内数据库模型

新增 `XPost`：

- `id`
- `provider`
- `external_id`
- `author`
- `username`
- `text`
- `canonical_url`
- `published_at`
- `importance`
- `received_at`
- `created_at`
- 唯一约束：`provider + external_id`

新增 `XEventReport`：

- `id`
- `idempotency_key`
- `status`
- `model_provider`
- `model_name`
- `title`
- `summary_markdown`
- `events_json`
- `risks_json`
- `post_ids_json`
- `received_at`
- 唯一约束：`idempotency_key`

`post_ids_json` 保存本轮动态的 `provider + external_id` 引用，而不是数据库内部 UUID，便于 Worker 输出的事件引用与网站查询保持一致。

数据库迁移新增版本，保证已有 `reports.db` 可重复执行迁移；旧表和旧接口不删除。

## 前端行为

`NewsEventsPage` 的“社交大事”页签调用 `/x-events/latest`：

- 顶部显示“AI 圈大事”和最近一次接收时间。
- 显示 Gemini 中文总体摘要。
- 显示关键事件及其重要度。
- 显示风险提示。
- 显示每条 X 动态的作者、账号、时间、重要度、正文和原文链接。
- 没有数据时显示等待首次推送的空状态。
- AI 新闻页签和现有 RSS 采集按钮保持兼容。

前端不接触 `RESEARCH_REPORTS_X_INGEST_TOKEN`、`SITE_PUSH_TOKEN` 或 `GEMINI_API_KEY`。

## 错误处理与安全

- FxTwitter、Gemini 和网站请求均使用 AbortController 超时。
- 网络错误、`408`、`429` 和 `5xx` 采用有限次数指数退避；`4xx` 参数错误不盲目重试。
- 账号抓取使用 `Promise.allSettled`，单账号失败不会中断整轮。
- Worker 手动触发接口使用 `MANUAL_TRIGGER_TOKEN`；健康检查只返回运行状态和版本，不返回密钥配置值。
- Worker 日志只记录 `runId`、Provider、账号、数量、状态和错误类型。
- 网站 Bearer Token 使用常量时间比较，不记录请求头。
- 写入接口使用请求体大小和字段长度限制，拒绝非 HTTPS 原文链接。
- 接收事务只在动态和摘要同时校验通过后提交，避免出现没有摘要的半批次数据。

## 配置与部署

### Cloudflare Worker

`wrangler.jsonc` 配置：

- Worker 名称为 `ai-circle-events`。
- `main` 指向 `src/index.ts`。
- `triggers.crons` 为 `["*/15 * * * *"]`。
- 绑定一个 KV namespace，binding 名称为 `AI_EVENTS_KV`。

Cloudflare KV namespace ID 在用户创建命名空间后写入 Wrangler 配置；不写入密钥，也不写入业务源码。

Secrets：

```text
GEMINI_API_KEY
SITE_PUSH_TOKEN
MANUAL_TRIGGER_TOKEN
```

Variables：

```text
SITE_API_URL
GEMINI_MODEL=gemini-2.5-flash
FXTWITTER_BASE_URL=https://api.fxtwitter.com
```

### 国内服务

新增环境变量：

```text
RESEARCH_REPORTS_X_INGEST_TOKEN
```

真实 Token 只写入服务器的 `.env.local` 或生产环境 Secret，不提交到 Git。现有 `/reports-api/` Nginx 代理继续转发新路由。

## 测试与验收

Worker 使用 Vitest 测试：

- FxTwitter 响应标准化。
- 游标判断和首次运行行为。
- 回复、广告、重复正文和重要转发过滤。
- 单个账号失败时其他账号继续。
- 无新动态时不调用 Gemini 和网站。
- 每轮只调用一次 Gemini。
- Gemini JSON、ID 集合、原文一致性和事件引用校验。
- Gemini/网站失败时不推进游标。
- 网站成功后推送和 KV 更新。
- 手动接口鉴权、超时、重试和健康检查。

国内服务使用 pytest 测试：

- 接收 Token 校验。
- X 动态和报告事务入库。
- 重复动态和重复幂等键。
- 最新报告读取。
- 迁移幂等性。

SD 前端使用 Vitest/Testing Library 测试社交页签的摘要、事件、风险、动态和空状态展示。

验收标准：

1. `npm test`、`npm run typecheck` 和 `npx wrangler deploy --dry-run` 通过。
2. 国内 `research-reports` pytest 全部通过。
3. 本地手动触发能够走通模拟的 `Worker → FxTwitter → Gemini → 网站 API` 链路。
4. 没有新动态时不产生 Gemini 请求。
5. 任意一步失败时不丢失游标边界，重试不会造成网站重复动态。
6. `/reports/news` 的社交大事页签能显示最近一次成功推送。

## 参考资料

- [Cloudflare Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/)
- [Cloudflare KV bindings](https://developers.cloudflare.com/kv/concepts/kv-bindings/)
- [FxTwitter v2 OpenAPI](https://github.com/FxEmbed/FxEmbed/blob/main/docs/specs/fxtwitter-openapi.json)
- [Gemini 2.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash)
- [Gemini Generate Content API](https://ai.google.dev/api/generate-content)
