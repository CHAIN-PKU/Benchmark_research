## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) finalizeHeredoc 中 strings.LastIndex(string(val),"\n") 返回字节下标,却用来切 []rune,多字节字符会导致 [4:2] 越界,要核对整个函数的字节/rune 混用,不要只改崩溃那一行。2) next() 中判断 heredoc 结束的 len(heredocMarker)(字节数)被用于切 rune 切片,marker 含非 ASCII 时也有同类问题,并核对 heredocMarkerRegexp 的字符集。3) lineText[len(paddingToStrip):] 的字节切片依赖 strings.Index==0 的检查,改动后需保持这个前提。
B. 空内容 heredoc(<<END\nEND);缩进或内容含多字节 UTF-8 字符(缩进一致与不一致两种);\r\n 换行;单行无结尾换行的短输入;内容中含类似 marker 的字符串。
C. lexer_test.go 现有 heredoc 用例(缩进剥离、mismatched leading whitespace 错误信息)要保持行为不变;lexer_fuzz.go 的 FuzzTokenize 要求任何输入都不 panic;heredocMarkerRegexp 定义了合法 marker 字符集。
D. 1) 用多字节字符做缩进和结束标记的 heredoc,并复现崩溃的约 7 字节输入。2) 跑全部现有 heredoc 回归测试。3) 对随机/截断的 UTF-8 输入循环调用 Tokenize,确认无 panic。
