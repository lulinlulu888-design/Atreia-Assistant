"""Reviewed Steam 26262663 differences; never apply by key alone."""
import hashlib
import re

EXACT = {
    'Abyssal Portal': '深渊传送门',
    'An item used to unlock the Battle Pass.': '用于解锁守护者通行证的道具。',
    "Atreia's Call": '亚特雷亚的呼唤',
    'Basic': '基础', 'Premium': '高级', 'Prelude to Flight': '飞翔序曲',
    'Collect 6 Types of Unique Expedition Artwork': '收集6种唯一远征画作',
    "Daeva's Styling Chest (Bound)": '守护者造型宝箱（绑定）',
    'Date/Time Achieved: {0} UTC': '达成时间：{0} UTC',
    'Deals MP Damage and restores MP on hitting a target afflicted with Fear': '攻击处于恐惧状态的目标时，造成精神力伤害并恢复精神力',
    'Disables Physical Skill use': '无法使用物理技能',
    "Grants the Ultimate Founder's Pack as a reward.": '可获得终极先驱礼包奖励。',
    'Increases Block and restores HP': '提高盾牌防御并恢复生命力',
    "Ludra's Subspace Entrance": '鲁德拉的异空间入口',
    "Moving to Ludra's Subspace...": '正在前往鲁德拉的异空间...',
    'Obtain 5 of one type of Soul Crystal among Cogni, Fera, Natura, and Varian.': '获得知性、野性、自然、变形灵魂结晶中的任意一种，共5个。',
    'Odyle Energy Cube': '奥德能量宝箱',
    'Odylium Repository Crystal Chest (Bound)': '奥德石储藏所结晶宝箱（绑定）',
    'Operating Odyle Energy Cube...': '正在启动奥德能量宝箱...',
    'Operating the Abyssal Portal...': '正在启动深渊传送门...',
    'Reduces HP absorbed from player active skills.': '减少玩家主动技能的生命力吸收量。',
    'Restores <desc_point>{abe:190044011:value02:divide100}%</> HP and MP': '恢复<desc_point>{abe:190044011:value02:divide100}%</>生命力和精神力',
    'Restores HP when HP is 1% or less': '生命力低于或等于1%时恢复生命力',
    'Secret Teatime Weapon Skin (Bound)': '秘密茶会武器外形（绑定）',
    'A chest containing a Secret Teatime Weapon Skin.\nGrants a Weapon Skin suitable for your class.': '装有秘密茶会武器外形的宝箱。\n可获得适合自身职业的武器外形。',
    'Special gemstone valued by the Shugo Merchants.\nCan be used to purchase special goods from the Shugo Merchants.': '术古商团珍视的特殊宝石。\n可用于向术古商团购买特殊商品。',
    'This item grants Battle Pass EXP.': '使用后可获得守护者通行证经验值。',
    "Ultimate Founder's Pack": '终极先驱礼包',
    '[{0}][{1}] {2}': '[{0}][{1}] {2}',
    'A chest containing a recharge ticket that can be used to recharge reward count and final boss kill count for Expedition/Transcendence.\n\n[Available Dungeons]\nExpedition - Conquest\nTranscendence': '装有远征/超越次数补充券的宝箱，可补充奖励领取次数和最终首领击杀次数。\n\n[适用副本]\n远征－征服\n超越',
}

ITEMS = {
    'Power Shard': '封魂石', 'Battle Enhance Scroll': '战斗强化咒文书',
    'Life Crystal': '生命结晶', 'Resurrection Spiritstone': '复活灵石',
    'Odyle Energy': '奥德能量', 'Small Odyle Energy': '小型奥德能量',
    'Content Usage Ticket Selection Chest': '玩法使用券自选箱',
    'Expedition Challenge Ticket Selection Chest': '远征挑战券自选箱',
    'Expedition/Transcendence Challenge Ticket Selection Chest': '远征/超越挑战券自选箱',
}

SKILLS = {
    '1e6b97056412eefcfee44f06625e144d3d8e874378b3bc52fd44add1838226ea': '在<desc_point>{se:216130711:effect_value01:time}</>期间，攻击力增加<desc_point>{se_abe_dmg:216130711:216130711:StatchangeTotal:none}</>，命中增加<desc_point>{se_abe_dmg:216130711:216130712:StatchangeTotal:none}</>，最大行动力增加<desc_point>{se_abe_dmg:216130711:216130713:StatchangeTotal:divide100}</>，行动力自然恢复量增加<desc_point>{se_abe_dmg:216130711:216130714:StatchangeTotal:divide100}%</>。',
    '5f4733522b53ea1c8aa711568a36d210ac6cad9a4bed8cc5f04371d1b28796cf': '跃向12m内的敌人并发动攻击，造成<desc_point>{se:4031011:SkillUIMinDmg}-{se:4031011:SkillUIMaxDmg}伤害。\n在<desc_point>{se:4031711:effect_value02:time}期间，自身物理防御提高<desc_point>20%。\n\n<system_game_system>消耗100精神力',
}
CHANTER = '使用[紧急回避]或处于飞行状态时，移动至20m内的目标并造成<chat_combat>{se_dmg:1821001021:SkillUIMinDmgSum}-{se_dmg:1821001021:SkillUIMaxDmgSum}</>伤害，有{se:1821000022:effect_value05:divide100}%的概率使目标眩晕{se:1821000022:effect_value01:time}。多段打击命中概率提高50%'
CHANTER_END = '。\n目标为NPC时，必定使其眩晕。\n\n眩晕量表伤害{se:1821000024:effect_value01}'
SKILLS['14b499ee67a1e0712733f37c6f7c2f0a8a4ec5d445161a46f1f754118ba836a7'] = CHANTER + '，并恢复{se:1821001111:effect_value01:divide100}行动力' + CHANTER_END
SKILLS['f3497b92ad3795b0a3a0fe2a1501bef751ec0e87555afdeb85c32631e39a329f'] = CHANTER + CHANTER_END


def replacement(key, source):
    if source in EXACT:
        return EXACT[source]
    if key.startswith('Skill'):
        return SKILLS.get(hashlib.sha256(source.encode('utf-8')).hexdigest())
    match = re.fullmatch(r'Kill \[(1-5 Star Officer|Commander, Supreme Commander|First-Class to Ninth-Class Soldier|General, Marshal)\] (\d+) times', source)
    if match and key.startswith('AchievementString_'):
        ranks = {'1-5 Star Officer': '一至五星将校', 'Commander, Supreme Commander': '司令官、总司令官',
                 'First-Class to Ninth-Class Soldier': '一至九等兵', 'General, Marshal': '将军、大将军'}
        return '击败[' + ranks[match[1]] + ']' + match[2] + '次'
    match = re.fullmatch(r'Waltzing with (Commanders|Generals|Officers) (I|II|III)', source)
    if match and key.startswith('AchievementString_'):
        return '与' + {'Commanders': '司令官', 'Generals': '将军', 'Officers': '将校'}[match[1]] + '共舞' + match[2]
    match = re.fullmatch(r'Season 1_2 Monthly Pass (EXP|Free Unlock|Paid Unlock)_(Asmodian|Elyos)', source)
    if match:
        return '第1赛季_2月度通行证' + {'EXP': '经验值', 'Free Unlock': '免费解锁', 'Paid Unlock': '付费解锁'}[match[1]] + '－' + {'Asmodian': '魔族', 'Elyos': '天族'}[match[2]]
    prefix = 'Contains rewards that assist Daeva in combat.\n'
    if source.startswith(prefix):
        rest = source[len(prefix):]
        mail = 'Can obtain the following items when receiving mail.\n'
        heading = '装有帮助守护者战斗的奖励。\n'
        if rest.startswith(mail):
            rest = rest[len(mail):]
            heading += '领取邮件时可获得下列道具。\n'
        if not rest.startswith('\n'):
            return None
        lines = []
        for line in rest[1:].split('\n'):
            match = re.fullmatch(r'([0-9,]+) (.+) \(Bound\)', line)
            if not match or match[2] not in ITEMS:
                return None
            lines.append(ITEMS[match[2]] + '（绑定）×' + match[1])
        return heading + '\n' + '\n'.join(lines)
    return None
