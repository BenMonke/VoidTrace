<p align="center"><img src="docs/logo.png" width="128" alt="VoidTrace logo"></p>

# VoidTrace

> [!WARNING]
> Use at your own risk. This is an unofficial fan project. It isn't made or approved by Digital
> Extremes or Warframe.Market. It only reads the game's log and your screen and never touches the
> game itself, but Digital Extremes decides what third-party tools are OK. There's no warranty, and
> I'm not responsible if you get banned, lose plat or items, or anything else goes wrong.
> Full text: [DISCLAIMER.md](DISCLAIMER.md).

A Warframe helper. It shows plat prices right on the relic reward screen, and has a window for the
rest: buying from players, managing your Warframe.Market orders, pricing rivens, and checking which
relics are worth cracking.

## Install (Windows)

1. Grab `VoidTrace-<version>-windows.zip` from [Releases](https://github.com/BenMonke/VoidTrace/releases/latest).
   It's under Assets. Don't take "Source code", that one has no exe.
2. Right-click the zip, Extract All, put it anywhere.
3. Open the folder and run `VoidTrace.exe`. A blue crystal shows up in the tray (bottom right).
   The first time, it asks if you want a Desktop and Start menu shortcut.

If Windows says "Windows protected your PC", click More info, then Run anyway. The exe isn't signed,
but all the source is right here.

You don't need to install anything else, OCR comes bundled. In Warframe, set Display Mode to
Borderless Fullscreen. Only run one of WFInfo / Overwolf / AlecaFrame / VoidTrace at a time, they all
fight over the same log channel.

Something broken? Right-click the tray icon, hit Run self-test, and send me the result plus
`voidtrace.log` (tray > Open log folder).

To uninstall: right-click the tray icon, Uninstall VoidTrace. It removes your saved sign-in and
Discord link, the shortcuts, and everything in `%LOCALAPPDATA%\VoidTrace` (settings, caches, trade
history, log). Then it shows you the VoidTrace folder so you can delete it. Your Warframe.Market
orders stay as they are.

## How to use it

Open a relic and the prices show up under each reward. Click a price to see who's selling it.

Click the tray icon to open the main window. The sidebar has three sections:

| Market | Rivens | Relics |
|---|---|---|
| Buy, Sell, My orders, Trades, Alerts | Find, Price check, Sell, My rivens | Unvaulted, Vaulted, Look up |

Sign in and the accent colour picker are at the bottom. It reopens on whatever page you had open last.

Hotkeys in game:

- Ctrl+Shift+M opens Market > Buy
- Ctrl+Shift+R reads the riven on your screen into Rivens > Price check

Right-click the tray icon for the on/off switches (riven popup, order updates after trades, online
status), accent colour, self-test, log folder, the disclaimer, and Quit.

## Market

Buy: search any item, mods too (ranked stuff gets a rank picker). People in game are listed first,
cheapest first. Troll prices stay in the list but greyed out. Click a seller to copy the whisper,
then paste it in game chat:

`/w Seller Hi! I want to buy: "Primed Continuity (rank 10)" for 45 platinum. (warframe.market through VoidTrace)`

Sell (needs sign in): shows the top 5 sell and buy orders for the rank you pick, then you post at
"match lowest", "lowest +/- something" (like -1 to undercut), or your own price. Your own listing is
ignored when matching.

My orders: your live orders. You can reprice to match the lowest, or delete.

After a trade: VoidTrace sees the trade in the game log and lowers the matching order by however many
you traded, or removes it if you're out. Stuff you gave lowers your sell orders, stuff you got lowers
your buy orders. A little card pops up top right with an Undo button for 10 seconds. You can turn this
off in the tray menu.

Trades: every trade it saw, newest first, with plat earned, spent and net for today, the last 7 days,
and all time. This works without signing in and stays on your PC (`trades.jsonl`).

Alerts: on Buy, click Alert me… and pick a price (it starts at 1 below the cheapest seller). Every
minute it checks, and when someone online lists it at or under your price you get a tray message.
Click it to copy the whisper. You only get told once per seller and price, and troll prices are skipped.

### About signing in

Warframe.Market doesn't let outside apps log in the proper way (no OAuth), so VoidTrace uses the same
email + password login the website uses. Your password only goes to api.warframe.market and is never
saved. The login token goes in Windows Credential Manager and gets removed when you sign out.

Nothing gets posted on its own. The only automatic change is lowering an order after a trade.

## Rivens

Open a riven in Inventory > Mods > Cycle or in Item Details, then press Ctrl+Shift+R to read and
price it.

You don't really need the hotkey though. While a riven is open on one of those screens, a small panel
pops up on the right with its stats, how good each roll is, and a price guess. Click it for the full
price check. It spots the card by the emblem at the top (it looks about every 0.7 s, and only while
Warframe is the active window). You can turn it off in the tray menu.

- Find: auctions for a weapon, filtered by the stats you want, curse, buyout only, and unrolled or
  rolled. Click one to copy a whisper for it.
- Price check: type the riven's name and the stats fill in (the name tells you the stats, e.g.
  Igni-insitron = Heat + Puncture + Damage to Corpus). Or read it off your screen. Each stat gets a
  letter grade for how well it rolled. The price comes from listings with the same stats and similar
  rolls. Rivens have no trade history, so these are asking prices.
- Sell and My rivens (need sign in): post an auction in one click, hide/show it, match the cheapest
  similar listing, close it.

Grades use the game's own base numbers from Warframe's Public Export (`voidtrace/data/riven_bases.json`,
update it with `python tools/update_riven_bases.py`):

`value = base x 10 x (rank + 1) x disposition x buff-count multiplier x roll`, where roll is 0.9 to 1.1.

Screen reading has been tested on real cards at 2560x1600, 1920x1200 and 1680x1050. 16:9 screens and
other UI scales haven't been checked yet.

## Relics

- Unvaulted / Vaulted: every relic that drops right now or doesn't anymore, with its average plat at
  Intact and Radiant, its ducats, and its best reward. Click a column header to sort, click again to
  flip it. Double-click a relic to see what's in it.
- Look up: search a relic (`axi a1`) or a reward (`nikana prime`) to see what it's worth in plat and
  ducats at each refinement, plus its 6 rewards with prices and drop chances.
- Solo / Squad of 4 (top right): with a squad you get the best of 4 drops, so the value goes up.

Cached prices show up right away and fresh ones load in the background. The very first load of
Vaulted takes a few minutes. Relic contents come from the Public Export and vaulted status from
Warframe.Market. Run `python tools/update_relics.py` to refresh `voidtrace/data/relics.json`.

## Online status (optional, off by default)

Tray > Show me in game on Warframe.Market while playing. When you're signed in, it sets your status
to In game when Warframe starts and puts it back to what it was (Online or Invisible) when the game
closes or you quit VoidTrace. That way buyers only see you when you can actually trade.

It sets In game for an hour at a time and renews it every 30 minutes. If VoidTrace crashes or your PC
goes to sleep, your status goes back on its own.

## Discord notifications (optional)

Get price alerts and finished trades in your own Discord channel, so they reach your phone too.

1. In Discord: Server Settings > Integrations > Webhooks > New Webhook, pick a channel, Copy Webhook URL.
2. In VoidTrace: click Discord at the bottom of the sidebar, paste the link, hit Send test, and tick
   what you want sent.

The link is saved in Windows Credential Manager. Whispers can't be forwarded because Warframe doesn't
write them to its log.

## Accent colour

Bottom of the sidebar (or the tray menu). Pick a preset (Void blue, Cyan, Purple, Pink, Gold, Green,
Red) or any colour with Custom… Everything updates right away and it remembers your pick
(`%LOCALAPPDATA%\VoidTrace\settings.json`).

## Running from source

```
pip install -r requirements.txt
winget install UB-Mannheim.TesseractOCR   # the OCR engine (or set TESSERACT_CMD)
python main_app.py
```

Some handy flags:

```
python main_app.py --demo shot.png        # run the reward screen reader once on a screenshot
python main_app.py --trigger-now          # grab the screen right now
python main_app.py --self-test            # check OCR, Warframe.Market and the game log
```

Tests: `pip install -r requirements-dev.txt`, then `pytest`. To build the Windows zip:
`pip install pyinstaller`, then `python tools/build_release.py`.

## How it works

It never writes to the game's files or touches the game process. It reads
`%LOCALAPPDATA%\Warframe\EE.log` (or the game's live debug output), takes screenshots, and draws its
own windows on top.

When you open a relic:

1. `log_watcher.py` notices the reward screen line in the game log.
2. `cv_cleaner.py` screenshots the reward names and cleans the image up for OCR (it works out the
   resolution and squad size by itself).
3. `text_cleaner.py` and `items.py` fix OCR mistakes (`N3kr0s` → `Nekros`) and match the text
   against the ~600 relic rewards.
4. `price_cleaner.py` gets the price. It uses recent sold prices when there are enough, otherwise
   the cheapest in-game sellers with troll prices filtered out.
5. `overlay.py` draws the price cards on top of the game. They're see-through and you can click
   through them.

The window's pages are in `voidtrace/ui/`, one file per page or group of pages, with the shared bits
in `ui/widgets.py`.

Prices are cached in `%LOCALAPPDATA%\VoidTrace\` for 15 minutes, and the cache is used as a backup
when Warframe.Market is down. The plat, ducat and chest icons are drawn in code (`voidtrace/icons.py`),
not ripped from the game.

## Not tested yet

- Other resolutions, UI scales, themes, and non-English game clients.
- Some reward screen fixes still need another real run: the card position under the squad's pick
  list, waiting for the names to finish fading in, and the second look at cards it couldn't read.

## License

GPL-3.0, see [LICENSE](LICENSE). You can use, change and share it, but if you share a changed
version it has to stay GPL-3.0 with the source available. It's GPL because it's built on PyQt6, which
is GPL too. The icons from Lucide are under their own licence (`licenses/lucide.txt`).
