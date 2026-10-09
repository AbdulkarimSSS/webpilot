import json, os
from scenarios import SCENARIOS

out = os.path.join(os.path.dirname(__file__), '..', 'expected')
os.makedirs(out, exist_ok=True)
for sid, sc in SCENARIOS.items():
    exp = sc.get('expected', {})
    path = os.path.join(out, f'{sid}_expected.json')
    with open(path,'w') as f:
        json.dump(exp, f, indent=2, ensure_ascii=False)
    print('wrote', sid)
