#!/usr/bin/env python3
"""
Update and build Breeze-merged custom icon themes from upstream repositories.
Keeps Breeze/Breeze-Dark monochrome icons and merges color apps & places icons
from each upstream theme.
"""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ICONS_DIR = Path("/home/elav/.local/share/icons")
STATE_FILE = ICONS_DIR / ".theme_sources.json"
BREEZE_LIGHT = Path("/usr/share/icons/breeze")
BREEZE_DARK = Path("/usr/share/icons/breeze-dark")

BREEZE_COLOR_DIRS = [
    "apps/32", "apps/48", "apps/64",
    "places/32", "places/48", "places/64", "places/96",
]

# Mapping of upstream repo -> target theme config(s)
THEMES = [
    {
        "repo": "BigSur-icon-theme",
        "url": "https://github.com/yeyushengfan258/BigSur-icon-theme",
        "theme_name": "BrisaSur",
        "layout": "src_links",
        "breeze_base": "dark",
    },
    {
        "repo": "Colloid-icon-theme",
        "url": "https://github.com/vinceliuice/Colloid-icon-theme",
        "theme_name": "Brisolloid",
        "layout": "src_links",
        "breeze_base": "dark",
    },
    {
        "repo": "Diagonal-icon-theme",
        "url": "https://github.com/tamascsabi/Diagonal-icon-theme",
        "theme_name": "Brisagonal",
        "layout": "diagonal",
        "breeze_base": "dark",
    },
    {
        "repo": "Flatery",
        "url": "https://github.com/cbrnix/Flatery",
        "theme_name": "Brisatery",
        "layout": "flatery",
        "breeze_base": "dark",
    },
    {
        "repo": "Fluent-icon-theme",
        "url": "https://github.com/vinceliuice/Fluent-icon-theme",
        "theme_name": "Brisuent",
        "layout": "src_links",
        "breeze_base": "dark",
    },
    {
        "repo": "Hatter",
        "url": "https://github.com/Mibea/Hatter",
        "theme_name": "Brisatter",
        "layout": "hatter",
        "breeze_base": "dark",
    },
    {
        "repo": "McMojave-circle",
        "url": "https://github.com/vinceliuice/McMojave-circle",
        "theme_name": "Brisajave",
        "layout": "src_links",
        "breeze_base": "dark",
    },
    {
        "repo": "Mkos-Big-Sur",
        "url": "https://github.com/zayronxio/Mkos-Big-Sur",
        "theme_name": "Brisakos",
        "layout": "mkos",
        "breeze_base": "dark",
    },
    {
        "repo": "Reversal-icon-theme",
        "url": "https://github.com/yeyushengfan258/Reversal-icon-theme",
        "theme_name": "Brisersal",
        "layout": "src_links",
        "breeze_base": "dark",
    },
    {
        "repo": "Tela-icon-theme",
        "url": "https://github.com/vinceliuice/Tela-icon-theme",
        "theme_name": "Brisela",
        "layout": "src_links",
        "breeze_base": "dark",
    },
    {
        "repo": "Tela-circle-icon-theme",
        "url": "https://github.com/vinceliuice/Tela-circle-icon-theme",
        "theme_name": "Brisela-Circle",
        "layout": "src_links",
        "breeze_base": "dark",
    },
    {
        "repo": "We10X-icon-theme",
        "url": "https://github.com/yeyushengfan258/We10X-icon-theme",
        "theme_name": "Brisa10X",
        "layout": "src_links",
        "breeze_base": "dark",
    },
    {
        "repo": "WhiteSur-icon-theme",
        "url": "https://github.com/vinceliuice/WhiteSur-icon-theme",
        "theme_name": "BrisaWhiteSur",
        "layout": "src_links",
        "breeze_base": "dark",
    },
    {
        "repo": "Zafiro-icons",
        "url": "https://github.com/zayronxio/Zafiro-icons",
        "theme_name": "Brisafiro",
        "layout": "zafiro",
        "breeze_base": "dark",
    },
    {
        "repo": "papirus-icon-theme",
        "url": "https://github.com/PapirusDevelopmentTeam/papirus-icon-theme",
        "theme_name": "Brisus",
        "layout": "papirus",
        "breeze_base": "light",
    },
    {
        "repo": "ocean-design",
        "url": "https://invent.kde.org/abetts/ocean-design",
        "theme_name": "Oceano",
        "layout": "ocean",
        "breeze_base": "dark",
    },
]


def get_remote_head(url: str):
    if "github.com/" in url:
        owner, repo = url.rstrip("/").split("github.com/")[1].split("/")[:2]
        req = urllib.request.Request(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers={"User-Agent": "CustomIcons-Updater"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            branch = json.loads(resp.read().decode()).get("default_branch", "main")
        req2 = urllib.request.Request(
            f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}",
            headers={"User-Agent": "CustomIcons-Updater"},
        )
        with urllib.request.urlopen(req2, timeout=20) as resp:
            sha = json.loads(resp.read().decode()).get("sha", "")
        zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
        return branch, sha, zip_url
    if "invent.kde.org/" in url:
        path = url.rstrip("/").split("invent.kde.org/")[1]
        repo = path.split("/")[-1]
        encoded = urllib.parse.quote(path, safe="")
        req = urllib.request.Request(
            f"https://invent.kde.org/api/v4/projects/{encoded}",
            headers={"User-Agent": "CustomIcons-Updater"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            branch = json.loads(resp.read().decode()).get("default_branch", "master")
        req2 = urllib.request.Request(
            f"https://invent.kde.org/api/v4/projects/{encoded}/repository/commits/{branch}",
            headers={"User-Agent": "CustomIcons-Updater"},
        )
        with urllib.request.urlopen(req2, timeout=20) as resp:
            sha = json.loads(resp.read().decode()).get("id", "")
        zip_url = f"https://invent.kde.org/{path}/-/archive/{branch}/{repo}-{branch}.zip"
        return branch, sha, zip_url
    raise ValueError(f"Unsupported URL: {url}")


def copy_icon_files(src_dir: Path, dst_dir: Path, skip_symbolic: bool = True):
    if not src_dir.is_dir():
        return
    dst_dir.mkdir(parents=True, exist_ok=True)
    for item in src_dir.iterdir():
        if skip_symbolic and "-symbolic" in item.name:
            continue
        dst_item = dst_dir / item.name
        if item.is_symlink():
            target = item.readlink()
            if ".." in str(target):
                resolved = item.resolve()
                if resolved.exists() and resolved.is_file():
                    shutil.copy2(resolved, dst_item)
            else:
                if dst_item.exists() or dst_item.is_symlink():
                    dst_item.unlink()
                os.symlink(target, dst_item)
        elif item.is_file() and item.suffix.lower() in (".svg", ".png"):
            shutil.copy2(item, dst_item)


def init_breeze_theme(theme_dir: Path, theme_name: str, breeze_base: str, remove_color_dirs: bool = True):
    base_path = BREEZE_DARK if breeze_base == "dark" else BREEZE_LIGHT
    inherits = "breeze-dark,breeze,hicolor" if breeze_base == "dark" else "breeze,hicolor"

    if theme_dir.exists() or theme_dir.is_symlink():
        shutil.rmtree(theme_dir)
    subprocess.run(["cp", "-a", str(base_path), str(theme_dir)], check=True)
    for cache_file in ("icon-theme.cache", "breeze-icons.rcc"):
        (theme_dir / cache_file).unlink(missing_ok=True)

    if remove_color_dirs:
        for d in BREEZE_COLOR_DIRS:
            t = theme_dir / d
            if t.exists():
                shutil.rmtree(t)
    return inherits


def update_index_theme(theme_dir: Path, theme_name: str, inherits: str, extra_dirs: list, extra_sections: str, removed_dirs: list):
    idx = theme_dir / "index.theme"
    lines = idx.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        if line.startswith("Name="):
            out.append(f"Name={theme_name}")
        elif line.startswith("Name["):
            continue
        elif line.startswith("Comment="):
            out.append(f"Comment={theme_name} (Breeze monochrome + custom folders & apps)")
        elif line.startswith("Comment["):
            continue
        elif line.startswith("Inherits="):
            out.append(f"Inherits={inherits}")
        elif line.startswith("Directories="):
            existing = [x for x in line.split("=", 1)[1].split(",") if x and x not in removed_dirs]
            for d in extra_dirs:
                if d not in existing:
                    existing.append(d)
            out.append("Directories=" + ",".join(existing))
        else:
            out.append(line)
    idx.write_text("\n".join(out) + "\n" + extra_sections, encoding="utf-8")


def find_repo_root(extracted_repo_dir: Path) -> Path:
    dirs = [d for d in extracted_repo_dir.iterdir() if d.is_dir()]
    return dirs[0] if len(dirs) == 1 else extracted_repo_dir


def build_from_extracted(cfg: dict, extracted_repo_dir: Path):
    root = find_repo_root(extracted_repo_dir)
    layout = cfg["layout"]
    name = cfg["theme_name"]
    theme_dir = ICONS_DIR / name

    if layout == "papirus":
        papirus_root = root / "Papirus"
        sizes_cats = [
            ("32x32", ["apps", "places"]), ("42x42", ["apps"]),
            ("48x48", ["apps", "places"]), ("64x64", ["apps", "places"]),
            ("84x84", ["apps"]), ("96x96", ["apps", "places"]),
            ("128x128", ["apps", "places"]),
        ]
        for sz, cats in sizes_cats:
            for cat in cats:
                copy_icon_files(papirus_root / sz / cat, theme_dir / sz / cat)
        for t in ("Brisus", "Brisus-Dark", "Brisus-Light"):
            if (ICONS_DIR / t).is_dir():
                subprocess.run(["gtk-update-icon-cache", "-f", "-t", str(ICONS_DIR / t)], check=False)
        return

    if layout == "ocean":
        ocean_root = root / "Icon Pack" / "Ocean"
        for d in ("places/32", "places/32@2x", "places/32@3x", "places/48", "places/64", "places/96",
                  "apps/32", "apps/32@2x", "apps/32@3x", "apps/48", "apps/64"):
            copy_icon_files(ocean_root / d, theme_dir / d)
        subprocess.run(["gtk-update-icon-cache", "-f", "-t", str(theme_dir)], check=False)
        return

    inherits = init_breeze_theme(theme_dir, name, cfg["breeze_base"], remove_color_dirs=True)
    extra_dirs = []
    extra_sections = []

    def add_dir(rel_path: str, context: str, size: int, scalable: bool = False):
        if rel_path not in extra_dirs:
            extra_dirs.append(rel_path)
            if scalable:
                extra_sections.append(f"\n[{rel_path}]\nContext={context}\nSize={size}\nMinSize=16\nMaxSize=256\nType=Scalable\n")
            else:
                extra_sections.append(f"\n[{rel_path}]\nContext={context}\nSize={size}\nType=Fixed\n")

    if layout == "src_links":
        for cat, ctx in (("apps", "Applications"), ("places", "Places")):
            for sub in ("scalable", "32", "48", "64"):
                for base in ("src", "links"):
                    p1 = root / base / cat / sub
                    p2 = root / base / sub / cat
                    if p1.is_dir() or p2.is_dir():
                        dst = theme_dir / f"{cat}/{sub}"
                        copy_icon_files(p1, dst)
                        copy_icon_files(p2, dst)
                        sz = 48 if sub == "scalable" else int(sub)
                        add_dir(f"{cat}/{sub}", ctx, sz, scalable=(sub == "scalable"))
    elif layout == "hatter":
        for cat, ctx in (("apps", "Applications"), ("places", "Places")):
            copy_icon_files(root / "Hatter" / "scalable" / cat, theme_dir / f"scalable/{cat}")
            add_dir(f"scalable/{cat}", ctx, 64, scalable=True)
    elif layout == "flatery":
        for cat, ctx in (("apps", "Applications"), ("places", "Places")):
            for sz in ("32", "48", "64"):
                copy_icon_files(root / "Flatery" / cat / sz, theme_dir / f"{cat}/{sz}")
                add_dir(f"{cat}/{sz}", ctx, int(sz), scalable=(sz == "64"))
    elif layout == "zafiro":
        for cat, ctx in (("apps", "Applications"), ("places", "Places")):
            for sub in ("48", "scalable"):
                src = root / "Dark" / cat / sub
                if src.is_dir():
                    copy_icon_files(src, theme_dir / f"{cat}/{sub}")
                    sz = 48 if sub == "scalable" else int(sub)
                    add_dir(f"{cat}/{sub}", ctx, sz, scalable=(sub == "scalable"))
    elif layout == "mkos":
        for sz_dir, sz, cat, ctx in (
            ("128x128", 128, "apps", "Applications"),
            ("64x64", 64, "apps", "Applications"),
            ("128x128", 128, "places", "Places"),
        ):
            src = root / sz_dir / cat
            if src.is_dir():
                copy_icon_files(src, theme_dir / f"{sz_dir}/{cat}")
                add_dir(f"{sz_dir}/{cat}", ctx, sz, scalable=(sz == 128))
    elif layout == "diagonal":
        for cat, ctx in (("apps", "Applications"), ("places", "Places")):
            for sz in ("32", "48", "64"):
                src = root / "base" / cat / sz
                if src.is_dir():
                    copy_icon_files(src, theme_dir / f"{cat}/{sz}")
                    add_dir(f"{cat}/{sz}", ctx, int(sz), scalable=False)
            src_sc = root / "base" / "scalable" / cat
            if src_sc.is_dir():
                copy_icon_files(src_sc, theme_dir / f"scalable/{cat}")
                add_dir(f"scalable/{cat}", ctx, 64, scalable=True)

    update_index_theme(theme_dir, name, inherits, extra_dirs, "".join(extra_sections), BREEZE_COLOR_DIRS)
    subprocess.run(["gtk-update-icon-cache", "-f", "-t", str(theme_dir)], check=False)


def main():
    parser = argparse.ArgumentParser(description="Build or update custom Breeze-merged icon themes.")
    parser.add_argument("--from-dir", type=Path, help="Build new themes from an existing extracted directory")
    parser.add_argument("--metadata", type=Path, help="Optional metadata.json with pre-fetched SHAs")
    parser.add_argument("--force", action="store_true", help="Force re-download and update all repos")
    args = parser.parse_args()

    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}

    if args.from_dir:
        meta_by_repo = {}
        if args.metadata and args.metadata.exists():
            for m in json.loads(args.metadata.read_text()):
                meta_by_repo[m["repo"]] = m
        for cfg in THEMES:
            repo = cfg["repo"]
            if cfg["layout"] in ("papirus", "ocean"):
                if repo in meta_by_repo:
                    state[repo] = {"url": cfg["url"], "sha": meta_by_repo[repo]["sha"], "branch": meta_by_repo[repo]["branch"]}
                continue
            ext_dir = args.from_dir / repo
            if ext_dir.is_dir():
                print(f"Building {cfg['theme_name']} from {repo}...")
                build_from_extracted(cfg, ext_dir)
                if repo in meta_by_repo:
                    state[repo] = {"url": cfg["url"], "sha": meta_by_repo[repo]["sha"], "branch": meta_by_repo[repo]["branch"]}
        STATE_FILE.write_text(json.dumps(state, indent=2))
        print("All themes built and state saved.")
        return

    # Online update check mode
    print("Checking for upstream icon updates...")
    to_update = []
    for cfg in THEMES:
        repo = cfg["repo"]
        try:
            branch, sha, zip_url = get_remote_head(cfg["url"])
            old_sha = state.get(repo, {}).get("sha", "")
            if args.force or not old_sha or (sha and sha != old_sha):
                print(f"  [UPDATE] {repo} -> {cfg['theme_name']} ({old_sha[:7] or 'none'} -> {sha[:7]})")
                to_update.append((cfg, branch, sha, zip_url))
            else:
                print(f"  [OK]     {repo} ({sha[:7]})")
        except Exception as e:
            print(f"  [WARN]   {repo}: could not check ({e})")

    if not to_update:
        print("Everything is already up to date.")
        return

    with tempfile.TemporaryDirectory(prefix="customicons_upd_") as tmp:
        tmp_path = Path(tmp)
        def process(item):
            cfg, branch, sha, zip_url = item
            repo = cfg["repo"]
            zpath = tmp_path / f"{repo}.zip"
            edir = tmp_path / repo
            edir.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(zip_url, headers={"User-Agent": "CustomIcons-Updater"})
            with urllib.request.urlopen(req, timeout=180) as resp, open(zpath, "wb") as f:
                shutil.copyfileobj(resp, f)
            with zipfile.ZipFile(zpath, "r") as zf:
                zf.extractall(edir)
            build_from_extracted(cfg, edir)
            return repo, branch, sha, cfg["url"]

        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = [ex.submit(process, it) for it in to_update]
            for fut in as_completed(futs):
                repo, branch, sha, url = fut.result()
                state[repo] = {"url": url, "sha": sha, "branch": branch}
                print(f"Updated {repo} ({sha[:7]})")

    STATE_FILE.write_text(json.dumps(state, indent=2))
    print("Update complete!")


if __name__ == "__main__":
    main()
