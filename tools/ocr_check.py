"""OCR accuracy on real screenshots, and an easy way to add more.

    python tools/ocr_check.py                   # score every saved screenshot
    python tools/ocr_check.py add               # add the samples the app saved (captures/, run from source)
    python tools/ocr_check.py add friend.zip    # a friend's "Export OCR samples" zip (tray menu)
    python tools/ocr_check.py add a.png folder  # or full-screen screenshots, or folders of either

Adding shows what the OCR read; press Enter if it is right or type the fix. Only the reward-name
band or the riven card is kept (no player names), next to the fixtures the tests already use, so
pytest checks the new samples too.
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))  # reuse the tests' own readers, so the score matches pytest

import cv2

from voidtrace import rivens
from voidtrace.cv_cleaner import find_tesseract, read_reward_texts, sample_frame, sample_parts
from voidtrace.items import Item, load_items
from voidtrace.riven_ocr import read_riven
from voidtrace.riven_watch import detect_card
from voidtrace.rivens import RivenAttr
from voidtrace.text_cleaner import EntityResolver

import test_real_screens as relic_t
import test_riven_ocr as riven_t

RELIC_ITEMS = relic_t.FIXTURES / "relic_rewards_2026-10-10.json"
RELIC_TRUTH = relic_t.BANDS / "truth.json"
RIVEN_META = riven_t.SCREENS / "screens.json"
CAPTURES = ROOT / "captures"  # where the app saves its OCR samples when run from source


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data, indent: int) -> None:  # each fixture keeps its own layout: small diffs
    path.write_text(json.dumps(data, indent=indent, ensure_ascii=False) + "\n", encoding="utf-8")


def riven_catalog():
    f = riven_t.FIXTURES
    return rivens.RivenCatalog(rivens.parse_weapons(load_json(f / "weapons.json")["data"]),
                               rivens.parse_stats(load_json(f / "attributes.json")["data"]))


def score() -> None:
    resolver = EntityResolver(Item(**i) for i in load_json(RELIC_ITEMS))
    ok = total = 0
    misses = []
    for key, case in load_json(RELIC_TRUTH).items():
        texts = relic_t.read_screen(key, case["screen"])
        for i, truth in enumerate(case["truth"]):
            res = resolver.resolve(texts[i]) if i < len(texts) else None
            total += 1
            if res and res.item and res.item.name == truth:
                ok += 1
            else:
                misses.append(f"  relic {key}: expected {truth!r}, got {res.item.name if res and res.item else None!r}")
    relic_line = f"Relic reward names: {ok}/{total} ({100 * ok / max(total, 1):.0f}%)"

    catalog = riven_catalog()
    ok = 0
    for key, (weapon, name, mr, rolls, rank, attrs) in riven_t.EXPECTED.items():
        read = read_riven(riven_t.screen(key), catalog)
        d = read.draft
        got = (d.weapon, d.name, d.mr, d.rolls, d.rank, list(d.attrs), d.polarity)
        want = (weapon, name, mr, rolls, rank, [RivenAttr(*a) for a in attrs], riven_t.POLARITY[key])
        if got == want and not read.warnings:
            ok += 1
        else:
            misses.append(f"  riven {key}: expected {want}\n{'':8}got {got} {read.warnings}")
    n = len(riven_t.EXPECTED)
    print(relic_line)
    print(f"Riven cards, every field right: {ok}/{n} ({100 * ok / max(n, 1):.0f}%)")
    if misses:
        print("\nMisses:\n" + "\n".join(misses))


def ask(prompt: str, default):
    answer = input(f"{prompt} [{default}]: ").strip()
    return type(default)(answer) if answer else default


def new_key(name: str, taken) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "shot"
    base, n = key, 2
    while key in taken:
        key, n = f"{base}_{n}", n + 1
    return key


def load_sample(png: Path):
    """(meta, parts) from an app sample (png + json) or a full-screen screenshot; None if unusable."""
    meta_path = png.with_suffix(".json")
    if meta_path.exists():
        meta = load_json(meta_path)
        parts = {"": cv2.imread(str(png))}
        fits = png.with_name(f"{png.stem}_fits.png")
        if fits.exists():
            parts["_fits"] = cv2.imread(str(fits))
        return (meta, parts) if parts[""] is not None else None
    frame = cv2.imread(str(png))
    if frame is None:
        return None
    return sample_parts(frame, "riven" if detect_card(frame) is not None else "relic")


def save_parts(folder: Path, key: str, parts) -> None:
    for suffix, img in parts.items():
        cv2.imwrite(str(folder / f"{key}{suffix}.png"), img)


def add_relic(source: Path, meta, parts) -> bool:
    items = load_items()  # every possible reward (cached by the app), not just the fixture's list
    by_name = {i.name.lower(): i for i in items}
    texts = read_reward_texts(sample_frame(meta, parts))
    if not texts:
        print("  no reward names found, skipped")
        return False
    truth = []
    for i, res in enumerate(EntityResolver(items).resolve_all(texts), 1):
        while True:
            name = ask(f"  reward {i} (s = skip shot)", res.item.name if res.item else "?")
            if name.lower() == "s":
                return False
            if name.lower() in by_name:
                truth.append(by_name[name.lower()].name)
                break
            print("    not a known relic reward, try again")

    manifest = load_json(RELIC_TRUTH)
    key = new_key(source.stem, manifest)
    save_parts(relic_t.BANDS, key, parts)
    manifest[key] = {"screen": meta["screen"], "truth": truth, "source": source.name}
    save_json(RELIC_TRUTH, manifest, 2)

    fixture = load_json(RELIC_ITEMS)  # the test resolver only knows these names
    known = {i["name"] for i in fixture}
    for name in truth:
        if name not in known:
            item = by_name[name.lower()]
            fixture.append({"name": item.name, "slug": item.slug, "ducats": item.ducats})
            known.add(name)
    save_json(RELIC_ITEMS, fixture, 0)
    print(f"  saved as {key}")
    return True


def add_riven(source: Path, meta, parts) -> bool:
    d = read_riven(sample_frame(meta, parts), riven_catalog()).draft
    print(f"  read: {d.weapon} {d.name}  MR {d.mr}  rolls {d.rolls}  rank {d.rank}  {d.polarity}")
    for a in d.attrs:
        print(f"        {a.slug} {a.value} {'buff' if a.positive else 'curse'}")
    answer = input("  Correct? Enter = yes, e = edit, s = skip: ").strip().lower()
    if answer == "s":
        return False
    truth = {"weapon": d.weapon, "name": d.name, "mr": d.mr, "rolls": d.rolls, "rank": d.rank,
             "polarity": d.polarity, "attrs": [[a.slug, a.value, a.positive] for a in d.attrs]}
    # shortcut: fields can be edited but stat lines can't be added; skip the shot if one was missed.
    if answer == "e":
        for field in ("weapon", "name", "mr", "rolls", "rank", "polarity"):
            truth[field] = ask(f"  {field}", truth[field])
        for a in truth["attrs"]:
            a[0] = ask("  stat", a[0])
            a[1] = ask(f"  {a[0]} value", a[1])

    screens = load_json(RIVEN_META)
    key = new_key(f"{truth['weapon']}_{truth['name']}" if truth["weapon"] else source.stem, screens)
    save_parts(riven_t.SCREENS, key, parts)
    screens[key] = {k: meta[k] for k in ("screen", "offset", "fits_offset") if k in meta}
    screens[key].update(source=source.name, truth=truth)
    save_json(RIVEN_META, screens, 1)
    print(f"  saved as {key}")
    return True


def expand(paths: list[str]) -> list[Path]:
    """Every png to look at: folders searched, zips unpacked next to captures/."""
    found = []
    for p in map(Path, paths):
        if p.suffix.lower() == ".zip":
            out = CAPTURES / "imported" / p.stem
            with zipfile.ZipFile(p) as z:  # extractall drops absolute paths and ".." parts
                z.extractall(out)
            p = out
        found += sorted(p.rglob("*.png")) if p.is_dir() else [p]
    return [f for f in found if not f.stem.endswith("_fits")]  # read together with its card


def add(paths: list[str]) -> None:
    from_captures = not paths
    files = expand(paths) if paths else [f for f in sorted(CAPTURES.glob("*.png")) if not f.stem.endswith("_fits")]
    if not files:
        print("No .png samples found there." if paths else
              f"Nothing in {CAPTURES} yet (the app saves samples there when run from source).")
        return
    added = 0
    for p in files:
        print(p.name)
        sample = load_sample(p)
        if sample is None:
            print("  not a relic reward screen or riven card, skipped")
        else:
            meta, parts = sample
            added += (add_riven if meta["kind"] == "riven" else add_relic)(p, meta, parts)
        if from_captures:  # looked at: moved aside (not deleted) so the next run only shows new ones
            (CAPTURES / "done").mkdir(exist_ok=True)
            for f in CAPTURES.glob(f"{p.stem}*"):
                if f.is_file():
                    f.replace(CAPTURES / "done" / f.name)
    print(f"\nAdded {added} of {len(files)}. Re-run without 'add' to see the new score.")


if __name__ == "__main__":
    if find_tesseract() is None:
        sys.exit("Tesseract not found.")
    if sys.argv[1:2] == ["add"]:
        add(sys.argv[2:])
    else:
        score()
