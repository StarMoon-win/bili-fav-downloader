# -*- coding: utf-8 -*-
"""
_paths.py — 共用路径解析

依赖查找顺序：
  1. <skill>/bin、<skill>/scripts        （自带，优先）
  2. config.json 里的 tools_dir          （本地配置，不进仓库）
  3. 环境变量 BILI_TOOLS_DIR
  4. 系统 PATH

cookies.txt 查找顺序：
  1. 环境变量 BILI_COOKIES
  2. config.json 里的 cookies
  3. <skill>/cookies.txt
  4. <skill>/scripts/cookies.txt
"""
import json
import os
import shutil
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPTS.parent
CONFIG_FILE = SKILL_ROOT / "config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


CFG = load_config()


def search_dirs() -> list[Path]:
    dirs = [SKILL_ROOT / "bin", SCRIPTS]
    if CFG.get("tools_dir"):
        dirs.append(Path(CFG["tools_dir"]))
    if os.environ.get("BILI_TOOLS_DIR"):
        dirs.append(Path(os.environ["BILI_TOOLS_DIR"]))
    return dirs


def find_exe(*rel_paths: str) -> Path | None:
    """在候选目录里找可执行文件，最后回退到 PATH"""
    for d in search_dirs():
        for rp in rel_paths:
            p = d / rp
            if p.exists():
                return p
    name = Path(rel_paths[-1]).name
    hit = shutil.which(name)
    return Path(hit) if hit else None


def cookie_candidates() -> list[Path]:
    cands = []
    if os.environ.get("BILI_COOKIES"):
        cands.append(Path(os.environ["BILI_COOKIES"]))
    if CFG.get("cookies"):
        cands.append(Path(CFG["cookies"]))
    cands += [SKILL_ROOT / "cookies.txt", SCRIPTS / "cookies.txt"]
    return cands


def cookie_file() -> Path | None:
    return next((p for p in cookie_candidates() if p.exists()), None)


def default_out() -> Path:
    return Path(CFG.get("out_dir") or (Path.home() / "Downloads" / "bili"))
