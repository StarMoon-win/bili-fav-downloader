# -*- coding: utf-8 -*-
"""
make_cookies.py — 把浏览器复制的 Cookie 字符串转成 Netscape 格式的 cookies.txt

用法:
    python make_cookies.py                    # 粘贴 Cookie 后按 Ctrl+Z 回车（Linux/Mac 用 Ctrl+D）
    python make_cookies.py -s "SESSDATA=xxx; bili_jct=yyy" -o cookies.txt
    python make_cookies.py -f raw_cookie.txt -o cookies.txt

Cookie 从哪来：浏览器打开 bilibili.com 并登录 → F12 → Network → 刷新 →
点任意 bilibili 请求 → Request Headers 里找到 Cookie: 整行复制。
"""
import argparse
import sys
from pathlib import Path

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "cookies.txt"


def parse(raw: str) -> list[tuple[str, str]]:
    pairs = []
    for seg in raw.split(";"):
        seg = seg.strip()
        if not seg or "=" not in seg:
            continue
        k, v = seg.split("=", 1)
        k, v = k.strip(), v.strip()
        if k:
            pairs.append((k, v))
    return pairs


def main() -> None:
    ap = argparse.ArgumentParser(description="Cookie 字符串 -> cookies.txt")
    ap.add_argument("-s", "--string", help="直接给 Cookie 字符串")
    ap.add_argument("-f", "--file", help="从文件读取 Cookie 字符串")
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT), help="输出路径")
    ap.add_argument("--expiry", type=int, default=0,
                    help="过期时间戳，0 表示读 SESSDATA 里的值（推荐）")
    args = ap.parse_args()

    if args.string:
        raw = args.string
    elif args.file:
        raw = Path(args.file).read_text(encoding="utf-8", errors="replace")
    else:
        print("粘贴 Cookie 字符串，然后按 Ctrl+Z 回车（Linux/Mac 按 Ctrl+D）：", file=sys.stderr)
        raw = sys.stdin.read()

    pairs = parse(raw)
    if not pairs:
        sys.exit("没解析到任何 cookie，检查粘贴内容")

    names = {k for k, _ in pairs}
    for must in ("SESSDATA", "bili_jct"):
        if must not in names:
            print(f"⚠ 缺少关键项 {must}，登录态可能不完整", file=sys.stderr)

    expiry = args.expiry
    if not expiry:
        for k, v in pairs:
            if k == "SESSDATA" and "," in v:
                try:
                    expiry = int(v.split(",")[1])
                except Exception:
                    expiry = 0
                break
    if not expiry:
        expiry = 2147483647

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Netscape HTTP Cookie File", "# 本地凭证，请勿分享或提交到仓库", ""]
    for k, v in pairs:
        lines.append(f".bilibili.com\tTRUE\t/\tTRUE\t{expiry}\t{k}\t{v}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"写入 {len(pairs)} 条 cookie -> {out}")


if __name__ == "__main__":
    main()
