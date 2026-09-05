"""Resolve append-only conflicts as unions. Never picks a side."""
import io,json,re,subprocess,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def stages(path):
    out={}
    for name,stg in (("ours",2),("theirs",3)):
        r=subprocess.run(["git","show",f":{stg}:{path}"],capture_output=True)
        out[name]=r.stdout.decode("utf-8",errors="replace") if r.returncode==0 else ""
    return out

def union_md(path):
    v=stages(path); seen=set(); out=[]
    for side in ("ours","theirs"):
        for b in re.split(r"\n(?=## )", v[side]):
            k=b.strip()
            if not k or k in seen: continue
            seen.add(k); out.append(b.rstrip())
    io.open(path,"w",encoding="utf-8",newline="").write("\n\n".join(out)+"\n")
    return len(out)

def union_json_map(path):
    v=stages(path); merged={}
    for side in ("ours","theirs"):
        try: d=json.loads(v[side]) or {}
        except ValueError: d={}
        for k,val in d.items():
            if k not in merged: merged[k]=val
            elif isinstance(val,dict) and isinstance(merged[k],dict):
                m=dict(merged[k])
                m["count"]=max(m.get("count",1),val.get("count",1))
                for f in ("last_seen","last_escalated"):
                    a,b=m.get(f),val.get(f)
                    m[f]=max([x for x in (a,b) if x], default=None)
                for f in ("first_seen",):
                    a,b=m.get(f),val.get(f)
                    m[f]=min([x for x in (a,b) if x], default=None)
                ks=list(dict.fromkeys((m.get("keys") or [])+(val.get("keys") or [])))[:64]
                if ks: m["keys"]=ks
                merged[k]=m
    io.open(path,"w",encoding="utf-8",newline="").write(json.dumps(merged,indent=1,ensure_ascii=False))
    return len(merged)

files=subprocess.run(["git","diff","--name-only","--diff-filter=U"],
                     capture_output=True,text=True).stdout.split()
for f in files:
    if f.endswith(".md"):
        print(f"{f}: {union_md(f)} blocks after union")
    elif f.endswith("_seen.json"):
        print(f"{f}: {union_json_map(f)} classes after union")
    elif f.endswith(".jsonl"):
        v=stages(f); seen=set(); out=[]
        for side in ("ours","theirs"):
            for line in v[side].splitlines():
                if line.strip() and line not in seen:
                    seen.add(line); out.append(line)
        io.open(f,"w",encoding="utf-8",newline="").write("\n".join(out)+"\n")
        print(f"{f}: {len(out)} lines after union")
    elif "claims/" in f:
        v=stages(f); cands=[]
        for side in ("ours","theirs"):
            try: cands.append(json.loads(v[side]))
            except ValueError: pass
        w=min(cands,key=lambda c:c.get("crossed_ts",1<<62))
        io.open(f,"w",encoding="utf-8",newline="").write(json.dumps(w))
        print(f"{f.split('/')[-1]}: kept the earlier crossing {w.get('crossed_at')}")
    else:
        print(f"{f}: UNHANDLED - needs a look")
