【档案】

**1 题面要点**
- 要求的行为：Cursor CLI 跑完任务后，会话应进入 idle/completed，loading 指示停止。
- 题面没有给复现命令或期望输出，也没有给修法建议。"Evaluation contract"给了具体规格：
  - 当带合成标题的 agent 上报非 working 状态时，要把终端标题与该 agent 的合成标题 profile 对齐。
  - Cursor `done`：把 spinner/working 标题、裸 `Cursor Agent`、过期的 permission 标题，替换为 `Cursor ready`。
  - Cursor `waiting` 或 `blocked`：用 `Cursor - action required`。
  - 描述性的已完成标题（不属于 working 或 permission）要保留。没有合成 profile 的 agent 不改写。
  - "Apply this resolver before storing agent-status snapshot titles."
- 接口：`src/renderer/src/lib/agent-status-terminal-title.ts` 里的 `resolveAgentStatusTerminalTitle(payload: Pick<ParsedAgentStatusPayload,'agentType'|'state'>, currentTitle: string|undefined): string|undefined`。"The IPC status integration must call this resolver before storing the title."

**2 相关代码**
- `src/main/index.ts:772-798`：`SYNTHETIC_TITLE_PROFILES`（cursor、opencode、droid、hermes），每项含 workingLabel、permissionLabel、idleLabel。它是 main 里的私有常量，renderer 目前取不到。
- `src/main/index.ts:1018-1061`：`driveSyntheticTitleFromHook`。working 时发 spinner 帧；其他状态先停 spinner，再向 pty 注入 OSC 标题，`done` 用 idleLabel，`blocked/waiting` 用 permissionLabel 加 BEL。它依赖 `getPtyIdForPaneKey`，pane 映射丢失就直接 return。
- `src/main/index.ts:609-631`：hook 回调先发 `agentStatus:set` IPC，再调 `driveSyntheticTitleFromHook`。
- `src/renderer/src/hooks/useIpcEvents.ts:2186-2310`（`applyAgentStatus`）：
  - 第 2206 行从 `resolvePaneKey(store, data.paneKey)`（2555 行）取出 `title`，第 2294 行把这个 `title` 传给 `store.setAgentStatus`。
  - 这个 `title` 是 renderer 当前持有的旧标题（可能是 spinner 或 `Cursor Agent`），整套修复大概率在这里接入。
- `src/renderer/src/store/slices/agent-status.ts:203-291`：`setAgentStatus(paneKey, payload, terminalTitle, timing)`。第 221 行 `effectiveTitle = terminalTitle ?? existing?.terminalTitle`，所以传 undefined 会沿用旧标题。
- `src/shared/agent-detection.ts:422-`：`detectAgentStatusFromTitle`。裸 `Cursor Agent` 返回 null；braille spinner 返回 working；"action required" 返回 permission；"ready" 返回 idle。
- `src/renderer/src/lib/agent-status.ts`：`detectAgentStatusFromTitle(tab.title) === 'working'`（96、287 行）用标题判断活动。旧的 spinner 标题留在存储里，UI 就一直显示加载。

**3 并列与牵连**
- 另有 4 个 `setAgentStatus` 调用点：`pty-connection.ts:768/792/833/1154`、`launch-agent-background-session.ts:193/219`、`launch-agent-in-new-tab.ts:55`、`automation-session-observer.ts:27`。题面只点名 IPC 路径，其余传 undefined 或自己的 title。
- 快照 replay 也走 `applyAgentStatus`（`options.replay`），所以 resolver 放在这里即可覆盖快照标题。
- 需要判断"哪些 agent 有合成 profile"。profile 表在 main，resolver 在 renderer，大概率要把 profile 抽到 `src/shared`，main 和 renderer 共用。如果在 renderer 里复制一份，main 与 renderer 会有两份真相。
- opencode、droid、hermes 也在同一张表里，resolver 对它们的行为应与 cursor 同构。题面只明确了 Cursor 的标题字符串。
- main 侧每次 `done` 本来就会注入 `Cursor ready`，所以 bug 大概率是竞态或丢失（pane 映射缺失，或 cursor 之后又重发 `Cursor Agent`），而不是注入逻辑没写。

**4 现有测试与约定**
- `src/renderer/src/lib/agent-status.test.ts:183-202` 锁定了分类契约：
  - `detectAgentStatusFromTitle('Cursor Agent')` 为 null（187 行）
  - `'⠋ Cursor Agent'` 为 working（193 行）
  - `'Cursor ready'` 为 idle（197 行）
  - `'Cursor - action required'` 为 permission（201 行）
- Droid 和 Hermes 在 204-216 行有同样的契约。
- `src/main/synthetic-title-spinner.test.ts` 和 `synthetic-title-visibility.test.ts` 覆盖 spinner 与可见性。
- `src/main/runtime/orca-runtime.test.ts:4562` 用到 `Cursor ready`。
- `agent-status.test.ts`（store slice）里没有 `terminalTitle` 断言。
- 隐藏测试大概率是新增的 `agent-status-terminal-title.test.ts`（针对 resolver 的纯函数测试），外加 `useIpcEvents` 或 store 层的集成测试。
- 题面与现有约定不冲突。"描述性已完成标题要保留"需要用 `detectAgentStatusFromTitle` 判断 working/permission，其余保留。

**5 边界与隐含要求**
- `currentTitle` 为 undefined：对 `done` 应返回 `Cursor ready`，还是保持 undefined？题面没说，需要拿捏。
- `payload.agentType` 为 undefined 或不在 profile 表中：原样返回 `currentTitle`。
- `working` 状态：不改写，原样返回。
- 已经是 `Cursor ready` 或描述性标题（例如 "Fix login bug"）：保留。
- 过期 permission 标题（`Cursor - action required`）在 `done` 时要被替换。
- `waiting`/`blocked` 时，即使当前标题是描述性的也要改成 action required。题面这一点写得不够清楚，要看隐藏测试怎么取舍。
- agentType 要用 `resolveHookPayloadAgentType` 解析后的值（第 2267 行），而不是原始 `data.agentType`。
- `done` 之外还有 `idle`/`interrupted` 之类状态吗？需要查 `ParsedAgentStatusPayload` 的 state 枚举。

**6 改动规模**
- 约 3 到 4 个文件：新增 `agent-status-terminal-title.ts`；`useIpcEvents.ts` 在第 2294 行前调用并传入结果；很可能把 profile 抽到 shared，并改 `main/index.ts` 引用；再加测试。
- 局部修补，没有新增架构。

**7 难点一句话**
接口和行为在题面里已经写得很清楚，难点在于：profile 表放在 main，要决定怎么共享给 renderer 而不重复；还要在 `applyAgentStatus` 里把 resolver 接对位置，并处理好 `currentTitle` 为 undefined、`waiting` 时描述性标题的边界。