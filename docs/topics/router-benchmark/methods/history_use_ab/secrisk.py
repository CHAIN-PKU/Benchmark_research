#!/usr/bin/env python3
"""历史用法 a：分节风险分。判断模型对仓库档案 7 节各打一个风险分（0~1）+ 总 p_fail；
之后由 fit_secrisk.py 用另一折仓库的历史成败学每节权重。用法：secrisk.py <模型> [--jobs N]"""
import sys, json, glob, os
import v4 as V
ROOT = V.ROOT; D = V.D
model = sys.argv[1]; jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 4
short = model.replace("claude-", "").replace("-5-5", "")
out = ROOT / "out_secrisk" / short; out.mkdir(parents=True, exist_ok=True)
ALL = sorted(os.path.basename(f)[:-3] for f in glob.glob(str(ROOT / "out_dossier/*.md")) if os.path.basename(f)[:-3] in D)
P = """判断{agent}修好下面这道题、并通过维护者隐藏测试的可能性。不要使用对上游修法的记忆。
请按档案的 7 节分别打「这一节暴露出的失败风险」（0=这方面毫无风险，1=这方面几乎必然出错）：
r1 题面：期望是否说不清、有没说出口的要求、修法建议是否可能误导
r2 相关代码：要改的位置是否难找、分散
r3 并列与牵连：是否有必须同步修改的并列实现、成对方法、多个调用点
r4 现有测试与约定：是否有容易违反的约定、断言格式、与题面冲突
r5 边界与隐含要求：隐藏测试可能考到的边界/隐含行为有多少、多隐蔽
r6 改动规模：改动量与跨文件程度
r7 核心难点：难点一句话所说的坑有多深
最后给总体失败概率 p_fail。

===== 完整题面 =====
{issue}
===== 动手前仓库档案 =====
{dos}

只输出一行 JSON：{{"r1":0~1,"r2":0~1,"r3":0~1,"r4":0~1,"r5":0~1,"r6":0~1,"r7":0~1,"p_fail":0~1}}"""
def f(t):
    if (out / f"{t}.json").exists(): return t, "skip"
    try:
        r = V.claude(P.format(agent=V.AGENT, issue=D[t]["issue"][:6000], dos=V.DOS(t)), model, "r7")
        float(r["p_fail"])
    except Exception as e:
        return t, f"err {e}"
    r["task"] = t; (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
if __name__ == "__main__":
    V.run(ALL[:2] if "--smoke" in sys.argv else ALL, f, jobs)
