# -*- coding: utf-8 -*-
"""
bili_fav.py — B 站收藏夹查询工具（走官方 API，速度快、信息全）

用法:
    python bili_fav.py folders                    # 列出我的所有收藏夹
    python bili_fav.py list <fid>                 # 列出某收藏夹的内容
    python bili_fav.py list <fid> --all           # 列出全部（默认只列前 50 条）
    python bili_fav.py stats <fid> [fid2..]       # 统计体量与预估体积
    python bili_fav.py stats <fid> --sample 100   # 大夹采样估算
    python bili_fav.py pick <fid> -i 1,3,5-10 -o sel.txt   # 按序号挑选，生成下载清单
    python bili_fav.py pick <fid> -i 1- -x 5,8             # 全选但排除 5、8
"""
import json
import sys
import time
from pathlib import Path

import requests

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from _paths import cookie_file  # noqa: E402

COOKIE_FILE = cookie_file()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}

# 1080P 高码率实测约 5253 kbps -> 每秒约 0.64 MB
MB_PER_SEC = 0.64


def load_cookies() -> dict:
    if not COOKIE_FILE or not COOKIE_FILE.exists():
        sys.exit("缺少 cookies.txt（获取方式见 SKILL.md「登录态」）")
    ck = {}
    for line in COOKIE_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        p = line.split("\t")
        if len(p) >= 7:
            ck[p[5]] = p[6]
    return ck


CK = load_cookies()
SESSION = requests.Session()
SESSION.trust_env = False          # 忽略环境变量里的代理，B 站直连
SESSION.cookies.update(CK)
SESSION.headers.update(HEADERS)


def api(url: str, params: dict | None = None) -> dict:
    delay = 1.0
    last_err = None
    for attempt in range(5):
        try:
            r = SESSION.get(url, params=params, timeout=20)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            j = r.json()
            if j.get("code") == 0:
                return j["data"]
            if j.get("code") == -412:
                raise RuntimeError("触发风控 -412")
            raise RuntimeError(f"API 返回 code={j.get('code')} {j.get('message')}")
        except Exception as e:
            last_err = e
            if attempt == 4:
                break
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"请求失败: {last_err}")


def my_mid() -> int:
    d = api("https://api.bilibili.com/x/web-interface/nav")
    return d["mid"]


def fmt_dur(sec: int) -> str:
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_size(mb: float) -> str:
    return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb:.0f} MB"


def cmd_folders() -> None:
    mid = my_mid()
    d = api("https://api.bilibili.com/x/v3/fav/folder/created/list-all",
            {"up_mid": mid, "type": 2, "rid": 0, "web_location": "333.1387"})
    lst = d.get("list") or []
    print(f"共 {len(lst)} 个收藏夹（UID {mid}）\n")
    total = 0
    for i, f in enumerate(lst, 1):
        total += f["media_count"]
        vis = "私密" if f["attr"] & 1 else "公开"
        print(f"{i:2d}. {f['title']:<18s} {f['media_count']:>5d} 条  {vis}  fid={f['id']}")
    print(f"\n合计 {total} 条")


def iter_medias(fid: int, max_items: int | None = None):
    pn = 1
    got = 0
    while True:
        d = api("https://api.bilibili.com/x/v3/fav/resource/list", {
            "media_id": fid, "pn": pn, "ps": 20, "platform": "web",
            "order": "mtime", "type": 0, "tid": 0,
        })
        medias = d.get("medias") or []
        if not medias:
            break
        for m in medias:
            yield m
            got += 1
            if max_items and got >= max_items:
                return
        if not d.get("has_more"):
            break
        pn += 1
        time.sleep(0.35)


def load_medias(fid: int, refresh: bool = False) -> list:
    """取收藏夹全部条目，带 1 小时本地缓存（避免反复翻页触发风控）"""
    cache_dir = TOOLS / ".cache"
    cache_dir.mkdir(exist_ok=True)
    cache = cache_dir / f"fav_{fid}.json"
    if not refresh and cache.exists() and time.time() - cache.stat().st_mtime < 3600:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            pass
    medias = list(iter_medias(fid))
    try:
        cache.write_text(json.dumps(medias, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return medias


def parse_items(expr: str, total: int) -> list[int]:
    """解析选择表达式：'1,3,5-10,20-' -> 有序序号列表"""
    sel = set()
    for part in expr.replace("，", ",").replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start = int(a) if a else 1
            end = int(b) if b else total
            sel.update(range(start, end + 1))
        else:
            sel.add(int(part))
    return sorted(x for x in sel if 1 <= x <= total)


def cmd_list(fid: int, show_all: bool) -> None:
    medias = load_medias(fid)
    limit = None if show_all else 50
    for i, m in enumerate(medias, 1):
        if limit and i > limit:
            print(f"... 还有 {len(medias) - limit} 条，用 --all 看全部")
            break
        dur = m.get("duration") or 0
        upper = (m.get("upper") or {}).get("name", "?")
        print(f"{i:4d}. {m['title'][:52]:<54s} {fmt_dur(dur):>8s}  {upper[:14]:<16s} {m['bvid']}")
    print(f"\n共 {len(medias)} 条")


def cmd_pick(fid: int, expr: str, out: str, exclude: str = "") -> None:
    medias = load_medias(fid)
    total = len(medias)
    sel = parse_items(expr, total) if expr else list(range(1, total + 1))
    if exclude:
        sel = [i for i in sel if i not in set(parse_items(exclude, total))]
    if not sel:
        sys.exit("没有选中任何条目")
    urls = [f"https://www.bilibili.com/video/{medias[i - 1]['bvid']}" for i in sel]
    Path(out).write_text("\n".join(urls) + "\n", encoding="utf-8")
    sec = sum((medias[i - 1].get("duration") or 0) for i in sel)
    print(f"收藏夹共 {total} 条 | 选中 {len(urls)} 条 | 总时长 {fmt_dur(sec)}")
    print(f"清单已写入: {out}\n")
    show = sel if len(sel) <= 20 else sel[:10] + ["..."] + sel[-3:]
    for i in show:
        if i == "...":
            print("   ...")
            continue
        m = medias[i - 1]
        print(f"{i:4d}. {m['title'][:46]:<48s} {fmt_dur(m.get('duration') or 0):>8s}  {m['bvid']}")


def folder_total(fid: int) -> int:
    d = api("https://api.bilibili.com/x/v3/fav/resource/list", {
        "media_id": fid, "pn": 1, "ps": 20, "platform": "web",
        "order": "mtime", "type": 0, "tid": 0,
    })
    return (d.get("info") or {}).get("media_count", 0)


def cmd_stats(fids: list[int], sample: int | None = None) -> None:
    grand_sec = 0.0
    grand_cnt = 0
    for fid in fids:
        total = folder_total(fid)
        limit = sample if (sample and total > sample) else None
        sec = cnt = 0
        for m in iter_medias(fid, limit):
            sec += m.get("duration") or 0
            cnt += 1
        if cnt == 0:
            print(f"fid={fid}: 空收藏夹")
            continue
        if limit and cnt < total:
            est_sec = sec / cnt * total
            grand_sec += est_sec
            grand_cnt += total
            print(f"fid={fid}: {total} 条（采样 {cnt} 条估算）, "
                  f"总时长约 {fmt_dur(int(est_sec))}, 1080P高码率约 {fmt_size(est_sec * MB_PER_SEC)}")
        else:
            grand_sec += sec
            grand_cnt += cnt
            print(f"fid={fid}: {cnt} 条, 总时长 {fmt_dur(sec)}, "
                  f"1080P高码率约 {fmt_size(sec * MB_PER_SEC)}")
    if len(fids) > 1:
        print(f"\n合计: {grand_cnt} 条, {fmt_dur(int(grand_sec))}, "
              f"约 {fmt_size(grand_sec * MB_PER_SEC)}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "folders":
        cmd_folders()
    elif cmd == "list" and len(sys.argv) > 2:
        cmd_list(int(sys.argv[2]), "--all" in sys.argv)
    elif cmd == "stats" and len(sys.argv) > 2:
        args = sys.argv[2:]
        sample = None
        fids = []
        skip_next = False
        for a in args:
            if skip_next:
                skip_next = False
                continue
            if a == "--sample":
                skip_next = True
                continue
            if a.isdigit():
                fids.append(int(a))
        if "--sample" in args:
            i = args.index("--sample")
            if i + 1 < len(args) and args[i + 1].isdigit():
                sample = int(args[i + 1])
        cmd_stats(fids, sample)
    elif cmd == "pick" and len(sys.argv) > 2:
        fid = int(sys.argv[2])
        args = sys.argv[3:]
        items, out, exclude = "", str(TOOLS / f"sel_{fid}.txt"), ""
        i = 0
        while i < len(args):
            if args[i] in ("-i", "--items") and i + 1 < len(args):
                items = args[i + 1]; i += 2
            elif args[i] in ("-o", "--out") and i + 1 < len(args):
                out = args[i + 1]; i += 2
            elif args[i] in ("-x", "--exclude") and i + 1 < len(args):
                exclude = args[i + 1]; i += 2
            else:
                i += 1
        cmd_pick(fid, items, out, exclude)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
