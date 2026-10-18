#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
bili.py — B 站视频 / 收藏夹批量下载器（yt-dlp 封装）

用法:
    python bili.py <URL>                      # 下载单个视频
    python bili.py <收藏夹URL>                 # 下载整个收藏夹
    python bili.py <收藏夹URL> -l              # 只列清单，不下载
    python bili.py <URL> -o D:\\Videos -b chrome

常用选项:
    -o, --out DIR       保存目录（默认 ~/Downloads/bili）
    -b, --browser NAME  从哪个浏览器读登录态: edge / chrome / firefox（默认 edge）
    --no-cookie         不使用登录态（公开内容，画质上限 1080P）
    -l, --list          只列出视频清单
    -q, --quality NUM   画质上限，如 2160 / 1080 / 720（默认不限制）
    -n, --dry-run       只看会做什么，不实际下载

说明:
    收藏夹 URL 形如 https://space.bilibili.com/<UID>/favlist?fid=<收藏夹ID>
    私密收藏夹、1080P+ / 4K 都需要登录态，见 SKILL.md「登录态」。
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import cookie_candidates, default_out, find_exe  # noqa: E402

FFMPEG = find_exe("ffmpeg/bin/ffmpeg.exe", "ffmpeg.exe")
DEFAULT_OUT = default_out()
COOKIE_CANDIDATES = cookie_candidates()


def find_ytdlp() -> list[str]:
    """优先用当前解释器的 -m yt_dlp，避免 PATH 问题。"""
    try:
        subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True, check=True, timeout=30,
        )
        return [sys.executable, "-m", "yt_dlp"]
    except Exception:
        exe = shutil.which("yt-dlp")
        if exe:
            return [exe]
        sys.exit("找不到 yt-dlp，请先运行: python -m pip install --user yt-dlp")


def main() -> None:
    ap = argparse.ArgumentParser(add_help=True, description="B站视频/收藏夹下载")
    ap.add_argument("url", help="视频或收藏夹 URL")
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT), help="保存目录")
    ap.add_argument("-b", "--browser", default="edge", help="读取登录态的浏览器")
    ap.add_argument("--no-cookie", action="store_true", help="不使用登录态")
    ap.add_argument("-l", "--list", action="store_true", help="只列清单")
    ap.add_argument("-q", "--quality", default="", help="画质上限，如 1080")
    ap.add_argument("--hq", default="",
                    choices=["", "4k-av1", "4k-hevc", "4k", "1080", "720"],
                    help="画质预设：4k-av1(体积最优) / 4k-hevc(兼容好) / 4k / 1080 / 720")
    ap.add_argument("-n", "--dry-run", action="store_true", help="只模拟不下载")
    args = ap.parse_args()

    # 画质预设 -> yt-dlp -S 排序规则
    HQ_PRESETS = {
        "4k-av1": "res:2160,vcodec:av01",     # 4K + AV1，体积约为 AVC 4K 的 40%
        "4k-hevc": "res:2160,vcodec:h265",    # 4K + HEVC，兼容性最好
        "4k": "res:2160",
        "1080": "res:1080",
        "720": "res:720",
    }

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = find_ytdlp() + [
        "--no-warnings",
        "--newline",                      # 进度按行刷新，方便实时看
        "--encoding", "utf-8",
        "--proxy", "",                    # 强制直连：B站是国内站，系统代理常是死链
        "--merge-output-format", "mp4",
        "--embed-metadata",
        "--concurrent-fragments", "4",
        # 文件名：UP主/标题 [BV号].mp4
        "-o", str(out_dir / "%(uploader)s" / "%(title).80s [%(id)s].%(ext)s"),
        # 增量：已下过的自动跳过
        "--download-archive", str(out_dir / ".downloaded.txt"),
        # 断点续传
        "--continue",
        "--retries", "10",
        "--fragment-retries", "10",
    ]

    if FFMPEG:
        cmd += ["--ffmpeg-location", str(FFMPEG)]
    else:
        print("⚠ 未找到 ffmpeg，音视频可能无法合并（见 SKILL.md「环境准备」）")

    cookie_file = next((p for p in COOKIE_CANDIDATES if p.exists()), None)
    if not args.no_cookie:
        if cookie_file:
            cmd += ["--cookies", str(cookie_file)]
        else:
            cmd += ["--cookies-from-browser", args.browser]

    if args.hq:
        cmd += ["-S", HQ_PRESETS[args.hq]]
    elif args.quality:
        cmd += ["-S", f"res:{args.quality}"]

    if args.list:
        cmd += ["--flat-playlist", "--print", "%(playlist_index)s. %(title)s  [%(id)s]"]
    elif args.dry_run:
        cmd += ["--simulate"]

    # 批量模式：url 以 @ 开头或指向已存在的文件时，读 URL 列表逐条下载
    url_arg = args.url
    if url_arg.startswith("@"):
        batch = url_arg[1:]
        if not Path(batch).is_file():
            sys.exit(f"批量文件不存在: {batch}")
        cmd += ["--batch-file", batch, "--ignore-errors"]
        shown = f"批量文件 {batch}"
    elif Path(url_arg).is_file():
        cmd += ["--batch-file", url_arg, "--ignore-errors"]
        shown = f"批量文件 {url_arg}"
    else:
        cmd.append(url_arg)
        shown = url_arg

    print("=" * 60)
    print("保存到:", out_dir)
    print("目标   :", shown)
    print("画质   :", args.hq or args.quality or "最高")
    print("=" * 60)

    env = dict(os.environ)
    # B 站国内直连，别让环境的代理变量把请求带偏
    for k in ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        env.pop(k, None)

    cookie_failed = False
    try:
        proc = subprocess.Popen(
            cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            if "cookie database" in line or "Failed to decrypt" in line:
                cookie_failed = True
        proc.wait()
    except KeyboardInterrupt:
        print("\n已中断")
        sys.exit(130)

    if cookie_failed and not args.no_cookie:
        print("\n" + "!" * 60)
        print("读取浏览器登录态失败（常见原因：浏览器正在运行，cookie 库被占用；")
        print("或 Chrome/Edge 127+ 的 App-Bound 加密）。三个办法：")
        print("  1) 完全退出 Edge/Chrome 后重跑本命令")
        print("  2) 加 --no-cookie 先下公开内容（画质上限 1080P）")
        print("  3) 用 F12 复制 Cookie 生成 cookies.txt（最稳，见 SKILL.md「登录态」）")
        print("!" * 60)

    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
