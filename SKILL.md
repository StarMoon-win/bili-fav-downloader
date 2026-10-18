---
name: bili-download
description: 把 B 站收藏夹 / 视频下载到本地，支持整夹下载和「按序号挑选」（下哪些、跳哪些）。当用户说「下载我 B 站收藏夹」「把这个收藏夹存到本地」「这几条我不要，其他都下」「补充新收藏的视频」「算一下这个夹多大」时使用。自带 yt-dlp/ffmpeg/BBDown 的调用封装与环境自检，含登录态、风控、磁盘写满的实战解法。
agent_created: true
---

# B 站收藏夹下载

## 目录结构（本 skill 自带脚本，不依赖外部安装位置）

```
<skill_dir>/
├── SKILL.md
├── config.json.example   本机配置模板（复制为 config.json 后填写，不进仓库）
├── scripts/
│   ├── _paths.py         共用路径解析
│   ├── check_env.py      环境自检
│   ├── bili_fav.py       查询：列收藏夹 / 列内容 / 算体量 / 按序号挑选
│   ├── bili.py           下载：单条 / 整夹 / 批量清单
│   ├── auto_switch.py    磁盘守护：一个盘满了自动切另一个盘续下
│   └── make_cookies.py   Cookie 字符串 -> cookies.txt
└── bin/                  可选：放 ffmpeg.exe / BBDown.exe
```

依赖查找顺序：`<skill_dir>/bin` → `config.json` 的 `tools_dir` → 环境变量 `BILI_TOOLS_DIR` → 系统 PATH。
cookie 查找顺序：`<skill_dir>/cookies.txt` → `config.json` 的 `cookies` → 环境变量 `BILI_COOKIES`。

> 工具装在别处时，把 `config.json.example` 复制成 `config.json` 填路径即可；
> 工具直接放 `bin/` 里则什么都不用配。

## 第 0 步：环境自检（必做，尤其第一次用）

```bash
cd <skill_dir>/scripts
python check_env.py
```

输出 `环境就绪` 才继续。缺什么按提示装：

| 缺失 | 安装方式 |
|---|---|
| yt-dlp | `python -m pip install --user yt-dlp` |
| ffmpeg | `python -m pip install --user imageio-ffmpeg`，把包内 `binaries/ffmpeg-win-x86_64-*.exe` 复制为 `bin/ffmpeg.exe` |
| BBDown | https://github.com/nilaoda/BBDown/releases 下 win-x64 版解压到 `bin/`（仅失败补救用，可选） |
| cookies.txt | 见下方「登录态」章节 |

## 标准工作流

### 1. 确定收藏夹

```bash
python bili_fav.py folders        # 列出所有收藏夹，拿 fid
```

用户给链接 `https://space.bilibili.com/<UID>/favlist?fid=<fid>` 时直接取 `fid`。

### 2. 先算体量（不能跳）

```bash
python bili_fav.py stats <fid>              # 全量精确
python bili_fav.py stats <fid> --sample 100 # 上千条的大夹用采样
```

**条数完全不能代表体积**：48 条可能是 848GB（几小时直播回放），226 条可能是 2TB（网课）。
同时 `df -h /c /d` 看剩余空间，需求留 10% 余量再决定下不下、下到哪个盘。

### 3. 列内容让用户挑

```bash
python bili_fav.py list <fid> --all
```

输出 `序号. 标题 时长 UP主 BV号`，序号按收藏时间倒序（最新在前）。把清单交给用户，
问清楚下哪些、跳哪些。用户可能说「1-20 都要，第 5 条不要」「只要 3 分钟以上的」。

### 4. 按选择生成清单

```bash
python bili_fav.py pick <fid> -i "1,3,5-10" -x "5" -o sel.txt   # 选 1,3,5-10 再排除 5
python bili_fav.py pick <fid> -i "1-" -o sel.txt                # 全选
```

表达式：`1,3,5-10,20-`（逗号分隔，`a-b` 区间，末尾留空表示到最后）。`-x` 排除。
`sel.txt` 是 URL 列表，供下一步。

### 5. 下载

```bash
python bili.py @sel.txt --hq 4k-hevc -o "C:/Users/<用户名>/Downloads/bili/<收藏夹名>"
```

| `--hq` | 说明 | 相对体积 |
|---|---|---:|
| `4k-av1` | 4K + AV1，体积最优，但老设备可能播不了 | 1.0 |
| `4k-hevc` | 4K + HEVC，兼容性最好（**默认选这个**） | 1.6 |
| `4k` | 4K 最高码率（AVC），最费空间 | 2.5 |
| `1080` | 1080P | 0.6 |

其他：`-o DIR` 输出目录（默认 `~/Downloads/bili`）、`--no-cookie` 不用登录态、`-q 1080` 限画质。
输出结构：`<目录>/<UP主名>/<标题> [BV号].mp4`。

### 6. 核对并汇报

```bash
python -c "
import re
from pathlib import Path
want={u.strip().rstrip('/').split('/')[-1] for u in open('sel.txt',encoding='utf-8') if u.strip()}
got=set()
for f in Path(r'<输出目录>').rglob('*.mp4'):
    m=re.search(r'\[(BV[0-9A-Za-z]+)', f.name)
    if m: got.add(re.sub(r'_p\d+$','',m.group(1)))
print('目标',len(want),'已下',len(got),'缺失',sorted(want-got))
"
```

汇报：成功条数 / 失败条数 / 总占用 / 存放路径 / 失败原因。

## 失败处理（重要）

批量下载总有零星失败，**不要直接当失效**：

1. **查状态**：`https://api.bilibili.com/x/web-interface/view?bvid=<BV>`
   - `code=0` → 视频还在，是解析问题，走第 2 步
   - `code=62002` 稿件不可见 / `62012` 状态异常 → 真没了，放弃
2. **换 BBDown 补**（yt-dlp 报 `Unable to extract initial state` 时几乎必成）：

```bash
cd <skill_dir>/bin          # 或 BBDown.exe 所在目录
CK=$(python -c "
ck=[]
for line in open(r'<cookies.txt 路径>',encoding='utf-8').read().splitlines():
    if line.startswith('#') or not line.strip(): continue
    p=line.split('\t')
    if len(p)>=7 and p[5] in ('SESSDATA','bili_jct','DedeUserID','buvid3'): ck.append(f'{p[5]}={p[6]}')
print('; '.join(ck))
")
./BBDown.exe "https://www.bilibili.com/video/<BV>" -c "$CK" \
  -q "4K 超清" -e "hevc,av01,avc" -F "<videoTitle> [<BV>]" \
  --work-dir "<输出目录>\_补漏" --skip-cover --skip-subtitle
```

BBDown 不按 UP 主建目录，统一放 `_补漏` 子目录，`-F` 保留 BV 号便于核对。

## 磁盘写满：自动切盘

`auto_switch.py` 是守护脚本，每 20s 检查一个盘，低于阈值时终止下载并切到另一个盘续下：

```bash
python auto_switch.py
```

改脚本顶部 `D_DIR` / `C_DIR` / `THRESHOLD_GB` / `URLS` 四个变量适配场景。
日志写 `switch.log`。实测在 2.99GB 时精准触发，已下文件不受影响、不重复。

## 登录态

判断是否有效：调 `https://api.bilibili.com/x/web-interface/nav` 看 `isLogin`。

**获取方式（唯一可行）**：浏览器 F12 → Network → 任一 bilibili 请求 → 复制 `Cookie:` 整行
→ 填进 `make_cookies.py` 的 `RAW` 变量 → 运行，生成 `cookies.txt` 放到 skill 根目录。

**以下三条已验证走不通，别浪费时间：**
1. `yt-dlp --cookies-from-browser edge/chrome` → `Failed to decrypt with DPAPI`
   （Chrome/Edge 127+ 的 App-Bound Encryption，密钥绑死浏览器进程）
2. `BBDown.exe login` 扫码 → 日志说登录成功，但 `BBDown.data` 里只有 ticket 没有 SESSDATA（B站改版了接口）
3. 浏览器扩展导出 cookie → 比 F12 更麻烦

## 踩坑清单

1. **系统代理会让 yt-dlp 全盘失败**：`Unable to connect to proxy` / `SSL: UNEXPECTED_EOF`。
   yt-dlp 读 Windows 注册表代理，清环境变量无效，**必须 `--proxy ""`**（bili.py 已内置）。
2. **`fav/resource/list` 会 HTTP 412 风控**：翻页太密触发，可能持续数小时。
   已加 0.35s 间隔 + 指数退避 + 1 小时缓存；彻底封时改用 `fav/resource/ids` 拿 bvid 列表，
   用 `bili.py @file` 批量下载绕过。
3. **`bili.py -l` 标题显示 NA**：flat 模式不返回标题，看内容用 `bili_fav.py list`。
4. **条数 ≠ 体积**：必须 `stats`。它用固定 0.64MB/s 系数，码率分布不均会偏；要准数就抽样测 `tbr`。
5. **多P视频**：一个 BV 产生多个文件（`BVxxx_p1.mp4`），归档匹配用
   `d == bv or d.startswith(bv + "_")`。
6. **增量下载**：`--download-archive` 记在 `<输出目录>/.downloaded.txt`，重跑只补新增。
   两个目录合并时要手动合并这个文件。
7. **AV1 兼容性**：老手机/电视/投影播不了；只在电脑看选 `4k-av1` 省空间，多设备选 `4k-hevc`。
8. **`-S res:2160,vcodec:av01` 只保证"优先"**：无 AV1 版本时仍选 AVC 4K，码率可能飙到 12-15Mbps。
9. **Git Bash 里跑 robocopy 必须加 `MSYS_NO_PATHCONV=1`**，否则 `/E` 被转成 `E:/` 报"无效参数"。
10. **删大文件后 `df` 会短暂读到旧值**，等 1-2 分钟才是真实空间。
