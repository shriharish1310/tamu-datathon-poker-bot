"""Hierarchical action frequencies calibrated on all simulated decisions.

No showdown-only fitting: offline simulation reveals folded holdings as well.
Online inputs contain only public state, our cards, and sampled enemy holdings.
"""
from collections import Counter
import json
from pathlib import Path


def texture(board):
    suits=Counter(c&3 for c in board); ranks=Counter(c>>2 for c in board)
    return int(max(suits.values(),default=0)>=2)+2*int(max(ranks.values(),default=0)>=2)


def context(street,board,history,aggression,facing):
    return (int(street),texture(board),min(2,history),min(2,int(aggression*3)),int(facing))


def keys(ctx,q):
    s,t,h,a,f=ctx; b=min(4,int(q*5))
    return f'{s},{f}',f'{s},{f},{a},{b}',f'{s},{t},{h},{a},{f},{b}'


class ActionModel:
    def __init__(self,path):
        self.data=json.loads(Path(path).read_text())
        self.cache={}

    def probabilities(self,ctx,q,shrink=32):
        general,broad,fine=keys(ctx,q)
        key=(fine,shrink)
        if key in self.cache:return self.cache[key]
        g=self.data['general'].get(general,[1,4,1,1]); n=sum(g)
        prior=[(v+1)/(n+4) for v in g]
        b=self.data['broad'].get(broad,[0]*4); n=sum(b)
        prior=[(v+32*p)/(n+32) for v,p in zip(b,prior)]
        c=self.data['fine'].get(fine,[0]*4); n=sum(c)
        answer=tuple((v+shrink*p)/(n+shrink) for v,p in zip(c,prior))
        self.cache[key]=answer
        return answer
