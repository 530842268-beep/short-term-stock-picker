#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取 short-term-stock-picker 生成的 result.csv，
取综合评分最高的前 N 只股票，格式化为 Markdown，
通过钉钉自定义机器人 webhook 发送。

环境变量（在 GitHub Secrets 中配置，不要写死在代码里）：
  DINGTALK_WEBHOOK : 机器人 webhook 完整地址
  DINGTALK_SECRET  : （可选）加签密钥。留空则不使用加签。
  RESULT_CSV       : （可选）结果文件路径，默认 result.csv
  TOP_N            : （可选）发送前几只，默认 20
"""
import os
import sys
import csv
import time
import json
import base64
import hmac
import hashlib
import urllib.parse
import urllib.request
from datetime import datetime

CSV_PATH = os.environ.get("RESULT_CSV", "result.csv")
TOP_N = int(os.environ.get("TOP_N", "20"))


def load_results(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"未找到结果文件: {path}")
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def sort_by_score(rows):
    def score(r):
        try:
            return float(r.get("综合评分") or 0)
        except (ValueError, TypeError):
            return 0.0
    return sorted(rows, key=score, reverse=True)


def build_markdown(rows):
    today = datetime.now().strftime("%Y-%m-%d")
    top = rows[:TOP_N]
    lines = [
        f"### 📈 短线强势股筛选 {today}",
        f"> 共筛选出 **{len(rows)}** 只，展示评分前 **{TOP_N}** 只",
        "",
        "| 排名 | 代码 | 名称 | 综合评分 | 最新价 | 流通市值(亿) | 涨停次数(近20日) |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for i, r in enumerate(top, 1):
        code = r.get("代码", "")
        name = r.get("名称", "")
        score = r.get("综合评分", "")
        price = r.get("最新价", "")
        cap = r.get("流通市值(亿)", "")
        zt = r.get("涨停次数(近20日)", "")
        lines.append(f"| {i} | {code} | {name} | {score} | {price} | {cap} | {zt} |")
    lines.append("")
    lines.append("> 数据来源 AKShare，仅供研究参考，不构成投资建议。")
    return "\n".join(lines)


def sign_url(webhook, secret):
    if not secret:
        return webhook
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode("utf-8")
    sep = "&" if "?" in webhook else "?"
    return f"{webhook}{sep}timestamp={timestamp}&sign={urllib.parse.quote_plus(sign)}"


def send(webhook, secret, markdown_text):
    url = sign_url(webhook, secret)
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": "短线强势股筛选结果",
            "text": markdown_text,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def main():
    webhook = os.environ.get("DINGTALK_WEBHOOK")
    secret = os.environ.get("DINGTALK_SECRET", "")
    if not webhook:
        print("ERROR: 未设置 DINGTALK_WEBHOOK 环境变量", file=sys.stderr)
        sys.exit(1)
    rows = load_results(CSV_PATH)
    rows = sort_by_score(rows)
    md = build_markdown(rows)
    result = send(webhook, secret, md)
    print("DingTalk 返回:", result)


if __name__ == "__main__":
    main()
