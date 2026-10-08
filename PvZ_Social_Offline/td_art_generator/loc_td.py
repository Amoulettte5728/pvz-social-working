# -*- coding: utf-8 -*-
"""Add the TD battle's text keys to the hand-made Localization.xml stub."""
import sys, re
T = {
 ('REMINDING','TUTORIAL'): {
  'CLICK_TO_SELECT_CARD':'点击卡片选择一个植物!', 'CLICK_TO_PLANT':'点击草地,把植物种下去!',
  'WELL_DONE':'干得好!', 'DEFEND':'不要让僵尸进入你的房子!', 'MORE_SUN':'你需要更多的阳光来种植物。',
  'CLICK_TO_COLLET_SUN':'点击掉落的阳光来收集它!', 'ENOUGH_SUN':'阳光够了!',
  'ANOTHER_PEASHOOTER':'再种一棵豌豆射手吧!', 'SUNFLOWER_IS_IMPORTANT':'向日葵非常重要,它能产生阳光!',
  'PLANT_THREE_SUNFLOWERS':'至少种三棵向日葵!', 'CLICK_TO_PICK_SHOVEL':'点击铲子把它拿起来。',
  'CLICK_TO_SHOVEL':'点击一棵植物把它铲掉。', 'CONTINUE_SHOVEL':'继续铲掉其余的植物。',
  'FIRST_ARENA_COMPLETE':'恭喜你完成了第一场比赛!'},
 ('REMINDING','TD'): {
  'GRAVEBUSTER_ON_TOMB':'墓碑吞噬者只能种在墓碑上。', 'LILYPAD_IN_WATER':'睡莲只能种在水里。',
  'LILY_PAD_FIRST':'要先在水里种睡莲。', 'MORE_ZOMBIES':'更多的僵尸来了!', 'ON_SHROOM':'只能种在蘑菇上。',
  'POTATO_ON_GROUND':'只能种在地面上。', 'SEASHROOM_IN_WATER':'海蘑菇只能种在水里。',
  'SPIKE_WEED_ON_GROUND':'地刺只能种在地面上。', 'SURVIVE_FIVE_FLAG':'坚持过五面旗帜!',
  'TAN_IN_WATER':'缠绕水草只能种在水里。'},
 ('TIPS','TD'): {
  'IN_CD':'冷却中', 'LEFT_BRACKET':'(', 'RIGHT_BRACKET':')', 'OR':'或者',
  'NEED_GEMS':'需要####宝石', 'NEED_LEVEL':'需要等级####', 'NEED_LEVEL_2':'等级达到####',
  'NEED_MONEY':'需要####金币', 'NEED_PARENT':'需要先种下前置植物', 'NOT_COMMEND':'不推荐使用',
  'NOT_ENOUGH_SUN':'阳光不足', 'NOT_SELECT':'不能选择', 'SLEEP_IN_DAY':'白天会睡觉', 'UNLOCK_SLOT':'解锁卡槽'},
 ('POPUP','TD'): {
  'CANNOT_UNLOCK_MON':'金币不足,需要####金币才能解锁。', 'CONFIRM_EXIT':'确定要退出本关吗?',
  'CONFIRM_UNLOCK':'确定花费####金币解锁吗?', 'WITHOUT_POT':'屋顶上要先种花盆。',
  'WITHOUT_SUN':'阳光不足!', 'WITHOUT_WATER':'这里没有水。'},
 ('UI','ENERGY'): {'TD_ENERGY_NOT_ENOUGH':'能量不足。'},
 ('UI','TD'): {
  'GAME_WIN':'胜利!', 'GAME_OVER':'游戏结束', 'SUN':'阳光', 'TIME':'时间', 'SCORE':'分数', 'SCORE_MUTLI':'分数 x####',
  'SURVIVAL_FLAG':'第####面旗帜', 'TIME_PRIZE_UNIT':'####秒',
  'SCENE_TD_COIN':'金币 +####', 'SCENE_TD_EXP':'经验 +####', 'SCENE_EXTRA_COIN_AND_EXP':'额外金币和经验 +####',
  'TD_PROP_PRIZE_MONEY':'金币 +####', 'TD_PROP_PRIZE_EXP':'经验 +####', 'TD_PROP_PRIZE_EXP_AND_MONEY':'额外金币和经验 +####',
  'CARD_CD_REFRESH':'卡片冷却已刷新', 'CARD_SOLT_UNLOCK_TIPS':'确定花费####宝石解锁卡槽吗?',
  'CARD_SOLT_UNLOCK_NO_GEM':'宝石不足,需要####宝石。', 'CARD_SOLT_UNLOCK_MONEY_TIPS':'确定花费####金币解锁卡槽吗?',
  'BOOST_LOCK_LEVEL':'等级####解锁', 'BOOST_LOCK_REQUIRED_OR':'或者', 'BOOST_LOCK_UNLOCK':'解锁',
  'BOOST_SOLT_UNLOCK_TIPS':'确定花费####宝石解锁这个格子吗?', 'BOOST_SOLT_UNLOCK_NO_GEM':'宝石不足,需要####宝石。',
  'BOOST_SOLT_UNLOCK_PREVONE':'请先解锁前一个格子。', 'BUY_BOOST_NO_MONEY':'金币不足,需要####金币。',
  'UNLOCK_BOOST_TIPS':'确定花费####宝石提前解锁吗?', 'UNLOCK_BOOST_NO_MONEY':'宝石不足,需要####宝石。',
  'BRING_IT_ON_BT_TIPS':'准备好了就点击开战!', 'MUTLI_ZOMBIE_TIPS':'这次会有很多僵尸!',
  'RAMPAGE_TIPS_OF_VASE':'打碎罐子看看里面有什么!'},
}
p = sys.argv[1]
raw = open(p, 'rb').read(); bom = raw.startswith(b'\xef\xbb\xbf')
s = raw.decode('utf-8-sig'); nl = '\r\n' if '\r\n' in s else '\n'
added = 0
for (mod, child), kv in T.items():
    mm = re.search(r'<%s>(.*?)</%s>' % (mod, mod), s, re.S)
    if not mm:
        s = s.replace('</Lang>', '\t<%s>%s\t</%s>%s</Lang>' % (mod, nl, mod, nl)); mm = re.search(r'<%s>(.*?)</%s>' % (mod, mod), s, re.S)
    block = mm.group(1)
    cm = re.search(r'<%s>(.*?)</%s>' % (child, child), block, re.S)
    lines = ''.join('\t\t\t<%s>%s</%s>%s' % (k, v, k, nl) for k, v in kv.items() if '<%s>' % k not in (cm.group(1) if cm else ''))
    added += lines.count('</')
    if not lines:
        continue
    if cm:
        nb = block.replace('</%s>' % child, lines + '\t\t</%s>' % child, 1)
    else:
        nb = block + '\t\t<%s>%s%s\t\t</%s>%s' % (child, nl, lines, child, nl)
    s = s[:mm.start(1)] + nb + s[mm.end(1):]
open(p, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + s.encode('utf-8'))
print('added', added)
