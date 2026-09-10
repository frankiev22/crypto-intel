"""Reading a file that exists and failing must never be written back as empty.

THE SHAPE, which this repo grew five times independently:

    def _load():
        try:    return json.load(open(PATH))
        except Exception: return {}          # <- transient failure looks empty
    ...
    d = _load(); d[k] = v; atomic_write(PATH, d)   # <- and is made permanent

A read can fail for reasons that have nothing to do with the file's contents:
the file is mid-rename by another writer, the disk is briefly unavailable, a
merge left conflict markers in it, the process is out of file handles. Every one
of those is transient. The bare `except` converts all of them into the same
answer as "this file does not exist yet", and the very next atomic write makes
that answer true. `data/findings/_seen.json` is 852 entries and 166KB, and it
came minutes from being replaced with `{}` during an uncommitted merge window.

This is the same family as "absence of evidence rendered as evidence of
absence", which has cost this project six findings. The difference is the cost:
there, it produced a wrong number that could be recomputed. Here it destroys the
input, and nothing can be recomputed from a file that no longer has contents.

THE DISTINCTION THAT FIXES IT. Absent and unreadable are different states:

  file does not exist   -> a fresh default. This is a real answer. Callers may
                           write it, because there was nothing to lose.
  file exists, won't parse -> LoadFailed. NOT an answer. The caller does not
                           know what is in the file, and a caller that does not
                           know what is in the file must not overwrite it.

Two independent layers, because one guard is a single point of failure:
  1. `load_json` raises instead of inventing an empty value.
  2. `save_json` refuses to replace a populated file with an empty one even if
     asked - so a future load path that regresses still cannot destroy data.
"""
import json
import os


class LoadFailed(RuntimeError):
    """The file is there and could not be read. Its contents are UNKNOWN.

    Never catch this and continue into a write. Catch it, skip the write, and
    report it - a stale file is recoverable, a truncated one is not.
    """


class RefusedShrink(RuntimeError):
    """A write would have emptied a populated file. Refused."""


def _empty(d):
    return d is None or (hasattr(d, "__len__") and len(d) == 0)


def load_json(path, absent=dict, expect=dict):
    """Absent -> `absent()`. Present-but-unreadable -> LoadFailed. Never {} for both."""
    if not os.path.exists(path):
        return absent()
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:
        raise LoadFailed(f"{path} exists ({os.path.getsize(path):,} bytes) but "
                         f"did not parse: {type(e).__name__}: {e}") from e
    if expect is not None and not isinstance(d, expect):
        # A JSON file that parses to the wrong type is corrupt, not empty.
        raise LoadFailed(f"{path} parsed to {type(d).__name__}, expected "
                         f"{expect.__name__} - treating as unreadable, not empty")
    return d


def save_json(path, data, allow_empty=False, indent=1):
    """Atomic write that REFUSES to empty a populated file unless told to.

    The second layer. `load_json` already stops the common path, but this one
    holds even when the caller assembled an empty value some other way.
    """
    if not allow_empty and _empty(data) and os.path.exists(path):
        try:
            existing = load_json(path, expect=None)
        except LoadFailed:
            raise RefusedShrink(
                f"refusing to write empty over {path}: the existing file could "
                f"not be read, so this write would destroy unknown contents")
        if not _empty(existing):
            raise RefusedShrink(
                f"refusing to write empty over {path}, which currently holds "
                f"{len(existing)} entries. Pass allow_empty=True to mean it.")
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    os.replace(tmp, path)
    return path


def save_text(path, text):
    """Atomic whole-file text write, for append-only records that are not JSON.

    A non-atomic truncating write racing an atomic one left 6 stray bytes on
    the tail of data/liveness.json on 2026-09-09 - a short write over a longer
    previous version. Nothing was lost, because load_json refused to read the
    result and save_json refused to overwrite it, but the repair was manual.
    Every whole-file writer goes through tmp+replace now.
    """
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)
    return path
