# 仓库档案：Megatron OPD top-k 蒸馏 loss 在 bshd 格式下报错

我读了 `losses.py`、`util.py`、`model_forward.py`、`distillation/losses.py` 和现有测试，没有运行任何代码。

## 1 题面要点
- **要求的行为**：Megatron 后端计算 OPD（top-k 前向 KL）loss 时，bshd 数据格式要能跑通。
- **复现**：题面没有给命令或完整堆栈。
  - 只指出位置 `verl/trainer/distillation/megatron/losses.py` 约 248 行（快照里是 291–292 行）的 `preprocess_bshd_engine(teacher_topk_log_probs, pre_process=True)`。
  - 原文是："teacher_topk_log_probs is [b, length, 64] but preprocess_bshd_engine this function need [n, length] dim"。
- **期望输出和修法建议**：都没有。
- **没有新接口**：题面写明 "No new interfaces are introduced."
- **触发条件**（据代码推断）：`data_format != "thd"`，即 GPT-OSS、Qwen3.5 这类不支持 THD 的模型。

## 2 相关代码
- `verl/trainer/distillation/megatron/losses.py:264-312`，`compute_forward_kl_topk`
  - 第 284 行断言输入是 nested tensor。
  - 第 287-292 行按 `data_format` 分支：thd 调 `preprocess_thd_engine`，否则调 `preprocess_bshd_engine`。
  - 第 291-292 行是出错点。输入形状是 jagged nested `(B, j, topk)`，用来按 CP 切分，并 pad 成与 student_logits 对齐的 `(B, S/cp, topk)`。
  - 第 293 行断言 `shape[:2]` 与 `student_logits.shape[:2]` 一致。
- `verl/models/mcore/util.py:564-662`，`preprocess_bshd_engine`
  - 它只为 2-D `(B, j)` 的 input_ids 设计。
  - 第 600-601 行创建 2-D 的 `attention_mask` 和 `input_ids_bshd`，形状是 `(B, local_max_seqlen)`。
  - 第 607 行 `input_ids_bshd[i,:seqlen_i] = input_ids[i]`，传入 3-D 时形状不匹配。
  - 第 610-631 行的 CP 路径同样假设 `seq` 是 1-D：`torch.zeros(max_seqlen)`、`seq[first_start:...]`。
  - 返回值是 `(input_ids_bshd, attention_mask, position_ids)`。
  - `need_roll` 在第 622-630 和 655-656 行处理，3-D 输入也会受影响。
- `verl/models/mcore/util.py:317-480`，`preprocess_thd_engine`
  - 第 378-379 行用 `shape = list(input_ids.shape[1:])`，已经支持尾部多维。
  - 所以 thd 路径对 `(B,j,topk)` 能工作。
- `verl/models/mcore/util.py:665-738`，`postprocess_bshd_engine`
  - 用 `attention_mask` 去 pad，再做 CP all_gather 和重组，已用 `*output.shape[2:]` 支持尾部维。
  - 它是对称的后处理，本问题不一定要改。

## 3 并列与牵连
- **并列实现**：`megatron/losses.py:291` 和 `292` 两处，分别处理 log_probs 和 ids，必须同样修改。
- **其他调用点**：`preprocess_bshd_engine` 的其他调用都是 2-D。
  - `model_forward.py:386`：input_ids。
  - `model_forward.py:404`：mtp 的 label 和 loss_mask。
  - `model_forward.py:429`：`logits_processor_args` 里的 label 和 `response_mask`，这些是 `(B, j)`。
  - 如果在 `util.py` 里把函数泛化，这几处的行为不能变。
  - 如果只在 `losses.py` 里写 helper，影响面最小。
- **teacher_ids 的 dtype**：ids 是整型，log_probs 是浮点。`input_ids_bshd` 用 `dtype=input_ids.dtype`，所以两者 dtype 都能保持。
- **fsdp 路径**：`fsdp/losses.py:35` 有同名函数，我没读，是否也有 bshd 分支没有核实。
- **调用入口**：`distillation/losses.py:123-162` 的 `compute_topk_loss` 把 `data_format` 传下来，并断言输出形状等于 `student_logits.shape[:2]`。
- **文档**：`docs/algo/opd.md:705-743` 提到该函数，一般不需要改。

## 4 现有测试与约定
- `tests/utils/test_special_megatron_kl_loss_tp.py:147-153`
  - 调用 `compute_forward_kl_topk_vp(..., data_format="thd")`，没有 bshd 用例。
  - 输入是 `to_nested`（第 120-121 行）生成的 jagged nested，形状 `(1, S, topk)`。
  - 第 159-166 行以 fsdp 实现作参考。
  - 第 172-182 行断言：`assert_close(vp_loss, ref_loss, atol=1e-4, rtol=1e-4)`、`overlap_count` 相等、梯度相等。
  - 这是分布式测试，需要 torchrun 和 GPU，隐藏测试大概率不是它。
- `tests/workers/test_distillation_topk_symmetry_on_cpu.py:44-45`
  - 导入了 fsdp 的 `compute_forward_kl_topk`，是 CPU 测试。
  - 隐藏测试可能是新增的 CPU 单测：mock `mpu`，用 nested 3-D 输入调用 `preprocess_bshd_engine` 或 megatron 的 `compute_forward_kl_topk`，bshd 分支。
  - 我没读这个文件，这只是推测。
- **约定**：docstring 写明 teacher 输入为 `(bsz, seqlen, topk)`，输出与 student_logits 的 `(bsz, seqlen/cp_size, ...)` 对齐。
  - 参考行为是第 293 行的断言。
  - 另一个参考是 `postprocess_bshd_engine` 的 zigzag CP 切法：每个 rank 取 chunk `cp_rank` 和 `2cp-1-cp_rank`。
  - 与题面不冲突。

## 5 边界与隐含要求
- **padding 值**：需要按 `max_seqlen` 对齐到 `tp_size*cp_size*2`，与 student 的 `local_max_seqlen` 完全一致，否则第 293 行断言失败。
  - 因此 teacher 必须沿用同一套 `max_seqlen` 计算。
  - 如果 student 用了 `use_fp8_padding`，teacher 也要同样 padding，而 `compute_forward_kl_topk` 没有这个参数。
- **pad 位置的填充值**：topk_ids 用 0、log_probs 用 0 都会参与 `exp`。
  - 这些位置会被 `response_mask` 去掉，但 NaN 不能出现。
  - `target_topk_logps` 填 0 会得到 prob=1，只要不进最终 loss 就没问题。
- **CP 的 zigzag 切分**：CP>1 时第 610-631 行的 1-D 假设要改成沿 dim 0 切，保留尾部维。
- **不能破坏 2-D 调用方**：`need_roll`、`attention_mask` 的 NPU 分支（第 658-660 行）不能受影响。
- **tp_size 与序列并行**：长度要能被 tp_size 整除。
- **返回值**：bshd 的 `preprocess_bshd_engine` 返回 3 元组，调用处用 `*_` 取第一项即可。
- **设备**：nested tensor 的 `offsets()` 在 GPU 上，`.tolist()` 有同步开销，通常可以接受。

## 6 改动规模
- 只改 1 个文件、约 2 处调用点，加一个 helper（局部修补）：
  - 在 `megatron/losses.py` 里写一个 bshd 版 3-D 切分/padding 函数，可能约 20-40 行。
  - 或者泛化 `util.py:564` 的 `preprocess_bshd_engine`，让它对 `input_ids.shape[2:]` 通用，约 10-20 行，改 6-8 处。
- 可能附带加一个 bshd 的测试用例，不属于必需改动。
- 不涉及新结构，也不贯穿多层。

## 7 难点一句话
- 代码本身不难，难在要在没有 Megatron 的 CPU 环境下，让 `preprocess_bshd_engine` 的 3-D nested 输入同时兼容 cp=1 和 zigzag CP>1，并保证 teacher 的 padding 和 student_logits 的 `local_max_seqlen` 严格一致。
- 没有复现手段，也没有期望输出，只能靠读代码推断。