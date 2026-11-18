"""从本地合成资料形成已知时点的指标报告或限水方案审议。"""
import argparse
import json
from pathlib import Path

from .evidence import connect, receive
from .report import generate, difference


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['inspect', 'plan'])
    parser.add_argument('input')
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding='utf8'))
    db = connect(':memory:')
    for doc in data['documents']:
        receive(db, doc)
    if args.command == 'inspect':
        before, after = [generate(db, t) for t in data['known_at']]
        out = {'before': before, 'after': after,
               'change': difference(before, after)}
    else:
        from .network import view
        from .allocation import evaluate
        from .plan import propose, review
        t1, t2 = data['known_at']
        before = view(db, t1, data['period'])
        after = view(db, t2, data['period'])
        chosen = data.get('plan_arrangement', '本地全部+调水')
        plan = propose(before, chosen, data.get('arrangements'))
        out = {'period': data['period'],
               'arrangements': evaluate(before, data.get('arrangements')),
               'excluded': before['excluded'],
               'plan': plan,
               'review': review(plan, before, after, data.get('arrangements'))}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    db.close()


if __name__ == '__main__':
    main()
