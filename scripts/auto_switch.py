# -*- coding: utf-8 -*-
"""
auto_switch.py — 磁盘守护：源盘不足阈值时，自动停掉下载并切到目标盘续下

用法:
    python auto_switch.py --src "D:/downloads/收藏夹A" --dst "C:/downloads/收藏夹A" \
                          --urls urls.txt [--threshold 3] [--hq 4k-hevc]

参数:
    --src        当前下载目录（监控它所在的盘）
    --dst        切换后的目标目录（通常另一个盘）
    --urls       完整 URL 列表（每行一个）
    --threshold  剩余空间阈值，单位 GB，默认 3
    --hq         画质档位，默认 4k-hevc
    --bili       bili.py 路径，默认用本 skill 自带的
    --interval   检查间隔秒数，默认 20

原理：监控 --src 所在磁盘剩余空间，低于阈值时用 psutil 终止 bili.py 进程树，
读取 --src 下的 .downloaded.txt 归档记录算出未完成条目，再启动下载到 --dst。
"""
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    import psutil
except ImportError:
    sys.exit("需要 psutil: python -m pip install --user psutil")


def log(msg: str, logfile: Path | None = None) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    if logfile:
        try:
            with logfile.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


def free_gb(path: Path) -> float:
    anchor = path
    while not anchor.exists() and anchor.parent != anchor:
        anchor = anchor.parent
    return shutil.disk_usage(anchor).free / 1024 ** 3


def kill_downloads() -> list[int]:
    killed = []
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            cl = " ".join(p.info["cmdline"] or [])
        except Exception:
            continue
        if "bili.py" in cl and "auto_switch" not in cl:
            try:
                for c in p.children(recursive=True):
                    try:
                        c.kill()
                    except Exception:
                        pass
                p.kill()
                killed.append(p.pid)
            except Exception:
                pass
    return killed


def done_ids(src: Path) -> set[str]:
    arch = src / ".downloaded.txt"
    if not arch.exists():
        return set()
    out = set()
    for line in arch.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            out.add(parts[1])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="磁盘守护：满了自动切盘续下")
    ap.add_argument("--src", required=True, help="当前下载目录")
    ap.add_argument("--dst", required=True, help="切换目标目录")
    ap.add_argument("--urls", required=True, help="完整 URL 列表文件")
    ap.add_argument("--threshold", type=float, default=3.0, help="剩余空间阈值 GB")
    ap.add_argument("--hq", default="4k-hevc", help="画质档位")
    ap.add_argument("--bili", default=str(Path(__file__).resolve().parent / "bili.py"))
    ap.add_argument("--interval", type=int, default=20, help="检查间隔秒")
    args = ap.parse_args()

    src = Path(args.src).resolve()
    dst = Path(args.dst).resolve()
    urls = Path(args.urls).resolve()
    bili = Path(args.bili).resolve()
    logfile = src.parent / "switch.log"

    log(f"守护启动 | 阈值 {args.threshold} GB | {src.drive} -> {dst.drive}", logfile)
    last_beat = 0.0
    while True:
        f = free_gb(src)
        now = time.time()
        if now - last_beat > 300:
            log(f"心跳 | {src.drive} 剩余 {f:.2f} GB", logfile)
            last_beat = now
        if f < args.threshold:
            log(f"⚠ {src.drive} 仅剩 {f:.2f} GB，触发切换", logfile)
            log(f"已终止下载进程 PID: {kill_downloads()}", logfile)
            time.sleep(6)

            done = done_ids(src)
            all_urls = [u.strip() for u in urls.read_text(encoding="utf-8").splitlines() if u.strip()]
            remain = []
            for u in all_urls:
                bv = u.rstrip("/").split("/")[-1].split("?")[0]
                if not any(d == bv or d.startswith(bv + "_") for d in done):
                    remain.append(u)
            log(f"归档 {len(done)} 条 | 剩余 {len(remain)} 条", logfile)
            if not remain:
                log("没有剩余条目，退出", logfile)
                return

            dst.mkdir(parents=True, exist_ok=True)
            remain_file = dst.parent / "remain.txt"
            remain_file.write_text("\n".join(remain) + "\n", encoding="utf-8")
            log(f"启动续下 -> {dst}", logfile)
            proc = subprocess.Popen(
                [sys.executable, str(bili), f"@{remain_file}", "--hq", args.hq, "-o", str(dst)],
                cwd=str(bili.parent),
            )
            log(f"续下任务已启动 PID={proc.pid}", logfile)
            proc.wait()
            log(f"续下任务结束，返回码 {proc.returncode}", logfile)
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
