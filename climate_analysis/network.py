"""按明确期间汇集片区供给网络的证据视图。

卫星储水异常、地面水厂、跨区调水线路和用水优先级四类记录都带明确
period（start、end），只有完整覆盖规划期间的版本进入视图，其余列入
排除清单；卫星异常缺测的片区在视图中保留但显式可见。
"""
from .evidence import records


def _covers(span, period):
    return span['start'] <= period['start'] and span['end'] >= period['end']


def empty_district():
    return {'anomaly': None, 'plants': {}, 'transfers_in': {},
            'transfers_out': {}, 'priority': None}


def view(db, known_at, period):
    """汇集 known_at 时点已知、期间覆盖规划期间的供给网络证据。"""
    excluded = []

    def applicable(kind):
        out = []
        for rec in records(db, kind, known_at):
            span = rec['payload'].get('period')
            if not span or not _covers(span, period):
                excluded.append({'id': rec['id'], 'kind': kind,
                                 'reason': '期间不覆盖规划期间'})
                continue
            out.append(rec)
        return out

    districts = {}

    def slot(region):
        return districts.setdefault(region, empty_district())

    for rec in applicable('anomaly'):
        region = rec['payload']['region']
        current = slot(region)['anomaly']
        if current is None or (rec['valid_from'], rec['id']) >= (current['valid_from'], current['id']):
            slot(region)['anomaly'] = rec
    for rec in applicable('plant'):
        slot(rec['payload']['region'])['plants'][rec['id']] = rec
    for rec in applicable('transfer'):
        payload = rec['payload']
        slot(payload['to'])['transfers_in'][rec['id']] = rec
        slot(payload['from'])['transfers_out'][rec['id']] = rec
    for rec in applicable('priority'):
        slot(rec['payload']['region'])['priority'] = rec
    return {'known_at': known_at, 'period': dict(period),
            'districts': districts, 'excluded': excluded}
