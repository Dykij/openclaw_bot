#!/usr/bin/env python3
import json, sys

lens = []
with open(sys.argv[1]) as f:
    for line in f:
        obj = json.loads(line.strip())
        txt = obj.get('instruction','') + ' ' + (obj.get('response','') or obj.get('output',''))
        lens.append(len(txt.split()))

lens.sort()
print(f"Count: {len(lens)}")
print(f"Mean words: {sum(lens)/len(lens):.0f}")
print(f"Median: {lens[len(lens)//2]}")
print(f"Max: {lens[-1]}")
print(f"P90: {lens[int(len(lens)*0.9)]}")
print(f"P95: {lens[int(len(lens)*0.95)]}")
print(f">128 words: {sum(1 for l in lens if l > 128)}")
print(f">256 words: {sum(1 for l in lens if l > 256)}")
print(f">512 words: {sum(1 for l in lens if l > 512)}")
