"""Resolve append-only conflicts as unions. Never picks a side."""
import io,json,re,subprocess,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def _n(x,d=0):
    try: return float(x)
    except (TypeError,ValueError): return d

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
    elif f.endswith("_ping_budget.json"):
        # A rolling window of ping timestamps per channel, used as a rate
        # limiter. Union both sides: recording MORE pings can only throttle
        # harder, which is the fail-safe direction for a notifier. Bounded so
        # the file cannot grow without limit.
        v=stages(f); m={}
        for side in ("ours","theirs"):
            try: d=json.loads(v[side]) or {}
            except ValueError: d={}
            for k,lst in d.items():
                m.setdefault(k,[]).extend(lst or [])
        for k in m:
            seen2,keep=set(),[]
            for item in sorted(m[k], key=lambda x: x[0] if isinstance(x,(list,tuple)) else 0):
                key=json.dumps(item,sort_keys=True)
                if key not in seen2: seen2.add(key); keep.append(item)
            m[k]=keep[-16:]
        io.open(f,"w",encoding="utf-8",newline="").write(json.dumps(m))
        print(f"{f}: {sum(len(x) for x in m.values())} ping stamps after union")
    elif f.endswith("quarantine.json"):
        # per contract. A quarantine is a fact about the pair, so the EARLIEST
        # rejection wins and its original reason is preserved; hits add up.
        v=stages(f); m={}
        for side in ("ours","theirs"):
            try: d=json.loads(v[side]) or {}
            except ValueError: d={}
            for k,r in d.items():
                if k not in m: m[k]=dict(r); continue
                a=m[k]
                first = a if _n(a.get("first_ts"),1<<62) <= _n(r.get("first_ts"),1<<62) else r
                m[k]={"confidence": first.get("confidence"),
                      "detail": first.get("detail"),
                      "first_ts": int(min(_n(a.get("first_ts"),1<<62),_n(r.get("first_ts"),1<<62))),
                      "first_horizon_h": first.get("first_horizon_h"),
                      "last_ts": int(max(_n(a.get("last_ts")),_n(r.get("last_ts")))),
                      "hits": int(max(_n(a.get("hits"),1),_n(r.get("hits"),1)))}
        io.open(f,"w",encoding="utf-8",newline="").write(json.dumps(m,indent=1,ensure_ascii=False))
        print(f"{f}: {len(m)} quarantined contracts after union")
    elif f.endswith("liveness.json"):
        # per component: counts are per-writer so max is a lower bound; the
        # monthly jsonl ledger stays the durable record.
        v=stages(f); m={}
        for side in ("ours","theirs"):
            try: d=json.loads(v[side]) or {}
            except ValueError: d={}
            for k,r in d.items():
                if k not in m: m[k]=dict(r); continue
                a=m[k]
                ts=[_n(x) for x in (a.get("first_ts"),r.get("first_ts")) if x]
                m[k]={"last_ts": int(max(_n(a.get("last_ts")),_n(r.get("last_ts")))),
                      "last_at": max([x for x in (a.get("last_at"),r.get("last_at")) if x], default=None),
                      "count": int(max(_n(a.get("count")),_n(r.get("count")))),
                      "first_ts": int(min(ts)) if ts else None,
                      "detail": a.get("detail") if a.get("detail") is not None else r.get("detail")}
        io.open(f,"w",encoding="utf-8",newline="").write(json.dumps(m,indent=1,ensure_ascii=False))
        print(f"{f}: {len(m)} components after union")
    elif f.endswith("active.json"):
        # per contract: keep the side that watched it longer, then repair the
        # fields where "more" is unambiguous.
        v=stages(f); m={}
        def _nc(c): return len(c) if isinstance(c,(list,tuple)) else int(_n(c))
        for side in ("ours","theirs"):
            try: d=json.loads(v[side]) or {}
            except ValueError: d={}
            for k,r in d.items():
                if k not in m: m[k]=dict(r); continue
                a=m[k]
                keep=a if _nc(a.get("checks"))>=_nc(r.get("checks")) else r
                mg=dict(keep)
                mg["peak_fdv"]=max(_n(a.get("peak_fdv")),_n(r.get("peak_fdv"))) or None
                at=[_n(x) for x in (a.get("added_ts"),r.get("added_ts")) if x]
                if at: mg["added_ts"]=int(min(at))
                ac,rc=a.get("checks"),r.get("checks")
                if isinstance(ac,(list,tuple)) or isinstance(rc,(list,tuple)):
                    seen2,chk=set(),[]
                    for c in (ac if isinstance(ac,(list,tuple)) else [])+(rc if isinstance(rc,(list,tuple)) else []):
                        kk=json.dumps(c,sort_keys=True)
                        if kk not in seen2: seen2.add(kk); chk.append(c)
                    mg["checks"]=chk
                else:
                    mg["checks"]=max(_nc(ac),_nc(rc))
                m[k]=mg
        io.open(f,"w",encoding="utf-8",newline="").write(json.dumps(m,indent=1,sort_keys=True,ensure_ascii=False))
        print(f"{f}: {len(m)} positions after union")
    else:
        print(f"{f}: UNHANDLED - needs a look")
