**【1 题面要点】**
- 目标：非导出的 `GET /api/eval/:id/table` 要给 `limit` 加上限。目前它接受任意正整数。
- 导出请求（`format=csv|json`）保持不变，仍使用 `Number.MAX_SAFE_INTEGER`。
- 超限时返回校验错误，风格要和邻近的 API schema 校验一致，也就是 400。
- 题面没有给复现命令，也没有给期望输出的原文。关键句是 "A cap of `500` or `1000` would likely cover normal UI usage"。
- 接口部分给出了硬性约定：`src/types/api/eval.ts` 里导出 `EVAL_TABLE_MAX_PAGE_SIZE = 1000`。它的描述是 "UI pagination controls derive their available page-size options from this value"。
- 建议的测试有三条：
  - `EvalSchemas.Table.Query.safeParse({ limit: '<cap+1>' })` 失败。
  - 路由对超限的非导出请求返回 400。
  - 导出路由测试继续断言 `MAX_SAFE_INTEGER`。

**【2 相关代码】**
- `src/types/api/eval.ts:86-100`：`EvalTableQuerySchema`。
  - `limit: z.coerce.number().int().positive().prefault(50)`（第 88 行）。这里要加上限，并导出常量。
  - `format` 是可选的 enum（第 87 行）。
  - 第 360-364 行把它挂到 `EvalSchemas.Table.Query`。
- `src/server/routes/eval.ts:309-338`：路由 `/:id/table`。
  - 第 318 行 `safeParse(req.query)` 失败时返回 400，内容是 `z.prettifyError`。
  - 第 337 行 `const limit = format ? UNLIMITED_RESULTS : baseLimit`。
- `src/app/src/pages/eval/components/ResultsTable.tsx:2473-2485`：页大小下拉框，硬编码 10/50/100/500/1000。第 1616-1632 行是分页初始状态。
- `src/app/src/pages/eval/components/store.ts:642-683`：拼 `limit=pageSize` 请求 `/eval/${id}/table`。
- `src/openapi/server.ts:515`：用 `query('EvalTableQuery', EvalSchemas.Table.Query)` 生成 OpenAPI。

**【3 并列与牵连】**
- 并列实现：`src/server/utils/evalTableUtils.ts:375` 有另一个 `UNLIMITED_RESULTS`。它属于 CSV 导出路径，不走 `limit` 校验，应该不用改。
- 第 381 行起的对比 eval 分支也调用 `getTablePage`（`routes/eval.ts:389` 附近）。它很可能复用同一个 `limit`，所以上限自然覆盖它。
- 前端下拉框是硬编码的。题面说选项应从该常量派生，所以 `ResultsTable.tsx` 可能要导入常量。这个文件在前端包里，要确认前端能否导入 `src/types/api/eval`。
- `downloads.ts:12` 请求 `?format=`，不带 limit，属于导出，不受影响。
- 改 schema 会改变 OpenAPI 输出（`maximum`）。需要看是否有生成的 spec 或快照文件要同步。

**【4 现有测试与约定】**
- `test/types/apiSchemas.redteam.test.ts:570-587`：
  - 第 570-584 行用 `format:'json', limit:'10'` 做 parse。
  - 第 585 行断言 `safeParse({limit:'1.5'}).success` 为 false。
  - 第 586-587 行对 offset 和 format 做同样的负向断言。
  - 隐藏测试大概率加在这里：`limit: String(MAX+1)` 应失败。
- `test/server/routes/eval.validation.test.ts:151-163`：`it.each` 校验 400。断言有 `response.body.error` 已定义、`toContain(field)`，以及 `mockFindById` 未被调用。新增 limit 超限用例很可能放在这个表里，所以错误信息里必须包含 "limit"。`z.prettifyError` 会带上路径，应该满足。
- `test/server/routes/eval.export.test.ts`：多处断言 `limit: Number.MAX_SAFE_INTEGER`（第 136、161、363 行等），都带 format。
- 邻近的上限先例：
  - `blobs.ts:23`：`.min(1).max(100)`。
  - `modelAudit.ts:140`：`.max(100)`。
  - `blobs.ts:79`：`.max(501)`。
  - 测试风格是 `safeParse({limit:'999'}).success` 为 false（`apiSchemas.redteam.test.ts:491`、`:529`）。
- 与题面期望没有冲突。

**【5 边界与隐含要求】**
- 最关键的一点：导出请求带 `format` 并且 `limit` 很大时，不能被 schema 拒绝。否则会破坏导出。
  - 如果在字段上直接 `.max(1000)`，`format=json&limit=5000` 会被拒绝。
  - 正确做法是在对象层用 `superRefine` 或 `refine`，只在没有 format 时检查。
  - 这个 refine 的 issue path 要指向 `limit`，这样路由测试里 `toContain('limit')` 才能通过。
  - 也要避免 `z.object` 后接 refine 引起类型或 `.shape` 变化。openapi 生成器（`query(...)`）是否支持 effects 类型要核实。
- 刚好等于上限（1000）要通过，1001 要失败。
- 默认值 50 不受影响。
- `limit` 是字符串，经 coerce 后再比较，所以 `'1001'` 也要失败。
- 前端：下拉框的选项最大值要与常量一致。如果常量以后变小，选项也要跟着变。

**【6 改动规模】**
- 必改：
  - `src/types/api/eval.ts`：新增常量，在 schema 上加条件上限。
  - 新增测试，在 schema 测试和 validation 测试各一处。
- 可能要改：
  - `ResultsTable.tsx`：选项从常量派生。
  - OpenAPI 或快照。
- 总共 2-4 个文件，改动是局部的，不需要新增结构，也不贯穿多层。

**【7 难点一句话】**
难点不在加上限本身，而在于"只对非导出请求生效"的校验要写在 schema 层。它要同时满足三点：不误伤 `format` 导出、错误路径指向 `limit`、不破坏 OpenAPI 生成。另外前端是否也要用这个常量，隐藏测试可能会涉及。