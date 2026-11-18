"""按供给安排计算各片区缺口与受影响人群。

供给安排声明可用的水厂角色和是否启用调水线路。调水按线路编号顺序
贪心分配：出口片区先满足自身需求，余量按线路能力送往缺口片区，
不是最优潮流，但结果确定、可解释。
"""

DEFAULT_ARRANGEMENTS = [
    {'name': '本地常规', 'plant_roles': ['常规'], 'transfers': False},
    {'name': '本地全部', 'plant_roles': ['常规', '备用'], 'transfers': False},
    {'name': '本地全部+调水', 'plant_roles': ['常规', '备用'], 'transfers': True},
]


def _curtail(tiers, supply):
    """按优先级从高到低供水，缺口落在最低优先级，返回削减清单。"""
    remaining = supply
    cuts = []
    for tier in sorted(tiers, key=lambda item: item['level']):
        demand = tier['demand']
        if remaining >= demand:
            remaining -= demand
            continue
        cut = demand - remaining
        served = remaining / demand if demand else 0.0
        affected = tier.get('population', 0) * (1 - served)
        cuts.append({'level': tier['level'], 'name': tier.get('name', ''),
                     'cut': round(cut, 6),
                     'affected_population': round(affected)})
        remaining = 0.0
    return cuts


def _units(district):
    units = {p['payload']['unit'] for p in district['plants'].values()}
    for lines in (district['transfers_in'], district['transfers_out']):
        units |= {line['payload']['unit'] for line in lines.values()}
    if district['priority'] is not None:
        units.add(district['priority']['payload']['unit'])
    return units


def evaluate(view, arrangements=None):
    """对每个供给安排返回各片区供需、缺口、削减与受影响人口。"""
    arrangements = arrangements or DEFAULT_ARRANGEMENTS
    districts = view['districts']
    results = {}
    for arrangement in arrangements:
        roles = set(arrangement.get('plant_roles', ['常规', '备用']))
        local, demand, tiers = {}, {}, {}
        rows = {}
        for name in sorted(districts):
            district = districts[name]
            if district['priority'] is None:
                rows[name] = {'status': '无需水记录'}
                continue
            units = _units(district)
            if len(units) > 1:
                rows[name] = {'status': '口径不符'}
                continue
            local[name] = sum(p['payload']['capacity']
                              for p in district['plants'].values()
                              if p['payload'].get('role', '常规') in roles)
            tiers[name] = district['priority']['payload']['tiers']
            demand[name] = sum(t['demand'] for t in tiers[name])
            rows[name] = {'unit': next(iter(units))}
        imported = {name: 0.0 for name in local}
        exported = {name: 0.0 for name in local}
        flows = []
        if arrangement.get('transfers'):
            lines = {}
            for district in districts.values():
                for line_id, rec in district['transfers_out'].items():
                    lines[line_id] = rec
            for line_id in sorted(lines):
                payload = lines[line_id]['payload']
                if payload.get('status', '启用') != '启用':
                    continue
                exporter, importer = payload['from'], payload['to']
                if exporter not in local or importer not in local:
                    continue
                surplus = local[exporter] - exported[exporter] + imported[exporter] - demand[exporter]
                deficit = demand[importer] - local[importer] + exported[importer] - imported[importer]
                amount = round(min(payload['capacity'],
                                   max(0.0, surplus), max(0.0, deficit)), 6)
                if amount <= 0:
                    continue
                exported[exporter] += amount
                imported[importer] += amount
                flows.append({'line': line_id, 'from': exporter,
                              'to': importer, 'amount': amount})
        for name in local:
            supply = round(local[name] - exported[name] + imported[name], 6)
            gap = round(max(0.0, demand[name] - supply), 6)
            cuts = _curtail(tiers[name], supply)
            rows[name].update({
                'status': '已评估',
                'demand': round(demand[name], 6),
                'local_supply': round(local[name], 6),
                'imported': round(imported[name], 6),
                'exported': round(exported[name], 6),
                'supply': supply, 'gap': gap, 'curtailment': cuts,
                'affected_population': sum(c['affected_population'] for c in cuts)})
        results[arrangement['name']] = {'districts': rows, 'flows': flows}
    return results
