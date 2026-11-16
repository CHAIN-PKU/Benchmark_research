**档案：try/finally 中 `return` 后 finally 体内局部变量被破坏**

**【1 题面要点】**
- 期望行为：方法 `get()` 在 `try: return self._i` / `finally: self._i += 1; if ...` 中，应和 CPython 一样返回 0，并执行 finally 里的自增。
- 实际行为：MicroPython v1.22.1 报 `AttributeError: 'int' object has no attribute '_i'`，发生在 finally 里的 `self._i`。也就是 `self` 被一个 int 覆盖了。
- 题面只给了复现和报错，没有给期望输出文本，也没有修法建议。

**【2 相关代码】**（我在快照里读到的）
- `py/compile.c:1672` `compile_try_finally`：
  - body 内用 `adjust_stack_size(3)`（1679–1681）为 UNWIND_JUMP 状态预留栈。
  - 之后 `load_const_tok None` 加上 `label_assign l_finally_block`（1685–1686），再编译 finally 体（1687）。
  - finally 体按编译期栈深约 1 来计算。
- `py/vm.c:1092-1125` `MP_BC_RETURN_VALUE` / `unwind_return`：
  - 把返回值复制到 `finally_sp[1]`（1110）。
  - 然后 `PUSH(MP_OBJ_NEW_SMALL_INT(-1))` 作为哨兵（1116），再跳到 handler。
  - 运行时 finally 体下方实际多了 2 个槽（返回值和哨兵）。
- `py/vm.c:665-706` `UNWIND_JUMP`：压入目的 ip 和计数，同样会多占栈槽。
- `py/vm.c:719-744` `END_FINALLY`：根据栈顶是 None、小整数还是异常来分派。
- `py/emitbc.c:285-296`：`n_state = num_locals + stack_size`，其中 `stack_size` 是编译期记录的最大栈深（`emitbc.c:411-418`）。
- `py/emitbc.c:787` `mp_emit_bc_return_value`。
- `py/emitbc.c:628` `mp_emit_bc_unwind_jump`。

我的推断（没有实际运行）：栈向上增长，局部变量在 state 数组末尾倒序存放。运行时 finally 体的栈使用量超过编译期估算，就会溢出到局部变量区，覆盖 `self`。`self._i += 1` 的 `LOAD self; DUP; LOAD_ATTR; ...` 在 finally 内部栈较深，正好触发这个溢出。

**【3 并列与牵连】**
- 并列的 finally 路径有：
  - `compile_async_with_stmt_helper`（compile.c:1837–1940）里的 `adjust_stack_size(3)`（1870）。
  - 普通 `with`（compile.c:约 1790–1830，1814 处有 `adjust_stack_size(1)`）。
  - 这几处与 try/finally 共用 `RETURN_VALUE`、`UNWIND_JUMP`、`END_FINALLY` 的栈协议，需要一起核对栈深预留是否够。
- native 发射器是另一套实现：`py/emitnative.c:2030` `emit_native_unwind_jump` 和 `emitnative.c:2761` `emit_native_return_value`。它用寄存器和局部变量保存状态，不走字节码栈。所以很可能不受影响，但要确认。
- 影响范围：所有 `.mpy` 字节码里 `stack_size` 的取值。如果改了预留量，frozen 模块和预编译的 mpy 栈大小会变。`MP_BC_*` 编码本身不变，不涉及 mpy 版本号。
- `py/showbc.c`、`py/profile.c` 只负责反汇编和 profile，不涉及栈计算。

**【4 现有测试与约定】**
- `tests/basics/try_finally_return.py`（73 行）：
  - finally 体里只有 `print("finally 1")` 这类简单调用，栈很浅，所以没覆盖到溢出。
  - 其中有嵌套 for 循环加嵌套 try/finally 里 return 的场景（26–72 行）。
- 还有 `try_finally_return2..5.py`、`try_finally_loops.py`、`try_finally_break*.py`、`try_finally_continue.py`、`try_finally1/2.py`。我只读了 `try_finally_return.py`，其余只确认了文件存在。
- 仓库没有专门约定栈预留量的文档。正确行为以 CPython 语义为准，`tests/` 通过对比 CPython 输出来判断，与题面期望没有冲突。
- 隐藏测试很可能是新增 `tests/basics/try_finally_*.py`，在 finally 体里做较深的表达式或属性赋值，期望输出与 CPython 一致。

**【5 边界与隐含要求】**
- finally 体栈深更深的情形：`return` 之外，`break` / `continue` 经过 finally（UNWIND_JUMP，多占 dest_ip 和计数）。
- 嵌套 try/finally，以及 for 循环迭代器在栈上时 return（vm.c:1105–1111 注释提到的 iter 槽）。
- `with` 和 `async with` 的清理路径。
- 生成器里的 return，状态存放不同。
- 不能把栈预留改得过大：嵌入式端 RAM 紧张，每个函数的 `n_state` 都会增大。
- 修改后要保证已有 try_finally 测试仍然通过，且 `-X emit=native` 和 `-X emit=bytecode` 行为一致。

**【6 改动规模】**
- 很可能是局部修补：主要改 `py/compile.c` 里 `compile_try_finally`（可能还有 with/async with 两处）的 `adjust_stack_size`，让 finally 体也计入哨兵和返回值所占的槽。约 1–3 个文件、数处改动，外加新增 1 个测试。
- 不过这是我的推断，没有改代码验证。也有可能修在 vm.c 的栈协议上，但那样会牵连更多分支。

**【7 难点一句话】**
难在定位：症状是局部变量 `self` 被覆盖，看起来像解释器内存损坏，实际是编译期栈深估算和运行时 finally 协程多占的栈槽不一致。找到这个原因之后，修改本身不大，但要确认预留量足够，又不能浪费栈。