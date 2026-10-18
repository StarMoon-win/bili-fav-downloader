# bili-download

把 B 站收藏夹批量下载到本地，**支持按序号挑选**（哪些下、哪些跳过）。

面向「收藏夹里攒了几百上千个视频，想挑着存下来」的场景。自带环境自检、登录态处理、风控绕过和磁盘写满自动切盘。

## 特性

- **按序号挑选**：`1,3,5-10` 选区间，`-x` 排除不要的，不用一个个复制链接
- **先算体量再下载**：条数完全不能代表体积（48 条可能是 848GB），下之前先估
- **4K 画质可选**：`4k-av1`（体积最优）/ `4k-hevc`（兼容性最好）/ `4k` / `1080`
- **增量下载**：归档记录，重跑只补新增，不重复下
- **失败补救**：yt-dlp 解析不了的视频自动换 BBDown 再试
- **磁盘守护**：一个盘快满了自动切到另一个盘续下
- **环境自检**：缺什么依赖直接告诉你装什么

## 依赖

| 组件 | 必需 | 说明 |
|---|---|---|
| Python 3.9+ | ✅ | |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | ✅ | `pip install --user yt-dlp` |
| ffmpeg | ✅ | B 站音视频分离，必须合并 |
| [BBDown](https://github.com/nilaoda/BBDown) | 可选 | 仅失败补救用 |

## 快速开始

```bash
git clone https://github.com/<你的用户名>/bili-download.git
cd bili-download/scripts
python check_env.py
```

`check_env.py` 会检查所有依赖，缺什么给什么安装命令。

### 准备登录态

私密收藏夹、1080P 高码率、4K 都需要登录：

1. 浏览器打开 bilibili.com 并登录
2. `F12` → **Network** → 刷新页面 → 点任意 bilibili 请求
3. 在 **Request Headers** 里找到 `Cookie:` 整行，完整复制
4. 生成 cookie 文件：

```bash
python make_cookies.py -s "把复制的整行粘在这里" -o ../cookies.txt
```

> **`cookies.txt` 等同你的登录凭证**，已加入 `.gitignore`，切勿提交或分享。

### 使用

```bash
# 1. 列出所有收藏夹，拿到 fid
python bili_fav.py folders

# 2. 算体量（务必先算）
python bili_fav.py stats <fid>
python bili_fav.py stats <fid> --sample 100    # 上千条的大夹用采样

# 3. 看内容，记下序号
python bili_fav.py list <fid> --all

# 4. 按序号挑选，生成下载清单
python bili_fav.py pick <fid> -i "1,3,5-10" -x "5" -o sel.txt

# 5. 下载
python bili.py @sel.txt --hq 4k-hevc -o "D:/downloads/我的收藏夹"
```

收藏夹链接形如 `https://space.bilibili.com/<UID>/favlist?fid=<收藏夹ID>`，其中 `fid` 就是第 1 步要的数字。

### 画质档位

| `--hq` | 说明 | 相对体积 |
|---|---|---:|
| `4k-av1` | 4K + AV1，体积最优，老设备可能播不了 | 1.0 |
| `4k-hevc` | 4K + HEVC，兼容性最好 | 1.6 |
| `4k` | 4K 最高码率（AVC），最费空间 | 2.5 |
| `1080` | 1080P | 0.6 |

同一视频实测：1080P 64MB / 4K-AV1 93MB / 4K-HEVC 172MB / 4K-AVC 230MB。

## 配置

工具装在别处时，把 `config.json.example` 复制为 `config.json`：

```json
{
  "tools_dir": "D:\\tools",
  "cookies": "D:\\tools\\cookies.txt",
  "out_dir": "D:\\downloads"
}
```

也可以直接用环境变量 `BILI_TOOLS_DIR` / `BILI_COOKIES`。工具放 `bin/` 里则无需任何配置。

## 磁盘写满自动切盘

```bash
python auto_switch.py --src "D:/downloads/收藏夹A" --dst "C:/downloads/收藏夹A" --urls urls.txt
```

监控 `--src` 所在磁盘，剩余空间低于 3GB 时自动终止下载、读取归档记录、切到 `--dst` 续下。

## 已知限制

- 已失效的视频（B 站返回 62002 / 62012）无法下载
- B 站 `fav/resource/list` 接口翻页过密会触发 412 风控，脚本已加退避，彻底封时需等待
- Chrome/Edge 127+ 的 cookie 无法被外部程序读取（App-Bound Encryption），只能用 F12 复制
- AV1 编码在老旧设备上可能无法播放

## 免责声明

仅供**个人备份自己收藏的视频**使用。请遵守 B 站用户协议和版权法规，不要用于二次分发或商业用途。下载内容的版权归原作者所有。

## License

MIT
