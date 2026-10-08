# PvZ Social Offline Reconstruction: Handover

Written 2026-09-28, updated the same day with section 12 (multi-device / Android play). Replaces the earlier session summary. The zip that was last delivered (`PvZ_Social_Offline.zip`) is the source of truth. Sandbox paths under `/home/claude` and `/tmp` may not survive between sessions.

## 1. What this project is

A standalone offline rebuild of PopCap's *Plants vs Zombies Social Edition* (Renren.com, 2011-2012). It is a Flash/AS3 game with AMF RPC. A local Python HTTP + AMF server (`server.py` + `amf.py`) stands in for the original backend. The user plays through `flashplayer_32_sa_debug.exe`. Three core SWFs (`main.swf`, `PVZEntry_1_.swf`, `townEntry_1_.swf`) share one ApplicationDomain. Shop art comes from a user-designed external file, `itemShop.swf`.

## 2. Current build

```
BUILD_LABEL = "2026-09-28-plant-i2017"
EXPECTED_BUILD = {
    "main.swf": (573225, "3b9c9779f1574ed2b1b407ce88c7530c"),
    "PVZEntry_1_.swf": (492952, "94ce7afa7c65673283ec3fc5fbc9eddb"),
    "townEntry_1_.swf": (474829, "43ba6c011b7246cd446c002b11362774"),
    "itemShop.swf":     (427447, "8d5e97f5667580d05a7e3fee224d0b18"),
}
```

- Working folder: `/home/claude/project_v7/`. It was started from the user's uploaded `PvZ_Social_Offline_shop_buttons_visible_fix.zip`. The earlier `project_v6/finalbuild` is a different lineage and is **not** the base any more.
- `server.py` prints `[OK]` or `[MISMATCH]` for these four files at startup. **Every time you ship a changed file, update its size and MD5 in `EXPECTED_BUILD` and change `BUILD_LABEL`.**
- Debug log helpers in the package: `Enable_Debug_Log.bat`, `Export_Debug_Log.bat`, `View_Debug_Log.bat`. The user sends back `pvz-social-logs-*.txt`, `debug_export.txt` and `server_log.txt`.

## 3. Status

**Working now, confirmed by the user:**
- The shop opens with no #2180 crash.
- All shop buttons show, after the tag-order fix (section 5).

**Built but not yet confirmed by the user in the game:**
- The nine-slot, three-row shop layout with 9 items per page (section 6).

## 4. Toolchain and pipeline

- JPEXS FFDec CLI v22.0.2 (`/home/claude/ffdec/ffdec-cli.jar` in the sandbox).
  - Export scripts: `-export script <dir> <swf>`
  - Replace scripts: `-importScript <in.swf> <out.swf> <scratchdir>`
  - Round-trip a SWF through XML: `-swf2xml` and `-xml2swf`
  - Render a frame or shape to PNG: `-format frame:png -export frame <dir> <swf>` and `-format shape:png -export shape ...`
- Standard workflow for a code change:
  1. Copy the class from a fresh export of the *current* SWF into a scratch folder, keeping the package path.
  2. Edit it and check parentheses and braces by hand.
  3. Run `-importScript` into the SWF. Errors show as `SEVERE:` lines.
  4. Re-export and `diff -rq` against the previous export. Only the intended files should differ. The script count should be unchanged (main 420, PVZEntry 407).
  5. Recompute size and MD5, update `EXPECTED_BUILD` and `BUILD_LABEL`, run `py_compile` on `server.py`, and zip.
- Standard workflow for a shop-file change (`itemShop.swf`): `-swf2xml`, edit the XML, `-xml2swf`. Then re-parse and check tag order, named instances, images, and that no placement references a character defined later. Render the frame to PNG and look at it.

## 5. The shop saga: root causes

| Symptom | Root cause | Fix |
|---|---|---|
| `#2180` on `addChild` in `buildShopSkin()`. The loaded content was an `AVM1Movie` with `actionScriptVersion=2`. | In `itemShop.swf` the `FileAttributesTag` was **not the first tag**. It sat mid-stream, so Flash Player ignored it and fell back to AVM1. The flag value was correct the whole time. | Moved `FileAttributesTag` to be the first tag. |
| Startup warning said all files were stale. | `check_build()` compared `str(size)` to an `int`, so it always failed. That was a bug in the check, not in the user's extraction. | Compare both as ints. |
| Shop opened but no buttons, tabs or item slots showed. Root had only 3 children. | 20 of 23 `PlaceObject2` tags came **before** the shapes and buttons they use. Flash silently skips a placement when the character is not yet defined. | Reordered so all definitions come before all placements. |

Structural rules for `itemShop.swf` and any hand-built SWF:
1. `FileAttributesTag` first (`actionScript3="true"`).
2. ABC (`DoABC2Tag`) inside frame 1, before `ShowFrameTag`. FFDec's GUI put it *after* the frame once. It was moved.
3. All `Define*` tags before every `PlaceObject2`.
4. Unique depth per placement.
5. If a build is checked only by reading values, also check *order* and *position*.

Code changes made along the way that are **still in the SWFs**. They did not turn out to be the cause and could probably be removed, but removing them has not been tested:
- `UIResourceManager.loadItemShopViaBytes()` loads the shop via `URLLoader` + `Loader.loadBytes()` into `new ApplicationDomain(ApplicationDomain.currentDomain)`, then waits 30 ms (`setTimeout`) before continuing. It only applies to `UI_RESOURCE_ITEM_SHOP`, and only in `main.swf`. It uses a captured `self` variable, not `this`.
- `SwfManager.setLoadedSwfContent(name, arr)`: a public setter added next to `setApplicationDomain()`, used by the code above.
- `SwfManager.onLoadComplete()` uses `MutliLoader.ownerDomainObj` instead of the shared `curDomainObj` (a genuine race fix, though it was not the cause of #2180).
- `ItemShopUI`: `ButtonSkinClip` (neutralises `gotoAndStop`/`gotoAndPlay`), `mapExternalButton()`, `wrapSkinAsMovieClip()`. This came from an earlier session and is in both `main.swf` and `PVZEntry_1_.swf`.
- `itemShop.swf` now contains two minimal classes, `shop.ShopRoot` and `anim_rampage`, added in FFDec's GUI. Unclear whether they were needed. The file worked without them on the tag-order fix alone.

## 6. Shop layout (latest change)

- Item slots are placed by name in `itemShop.swf`. `ItemShopUI` maps `itemSlotN` to `itemN`. `EXTERNAL_SHOP.txt` in the package lists the full name mapping (`shopBackground` -> `mainBg`, `prevButton` -> `prevBt`, `tab_*_1` -> `tabBtn*`, and so on).
- All nine slots reuse one grass shape (characterId 26, 115x92 px). Slots 1-6 use depths 20-25. Slots 7-9 use depths **32-34**, because 26-28 belong to `mysteryBox1`, `lockIcon1` and `leaf1`.
- Layout: scale 1.10 for all nine. X in twips: 5732, 8634, 11536. Y in twips: 2196, 5136, 7776. Bottom edges sit on shelf tops at y = 211, 358 and 490 px. The bottom compartment is only about 100 px tall, which is why 1.10 is the largest size that fits.
- `ItemShopUI.itemCount` and `pageSize` were changed from 6 to 9 in both `main.swf` and `PVZEntry_1_.swf`.

## 7. Pitfalls learned

- **`-importScript` cannot add a brand-new class.** It only replaces the source of a class that already exists. On a file with no ABC it does nothing, prints no error, and still rewrites the file (the MD5 changes). Back up before any import.
- Do not use a blanket `sed` on imports. One did, and it corrupted `import flash.utils.getQualifiedClassName;` into an invalid line. That caused a game-startup `#1065` crash. For diagnostic class names use `String(obj)`.
- In nested AS3 closures, `this` is not reliable. Capture `var self:Foo = this;` and use `self`.
- Count parentheses in long `trace(...)` lines. A missing `)` was caught only because import printed a parse error.
- Keep baselines separate. `main.swf`, `PVZEntry_1_.swf` and `townEntry_1_.swf` each have their own copy of many classes. Patch the copy that is actually used. `UIResourceManager.loadItemShopViaBytes` exists only in `main.swf`.
- Do not reason from a static read of a file alone. The decisive facts each time came from runtime logs or from rendering the shop to a PNG.
- Package docs `BUILD_STATUS.txt`, `SHOP_FIX_STATUS.txt` and `INSTALL.txt` are stale. They describe older builds.

## 8. Debug output still embedded

Added during this work, safe to strip later: `[DEBUG-BTNMAP]`, `[DEBUG-WRAPSKIN]`, `[DEBUG-SETSKIN]` (in `McButton`), `[DEBUG-LOADBYTES]`, `[DEBUG-ROOTDUMP]` (in `buildShopSkin`), and `[DEBUG-SERVING-ITEMSHOP]` (in `server.py` `do_GET`). Most of the other `[DEBUG-*]` lines in the SWFs (tutorial, flow, skin, and so on) were already there and are not part of this work.

Also in the package: `FlashPlayerTrust/pvzsocial.cfg` and `Install_Flash_Trust.bat`. That was an experiment that made no difference. It is harmless and can be removed.

## 9. Not yet verified

- The nine-slot layout in the running game.
- How item image, name and price look at the smaller 1.10 scale.
- What happens on a last page with fewer than 9 items.
- The shop opened from a route that uses `PVZEntry_1_.swf`'s copy of the shop code rather than `main.swf`'s.

## 10. Open work

1. **Grass under placed town buildings.** The user mentioned wanting one shared grass background for houses and buildings placed in town. Only the shop-slot grass has been handled. The town side has not been looked at and needs clarifying with the user.
2. **Land-plot unlock zones.** Investigated, not enabled. `i2001_payload()` sends all 16 zones open (`"grounds": {str(i): [i*36, i*36+35] for i in range(16)}`) and `unlockRules: {}`. To enable: fill `unlockRules` in `i1001_payload()`, reduce `grounds` to the open zones, and extend the `I5001` handler to treat the argument as an area index when it is not a known resource id. An earlier attempt was backed out at the user's request.
3. **"Invite friend to house" (`services.I2018`).** Crash guarded, not implemented.
4. **Building move/sell** is not tracked on the server. `I2012` handles only `QUEUE_TYPE_ADD_BLD = 0`, so moved or sold buildings reappear after a reload.
5. **TD battle module.** `BasicMission.as` has a guard against an infinite loop on an empty zombie pool. Real TD gameplay is not implemented.
6. **PeopleHouse roomer / town-visit.** Infrastructure exists, but the "choose which friend lives here" UI is not built.

## 11. Other systems, still active (from earlier sessions)

- **Player identity.** The player's own UID is fixed at `245953145` for all accounts. `AmfCaller.onResult()` drops responses whose `user.uid` differs from `commonModel.id`, and the client hardcodes that id. Friends get distinct md5-derived UIDs via `_uid_for_username()`.
- **Friends.** `friends.json` (owned by `launcher.py`) holds `{username: {friends, incoming, outgoing}}`. `server.py` `i1003_payload()` returns the real list, or `null` when empty (a deliberate workaround for an empty-versus-null bug). `Flow.as` `onLoadPlayerFriendsComplete()` calls `FriendManager.instance.pushFriendData(...)`.
- **AMF decoding.** Incoming values start with `0x0A` (AMF0 strict array). The framework prepends uid and session token, so explicit arguments are read from the **end** of the list (`decode_amf0_args()`). AMF3 object decoding handles the traits reference table.
- **Building system.** House 701 is `subType: 1`. Five real FuncHouse buildings (resourceIds 9110-9150, subType 7) keep the tab populated. Tier 2+ entries set `category: -1`. `I2012` records placements and deducts money. `I2020` credits income and exp. Saves live in `current_save()["placedBuildings"]`.
- **Crash guards from earlier.** `levelUpBonus` map filled for levels 1-60. `TownFlow.onRentalMoviePlayComplete()` checks `building != null`.

## 12. Multi-device / Android play (2026-09-28, second session)

No SWF was changed in this step (section 13 changed them later). Only `server.py`, `launcher.py` and new files changed.

**How it works**
- `/play` runs `main.swf` in Ruffle 0.6.0 (npm `@ruffle-rs/ruffle`), bundled in `ruffle/`. A 3 MB Noto Sans CJK SC subset (GB2312 plus all characters in the game's XML and scripts) is bundled as `fonts/pvz-cjk.otf`. Without it, all Chinese device-font text is blank in Ruffle.
- The page defines `window.util.getAmfGateway` (returns `location.origin + "/"`) and `window.util.getSessionKey`. `Flow.as` already calls these through ExternalInterface. The gateway override is what lets phones reach the PC instead of `127.0.0.1`.
- Identity: `/api/login` and `/api/register` create a cookie session (`sessions.json`, token `web_<hex>`). They **no longer write `active_account.json`**; that file now belongs only to the launcher and projector. I1001 receives the token as `args[1]`. The server returns it as `popcapId`, and `AmfCaller` then sends it as `args[2]` of every later call. `_scope_body()` sets a thread-local account per AMF body, and `get_active_account()` returns it. Calls without a `web_` token (the projector) fall back to `active_account.json`.
- The server is threaded (`ThreadingPvZServer`) and still listens on all interfaces. AMF handling is serialised by `_state_lock`. Avatar URLs use the request's Host header. `/ruffle/` and `/fonts/` are cacheable; everything else stays `no-store`.
- Ruffle config: `forceScale` + `showAll`, `forceAlign` + `salign ""` (the game asks for top-left), letterbox, `autoplay "auto"` (the phone needs one tap, which also unlocks audio).
- New files: `Allow_Phone_Access.bat` (firewall rule for TCP 9090 on Private networks) and `PLAY_ON_PHONE.txt`. The launcher footer shows the LAN URL, and `server.py` prints it at startup.

**Verified in headless Chromium, including an emulated Android phone with touch**
- A desktop and a phone ran at the same time on two different accounts. Every AMF call was logged with the right account, and all went to the LAN address.
- Chinese text renders. Tapping advances Dave's dialog; a real ~150 ms touch works, but Playwright's instant `tap()` is too fast for Ruffle.
- The tutorial shop button opens the shop. The `loadBytes` path works and all 26 named parts (9 slots) are present.

**Open**
- In Ruffle the shop shelves show empty ("0/0"), and tapping the house tab changed nothing visible. It is not yet known whether this also happens in the Flash projector with the nine-slot build. Compare there first.
- A sound URL resolves to `/null` (404). This was already happening before and is harmless.
- Playing one account on two devices at once means the last save wins.
- Test with a real phone: performance, dragging the map, text input.

## 13. Every house opens the adventure panel (2026-09-28)

**Cause.** `Manager.checkBldClickEvent` sends every home (`subType 1`) and FuncHouse click as `SELECT_MISSION_MODE`. `TownFlow.onSelMissionMode` then looked up `houseMissionMap[tid]`. The server never answers `I1033`, so the map is empty and the click did nothing. A mission list starting with an id <= 0 would have opened Rampage instead.

**Fix.** Only `TownFlow` changed, identically in `main.swf`, `PVZEntry_1_.swf` and `townEntry_1_.swf`. All three had byte-identical copies, so all were patched.
- `onSelMissionMode` now always calls `openAdventureForHouse(bld)`. Rampage is still reachable from its own button (`onSelRampageMode`).
- `openAdventureForHouse` checks that `houseMissionMap` is not null, keeps only mission ids > 0, and falls back to `[1]`.
- New trace: `[DEBUG-HOUSECLICK]`.
- Re-export diff showed only `TownFlow.as` changed. Script counts: 420 / 407 / 400.

**Text.** `Localization.xml` (the hand-made stub) gained `MISSION_CENTER` entries under `NPC_DIALOGUE` (`INTRODUCTION`, `DIALOGUE1`), `TIPS` (`LVL_REQUEST`), `UI` (`LOADING`) and a new `POPUP` block (`LVL_REQUIRED`, `PREV_MISSION`, `FINISH_PREV`). Before this, Dave said "Error" on the panel.

**Verified in Ruffle.** Tested with a copy of a finished-tutorial save (house 701 at 320). Clicking the house opens the 练习 panel with 新兵训练1, and Dave speaks the new line. The X closes it and the house can be reopened. Note: in the browser the first click only focuses the player.

**Not changed.** Business buildings (subType 2) keep their income/citizen behaviour. Starting a level still leads to the unimplemented TD battle (open item 5).

## 14. Town plant art (2026-09-28)

**New files.** `Plant_Peashooter.swf`, `Plant_Repeater.swf`, `Plant_SnowPeashooter.swf` and `Plant_Sunflower.swf` were made by the user's friend (see `PLANT_ART.txt`). Each exports class `Plant_X`, has correct tag order, and its frames match `conf_1_.xml` `<plantAnimator>` (seedling, growing, grown). They sit in the root and are listed in `config.gz` (`build_config.py` would pick them up too). New shop icons `item_105_1_.png` and `item_118_1_.png` were cut from the art.

**SWF fix.** Only `PlantBuilding.as` changed, in all three SWFs. Its file-private `PlantTipTile.enterContainer()` never stored `initData`, so `setGrowthTime()` threw #1009 for every plant and aborted `createTownBuildList` (in Flash too). It now sets `this.initData = param1`; `super.enterContainer()` does not compile in FFDec for a file-private class. `setGrowthTime` also looks up `String(seedId)` and null-guards. New trace: `[DEBUG-PLANT]`.

**Server.**
- `_SEED_DEFS` gained 105 (Snow Pea) and 118 (Repeater).
- `_SEEDS_WITH_ART` = 101, 102, 105, 118. These are buyable once `tutorialStep >= 3`; during the tutorial only 102 is.
- `plantSettings` gained `growTime` 300 s and `growthChain` "1:0.3,2:0.4,3:0.3". Without `growthChain`, plants never left stage 1.
- `pvzData.defaultGreenPoints` = 10 (`_DEFAULT_PLANT_CAPACITY`). With 0, `addAndDrapNewItem` refused every seed.
- Plants are saved: `apply_town_queue` handles action 9 (add: `seedId`, `pos`, `pid`) and 10 (move: `pid`, `pos`; also matches the session's `clientPid`). They are stored in `save["plants"]` / `nextPlantId`, and I2001 returns them via `_town_plants()`.

**Verified.** In Ruffle, a finished-tutorial save with all four plants at different stages renders correctly with no errors, and the counter reads 4/10. `apply_town_queue` was unit-tested (add, duplicate position rejected, unknown seed rejected, move), as was the shop gating.

**Not verified / open.**
- Buying and planting through the shop in the running game, because in Ruffle the shop shelves are still empty (section 12).
- Harvesting, and removing a plant, are not handled on the server.
- Seeds are not charged on the server.

## 15. Planting reply: services.I2017 (2026-09-28)

The user hit `TypeError #1010 at Manager/__onPlantComplete()` when planting. Planting sends the queue (I2012 action 9) and then `sendAndCall("services.I2017", __onPlantComplete, seedId, position)`. `__onPlantComplete` reads `param1.plant.id` / `.position` with no guard. The server had no I2017 handler, so the generic reply had no `plant`.

**Fix (`server.py` only; SWFs unchanged).** `i2017_payload()` runs the same `apply_town_queue` action 9, so whichever of I2012 or I2017 arrives first records the plant and the other is ignored. It returns `{"plant": {id, seedId, position, harvestTime, stealList, stealCount}}`. On failure it still returns `plant: {id: 0, position}`. The client stores `plant.id` as the plant's `buyId`, so later moves (action 10) match the saved id.

**Verified.** Real AMF requests against a test server, with a web session: the plant was saved with its id, and a bad seed id still got a safe reply. It has not been verified by planting in the running game (the Ruffle shop is still empty); waiting on the user.

## 16. TD battle: level 1 is playable (2026-09-29)

Build label `2026-09-29-td-level1`. Built from the uploaded `PvZ_Social_Offline.zip` (plant-i2017). Ten files differ from it, nothing else.

**New file `pvzTD_1_.swf`** (65910 bytes). Placeholder battle art: 131 clips, each an AS3 class `extends MovieClip`. It holds 45 plants (incl. `Plant_QK`, `Plant_Pumpkin_back`, `Plant_Qiake_back`), 15 bullets, `LawnMower` (34 frames), `PoolCleaner` (83), zombie armour `Prop_<Cone|Bucket|Paper|Flag|Door|Football|BlackFootball|Box><1|2|3>` (292 frames each), `Prop_Paper_ForDrop`, `Prop_Door_ForDrop`, and about 35 effects (`pea_bullet_effect1-3`, `Dirt1-3`, `Cherry_Bomb_Effect`, `SleepEffect`, `portal`, `rakeMc`, `tanglekelp_arm`, ...). Generated by `td_art_generator/make_td.py` (uses `swfw.py`, a small SWF writer). Rules the art must keep:
- Class name exactly as the engine asks (`PlantsConfig.PLANT_RESOURCE_LIST`, `BulletsConfig`, `ZombiesConfig` prop table, `EffectMovieManager.showEffectMc` calls).
- At least as many frames as the engine plays. Plant counts come from `PLANT_FRAME_LIST` plus constants in the plant classes (Chomper 94, Magnet-shroom 127, Cactus 95, Squash 82, Scaredy 81). `BitmapMovieClip` indexes `offsetArr[frame-1]`, so a short clip throws.
- Every frame must draw something. `BitmapUtil.drawMovieClip` bounds each frame, and an empty frame gives a null bitmap.
- Swapping in real art: same class name, at least the same frame count.

**Config.** `conf_1_.xml` newTD `commonResource`: `pvzPlant` became `pvzTD`, and `pvzBullet` is commented out (now inside pvzTD). `config.gz` lists `pvzTD`.

**SWFs.** Only `ResourceCache.as` changed, identically in all three. `getSprite`/`getDisplayObject` return `missingResource(name)` instead of throwing: a 4x4 transparent MovieClip plus a `[DEBUG-TDRES]` trace. Verified by a full re-export diff against the zip's SWFs (420 / 407 / 400 scripts, only this file differs). Note: the fallback has 1 frame, so it only protects clips that are drawn once, not animated ones.

**server.py.** Two changes:
- `PvZServerHandler.translate_path` matches path parts case-insensitively when the exact path is missing, and logs `[DEBUG-CASEFIX]`. The battle requests `conf/plantData.xml` and `conf/zombieData.xml`, but the files are `PlantData.xml` and `ZombieData.xml`. Windows hid this; on Linux/Android both 404ed and the battle ran with no plant or zombie data.
- `EXPECTED_BUILD` now also covers `pvzTD_1_.swf`.

**Data (read by `PVZXmlParser.dicParsr`).**
- `conf/PlantData.xml`: `price` (sun), `bulletId`, `bulletAtt`, `damageType` for all 37 plants. Without `bulletId`, `PlantPolicy.isShooting()` is false and Peashooters never target. `price` was 0.
- `conf/ZombieData.xml`: `hp`, `weight`, `value`, `firstAllowWave`, `propIdList`, `hpCoefficient="0.1"` for 20 zombies (original PvZ numbers). `hpCoefficient` is additive per difficulty level (`hp + hp*coef*level`).
- `Localization.xml`: 75 keys under REMINDING/TUTORIAL, REMINDING/TD, TIPS/TD, POPUP/TD, UI/TD, UI/ENERGY. `####` is the number placeholder. A missing key shows as "Error".

**Verified in Ruffle (headless Chromium), from the packaged files.** All five `[OK]` at startup. House → 练习 → 新兵训练1 → 确定 loads `PVZEntry`, then `pvzTD` + `pvzTDSound`, then `pvzUI` + `pvzScreen1` + `pvzNormalZombie`. The sod row rolls out and the mower appears. Peashooter costs 100, tutorial text shows, sun falls and can be collected. Peashooters shoot, zombies lose their heads and die. No `[DEBUG-TDRES]` lines.

**Not verified / open.**
- The rest of the level: final wave, win screen, rewards. The level panel shows 0 coins and 0 exp.
- Other levels, other plants in battle, night/pool scenes (`pvzScreen2`, `pvzScreen4`-`pvzScreen6` are not in the folder).
- `SuperChomper.swf` → `Plant_ReinforcedChomper` (currently a placeholder).
- `TombStone*` / `TombMound*` (night graves) are BitmapData lookups and are not provided yet.
- Test workflow: a copy of the package with `logLevel "info"`, `maxExecutionDuration: 120`, `autoplay "on"` in the /play page, plus Playwright. The first click after load or after a dialog often only focuses the player.

### 16a. Rebuild "-b": pvzTD class layout (2026-09-29)

The user got `VerifyError: Error #1107: The ABC data is corrupt, attempt to read out of bounds` in the Flash projector. Ruffle and FFDec accepted everything.
- A strict parser (`td_art_generator/abccheck.py` for structure, `opcheck.py` for every instruction) finds no fault in any of the 65 SWFs. The source of #1107 is therefore **not confirmed**.
- The only hand-written bytecode in the package was the class block in `pvzTD_1_.swf`. It was minimal: one script for all classes, sealed classes, no protected namespace, no base-class scope chain.
- `swfw.abc_for_classes` now emits exactly what Flash's compiler emits for a MovieClip subclass, byte-compared against the Flash-built `Plant_Peashooter.swf`: one script per class, flag 0x08 plus a protected namespace, script init that pushes Object..MovieClip before `newclass`, and scope depths 9/10/11.
- New `pvzTD_1_.swf` is 67204 bytes. Retested in Ruffle: level 1 plays.
- If #1107 still appears, the full error text (stack lines / which SWF) is needed. The other changed code is FFDec's recompiled `ResourceCache` in the three game SWFs.

## 17. Battle plant art from sprite parts (2026-09-29, plant-sprites-1)
See PLANT_SPRITES_BATTLE_2026-09-29.txt.
- `td_art_generator/poses.py` composes each plant pose from the user's
  `pvzPlant[1]-N.png` parts: a 140x150 canvas with the ground at y=140, centred at x=70.
- `make_td.py` embeds each pose once (DefineBitsLossless2 plus a bitmap-filled
  DefineShape3). `bitmap_frame()` picks a pose per engine frame from
  PLANT_FRAME_LIST state (idle / attack+fire / hurt1 / hurt2 / sleep, plus
  per-plant special cases) and adds a small bob, lean or scale.
- Clip placement: canvas ground centre -> clip (34,76), scale 0.85.
- Classes, frame counts and ABC layout are unchanged from 16a.
- Almanac fix (Blover id 33): server.py reads the displayed plant ids from PlantData.xml.

## 18. PvZ 1 FLA art (2026-09-29, pvz1-fla-art)
See PVZ1_FLA_ART_2026-09-29.txt.
- The FLAs are XFL zips with a broken central directory. `rawzip.py` walks the local headers.
- Bitmaps are `bin/*.dat` (Flash lossless 0x0503, zlib chunks, premultiplied ARGB) -> `xfldat.py`.
- `xflrender.Doc.placements(frame)` returns (image, matrix, alpha) per part. It handles
  motion tweens (decomposed interpolation), nested graphic symbols, and skips `_guide`.
- `fla_plants.SPECS` maps engine frames to FLA frames. Most plants use `offset(first idle
  frame)`. Shooters use head + body attach: head shifted by
  stem(bodyFrame) * stem(bodyStart)^-1, verified against anim_full_idle.
- SWF: every FLA image is embedded once (DefineBitsLossless2 + bitmap shape) and placed per
  frame with its full matrix (`swfw.define_sprite_raw`). FLA stage coordinates are the
  clip coordinates.
- The engine's lawn mower plays 1-17 (normal) / 18-34 (tricked), which matches LawnMower.fla exactly.
