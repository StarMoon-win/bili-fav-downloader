# -*- coding: utf-8 -*-
"""
check_env.py — 环境自检：确认下载所需组件是否齐备，缺什么给什么安装命令

用法: python check_env.py
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import cookie_candidates, find_exe  # noqa: E402

OK, BAD, WARN = "[OK]", "[!!]", "[??]"


def ytdlp_version():
    try:
        r = subprocess.run([sys.executable, "-m", "yt_dlp", "--version"],
                           capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def cookie_info():
    for p in cookie_candidates():
        if not p.exists():
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        return p, ("SESSDATA" in txt and "bili_jct" in txt), ("SESSDATA" in txt)
    return None, False, False


def main() -> int:
    problems = []
    print("=" * 62)
    print("B站下载环境自检")
    print("=" * 62)

    v = sys.version.split()[0]
    if sys.version_info[:2] >= (3, 9):
        print(f"{OK} Python {v}")
    else:
        print(f"{BAD} Python {v}（需要 3.9+）")
        problems.append("升级 Python 到 3.9 以上")

    ver = ytdlp_version()
    if ver:
        print(f"{OK} yt-dlp {ver}")
    else:
        print(f"{BAD} yt-dlp 未安装")
        problems.append("python -m pip install --user yt-dlp")

    ff = find_exe("ffmpeg/bin/ffmpeg.exe", "ffmpeg.exe")
    if ff:
        print(f"{OK} ffmpeg {ff}")
    else:
        print(f"{BAD} ffmpeg 未找到（音视频无法合并）")
        problems.append(
            "python -m pip install --user imageio-ffmpeg，"
            "再把包内 binaries/ffmpeg-win-x86_64-*.exe 复制为 bin/ffmpeg.exe"
        )

    bd = find_exe("BBDown/BBDown.exe", "BBDown.exe")
    if bd:
        print(f"{OK} BBDown {bd}")
    else:
        print(f"{WARN} BBDown 未找到（仅影响失败补救，日常下载不需要）")
        print("     https://github.com/nilaoda/BBDown/releases 下载 win-x64 版解压到 bin/")

    path, good, has_sess = cookie_info()
    if path and good:
        print(f"{OK} 登录态 {path}")
    elif path and has_sess:
        print(f"{WARN} 登录态 {path}（缺少 bili_jct，部分功能受限）")
    else:
        print(f"{BAD} 未找到有效 cookies.txt")
        problems.append("按 SKILL.md「登录态」章节用 F12 复制 Cookie 生成 cookies.txt")

    print("-" * 62)
    if problems:
        print("需要处理：")
        for i, p in enumerate(problems, 1):
            print(f"  {i}. {p}")
        return 1
    print("环境就绪，可以开始下载。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
