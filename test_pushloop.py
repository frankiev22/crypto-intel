"""⛔ The runner's push loop, executed rather than read.

WHY THIS FILE EXISTS. Twice now the step whose entire job is "never lose a
collected pass" has lost one, and both times the code LOOKED right:

  2026-09-18  `git pull --rebase` stopped at the first conflict and the retry
              pushed from a half-rebased tree. Rows lost.
  2026-09-23  the fix for that lost a pass of its own to ONE FLAG.
              `git rebase --continue -q` is a usage error - git exits 129 and
              prints its usage, because --continue takes no -q. The loop sent
              that to /dev/null and followed it with `|| true`, so a malformed
              command was indistinguishable from a working one. The conflict
              resolution was CORRECT every time; the rebase was simply never
              continued, and the leftover rebase directory then triggered
              "after 10 rounds - aborting it", discarding a good resolution.
              1,304 rows went to an artifact and were recovered by hand (db4cfe0).

Reading the YAML would not have caught either. So this suite EXTRACTS the real
script out of .github/workflows/collect.yml, syntax checks it, and RUNS it
against a throwaway repository where a second writer has pushed mid-pass. It
then asserts on the pushed result: the run's commit landed, the other writer's
commit is still there, and every append-only file carries BOTH writers' rows.

That is standing rule 16 applied to the shell: verify the output, never the
execution. Offline and hermetic - a bare repo on local disk, no network, and
nothing outside a temp directory is written.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
WF = os.path.join(HERE, ".github", "workflows", "collect.yml")
ATTRS = os.path.join(HERE, ".gitattributes")
MARKER = "# \u26d4 A CONFLICT MUST NEVER DISCARD A COMPLETED PASS."

R = []


def check(label, cond, detail=""):
    R.append((label, bool(cond), detail))
    mark = "ok  " if cond else "FAIL"
    line = f"  {mark}  {label}"
    if not cond and detail:
        line += f"\n          {detail}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode("ascii"))


def section(t):
    try:
        print("\n" + t)
    except UnicodeEncodeError:
        print("\n" + t.encode("ascii", "replace").decode("ascii"))


def find_bash():
    """The workflow runs on Git Bash semantics.

    ⚠️ On Windows a bare "bash" resolves to WSL's bash.exe in System32, where
    /c/... does not exist - so the test would silently run in a different shell
    than the thing it is testing.
    """
    if os.name != "nt":
        return shutil.which("bash")
    for p in (r"C:\Program Files\Git\bin\bash.exe",
              r"C:\Program Files (x86)\Git\bin\bash.exe",
              r"C:\Program Files\Git\usr\bin\bash.exe"):
        if os.path.exists(p):
            return p
    g = shutil.which("git")
    if g:
        cand = os.path.join(os.path.dirname(os.path.dirname(g)), "bin", "bash.exe")
        if os.path.exists(cand):
            return cand
    return None


BASH = find_bash()


def posix(path):
    path = os.path.abspath(path).replace(os.sep, "/")
    if os.name == "nt" and len(path) > 1 and path[1] == ":":
        path = "/" + path[0].lower() + path[2:]
    return path


# ---------------------------------------------------------------------------
section("1. \u26d4 the script's own text: the flags that cost two passes")
src = io.open(WF, encoding="utf-8").read()

# The step's `run:` block, pulled out without needing a YAML library.
start = src.index("- name: Commit the journal")
nxt = src.index("\n      - name:", start + 10)
step = src[start:nxt]
check("the Commit the journal step is still found in the workflow", bool(step))
check("...and it still carries the never-discard-a-pass marker", MARKER in step)

loop = step[step.index(MARKER):] if MARKER in step else ""
# ⛔ THE 2026-09-23 BUG, asserted directly. git rejects --continue with -q.

# Only EXECUTABLE lines may be scanned for the bad flags. The comment above the
# loop quotes `git rebase --continue -q` deliberately, to record what went
# wrong, so a scan of the raw text fails on the documentation, not the code.
code = "\n".join(ln for ln in loop.splitlines()
                 if ln.strip() and not ln.strip().startswith("#"))

for bad in ("--continue -q", "--continue --quiet", "-q --continue", "--quiet --continue"):
    check(f"\u26d4 `git rebase {bad}` never appears in CODE (usage error, exit 129)",
          bad not in code, f"found: {bad}")
check("...and the comment still records why, so nobody re-adds it",
      "usage error" in loop and "129" in loop)
check("\u26d4 --continue's result is never thrown away with `|| true`",
      "git rebase --continue" in code and "--continue 2>&1 || true" not in code
      and "--continue >/dev/null 2>&1 || true" not in code)
check("...its exit code is captured and tested",
      "cont_rc" in code and "-ne 0" in code)
check("...and a failure it does not recognise is printed, not swallowed",
      "::error::git rebase --continue failed" in code)
check("an empty resolution is skipped rather than looped on",
      "rebase --skip" in code)
check("\u2b50 the loop asks the INDEX which paths are unmerged (git ls-files -u)",
      "git ls-files -u" in code)
check("...and every resolution says which side it kept, by name",
      "kept THIS RUN's version" in code and "kept UPSTREAM's version" in code)

attrs = io.open(ATTRS, encoding="utf-8").read()
check("*.jsonl still merges by union", "*.jsonl merge=union" in attrs)
check("\u2b50 the findings day file merges by union too (it is append-only)",
      "data/findings/*.md merge=union" in attrs)

# ---------------------------------------------------------------------------
section("2. \u2b50 and now RUN it: a second writer pushes mid-pass")
if not BASH:
    print("  SKIP  no bash found; the shell half of this suite cannot run here")
elif not shutil.which("git"):
    print("  SKIP  no git on PATH")
else:
    tmp = tempfile.mkdtemp(prefix="pushloop_")
    try:
        def sh(cmd, cwd):
            return subprocess.run([BASH, "-c", cmd], cwd=cwd,
                                  capture_output=True, text=True)

        def w(base, rel, text, mode="w"):
            p = os.path.join(base, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with io.open(p, mode, encoding="utf-8", newline="\n") as f:
                f.write(text)

        script = os.path.join(tmp, "loop.sh")
        io.open(script, "w", encoding="utf-8", newline="\n").write(
            "#!/bin/bash\nset -u\n" + loop)
        syn = subprocess.run([BASH, "-n", posix(script)], capture_output=True, text=True)
        check("\u26d4 the extracted script is valid bash (bash -n)",
              syn.returncode == 0, syn.stderr.strip()[:300])

        sh("git init -q --bare remote.git && git clone -q remote.git work", tmp)
        W = os.path.join(tmp, "work")
        sh('git config user.email r@x && git config user.name runner', W)
        shutil.copyfile(ATTRS, os.path.join(W, ".gitattributes"))
        w(W, "data/market/index.json", '{"v":1}\n')
        w(W, "data/universe/members.json", '{"n":1}\n')
        w(W, "data/log.jsonl", '{"row":"base"}\n')
        sh("git add -A && git commit -qm base && git push -q origin master", W)

        # The desktop task commits and pushes during the runner's ~10 minutes.
        sh("git clone -q remote.git other", tmp)
        O = os.path.join(tmp, "other")
        sh('git config user.email d@x && git config user.name desktop', O)
        w(O, "data/market/index.json", '{"v":2,"by":"desktop"}\n')
        w(O, "data/universe/members.json", '{"n":2}\n')
        w(O, "data/log.jsonl", '{"row":"DESKTOP"}\n', "a")
        w(O, "data/findings/2026-09-23.md",
          "## 01:00:00 UTC \u00b7 outcome-win \u00b7 DESKTOPCONTRACT\ndesktop finding\n")
        w(O, "data/milestones/claims/AAA__mcap_1m.json", '{"by":"desktop"}\n')
        sh("git add -A && git commit -qm desktop && git push -q origin master", O)

        # The runner's own pass touches the same files.
        w(W, "data/market/index.json", '{"v":3,"by":"runner"}\n')
        w(W, "data/universe/members.json", '{"n":3}\n')
        w(W, "data/log.jsonl", '{"row":"RUNNER"}\n', "a")
        w(W, "data/findings/2026-09-23.md",
          "## 01:41:00 UTC \u00b7 outcome-win \u00b7 RUNNERCONTRACT\nrunner finding\n")
        w(W, "data/milestones/claims/AAA__mcap_1m.json", '{"by":"runner"}\n')
        sh("git add -A && git commit -qm 'collect: run'", W)

        ghenv = os.path.join(tmp, "ghenv")
        io.open(ghenv, "w").write("")
        env = dict(os.environ, GITHUB_REF_NAME="master", GITHUB_ENV=ghenv,
                   GITHUB_STEP_SUMMARY=os.path.join(tmp, "ghsum"))
        run = subprocess.run([BASH, posix(script)], cwd=W, capture_output=True,
                             text=True, env=env)
        out = run.stdout + run.stderr

        check("\u2b50 the loop pushes instead of giving up", run.returncode == 0,
              f"exit {run.returncode}\n          " + out.strip()[-500:])
        check("...leaving no rebase in progress for the next step to trip over",
              not os.path.isdir(os.path.join(W, ".git", "rebase-merge"))
              and not os.path.isdir(os.path.join(W, ".git", "rebase-apply")))
        check("...and PUSH_FAILED is not set", "PUSH_FAILED" not in io.open(ghenv).read())
        check("\u26d4 it never prints the 'aborting it' path on a resolvable conflict",
              "aborting it" not in out, out.strip()[-300:])

        log = sh("git log --oneline", os.path.join(tmp, "remote.git")).stdout
        check("the run's commit reached the remote", "collect: run" in log, log.strip())
        check("...and the other writer's commit is still there", "desktop" in log, log.strip())

        sh("git clone -q remote.git after", tmp)
        A = os.path.join(tmp, "after")

        def read(rel):
            p = os.path.join(A, rel)
            if not os.path.exists(p):
                return ""
            return io.open(p, encoding="utf-8", errors="replace").read()

        jl = read("data/log.jsonl")
        check("\u2b50 the jsonl union merge kept BOTH writers' rows (rule 8)",
              '"DESKTOP"' in jl and '"RUNNER"' in jl, repr(jl))
        md = read("data/findings/2026-09-23.md")
        check("\u2b50 the findings day file kept BOTH writers' findings (rule 8)",
              "DESKTOPCONTRACT" in md and "RUNNERCONTRACT" in md, repr(md))
        for rel in ("data/findings/2026-09-23.md", "data/market/index.json",
                    "data/universe/members.json",
                    "data/milestones/claims/AAA__mcap_1m.json"):
            body = read(rel)
            check(f"no conflict markers survive in {rel}",
                  "<<<<<<<" not in body and ">>>>>>>" not in body, repr(body[:120]))
        idx = read("data/market/index.json")
        check("a whole-document json keeps THIS RUN's freshly computed version",
              '"by":"runner"' in idx, repr(idx))
        try:
            json.loads(idx)
            valid = True
        except Exception:
            valid = False
        check("...and is still parseable JSON, not two concatenated documents", valid, repr(idx))
    finally:
        # git marks pack files read-only on Windows, so plain rmtree can fail.
        def _force(func, path, _exc):
            try:
                os.chmod(path, 0o700)
                func(path)
            except Exception:
                pass
        try:
            shutil.rmtree(tmp, onexc=_force)
        except TypeError:
            shutil.rmtree(tmp, onerror=_force)

# ---------------------------------------------------------------------------
section("3. the misleading message, MEASURED on the installed git")
# ⛔ `git rebase --continue` answers UNSTAGED CHANGES with the wording of a
# CONFLICT: builtin/rebase.c calls has_unstaged_changes() and prints "You must
# edit all merge conflicts...". I hit this by hand on 2026-09-24 with an empty
# `git ls-files -u`, which is the index saying there is no conflict at all.
# ⭐ This section does not take that on trust: it reproduces the state and reads
# what THIS git actually prints, then asserts the loop guards it.
check("⭐ the loop stages unstaged paths before --continue",
      "git diff --quiet" in code and "git add -A -- ." in code)
check("...and names them rather than staging silently",
      "unstaged path(s)" in code)
check("⭐ and if it happens anyway, the log says the wording is misleading",
      "wording is MISLEADING" in code and "NO unmerged paths" in code)

if not BASH or not shutil.which("git"):
    print("  SKIP  no bash/git; the measured half cannot run here")
else:
    tmp3 = tempfile.mkdtemp(prefix="pushloop_msg_")
    try:
        def sh3(cmd):
            return subprocess.run([BASH, "-c", cmd], cwd=tmp3,
                                  capture_output=True, text=True)
        sh3("git init -q . && git config user.email t@x && git config user.name t")
        io.open(os.path.join(tmp3, "conflicted.json"), "w").write('{"v":0}' + chr(10))
        io.open(os.path.join(tmp3, "rows.jsonl"), "w").write('{"row":0}' + chr(10))
        sh3("git add -A && git commit -qm base")
        sh3("git checkout -q -b other")
        io.open(os.path.join(tmp3, "conflicted.json"), "w").write('{"v":"other"}' + chr(10))
        sh3("git commit -qam other")
        sh3("git checkout -q master")
        io.open(os.path.join(tmp3, "conflicted.json"), "w").write('{"v":"mine"}' + chr(10))
        sh3("git commit -qam mine")
        reb = sh3("git rebase other")
        check("the reproduction really is mid-rebase",
              os.path.isdir(os.path.join(tmp3, ".git", "rebase-merge"))
              or os.path.isdir(os.path.join(tmp3, ".git", "rebase-apply")),
              (reb.stdout + reb.stderr).strip()[-200:])
        # resolve the conflict properly, THEN dirty an unrelated tracked file,
        # which is what the hourly collector does to this repo continuously.
        io.open(os.path.join(tmp3, "conflicted.json"), "w").write('{"v":"resolved"}' + chr(10))
        sh3("git add conflicted.json")
        io.open(os.path.join(tmp3, "rows.jsonl"), "a").write('{"row":"late"}' + chr(10))
        unmerged = sh3("git ls-files -u").stdout.strip()
        cont = sh3("GIT_EDITOR=true git rebase --continue")
        msg = (cont.stdout + cont.stderr)
        check("⛔ MEASURED: --continue fails with NO unmerged paths in the index",
              cont.returncode != 0 and unmerged == "",
              "rc=%s unmerged=%r" % (cont.returncode, unmerged))
        check("⛔ ...and it blames merge conflicts, which is why the log lied",
              "merge conflict" in msg.lower(), msg.strip()[:200])
        # and the fix the loop now applies
        sh3("git add -A")
        cont2 = sh3("GIT_EDITOR=true git rebase --continue")
        check("⭐ staging the unstaged rows is all it took",
              cont2.returncode == 0,
              (cont2.stdout + cont2.stderr).strip()[-200:])
        check("...and the late row is in the commit, not lost (rule 8)",
              '"late"' in io.open(os.path.join(tmp3, "rows.jsonl")).read())
    finally:
        def _f3(func, path, _exc):
            try:
                os.chmod(path, 0o700)
                func(path)
            except Exception:
                pass
        try:
            shutil.rmtree(tmp3, onexc=_f3)
        except TypeError:
            shutil.rmtree(tmp3, onerror=_f3)

ok = sum(1 for _, c, _ in R if c)
print(f"\n{ok}/{len(R)} passed")
sys.exit(0 if ok == len(R) else 1)
