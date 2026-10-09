#!/usr/bin/env python3
"""
Run this once from inside your game folder (next to main.swf / server.py).
It scans whatever .swf and .xml files are actually sitting in this folder
and generates:

  - config.gz         (gzip'd XML the client fetches right after login;
                        tells it where every swfId/xmlId actually lives)
  - Localization.xml   (empty stub - we don't have the real one, this just
                        stops the loader from hanging waiting for it)
  - conf/PropData.xml, pvz/conf/pvzBulletData.xml
                       (copied from your uploads, at the exact hardcoded
                        paths the tower-defense module's offline mode asks
                        for; conf/PlantData.xml, conf/ZombieData.xml and
                        conf/BoostData.xml are NOT in your upload set, so
                        those three are still gaps - see the printed report)

Safe to re-run any time you add more files; it always rebuilds from
scratch based on what's currently in this folder.
"""
import glob
import gzip
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))


def swf_entries():
    entries = []
    for path in sorted(glob.glob(os.path.join(HERE, "*.swf"))):
        fname = os.path.basename(path)
        if fname == "main.swf":
            continue
        swf_id = fname[:-4]
        if swf_id.endswith("_1_"):
            swf_id = swf_id[:-3]
        entries.append((swf_id, fname))
    return entries


def img_entries():
    # Item/prop icons (e.g. item_1006_1_.png -> id "item_1006"), looked up by
    # DataManager.imgList[propData.img] from GamePropItem_1_.xml's img="..."
    # field - same swf/-stripping id convention as swf_entries() above.
    # CardBigImage_*.jpg (e.g. CardBigImage_12_1_.jpg -> id "CardBigImage_12")
    # is the same mechanism for the OTHER image field, bigImg - used by the
    # almanac's card-detail view (CardDetailPanel.as:
    # imgList[propItemsConfigMap.get(cardId).bigImg]), confirmed against
    # GamePropItem_1_.xml's own bigImg="CardBigImage_N" attributes.
    # zombieBigImage_*.jpg is the zombie-almanac equivalent of that bigImg
    # field (ZombieDetailPanel.as: imgList[zombieNode.@bigImg] - the
    # attribute will live in ZombieData.xml once that exists, not here).
    # zombieCard_*.jpg is DIFFERENT: ZombieTile.as builds the id as a
    # literal "zombieCard_" + zombie id, not read from any XML attribute at
    # all - still needs registering here the same way, just isn't tied to
    # a specific XML field the way the other three are.
    # item_*.jpg is a SEPARATE set from item_*.png above - the almanac
    # reference cards (category=2 in GamePropItem_1_.xml, img="item_N" same
    # as the shop icons use, just a different file per resourceId - the two
    # sets don't overlap in practice, shop icons are 101-116ish, almanac
    # cards are 1-75ish) - same imgList mechanism, same id convention.
    entries = []
    for pattern in ("item_*.png", "item_*.jpg", "CardBigImage_*.jpg", "zombieBigImage_*.jpg", "zombieCard_*.jpg"):
        for path in sorted(glob.glob(os.path.join(HERE, pattern))):
            fname = os.path.basename(path)
            img_id = os.path.splitext(fname)[0]
            if img_id.endswith("_1_"):
                img_id = img_id[:-3]
            entries.append((img_id, fname))
    return entries


# xml ids the decompiled Flow.as asks for by name, mapped to whatever file
# you actually uploaded for each (edit the right-hand side if yours differ)
XML_ID_TO_FILE = {
    "conf": "conf_1_.xml",
    "Localization": "Localization.xml",       # generated stub, see below
    "GamePropItem": "GamePropItem_1_.xml",
    "QuestList": "QuestList_1_.xml",
    "EventList": "EventList_1_.xml",
    "FeedPost": "FeedPost_1_.xml",
    "PropData": "PropData_1_.xml",
    "pvzBulletData": "pvzBulletData_1_.xml",
}


def build_config_xml():
    swf_lines = []
    for swf_id, fname in swf_entries():
        url = f"local/swf/v1/{fname}"
        swf_lines.append(f'    <swf id="{swf_id}" url="{url}"/>')

    xml_lines = []
    for xml_id, fname in XML_ID_TO_FILE.items():
        if os.path.exists(os.path.join(HERE, fname)):
            url = f"local/swf/v1/{fname}"
            xml_lines.append(f'    <xml id="{xml_id}" url="{url}"/>')

    img_lines = []
    for img_id, fname in img_entries():
        url = f"local/swf/v1/{fname}"
        img_lines.append(f'    <img id="{img_id}" url="{url}"/>')

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<config>
  <version>offline-1</version>
  <swfList>
{chr(10).join(swf_lines)}
  </swfList>
  <xmlList>
{chr(10).join(xml_lines)}
  </xmlList>
  <imgList>
{chr(10).join(img_lines)}
  </imgList>
  <musicList></musicList>
  <cryptlist></cryptlist>
</config>
"""
    return xml


def main():
    report = []

    # Create the Localization.xml stub FIRST - build_config_xml() below only
    # lists an xml entry if the file already exists on disk, so this has to
    # happen before we scan, or the entry gets silently left out.
    loc_path = os.path.join(HERE, "Localization.xml")
    if not os.path.exists(loc_path):
        with open(loc_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<Lang></Lang>\n')
        report.append("[ok] Localization.xml stub created (empty - no real UI text)")

    xml = build_config_xml()
    with gzip.open(os.path.join(HERE, "config.gz"), "wb") as f:
        f.write(xml.encode("utf-8"))
    report.append(f"[ok] config.gz written ({len(swf_entries())} swf entries, {len(img_entries())} img entries)")

    # Hardcoded TD-module offline-mode paths (from PVZEntry.as's
    # onAddToStageInDebugMode). These are requested directly, not looked up
    # via config.gz, so they must exist at these literal relative paths.
    os.makedirs(os.path.join(HERE, "conf"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "pvz", "conf"), exist_ok=True)

    copies = [
        ("PropData_1_.xml", "conf/PropData.xml"),
        ("pvzBulletData_1_.xml", "pvz/conf/pvzBulletData.xml"),
    ]
    for src, dst in copies:
        src_path = os.path.join(HERE, src)
        dst_path = os.path.join(HERE, dst)
        if os.path.exists(src_path):
            shutil.copyfile(src_path, dst_path)
            report.append(f"[ok] {dst} <- {src}")
        else:
            report.append(f"[skip] {dst}: source {src} not found")

    missing = ["conf/PlantData.xml", "conf/ZombieData.xml", "conf/BoostData.xml"]
    report.append("[gap] not in your uploads, will 404 once you reach a TD battle: "
                   + ", ".join(missing))

    print("\n".join(report))


if __name__ == "__main__":
    main()
