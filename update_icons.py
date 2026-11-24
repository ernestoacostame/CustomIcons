#!/usr/bin/env python3
"""
Interactive & CLI manager for Breeze-merged custom icon themes.
- Checks and applies upstream updates for all tracked themes.
- Lets the user add new icon themes from GitHub / GitLab URLs interactively.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ICONS_DIR = Path("/home/elav/.local/share/icons")
STATE_FILE = ICONS_DIR / ".theme_sources.json"
BREEZE_LIGHT = Path("/usr/share/icons/breeze")
BREEZE_DARK = Path("/usr/share/icons/breeze-dark")

BREEZE_COLOR_DIRS = [
    "apps/16", "apps/16@2x", "apps/16@3x",
    "apps/22", "apps/22@2x", "apps/22@3x",
    "apps/24", "apps/24@2x", "apps/24@3x",
    "apps/32", "apps/48", "apps/64",
    "places/32", "places/48", "places/64", "places/96",
]

BUILTIN_THEMES = [
    {"repo": "BigSur-icon-theme", "url": "https://github.com/yeyushengfan258/BigSur-icon-theme", "theme_name": "BrisaSur", "layout": "src_links", "breeze_base": "dark"},
    {"repo": "Colloid-icon-theme", "url": "https://github.com/vinceliuice/Colloid-icon-theme", "theme_name": "Brisolloid", "layout": "src_links", "breeze_base": "dark"},
    {"repo": "Diagonal-icon-theme", "url": "https://github.com/tamascsabi/Diagonal-icon-theme", "theme_name": "Brisagonal", "layout": "diagonal", "breeze_base": "dark"},
    {"repo": "Flatery", "url": "https://github.com/cbrnix/Flatery", "theme_name": "Brisatery", "layout": "flatery", "breeze_base": "dark"},
    {"repo": "Fluent-icon-theme", "url": "https://github.com/vinceliuice/Fluent-icon-theme", "theme_name": "Brisuent", "layout": "src_links", "breeze_base": "dark"},
    {"repo": "Hatter", "url": "https://github.com/Mibea/Hatter", "theme_name": "Brisatter", "layout": "hatter", "breeze_base": "dark"},
    {"repo": "McMojave-circle", "url": "https://github.com/vinceliuice/McMojave-circle", "theme_name": "Brisajave", "layout": "src_links", "breeze_base": "dark"},
    {"repo": "Mkos-Big-Sur", "url": "https://github.com/zayronxio/Mkos-Big-Sur", "theme_name": "Brisakos", "layout": "mkos", "breeze_base": "dark"},
    {"repo": "Reversal-icon-theme", "url": "https://github.com/yeyushengfan258/Reversal-icon-theme", "theme_name": "Brisersal", "layout": "src_links", "breeze_base": "dark"},
    {"repo": "Tela-icon-theme", "url": "https://github.com/vinceliuice/Tela-icon-theme", "theme_name": "Brisela", "layout": "src_links", "breeze_base": "dark"},
    {"repo": "Tela-circle-icon-theme", "url": "https://github.com/vinceliuice/Tela-circle-icon-theme", "theme_name": "Brisela-Circle", "layout": "src_links", "breeze_base": "dark"},
    {"repo": "We10X-icon-theme", "url": "https://github.com/yeyushengfan258/We10X-icon-theme", "theme_name": "Brisa10X", "layout": "src_links", "breeze_base": "dark"},
    {"repo": "WhiteSur-icon-theme", "url": "https://github.com/vinceliuice/WhiteSur-icon-theme", "theme_name": "BrisaWhiteSur", "layout": "src_links", "breeze_base": "dark"},
    {"repo": "Zafiro-icons", "url": "https://github.com/zayronxio/Zafiro-icons", "theme_name": "Brisafiro", "layout": "zafiro", "breeze_base": "dark"},
    {"repo": "papirus-icon-theme", "url": "https://github.com/PapirusDevelopmentTeam/papirus-icon-theme", "theme_name": "Brisus", "layout": "papirus", "breeze_base": "light"},
    {"repo": "ocean-design", "url": "https://invent.kde.org/abetts/ocean-design", "theme_name": "Oceano", "layout": "ocean", "breeze_base": "dark"},
]


def load_state() -> dict:
    return json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def get_all_themes(state: dict) -> list:
    themes = list(BUILTIN_THEMES)
    known_repos = {t["repo"] for t in themes}
    for repo, info in state.items():
        if repo not in known_repos and info.get("custom"):
            themes.append({
                "repo": repo,
                "url": info["url"],
                "theme_name": info["theme_name"],
                "layout": info.get("layout", "auto"),
                "breeze_base": info.get("breeze_base", "dark"),
                "subpath": info.get("subpath", ""),
            })
    return themes


def get_remote_head(url: str):
    clean_url = url.rstrip("/")
    if clean_url.endswith(".git"):
        clean_url = clean_url[:-4]
    res = subprocess.run(
        ["git", "ls-remote", "--symref", clean_url, "HEAD"],
        capture_output=True, text=True, check=True, timeout=25,
    )
    branch = "main"
    sha = ""
    for line in res.stdout.splitlines():
        if line.startswith("ref: refs/heads/"):
            branch = line.split("ref: refs/heads/", 1)[1].split()[0]
        elif "\tHEAD" in line:
            sha = line.split()[0]

    if "github.com/" in clean_url:
        owner, repo = clean_url.split("github.com/")[1].split("/")[:2]
        zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
        return branch, sha, zip_url
    if "invent.kde.org/" in clean_url or "gitlab.com/" in clean_url:
        host = "invent.kde.org" if "invent.kde.org/" in clean_url else "gitlab.com"
        path = clean_url.split(f"{host}/")[1]
        repo = path.split("/")[-1]
        zip_url = f"https://{host}/{path}/-/archive/{branch}/{repo}-{branch}.zip"
        return branch, sha, zip_url
    raise ValueError(f"URL no soportada (usa GitHub, GitLab o invent.kde.org): {url}")


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
                    if dst_item.exists() or dst_item.is_symlink():
                        dst_item.unlink()
                    shutil.copy2(resolved, dst_item)
            else:
                if dst_item.exists() or dst_item.is_symlink():
                    dst_item.unlink()
                os.symlink(target, dst_item)
        elif item.is_file() and item.suffix.lower() in (".svg", ".png"):
            if dst_item.exists() or dst_item.is_symlink():
                dst_item.unlink()
            shutil.copy2(item, dst_item)


def init_breeze_theme(theme_dir: Path, breeze_base: str, remove_color_dirs: bool = True) -> str:
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
            if t.is_symlink():
                t.unlink()
            elif t.exists():
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
        elif line.startswith("Directories=") or line.startswith("ScaledDirectories="):
            key, val = line.split("=", 1)
            existing = [x for x in val.split(",") if x and x not in removed_dirs]
            if key == "Directories":
                for d in extra_dirs:
                    if d not in existing:
                        existing.append(d)
            out.append(f"{key}=" + ",".join(existing))
        else:
            out.append(line)
    idx.write_text("\n".join(out) + "\n" + extra_sections, encoding="utf-8")


def find_repo_root(extracted_repo_dir: Path) -> Path:
    dirs = [d for d in extracted_repo_dir.iterdir() if d.is_dir()]
    return dirs[0] if len(dirs) == 1 else extracted_repo_dir


def add_dir_entry(extra_dirs: list, extra_sections: list, rel_path: str, context: str, size: int, scalable: bool = False):
    if rel_path not in extra_dirs:
        extra_dirs.append(rel_path)
        if scalable:
            extra_sections.append(f"\n[{rel_path}]\nContext={context}\nSize={size}\nMinSize=16\nMaxSize=256\nType=Scalable\n")
        else:
            extra_sections.append(f"\n[{rel_path}]\nContext={context}\nSize={size}\nType=Fixed\n")


def copy_auto_layout(src_root: Path, theme_dir: Path, extra_dirs: list, extra_sections: list):
    """Auto-detect and copy color apps & places directories from any standard XDG icon theme."""
    # 1. src/ + links/ layout
    if (src_root / "src").is_dir():
        for cat, ctx in (("apps", "Applications"), ("places", "Places")):
            for sub in ("scalable", "32", "48", "64", "96", "128"):
                for base in ("src", "links"):
                    p1 = src_root / base / cat / sub
                    p2 = src_root / base / sub / cat
                    if p1.is_dir() or p2.is_dir():
                        dst = theme_dir / f"{cat}/{sub}"
                        copy_icon_files(p1, dst)
                        copy_icon_files(p2, dst)
                        sz = 48 if sub == "scalable" else int(sub)
                        add_dir_entry(extra_dirs, extra_sections, f"{cat}/{sub}", ctx, sz, scalable=(sub == "scalable"))
        if extra_dirs:
            return

    # 2. Direct category-first layout: <root>/{apps,places}/{32,48,64,96,128,scalable}
    for cat, ctx in (("apps", "Applications"), ("places", "Places")):
        cat_dir = src_root / cat
        if cat_dir.is_dir():
            for sub in sorted(cat_dir.iterdir()):
                if not sub.is_dir():
                    continue
                if sub.name in ("scalable", "32", "48", "64", "96", "128", "256"):
                    copy_icon_files(sub, theme_dir / f"{cat}/{sub.name}")
                    sz = 64 if sub.name == "scalable" else int(sub.name)
                    add_dir_entry(extra_dirs, extra_sections, f"{cat}/{sub.name}", ctx, sz, scalable=(sub.name in ("scalable", "64", "128", "256")))

    # 3. Direct size-first layout: <root>/{32,32x32,48,48x48,64,64x64,96,96x96,128,128x128,scalable}/{apps,places}
    size_map = {
        "32": 32, "32x32": 32, "42x42": 42, "48": 48, "48x48": 48,
        "64": 64, "64x64": 64, "84x84": 84, "96": 96, "96x96": 96,
        "128": 128, "128x128": 128, "scalable": 64,
    }
    for sz_name, sz in size_map.items():
        sz_dir = src_root / sz_name
        if sz_dir.is_dir():
            for cat, ctx in (("apps", "Applications"), ("places", "Places")):
                if (sz_dir / cat).is_dir():
                    copy_icon_files(sz_dir / cat, theme_dir / f"{sz_name}/{cat}")
                    add_dir_entry(extra_dirs, extra_sections, f"{sz_name}/{cat}", ctx, sz, scalable=(sz_name == "scalable" or sz >= 64))


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
        for t in ("Brisus", "Brisus-Dark", "Brisus-Light"):
            t_dir = ICONS_DIR / t
            if t_dir.is_dir():
                for sz, cats in sizes_cats:
                    for cat in cats:
                        copy_icon_files(papirus_root / sz / cat, t_dir / sz / cat)
                subprocess.run(["gtk-update-icon-cache", "-f", "-t", str(t_dir)], check=False)
        return

    if layout == "ocean":
        ocean_root = root / "Icon Pack" / "Ocean"
        for d in ("places/32", "places/32@2x", "places/32@3x", "places/48", "places/64", "places/96",
                  "apps/32", "apps/32@2x", "apps/32@3x", "apps/48", "apps/64"):
            copy_icon_files(ocean_root / d, theme_dir / d)
        subprocess.run(["gtk-update-icon-cache", "-f", "-t", str(theme_dir)], check=False)
        return

    inherits = init_breeze_theme(theme_dir, cfg["breeze_base"], remove_color_dirs=True)
    extra_dirs = []
    extra_sections = []

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
                        add_dir_entry(extra_dirs, extra_sections, f"{cat}/{sub}", ctx, sz, scalable=(sub == "scalable"))
    elif layout == "hatter":
        for cat, ctx in (("apps", "Applications"), ("places", "Places")):
            copy_icon_files(root / "Hatter" / "scalable" / cat, theme_dir / f"scalable/{cat}")
            add_dir_entry(extra_dirs, extra_sections, f"scalable/{cat}", ctx, 64, scalable=True)
    elif layout == "flatery":
        for cat, ctx in (("apps", "Applications"), ("places", "Places")):
            for sz in ("32", "48", "64"):
                copy_icon_files(root / "Flatery" / cat / sz, theme_dir / f"{cat}/{sz}")
                add_dir_entry(extra_dirs, extra_sections, f"{cat}/{sz}", ctx, int(sz), scalable=(sz == "64"))
    elif layout == "zafiro":
        for cat, ctx in (("apps", "Applications"), ("places", "Places")):
            for sub in ("48", "scalable"):
                src = root / "Dark" / cat / sub
                if src.is_dir():
                    copy_icon_files(src, theme_dir / f"{cat}/{sub}")
                    sz = 48 if sub == "scalable" else int(sub)
                    add_dir_entry(extra_dirs, extra_sections, f"{cat}/{sub}", ctx, sz, scalable=(sub == "scalable"))
    elif layout == "mkos":
        for sz_dir, sz, cat, ctx in (
            ("128x128", 128, "apps", "Applications"),
            ("64x64", 64, "apps", "Applications"),
            ("128x128", 128, "places", "Places"),
        ):
            src = root / sz_dir / cat
            if src.is_dir():
                copy_icon_files(src, theme_dir / f"{sz_dir}/{cat}")
                add_dir_entry(extra_dirs, extra_sections, f"{sz_dir}/{cat}", ctx, sz, scalable=(sz == 128))
    elif layout == "diagonal":
        for cat, ctx in (("apps", "Applications"), ("places", "Places")):
            for sz in ("32", "48", "64"):
                src = root / "base" / cat / sz
                if src.is_dir():
                    copy_icon_files(src, theme_dir / f"{cat}/{sz}")
                    add_dir_entry(extra_dirs, extra_sections, f"{cat}/{sz}", ctx, int(sz), scalable=False)
            src_sc = root / "base" / "scalable" / cat
            if src_sc.is_dir():
                copy_icon_files(src_sc, theme_dir / f"scalable/{cat}")
                add_dir_entry(extra_dirs, extra_sections, f"scalable/{cat}", ctx, 64, scalable=True)
    else:
        subpath = cfg.get("subpath", "")
        src_root = root / subpath if subpath else root
        copy_auto_layout(src_root, theme_dir, extra_dirs, extra_sections)

    update_index_theme(theme_dir, name, inherits, extra_dirs, "".join(extra_sections), BREEZE_COLOR_DIRS)
    subprocess.run(["gtk-update-icon-cache", "-f", "-t", str(theme_dir)], check=False)


def download_and_extract(zip_url: str, dest_dir: Path):
    zpath = dest_dir / "repo.zip"
    edir = dest_dir / "extracted"
    edir.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(zip_url, headers={"User-Agent": "CustomIcons-Updater"})
    with urllib.request.urlopen(req, timeout=180) as resp, open(zpath, "wb") as f:
        shutil.copyfileobj(resp, f)
    subprocess.run(["unzip", "-q", "-o", str(zpath), "-d", str(edir)], check=True)
    return edir


def run_updates(force: bool = False):
    state = load_state()
    themes = get_all_themes(state)
    print("Comprobando actualizaciones de iconos...")
    to_update = []
    for cfg in themes:
        repo = cfg["repo"]
        try:
            branch, sha, zip_url = get_remote_head(cfg["url"])
            old_sha = state.get(repo, {}).get("sha", "")
            if force or not old_sha or (sha and sha != old_sha):
                print(f"  [ACTUALIZAR] {repo} -> {cfg['theme_name']} ({old_sha[:7] or 'nuevo'} -> {sha[:7]})")
                to_update.append((cfg, branch, sha, zip_url))
            else:
                print(f"  [OK]         {repo} ({sha[:7]})")
        except Exception as e:
            print(f"  [AVISO]      {repo}: no se pudo comprobar ({e})")

    if not to_update:
        print("Todos los temas están al día.")
        return

    with tempfile.TemporaryDirectory(prefix="customicons_upd_") as tmp:
        tmp_path = Path(tmp)

        def process(item):
            cfg, branch, sha, zip_url = item
            edir = download_and_extract(zip_url, tmp_path / cfg["repo"])
            build_from_extracted(cfg, edir)
            return cfg, branch, sha

        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = [ex.submit(process, it) for it in to_update]
            for fut in as_completed(futs):
                cfg, branch, sha = fut.result()
                repo = cfg["repo"]
                entry = state.get(repo, {})
                entry.update({"url": cfg["url"], "sha": sha, "branch": branch})
                state[repo] = entry
                print(f"Actualizado {cfg['theme_name']} ({sha[:7]})")

    save_state(state)
    print("Actualización completada.")


def suggest_brisa_name(repo_name: str) -> str:
    clean = re.sub(r"[-_]?icon[-_]?theme$", "", repo_name, flags=re.IGNORECASE)
    clean = re.sub(r"[-_]?icons?$", "", clean, flags=re.IGNORECASE)
    clean = clean.strip("-_ ") or repo_name
    return f"Brisa{clean[0].upper()}{clean[1:]}"


def add_theme_interactive():
    url = input("\nURL del repositorio (GitHub / GitLab / invent.kde.org): ").strip()
    if not url:
        print("URL vacía. Cancelando.")
        return

    clean_url = url.rstrip("/")
    if clean_url.endswith(".git"):
        clean_url = clean_url[:-4]
    repo_name = clean_url.split("/")[-1]
    default_name = suggest_brisa_name(repo_name)

    theme_name = input(f"Nombre para el tema modificado [{default_name}]: ").strip() or default_name
    base_choice = input("Base monocromática de Breeze? [D]ark / [L]ight (por defecto Dark): ").strip().lower()
    breeze_base = "light" if base_choice.startswith("l") else "dark"

    print(f"\nConsultando {clean_url}...")
    branch, sha, zip_url = get_remote_head(clean_url)
    print(f"Descargando rama '{branch}' ({sha[:7]})...")

    with tempfile.TemporaryDirectory(prefix="customicons_add_") as tmp:
        edir = download_and_extract(zip_url, Path(tmp))
        root = find_repo_root(edir)

        # Detect if there are multiple index.theme subdirs or src/
        subpath = ""
        if not (root / "src").is_dir() and not (root / "apps").is_dir() and not (root / "48x48").is_dir():
            candidates = sorted(
                {str(p.parent.relative_to(root)) for p in root.rglob("index.theme") if "cursor" not in str(p).lower()}
            )
            if len(candidates) > 1:
                print("\nSe encontraron varias variantes en el repositorio:")
                for i, c in enumerate(candidates, 1):
                    print(f"  {i}) {c}")
                pick = input("Elige el número de la variante [1]: ").strip()
                idx = int(pick) - 1 if pick.isdigit() and 1 <= int(pick) <= len(candidates) else 0
                subpath = "" if candidates[idx] == "." else candidates[idx]
            elif len(candidates) == 1 and candidates[0] != ".":
                subpath = candidates[0]

        cfg = {
            "repo": repo_name,
            "url": clean_url,
            "theme_name": theme_name,
            "layout": "auto",
            "breeze_base": breeze_base,
            "subpath": subpath,
        }
        print(f"Construyendo {theme_name} (Breeze {breeze_base} + {repo_name})...")
        build_from_extracted(cfg, edir)

    state = load_state()
    state[repo_name] = {
        "url": clean_url,
        "sha": sha,
        "branch": branch,
        "custom": True,
        "theme_name": theme_name,
        "layout": "auto",
        "breeze_base": breeze_base,
        "subpath": subpath,
    }
    save_state(state)
    print(f"\nTema '{theme_name}' creado en {ICONS_DIR / theme_name} y añadido al seguimiento de actualizaciones.")


def interactive_menu():
    while True:
        print("\n=== Gestor de CustomIcons ===")
        print("1) Buscar y aplicar actualizaciones de los temas instalados")
        print("2) Agregar un nuevo tema de iconos desde una URL (GitHub / GitLab)")
        print("3) Forzar reconstrucción de todos los temas")
        print("4) Salir")
        choice = input("Selecciona una opción [1-4]: ").strip()
        if choice == "1":
            run_updates(force=False)
        elif choice == "2":
            add_theme_interactive()
        elif choice == "3":
            run_updates(force=True)
        elif choice == "4" or choice.lower() in ("q", "salir", "exit"):
            break
        else:
            print("Opción no válida.")


def main():
    parser = argparse.ArgumentParser(description="Gestor interactivo y actualizador de temas CustomIcons.")
    parser.add_argument("--update", action="store_true", help="Comprobar y aplicar actualizaciones sin menú")
    parser.add_argument("--force", action="store_true", help="Forzar descarga y reconstrucción de todos los temas")
    parser.add_argument("--add", action="store_true", help="Ir directo a agregar un nuevo tema por URL")
    args = parser.parse_args()

    if args.force:
        run_updates(force=True)
    elif args.update:
        run_updates(force=False)
    elif args.add:
        add_theme_interactive()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
