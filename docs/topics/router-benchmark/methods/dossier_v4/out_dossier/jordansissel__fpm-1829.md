# 仓库档案：fpm deb `Provides` 版本约束校验

(查证了 `lib/fpm/package/deb.rb`、`templates/deb.erb`、`spec/fpm/package/deb_spec.rb`、`spec/conversion/gem_to_deb.rb`，以及 `lib/fpm` 下其他格式对 provides 的处理。)

## 【1 题面要点】
- 要求的行为：生成 deb 时，如果 `--provides` 里带了非 `=` 的版本约束，例如 `foo (<< 1.0.0-54)`，应在构建期报错或拒绝，而不是放行到安装期才失败。
- 理由：dpkg 的 Provides 只允许精确版本 `=`。
- 题面没有给复现命令，没有给期望输出，也没有给修法建议。
- 关键句：“If fpm checked for that, I would have caught the error at build time rather than install time. I don't know if policy enforcement like that is considered one of fpm's responsibilities”。
- 题面没说是 raise 还是 warn，也没说抛什么异常，错误信息文本也没定。这一点是模糊的。
- 题面还提到 #1788、#1803，这两个 PR 让 fpm 开始原样透传版本字符串。仓库里没找到它们的记录，CHANGELIST 文件不存在。

## 【2 相关代码】
- `lib/fpm/package/deb.rb:777-797` `fix_provides(provides)`：这是最可能要改的函数。
  - 它把名字转小写，并把 `_` 换成 `-`。
  - `deb.rb:792` 用 `^([A-Za-z0-9_-]+)\s*=\s*(\d+.*$)` 把 `name = ver` 改写成 `name (= ver)`。
  - 其余情况原样返回，所以 `foo (<< 1.0)` 会直接通过。没有任何校验。
- `deb.rb:428-429` `output` 开头执行 `self.provides = self.provides.collect { |p| fix_provides(p) }`。这是主要的构建调用点。
- `deb.rb:655-661` `converted_from` 同样对 provides 调用 `fix_provides`，是转换时的第二个调用点。
- `deb.rb:691-702` gem 来源的 provides 转换：把 `rubygem-name = ver` 转成 `(= ver)`。
- `templates/deb.erb:25-29` 渲染 `Provides: <%= provides.join ", " %>`，不做校验。
- `deb.rb:329-337` 是读取 deb 输入的路径，`provides_str.split(/\s*,\s*/)`，不经过 `fix_provides`。

## 【3 并列与牵连】
- `fix_dependency`（`deb.rb:711-775`）是并列的成对方法。它会把 `>`、`<` 转成 `>>`、`<<`。
  - 一个很可能的错误方向：用户可能写 `foo (< 1.0)`。若只校验是否为 `=`，这里就会被拒。
  - 不应让校验去碰 `fix_dependency`。
- `fix_provides` 有两个调用点（`output` 和 `converted_from`）。校验放在函数内部才能同时覆盖两处。
- 其他格式（rpm、pacman）的 provides 不受影响。rpm 允许版本比较，rpm.rb 的 provides 处理不需要改。
- gem、cpan 输入生成 `name = version`（`gem.rb:185`、`cpan.rb:107`）。这类 provides 必须继续通过校验，经 `fix_provides` 转成 `(= ver)`。
- 从 deb 读入的包，provides 若包含 `<<` 等，经 `converted_from` 转 deb 时会触发新的错误。这是 deb→deb 的牵连。

## 【4 现有测试与约定】
- `spec/fpm/package/deb_spec.rb:146`：`original.provides << "#{original.name} (= #{original.version})"`，合法形式，必须继续通过。
- `deb_spec.rb:149`：`original.provides << "Some-SILLY_name"`，没有版本。
- `deb_spec.rb:240`：`insist { input.provides }.include?("some-silly-name")`，没有版本的名字要照常通过。
- `spec/conversion/gem_to_deb.rb:33`：`insist { deb.provides.first } =~ /^rubygem-rails \(= \d+\.\d+\.\d+\)$/`。
- 没有任何现成的 `fix_provides` 单测，也没有对 `<<` provides 的测试。
- 约定：Debian policy 的 Provides 章节（题面链接）。
  - 只允许 `name` 或 `name (= version)`。
  - 本仓库其他无效配置都抛 `FPM::InvalidPackageConfiguration`（`deb.rb:418`、`609`、`836`、`955`）。
  - 隐藏测试大概率期望抛这个异常，但这只是推测。题面没有明说。
- 与题面不冲突。

## 【5 边界与隐含要求】
- 带空格的写法：`foo (= 1.0)`、`foo(=1.0)`、`foo (=1.0)`。
- 多余空白或尾部空白（现有代码会 `rstrip`）。
- 被拒的运算符：`<<`、`<=`、`>=`、`>>`，以及用户习惯写的 `<`、`>`、`<`。`=` 与 `==` 的处理。
- 校验顺序：必须在 `name = ver` 改写之后做，否则 gem 的 `name = ver` 会被误拒。
- 下划线替换（`deb.rb:786-790`）会作用在整个字符串上，版本里的 `_` 也被改掉，但这与本题无关。
- 一个 provides 带多个约束或带 `|`，例如 `foo (= 1) | bar`。
- 异常类型和消息：隐藏测试可能断言 `raise_error(FPM::InvalidPackageConfiguration)` 或消息匹配。这一点题面没定。
- 对 `output` 与 `converted_from` 两个入口，行为要一致。
- 题面里的 `foo (<< 1.0.0-54)` 不是合法 deb 版本以外的特例，它被拒的原因只是运算符。

## 【6 改动规模】
- 主要改动：`deb.rb` 的 `fix_provides` 内加一段校验，约 5–10 行，一个文件。
- 可能再加一个 spec，在 `deb_spec.rb` 中加例子。
- 局部修补，不需要新增结构，也不贯穿多层。

## 【7 难点一句话】
改动本身很小，难点是猜对隐藏测试的预期：要不要抛异常，抛哪个类，以及校验要放在 `name = ver` 改写之后，才不会误伤 gem/cpan 的 `=` provides 与无版本的名字。