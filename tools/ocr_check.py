"""OCR accuracy on real screenshots, and an easy way to add more.

    python tools/ocr_check.py                 # score every saved screenshot
    python tools/ocr_check.py add             # add what the app captured (captures/, when run from source)
    python tools/ocr_check.py add a.png b.png # or add your own full-screen screenshots

Adding shows what the OCR read; press Enter if it is right or type the fix. Only the reward-name
band or the riven card is kept (no player names), next to the fixtures the tests already use, so
pytest checks the new screenshots too.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))  # reuse the tests' own readers, so the score matches pytest

import cv2

from voidtrace import rivens
from voidtrace.cv_cleaner import Box, crop, find_tesseract, read_reward_texts, reward_band
from voidtrace.items import Item, load_items
from voidtrace.riven_ocr import read_riven, ref_box
from voidtrace.riven_watch import detect_card
from voidtrace.rivens import RivenAttr
from voidtrace.text_cleaner import EntityResolver

import test_real_screens as relic_t
import test_riven_ocr as riven_t

RELIC_ITEMS = relic_t.FIXTURES / "relic_rewards_2026-10-10.json"
RELIC_TRUTH = relic_t.BANDS / "truth.json"
RIVEN_META = riven_t.SCREENS / "screens.json"
CAPTURES = ROOT / "captures"  # where the app saves what it OCRs (cv_cleaner.keep_capture)
MARGIN = 8


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


def add_relic(path: Path, frame) -> None:
    h, w = frame.shape[:2]
    items = load_items()  # every possible reward (cached by the app), not just the fixture's list
    by_name = {i.name.lower(): i for i in items}
    texts = read_reward_texts(frame)
    if not texts:
        print("  no reward names found, skipped")
        return
    truth = []
    for i, res in enumerate(EntityResolver(items).resolve_all(texts), 1):
        while True:
            name = ask(f"  reward {i}", res.item.name if res.item else "?")
            if name.lower() in by_name:
                truth.append(by_name[name.lower()].name)
                break
            print("    not a known relic reward, try again")

    manifest = load_json(RELIC_TRUTH)
    key = new_key(path.stem, manifest)
    band = reward_band(w, h)
    cv2.imwrite(str(relic_t.BANDS / f"{key}.png"), crop(frame, band))
    manifest[key] = {"screen": [w, h], "truth": truth, "source": path.name}
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


def add_riven(path: Path, frame, layout) -> None:
    h, w = frame.shape[:2]
    d = read_riven(frame, riven_catalog()).draft
    print(f"  read: {d.weapon} {d.name}  MR {d.mr}  rolls {d.rolls}  rank {d.rank}  {d.polarity}")
    for a in d.attrs:
        print(f"        {a.slug} {a.value} {'buff' if a.positive else 'curse'}")
    answer = input("  Correct? Enter = yes, e = edit, s = skip: ").strip().lower()
    if answer == "s":
        return
    truth = {"weapon": d.weapon, "name": d.name, "mr": d.mr, "rolls": d.rolls, "rank": d.rank,
             "polarity": d.polarity, "attrs": [[a.slug, a.value, a.positive] for a in d.attrs]}
    # shortcut: fields can be edited but stat lines can't be added; skip the shot if one was missed.
    if answer == "e":
        for field in ("weapon", "name", "mr", "rolls", "rank", "polarity"):
            truth[field] = ask(f"  {field}", truth[field])
        for a in truth["attrs"]:
            a[0] = ask("  stat", a[0])
            a[1] = ask(f"  {a[0]} value", a[1])

    meta = load_json(RIVEN_META)
    key = new_key(f"{d.weapon}_{d.name}" if d.weapon else path.stem, meta)
    boxes = [ref_box(frame, b) for b in (layout.text, layout.bar, layout.drain, layout.polarity, layout.cost) if b]
    x0, y0 = min(b.x for b in boxes) - MARGIN, min(b.y for b in boxes) - MARGIN
    x1 = max(b.x + b.w for b in boxes) + MARGIN
    y1 = max(b.y + b.h for b in boxes) + MARGIN
    cv2.imwrite(str(riven_t.SCREENS / f"{key}.png"), crop(frame, Box(x0, y0, x1 - x0, y1 - y0)))
    entry = {"screen": [w, h], "offset": [max(0, x0), max(0, y0)], "source": path.name, "truth": truth}
    if layout.fits:  # the Cycle screen's "FITS IN" name sits far from the card: kept as its own crop
        f = ref_box(frame, layout.fits)
        cv2.imwrite(str(riven_t.SCREENS / f"{key}_fits.png"), crop(frame, f))
        entry["fits_offset"] = [f.x, f.y]
    meta[key] = entry
    save_json(RIVEN_META, meta, 1)
    print(f"  saved as {key}")


def add(paths: list[str]) -> None:
    from_captures = not paths
    files = [Path(p) for p in paths] or sorted(CAPTURES.glob("*.png"))
    if not files:
        print(f"No screenshots given and none in {CAPTURES} (the app saves them there when run from source).")
        return
    for p in files:
        frame = cv2.imread(str(p))
        if frame is None:
            print(f"{p}: not an image, skipped")
            continue
        print(p.name)
        layout = detect_card(frame)
        if layout is not None:
            add_riven(p, frame, layout)
        else:
            add_relic(p, frame)
        if from_captures:  # looked at: moved aside (not deleted) so the next run only shows new ones
            (CAPTURES / "done").mkdir(exist_ok=True)
            p.replace(CAPTURES / "done" / p.name)
    print("\nRe-run without 'add' to see the new score.")


if __name__ == "__main__":
    if find_tesseract() is None:
        sys.exit("Tesseract not found.")
    if sys.argv[1:2] == ["add"]:
        add(sys.argv[2:])
    else:
        score()
