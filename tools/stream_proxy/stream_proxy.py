#!/usr/bin/env python3
"""最小的 Anthropic 兼容「真流式」转发代理（参考实现，给 DSH 对照用）。

要点（下午 23 分钟零回复的教训）：
  * 上游返回 SSE（stream=true）时，必须「读到一块就立刻写出、立刻 flush」，
    不能用 resp.read() / readlines() 这类会攒满整段才返回的读法。
  * 用 http.client 的 resp.read1(n)：有多少给多少，不等凑满 n 字节。
  * 对下游用 chunked 传输编码，逐块写出。
  * GET 一律回 200（Claude Code 启动时会探测模型），只转发 POST /v1/messages。

用法：
  UPSTREAM_HOST=api.deepseek.com UPSTREAM_PREFIX=/anthropic \
  UPSTREAM_AUTH_HEADER=x-dsh-auth-token UPSTREAM_TOKEN_ENV=DSH_TOKEN \
  MODEL_MAP='deepseek/deepseek-v4.1-flash=deepseek-flash' \
  python3 stream_proxy.py 18080
令牌只从环境变量读，不落盘、不打印。
"""
import http.client
import http.server
import json
import os
import socketserver
import ssl
import sys
import time

HOST = os.environ.get("UPSTREAM_HOST", "api.deepseek.com")
SCHEME = os.environ.get("UPSTREAM_SCHEME", "https")
PREFIX = os.environ.get("UPSTREAM_PREFIX", "/anthropic")
AUTH_HEADER = os.environ.get("UPSTREAM_AUTH_HEADER", "x-api-key")
TOKEN = os.environ.get(os.environ.get("UPSTREAM_TOKEN_ENV", "UPSTREAM_TOKEN"), "")
MODEL_MAP = dict(kv.split("=", 1) for kv in os.environ.get("MODEL_MAP", "").split(",") if "=" in kv)
LOG = os.environ.get("PROXY_LOG", "stream_proxy.log")
HOP = {"connection", "keep-alive", "transfer-encoding", "content-length", "host"}


def log(**kw):
    kw["t"] = time.strftime("%F %T")
    with open(LOG, "a") as f:
        f.write(json.dumps(kw, ensure_ascii=False) + "\n")


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # 静默默认日志
        pass

    def do_GET(self):
        body = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        t0 = time.time()
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        try:
            req = json.loads(raw)
            if req.get("model") in MODEL_MAP:
                req["model"] = MODEL_MAP[req["model"]]
            raw = json.dumps(req).encode()
            meta = {"stream": req.get("stream"), "thinking": req.get("thinking"), "max_tokens": req.get("max_tokens"),
                    "n_tools": len(req.get("tools") or [])}
        except Exception:
            meta = {"parse_error": True}
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP | {"authorization", "x-api-key"}}
        headers[AUTH_HEADER] = TOKEN
        headers["Content-Length"] = str(len(raw))
        conn = (http.client.HTTPSConnection(HOST, timeout=600, context=ssl.create_default_context())
                if SCHEME == "https" else http.client.HTTPConnection(HOST, timeout=600))
        conn.request("POST", PREFIX + self.path, body=raw, headers=headers)
        resp = conn.getresponse()
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() not in HOP:
                self.send_header(k, v)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        first, total = None, 0
        while True:
            chunk = resp.read1(65536)          # 有多少给多少，不等凑满
            if not chunk:
                break
            if first is None:
                first = time.time() - t0
            total += len(chunk)
            self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
            self.wfile.flush()                 # 立刻推给下游
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()
        conn.close()
        log(path=self.path, status=resp.status, first_byte_s=round(first or -1, 2), total_s=round(time.time() - t0, 2),
            bytes=total, **meta)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18080
    Server(("127.0.0.1", port), Handler).serve_forever()
