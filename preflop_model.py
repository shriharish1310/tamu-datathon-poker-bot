"""Pure Python preflop inference. No model loading inside a decision."""
from itertools import permutations
from math import isfinite

SUIT_PERMUTATIONS = tuple(permutations(range(4)))


def canonical(hole):
    return min(tuple(sorted((c & ~3) + p[c & 3] for c in hole)) for p in SUIT_PERMUTATIONS)


def features(hole):
    if len(hole) != 5 or len(set(hole)) != 5 or any(type(c) is not int or not 0 <= c < 36 for c in hole):
        return None
    ranks = [0] * 9
    suits = [0] * 4
    for c in hole:
        ranks[c >> 2] += 1
        suits[c & 3] |= 1 << (c >> 2)
    suits.sort(reverse=True)
    counts = [s.bit_count() for s in suits]
    return ([n / 4 for n in ranks] + [float(bool(s & (1 << r))) for s in suits for r in range(9)]
            + [n / 5 for n in counts] + [sum(n >= 2 for n in ranks) / 2,
              sum(n >= 3 for n in ranks), sum(bool(ranks[r] and ranks[r+1]) for r in range(8)) / 4,
              sum((s & (s >> 1)).bit_count() for s in suits) / 4, max(counts) / 5,
              sum(r * n for r, n in enumerate(ranks)) / 40])


def predict(x, model):
    if x is None:
        return None
    if model['kind'] == 'mlp':
        hidden = [max(0., b + sum(a*w for a,w in zip(x,col))) for b,col in zip(model['b1'],model['w1'])]
        value = model['b2'] + sum(a*w for a,w in zip(hidden,model['w2']))
    else:
        value = 0.
        for tree in model['trees']:
            i = 0
            while tree['left'][i] != -1:
                i = tree['left'][i] if x[tree['feature'][i]] <= tree['threshold'][i] else tree['right'][i]
            value += tree['value'][i]
        value /= len(model['trees'])
    return min(1., max(0., value)) if isfinite(value) else None
