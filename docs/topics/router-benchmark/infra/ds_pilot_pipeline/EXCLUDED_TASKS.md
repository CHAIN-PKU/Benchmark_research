# 排除 / 挂起题单（截至 2026-11-14 17:00）

原则：排除的题必须有原因、有证据、可复查；排除清单和数据一起封存，统计里不计。

## A. 环境不支持（本阶段排除，不再尝试）
| 任务 | 原因 | 证据 |
| --- | --- | --- |
| apache__druid-14092 | 50+ 模块 Maven 工程，沙箱离线插件/依赖不全 | 根目录 `mvn -o test-compile` → PluginResolutionException；模块单测 → PluginResolutionException；另一模块 → DependencyResolutionException；评测镜像 oracle=True/null=False 正常 |
| apache__druid-15402 | 同上 | 同上 |
| apache__druid-16875 | 同上 | 同上 |

## B. 题目本身有问题（排除）
| 任务 | 原因 |
| --- | --- |
| rubocop__rubocop-13653 | 自检时标准答案（gold）都过不了，题目/判分数据有问题 |

## C. 挂起（不是排除，之后要跑）
| 集合 | 数量 | 说明 |
| --- | --- | --- |
| lucene 盲测题 | 10 | 盲测组，等预测冻结之后跑；环境到时候按 Java 标准补 |
| Python 缺环境题 | 29 | 需按 Java 同标准补环境（沙箱断网能跑 pytest + 自检通过）再跑 |
| nushell / docusaurus / Rust 大项目 | 若干 | 排到最后单独跑，跑一道清一道 |
