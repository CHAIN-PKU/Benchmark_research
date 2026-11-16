# 仓库档案：`_coalesced_run_refresh_cmd` 提前取消时的 generation 幻影 bump

## 【1 题面要点】
- **要求的行为**：调用方在 `_coalesced_run_refresh_cmd` 里、首个 `with _REFRESH_STATE_LOCK:` 之前被取消，此时没有 future 注册，也没有子进程运行。这种情况下不能 bump `_REFRESH_GENERATIONS[refresh_key]`。
- **复现**：题面给了 8 步竖直时序（race 复现），没有可运行脚本。
- **期望输出**：无具体输出。期望是不 bump，并且仍然抛 `CancelledError`（第 8 步）。
- **修法建议（两种）**：
  - 「Track whether ``inflight`` was ever non-None during the cancel-recovery loop. Only bump generation if ``subprocess_exc is None AND observed_inflight is True``」
  - 「raise immediately when ``inflight is None`` at the top of the cancel handler」
- **接口**：「No new interfaces are introduced.」
- **题面行号已过时**：`refresh.py:487-537` 现在对应约 485-550 行。

## 【2 相关代码】
- `src/notebooklm/_auth/refresh.py:401` 的 `_fetch_tokens_with_refresh`。这是真正要改的地方，bug 在它的取消恢复循环里，而不是 `_coalesced_run_refresh_cmd` 里。
  - 454-455 行：加锁快照 `refresh_generation`。
  - 469-475 行：在 `_REFRESH_STATE_LOCK` 下比较 `current_generation <= refresh_generation`，得到 `should_run_refresh`。
  - 485-520 行：`while True` 循环调用 `_coalesced_run_refresh_cmd`。
    - 493 行的 `except CancelledError` 置 `caller_cancelled=True`，并通过 `registry.get(refresh_key)` 取 `inflight`。
    - 501 行：`if inflight is None or inflight.done():`
    - 509-515 行：`inflight` 非 None 时读取 `cancelled()` / `exception()`，然后 `break`。
    - `inflight` 仍在运行时，不 break，继续循环重新 await。
  - 522-531 行：`subprocess_exc` 非空时抛异常，不 bump。
  - 538-543 行：bump `max(existing, refresh_generation+1)`。
  - 545-550 行：`caller_cancelled` 时抛 `CancelledError`。
- `refresh.py:144-214` 的 `_coalesced_run_refresh_cmd`：
  - 172-179 行：加锁 get-or-create future。
  - 182-210 行：leader 创建 task，`_settle` 回调。
  - 214 行：`await asyncio.shield(future)`。
  - 202-208 行的注释说明 `_settle` 特意把已完成的 future 留在 registry 里。
- `refresh.py:127` 的 `_get_inflight_registry`，以及 115 行的 `_REFRESH_INFLIGHT_BY_LOOP`。
- `src/notebooklm/auth.py:709-719` 只是转发的 facade，不用改。

## 【3 并列与牵连】
- 没有并列实现。`_fetch_tokens_with_refresh` 只有一份，`auth.py` 里只是别名。
- 调用方在 `refresh.py:684`、`:731` 以及 `auth.py:514`。它们都经过同一段逻辑，所以改一处就够。
- **残留 done future 的问题**：`_settle` 有意把已完成的 future 留在 registry 里（202-208 行）。这会让"observed_inflight"一类的判断变复杂：
  - 取消发生在 leader 注册之前，但 registry 里还留着上一轮周期的已完成 future。此时 `inflight` 不是 None 且 `done()`，`exception()` 为 None，会走成功分支，同样会幻影 bump。
  - 题面的 `inflight is None` 判断覆盖不到这种情况。
  - 这是我从代码推断的，不是题面写的。
- 跨 loop 影响：generation 被其他 loop 的等待者读取（469-475 行），所以修复要保持 `_REFRESH_STATE_LOCK` 的原子语义。

## 【4 现有测试与约定】
- `tests/integration/concurrency/test_refresh_cmd_race.py:456` 的 `test_cancel_settle_race_does_not_bump_on_failure`：
  - 断言 `isinstance(result[0], asyncio.CancelledError)`（514 行）。
  - 断言 `_REFRESH_GENERATIONS.get(refresh_key, 0) == 0`（524 行）。
  - 这条覆盖"子进程失败且同时被取消"。
- 同文件 183 行的断言：失败时 generation 为 0。
- 同文件 450 行的断言：`_REFRESH_GENERATIONS.get(refresh_key, 0) == 1`，即成功后 bump。
- 取消发生在成功子进程之后时，现有约定是 bump 仍然保留，同时 `CancelledError` 向上抛（545-550 行注释）。修复不能破坏这一点。
- `tests/unit/test_refresh_lock_registry.py`、`tests/unit/test_public_shims.py:1336-1449` 会 monkeypatch `auth_mod._run_refresh_cmd`，说明测试通过 facade 打补丁。
- 我搜索了 `_REFRESH_INFLIGHT_BY_LOOP` 和 `_get_inflight_registry`，tests 目录里没有命中。因此现有测试没有直接构造 registry 状态，隐藏测试可能要自行搭建"取消先于注册"。
- 题面期望与现有测试没有冲突。

## 【5 边界与隐含要求】
- 取消先于 leader 注册，registry 为空：不 bump，抛 `CancelledError`。
- 取消先于注册，但 registry 残留上一轮已完成 future。这时不应把旧 future 当作本次的子进程。要么区分是否本次观察到过 inflight，要么比较 future 身份。
- 取消时子进程仍在运行：继续 re-await，等它结束后再决定（现有逻辑，保持不变）。
- 取消时子进程已成功完成：照旧 bump，然后抛 `CancelledError`。
- 取消时子进程失败：不 bump，`raise CancelledError() from subprocess_exc`。
- 异常类型：必须仍是 `CancelledError`。如果只是"不 bump"但没抛，调用方会继续走 `build_httpx_cookies_from_storage`。
- 提前 raise 时仍要走 `finally`，复位 `_REFRESH_ATTEMPTED_CONTEXT`（565-566 行）。
- 第二次循环（重新 await）里再次被取消的情形，需要在 `observed_inflight` 里正确累积。

## 【6 改动规模】
- 约 1 个源文件（`refresh.py`），在取消处理段改 5-15 行：加一个标志，或在 `inflight is None` 时提前 raise。
- 属于局部修补，不新增结构，也不贯穿多层。
- 测试可能新增 1 个：通过 monkeypatch 在 `_coalesced_run_refresh_cmd` 里、注册 future 之前抛 `CancelledError`，再断言 generation 仍为 0。

## 【7 难点一句话】
改动本身很小，难点在两处：一是识别出被 `_settle` 留在 registry 里的已完成旧 future 会让"`inflight is None`"和"观察到过 inflight"这类判断失效；二是在保留"成功后被取消仍 bump"约定的前提下，不引入新的回归。