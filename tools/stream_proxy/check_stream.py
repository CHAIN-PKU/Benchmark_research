#!/usr/bin/env python3
"""流式代理验收：发一个长思考的流式请求，量首字节时间、事件数、是否完整结束。

用法：python3 check_stream.py http://127.0.0.1:8766 [model]
通过标准：首字节 ≤ 5 秒；收到 message_stop；中途无断开。
"""
import http.client
import json
import sys
import time
import urllib.parse

url = urllib.parse.urlparse(sys.argv[1])
model = sys.argv[2] if len(sys.argv) > 2 else "deepseek/deepseek-v4.1-flash"
body = json.dumps({
    "model": model, "max_tokens": 32000, "stream": True,
    "thinking": {"type": "enabled", "budget_tokens": 16000},
    "messages": [{"role": "user", "content": "请仔细推理：证明存在无穷多个素数，并给出至少三种不同证明，每种都详细展开。"}],
}).encode()
conn = http.client.HTTPConnection(url.hostname, url.port, timeout=900)
t0 = time.time()
conn.request("POST", "/v1/messages", body=body, headers={
    "Content-Type": "application/json", "anthropic-version": "2023-06-01", "x-api-key": "placeholder"})
resp = conn.getresponse()
first, events, done, buf = None, 0, False, b""
while True:
    chunk = resp.read1(4096)
    if not chunk:
        break
    if first is None:
        first = time.time() - t0
    buf += chunk
    events += chunk.count(b"\nevent:") + chunk.startswith(b"event:")
    if b"message_stop" in buf[-2000:]:
        done = True
total = time.time() - t0
ok = resp.status == 200 and first is not None and first <= 5 and done
print(json.dumps({"status": resp.status, "first_byte_s": round(first or -1, 2), "total_s": round(total, 1),
                  "events": events, "got_message_stop": done, "PASS": ok}, ensure_ascii=False))
sys.exit(0 if ok else 1)
