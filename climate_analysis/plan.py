"""形成并保留限水方案，区分证据变化与实际保障能力变化。

方案按 known_at 时点的证据形成并留存。之后卫星资料缺测、调水线路
停用或水厂报表修订时：报表类记录的修订只改变掌握的资料，归为证据
变化；调水线路状态或能力改变实际保障能力，归为能力变化。两类变化
都不改动已保留的方案，只把受影响片区列入重新审议清单。
"""
import hashlib
import json

from .allocation import evaluate
from .network import empty_district

CLASSIFICATION = {'anomaly': '证据变化', 'plant': '证据变化',
                  'priority': '证据变化', 'transfer': '能力变化'}


def _fingerprint(payload):
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


def _anomaly_info(district):
    rec = district['anomaly']
    if rec is None:
        return {'status': '缺测', 'detail': '无适用卫星记录'}
    if rec['payload'].get('value') is None:
        return {'status': '缺测', 'detail': '卫星资料缺测',
                'record': rec['id'], 'revision': rec['revision']}
    return {'status': '正常', 'value': rec['payload']['value'],
            'unit': rec['payload'].get('unit'),
            'record': rec['id'], 'revision': rec['revision']}


def _sources(district):
    refs = []
    for rec in (district['anomaly'], district['priority']):
        if rec is not None:
            refs.append(rec['source']['sha256'])
    for group in ('plants', 'transfers_in', 'transfers_out'):
        refs += [rec['source']['sha256'] for rec in district[group].values()]
    return sorted(set(refs))


def propose(view, arrangement, arrangements=None):
    """按指定供给安排形成限水方案；异常只作触发证据，缺口决定限水。"""
    table = evaluate(view, arrangements)[arrangement]['districts']
    entries = []
    for name in sorted(table):
        district = view['districts'][name]
        row = table[name]
        info = _anomaly_info(district)
        if row['status'] != '已评估':
            entries.append({'district': name, 'status': row['status'],
                            'anomaly': info})
            continue
        cuts = row['curtailment']
        entries.append({
            'district': name, 'status': '已评估',
            'action': '限水' if row['gap'] > 0 else '常态',
            'anomaly': info, 'unit': row['unit'],
            'demand': row['demand'], 'supply': row['supply'], 'gap': row['gap'],
            'restrict_from_level': min((c['level'] for c in cuts), default=None),
            'affected_population': row['affected_population'],
            'sources': _sources(district)})
    plan = {'known_at': view['known_at'], 'period': view['period'],
            'arrangement': arrangement, 'districts': entries}
    plan['fingerprint'] = _fingerprint(plan)
    return plan


def _reason(record_kind, detail, *recs):
    refs = sorted({r['source']['sha256'] for r in recs if r})
    return {'kind': CLASSIFICATION[record_kind], 'detail': detail,
            'record': next(r['id'] for r in recs if r), 'sources': refs}


def _diff_district(before, after):
    """比较单片区两时点的证据视图，返回变化原因清单。"""
    reasons = []
    b_ano, a_ano = before['anomaly'], after['anomaly']
    if (b_ano is None) != (a_ano is None):
        reasons.append(_reason('anomaly', '卫星记录适用性变化', b_ano, a_ano))
    elif b_ano and a_ano and b_ano['payload'] != a_ano['payload']:
        b_val, a_val = b_ano['payload'].get('value'), a_ano['payload'].get('value')
        if a_val is None:
            detail = '卫星资料缺测'
        elif b_val is None:
            detail = '卫星资料恢复'
        else:
            detail = '卫星异常值修订'
        reasons.append(_reason('anomaly', detail, b_ano, a_ano))
    b_plants, a_plants = before['plants'], after['plants']
    for pid in sorted(b_plants.keys() | a_plants.keys()):
        b, a = b_plants.get(pid), a_plants.get(pid)
        if b is None or a is None:
            reasons.append(_reason('plant', '水厂记录适用性变化', b, a))
        elif b['payload'] != a['payload']:
            if b['payload'].get('capacity') != a['payload'].get('capacity'):
                reasons.append(_reason('plant', '水厂报表修订', b, a))
            else:
                reasons.append(_reason('plant', '水厂记录修订', b, a))
    b_lines = {**before['transfers_in'], **before['transfers_out']}
    a_lines = {**after['transfers_in'], **after['transfers_out']}
    for lid in sorted(b_lines.keys() | a_lines.keys()):
        b, a = b_lines.get(lid), a_lines.get(lid)
        if b is None or a is None:
            reasons.append(_reason('transfer', '调水线路适用性变化', b, a))
        elif b['payload'] != a['payload']:
            b_st = b['payload'].get('status', '启用')
            a_st = a['payload'].get('status', '启用')
            if b_st != a_st:
                detail = '调水线路停用' if a_st == '停用' else '调水线路恢复'
            else:
                detail = '调水能力修订'
            reasons.append(_reason('transfer', detail, b, a))
    b_pri, a_pri = before['priority'], after['priority']
    if (b_pri is None) != (a_pri is None):
        reasons.append(_reason('priority', '需水记录适用性变化', b_pri, a_pri))
    elif b_pri and a_pri and b_pri['payload'] != a_pri['payload']:
        reasons.append(_reason('priority', '需水申报修订', b_pri, a_pri))
    return reasons


def review(plan, before, after, arrangements=None):
    """保留原方案，比较两时点证据视图，列出需重新审议的片区。"""
    current = evaluate(after, arrangements)[plan['arrangement']]['districts']
    planned = {e['district']: e for e in plan['districts']}
    names = sorted(before['districts'].keys() | after['districts'].keys())
    re_review, unchanged = [], []
    for name in names:
        reasons = _diff_district(before['districts'].get(name, empty_district()),
                                 after['districts'].get(name, empty_district()))
        if not reasons:
            unchanged.append(name)
            continue
        re_review.append({
            'district': name,
            'reasons': reasons,
            'capability_changed': any(r['kind'] == '能力变化' for r in reasons),
            'gap_in_plan': planned.get(name, {}).get('gap'),
            'gap_if_recomputed': current.get(name, {}).get('gap')})
    re_review.sort(key=lambda item: (not item['capability_changed'], item['district']))
    kept = json.loads(json.dumps(plan, ensure_ascii=False))
    return {'period': plan['period'], 'arrangement': plan['arrangement'],
            'kept_plan': kept, 're_review': re_review, 'unchanged': unchanged}
