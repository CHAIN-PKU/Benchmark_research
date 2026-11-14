# DeepSWE 抽题（v1，2026-11-15，跑正式批之前冻结）

- 来源：datacurve deep-swe 官方仓库 commit 0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea，tasks/ 下实有 **113** 道（另 4 个是 dataset.toml / manifest 等文件，不是题）。
- 规则见 make_deepswe_sample.py：按语言分层、种子 20261115、40 道；go 11 / typescript 11 / python 10 / rust 4 / javascript 4。
- 盲测组 8 道（group=blind）：DS 预测冻结并存 sha256 之前不跑。
- deepswe_sample_v1_20261115.csv sha256 = 292f7f5ecebd16fab289f5bb5f0209b19f3af513ab560ff4a60b991db578a060
- 试跑过的 abs / arktype / boa 不特殊处理：被抽中就照常计，没抽中只作试跑记录。
