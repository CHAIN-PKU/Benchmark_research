## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) lexer.go next() 约140-164行：heredoc 起始判断为 len(val)>1 && val[:2]=="<<"，之后一直收集到换行，空格不结束 token，所以 `<< >>` 被当成一个 token，需想清楚判定位置。2) 同文件253-279行 token 累积逻辑与 heredocEscaped 转义分支(`\<<`)要保持行为。3) 144-146行 \r 处理与141行 `<<<` 报错不能被破坏。4) 排查下游 Token.heredocMarker、wasQuoted=='<' 及 dispenser.go ~206行 heredoc 说明。
B. `between << >>`、`<<>>`、`<<` 后紧跟其他符号；`<<` 单独在行尾/后接换行（现为空 marker 报错，需明确处理）；合法 heredoc(<<EOF、<<VERY-LONG-MARKER、<<s) 仍正常，`<<HERE SAME LINE` 是否仍报错；引号/反引号内及 token 中间的 `<<`。
C. lexer_test.go 253-405行有完整 heredoc 用例与精确错误文案，应继续通过；`heredoc <EOF` 用例说明单个 < 不算 heredoc；heredocMarkerRegexp 在340行；查文档/注释中关于 heredoc 与 `\<<` 的描述是否需同步。
D. 1) 用题面 Caddyfile adapt，确认 between 得到 `<<` 与 `>>` 两个独立 token 且行号正确。2) 跑全部现有 heredoc 用例，重点多行、CRLF、<<<EOF 报错、缺结束 marker 报错。3) 补测 `<<>>`、`a << b` 以及 `<<` 后接换行，确认不被误判为 heredoc、结果符合预期。
