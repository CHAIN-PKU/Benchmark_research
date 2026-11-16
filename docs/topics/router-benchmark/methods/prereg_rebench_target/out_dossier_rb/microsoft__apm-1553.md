## 仓库档案：apm install 第二次报 `Content hash mismatch`

我没能把"第二次 hash 为什么不同"完全定位到一行代码，下面区分了已确认的和推断的。

### 【1 题面要点】
- 要求的行为：第二次执行 `apm install` 不应报 Content hash mismatch。
- 复现：`apm install <repo>`，再 `apm install`。Windows，APM 0.16.0。
- 期望输出：只有模板句 "A clear and concise description…"，没有实质内容。
- 修法建议：没有。
- 报错句：`Content hash mismatch for <org>/tools/github-copilot-agent-skills/.apm/instructions/testing.instructions.md: expected sha256:2227…, got sha256:b82d…`，随后建议 `apm install --update`。
- 日志里失败的依赖有这些特征：
  - 它是 ADO 上的单个 `.instructions.md` 虚拟文件依赖。
  - 显示为 `#main`，没有 `@sha`。
  - 同一次运行里有 3 个 `.instructions.md` 依赖，其他依赖都是 `@d479f42e (cached)`。
  - `cache-pin: ... has no resolved_commit`。
  - `11 dependencies unpinned`。
- 题面描述的"第一次安装日志看着怪"（如 partial clone 重试）与本 bug 无关，可能是干扰项。

### 【2 相关代码】
- `src/apm_cli/install/sources.py:765-787`（`FreshDependencySource.acquire`）：
  - 全新下载后计算 `_compute_hash(install_path)`，存入 `ctx.package_hashes[dep_key]`。
  - 若 `not ctx.update_refs`、`dep_key` 不在 `expected_hash_change_deps`、且 lockfile 有 `content_hash`，则比较两者。
  - 不相等就 `safe_rmtree` 并 `sys.exit(1)`，输出的就是题面的报错文案。这是直接的"报错点"。
- `src/apm_cli/install/phases/integrate.py:36-218`（`_resolve_download_strategy`）：
  - 决定是否 `skip_download`。
  - 只有 `locked_dep.resolved_commit` 存在且不是 `"cached"` 才可能 `lockfile_match`（行 115-150）。
  - `is_cacheable` 只对 tag/commit 成立（行 85-88），branch 一律重新下载。
  - 行 193-202：命中缓存时先 `verify_package_hash`，不一致则只警告并重下。
  - 行 97-103：`ref_changed` 时加入 `expected_hash_change_deps`，这是现有的绕过机制。
- `src/apm_cli/deps/github_downloader.py:862-1016`（`download_virtual_file_package`）：
  - 写 `.apm/<subdir>/<file>` 和生成的 `apm.yml`。
  - `apm.yml` 内容只由 name、version、description、author 决定，是确定性的。
  - `resolved_commit` 来自 `_resolve_commit_sha_for_ref`。
- `src/apm_cli/deps/git_reference_resolver.py:236-242`：对 `is_azure_devops()` 或 artifactory 直接 `return None`。所以 ADO 虚拟文件的 `resolved_commit` 恒为 None。这解释了日志中没有 `@sha`。
- `src/apm_cli/utils/content_hash.py:25-71`：`compute_package_hash` 对相对路径和字节做 sha256。排除 `.git`、`__pycache__` 和根目录的 `.apm-pin`。
- `src/apm_cli/models/dependency/reference.py:382-470`、`218-241`：
  - 虚拟文件的安装目录是 `apm_modules/<org>/<project>/<repo名>-<文件基名>`。
  - 这个名字只用 repo 末段和文件基名，不含 virtual_path 的中间目录。
- `src/apm_cli/install/phases/lockfile.py:157-160`：把 `ctx.package_hashes` 写入 `content_hash`。
- `src/apm_cli/install/cache_pin.py:131-198`：对无 `resolved_commit` 的依赖只警告，不写 marker。

### 【3 并列与牵连】
- 三个 hash 校验点互相独立：
  - `sources.py:765-787`：fatal。
  - `integrate.py:193-202`：只警告并重下。
  - registry 的 `download_from_lockfile` 另有校验。
- 修改要保持 `ctx.expected_hash_change_deps` 的语义，该机制由 `resolve.py` 的 BFS 回调和各类 heal（`install/heals/*`）共用。
- `sources.py:291`、`525`、`753` 是三处 `package_hashes[dep_key] = _compute_hash(...)`，分别对应 Local、Cached、Fresh 三种来源，需要保持一致。
- 同类的其他虚拟依赖（subdirectory、skill）也走 `Fresh` 路径。ADO 上任何 branch 引用、无 resolved_commit 的依赖都可能同样触发。
- 改 `GitReferenceResolver` 的 ADO 分支（让 ADO 也解析 SHA）会影响 lockfile 内容和 `cache_pin` marker。

### 【4 现有测试与约定】
- `tests/unit/install/test_integrate_orchestration.py:123` `test_content_hash_mismatch_forces_redownload`：针对 `integrate.py` 的"警告并重下"路径。
- `tests/unit/install/test_branch_ref_drift.py:171-178`、`300-310`：回归断言 `expected_hash_change_deps` 必须被填充，否则 supply-chain hard-block 会终止恢复。
- `tests/integration/test_diff_aware_install_e2e.py:549-625`：自愈路径不得触发 hard-block。
- `tests/unit/install/test_drift.py:303`：无 pin 的 remote dep 在审计时 fail-closed。
- `tests/fixtures/spec-conformance/integrity/hash-mismatch.frozen.yaml`（req-lk-013）：规范要求 hash 不匹配时 fail closed。
- 文档 `docs/src/content/docs/consumer/drift-and-secure-by-default.md:47`、`:152` 与 `troubleshooting/common-errors.md:79` 把该错误定性为"上游内容变化，需调查"。
- 冲突：题面期望"不报错"，而规范与文档要求对真实内容变化 fail closed。修复必须区分"合法的内容变化"（branch 前进、虚拟文件无 pin）与"篡改"。我没读到这些测试的具体断言，只确认了它们存在。

### 【5 边界与隐含要求】
- 已确认：这个依赖是 branch 引用且无 resolved_commit，所以永远走 Fresh 下载，每次都要和旧 hash 比较。若上游 branch 有新提交，hash 一定变，所以仅靠"放宽比较"会削弱校验。
- 推断（未证实）：为什么在上游没变的情况下 hash 也变。候选如下：
  - 安装目录冲突。路径名只含 `repo-基名`，不同 virtual_path 可能撞到同一目录。
  - 目录里残留旧文件，或与其他依赖共享目录。
  - ADO 下载字节随换行符（Windows）变化。
  - 注意本地副本里没有对 CRLF 的处理代码，我没找到证据。
- 需要考虑：
  - `--update` 与不带 `--update` 的行为差异。
  - 只有 resolved_commit 为 None 的依赖是否要豁免。
  - 还是要让 ADO 解析 SHA。
  - 或者对 branch 引用不再比较 hash。
  - 并行预下载（`pre_download_results`）路径。
  - 多个同名依赖共用 `install_path`。
  - 失败后 `safe_rmtree` 会删除缓存，使后续运行也受影响。

### 【6 改动规模】
- 最小修法大概是 1-2 个文件、几处：`sources.py` 的校验条件，或 `integrate.py` 里把此类依赖加入 `expected_hash_change_deps`。
- 若改为让 ADO 解析 SHA 或统一虚拟文件目录，就会牵涉 resolver、lockfile、cache_pin，约 3-5 个文件。
- 属于局部修补，不需要新增结构；但要补单元测试。

### 【7 难点一句话】
难在无法从快照直接复现，"上游没变 hash 却变了"的根因要靠推断，而且修法必须在不削弱 fail-closed 供应链校验的前提下，区分"无 pin 的 branch 依赖合法变化"与"篡改"。