#!/usr/bin/env python3
"""
配る zip を集める
================
兄弟に並ぶ各ツールのリポジトリで書き出しの道具を動かし、できた zip をこのリポジトリに置いてコミットする。

  python3 collect.py                    tools.txt のすべて
  python3 collect.py <ツール名> ...      名前を付けたものだけ（tools.txt にあるもの）
  python3 collect.py --check            集めずに、このリポジトリ全体の漏れだけを検査する

ツールのリポジトリは、既定ではこのリポジトリの親フォルダに並ぶ。環境変数 OFFLINE_DIST_TOOLS で変えられる。

ツールごとに次を行い、どれかで落ちたらそのツールは書き換えない（他のツールは続ける）。
  1. 元のリポジトリが push 済みの main であることを確かめる（作業ツリーがきれい・main・origin/main と同じ）
  2. 元のリポジトリの scripts/export_offline.py を、出力先を一時フォルダにして動かす
  3. zip の中身を、展開した形で検査する（決まった語・git の user.email・$USER・$HOME）
  4. 中身が今の zip と同じなら何もしない。違えば置き換えてコミットする
最後に、このリポジトリ全体（zip は展開した中身）に同じ検査を掛ける。

元のリポジトリには書かない。git は読むだけで、索引の更新も止める（GIT_OPTIONAL_LOCKS=0）。
origin/main は手元にある追跡ブランチを見る。fetch は元のリポジトリに書くため行わない。
push はしない。検査が通ったのを見てから、人が行う。
"""

import io
import os
import re
import subprocess
import sys
import tempfile
import zipfile

REPO = os.path.dirname(os.path.abspath(__file__))
TOOLS_LIST = "tools.txt"
EXPORT_SCRIPT = os.path.join("scripts", "export_offline.py")
TOP_FILES = ("import.bat", "SOURCE.txt", "COMMIT_MSG.txt")

# 作業環境を指す語。大小を問わない。
# このファイルも検査に掛かるため、語そのものを書かずに分けて書く
FORBIDDEN = ("ws-" + "conventions", "propos" + "als", "cla" + "ude")

NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


class CollectError(Exception):
    """そのツールを書き換えない理由。行の一覧を持つ"""

    def __init__(self, title, lines=()):
        Exception.__init__(self, title)
        self.title = title
        self.lines = list(lines)


# ---------------- git ----------------

def git(args, cwd):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", LC_ALL="C")
    r = subprocess.run(["git"] + args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise CollectError("git {} が失敗しました".format(args[0]),
                           r.stderr.decode("utf-8", "replace").splitlines())
    return r.stdout.decode("utf-8", "replace")


def tools_home():
    return os.environ.get("OFFLINE_DIST_TOOLS") or os.path.dirname(REPO)


def read_tools(repo=REPO):
    names = []
    with open(os.path.join(repo, TOOLS_LIST), encoding="utf-8") as f:
        for raw in f:
            line = raw.split("#", 1)[0].strip()
            if line:
                names.append(line)
    return names


# ---------------- 1. 元のリポジトリ ----------------

def check_source(src):
    """push 済みの main なら、そのコミットのハッシュを返す"""
    if not os.path.isdir(src):
        raise CollectError("ツールのリポジトリがありません: " + src)
    if not os.path.isfile(os.path.join(src, EXPORT_SCRIPT)):
        raise CollectError("書き出しの道具がありません: " + EXPORT_SCRIPT)
    dirty = git(["status", "--porcelain", "--untracked-files=normal"], src).splitlines()
    if dirty:
        raise CollectError("作業ツリーが汚れています。コミットして push してから集めてください。", dirty)
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"], src).strip()
    if branch != "main":
        raise CollectError("main ではありません（今は {}）。".format(branch))
    head = git(["rev-parse", "HEAD"], src).strip()
    try:
        remote = git(["rev-parse", "--verify", "-q", "refs/remotes/origin/main"], src).strip()
    except CollectError:
        raise CollectError("origin/main がありません。push してから集めてください。")
    if head != remote:
        raise CollectError("main が origin/main と一致しません。push してから集めてください。",
                           ["main        " + head, "origin/main " + remote])
    return head


# ---------------- 2. 書き出す ----------------

def export(src, name, out_dir):
    """元のリポジトリの道具で zip を書き出し、そのバイト列を返す"""
    r = subprocess.run([sys.executable, "-B", os.path.join(src, EXPORT_SCRIPT), out_dir], cwd=src,
                       env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"),
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = r.stdout.decode("utf-8", "replace").splitlines()
    if r.returncode != 0:
        raise CollectError("書き出しが失敗しました（終了コード {}）。".format(r.returncode), output)
    path = os.path.join(out_dir, name + "-offline.zip")
    if not os.path.isfile(path):
        raise CollectError("書き出しは終わりましたが、zip がありません: " + os.path.basename(path), output)
    with open(path, "rb") as f:
        return f.read()


def read_entries(data):
    """{zip の中の相対パス: バイト列}"""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return {i.filename: z.read(i) for i in z.infolist() if not i.is_dir()}
    except zipfile.BadZipFile as e:
        raise CollectError("zip として読めません: {}".format(e))


def source_field(entries, key):
    text = entries.get("SOURCE.txt", b"").decode("ascii", "replace")
    for line in text.splitlines():
        if line.startswith(key + "="):
            return line[len(key) + 1:].strip()
    return None


def check_shape(entries, name):
    """直下に TOP_FILES、中身は <ツール名>/ の下"""
    missing = [f for f in TOP_FILES if f not in entries]
    if missing:
        raise CollectError("zip の直下に要るファイルがありません。", missing)
    if source_field(entries, "tool") != name:
        raise CollectError("SOURCE.txt の tool が {} ではありません。".format(name))
    if not source_field(entries, "content"):
        raise CollectError("SOURCE.txt に content がありません。")
    stray = sorted(n for n in entries if n not in TOP_FILES and not n.startswith(name + "/"))
    if stray:
        raise CollectError("zip の中に、決まった形の外のファイルがあります。", stray)


# ---------------- 3. 漏れの検査 ----------------

def leak_words(repo=REPO):
    """探す語（小文字）。決まった語と、実行した人の user.email・$USER・$HOME"""
    words = list(FORBIDDEN)
    try:
        words.append(git(["config", "user.email"], repo).strip())
    except CollectError:
        pass
    words.append(os.environ.get("USER", ""))
    words.append(os.environ.get("HOME", ""))
    return sorted({w.lower() for w in words if w and len(w) >= 3})


def is_zip(data):
    return data[:4] == b"PK\x03\x04"


def scan(rel, data, words, skip_line=None, depth=0):
    """見つけた所の一覧。テキストは行ごと、それ以外はバイト列で探す。zip（xlsx なども）は中を開いて探す"""
    hits = []
    if is_zip(data) and depth < 3:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for info in z.infolist():
                    if not info.is_dir():
                        hits += scan(rel + "!" + info.filename, z.read(info), words, skip_line, depth + 1)
            return hits
        except zipfile.BadZipFile:
            pass
    try:
        text = None if b"\0" in data else data.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    if text is None:
        low = data.lower()
        for w in words:
            if w.encode("utf-8") in low:
                hits.append("{}: 「{}」（テキストでないファイル）".format(rel, w))
        return hits
    for no, line in enumerate(text.splitlines(), 1):
        if skip_line and skip_line(rel, line):
            continue
        low = line.lower()
        for w in words:
            if w in low:
                hits.append("{}:{}: 「{}」 {}".format(rel, no, w, line.strip()))
    return hits


def license_holder(rel, line):
    """LICENSE の著作権者の行は、利用者名でも意図して書く公開情報なので探さない"""
    return rel == "LICENSE" and line.startswith("Copyright ")


def check_repo(repo=REPO, words=None):
    """このリポジトリの追跡するファイル（無視されないもの）を検査し、見つけた所の一覧を返す"""
    words = leak_words(repo) if words is None else words
    out = git(["ls-files", "-z", "--cached", "--others", "--exclude-standard"], repo)
    hits = []
    for rel in sorted(n for n in out.split("\0") if n):
        path = os.path.join(repo, rel)
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as f:
            hits += scan(rel, f.read(), words, license_holder)
    return hits


# ---------------- 4. 置き換えてコミットする ----------------

def zip_rel(name):
    return name + "/" + name + "-offline.zip"


def current_entries(repo, name):
    path = os.path.join(repo, zip_rel(name))
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return read_entries(f.read())


def commit_message(name, digest, head):
    return "chore({}): 配る zip を中身 {} にする\n\n元のコミット: {}\n".format(name, digest, head)


def replace_and_commit(repo, name, data, message):
    rel = zip_rel(name)
    path = os.path.join(repo, rel)
    old = None
    if os.path.isfile(path):
        with open(path, "rb") as f:
            old = f.read()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
    try:
        git(["add", "--", rel], repo)
        git(["commit", "-q", "-m", message, "--", rel], repo)
    except CollectError:
        # コミットできなければ、前の zip に戻す
        if old is None:
            git(["rm", "-q", "--cached", "--ignore-unmatch", "--", rel], repo)
            os.remove(path)
        else:
            with open(path, "wb") as f:
                f.write(old)
            git(["add", "--", rel], repo)
        raise


# ---------------- まとめ ----------------

def collect_one(name, repo=REPO, home=None, words=None):
    """1 つのツールを集める。'更新' か '変わりなし' を返す。落ちれば CollectError"""
    src = os.path.join(home or tools_home(), name)
    head = check_source(src)
    with tempfile.TemporaryDirectory() as tmp:
        data = export(src, name, tmp)
    # 書き出しが元のリポジトリを変えていないこと
    if git(["status", "--porcelain", "--untracked-files=normal"], src).strip() or \
            git(["rev-parse", "HEAD"], src).strip() != head:
        raise CollectError("書き出しの後で、元のリポジトリが変わりました。書き出しの道具を確かめてください。")
    entries = read_entries(data)
    check_shape(entries, name)
    words = leak_words(repo) if words is None else words
    hits = []
    for rel in sorted(entries):
        hits += scan(rel, entries[rel], words)
    if hits:
        raise CollectError("zip の中に、公開できない記述があります。元のリポジトリを直してください。", hits)
    if current_entries(repo, name) == entries:
        return "変わりなし"
    replace_and_commit(repo, name, data, commit_message(name, source_field(entries, "content"), head))
    return "更新"


def print_error(e):
    print("  NG: " + e.title)
    for line in e.lines:
        print("    " + line)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--check"]:
        names = []
    elif any(a.startswith("-") for a in argv):
        print("使い方: python3 collect.py [<ツール名> ...] | --check")
        return 2
    else:
        listed = read_tools()
        names = argv or listed
        unknown = [n for n in names if n not in listed or not NAME.match(n)]
        if unknown:
            print("{} に無い名前です: {}".format(TOOLS_LIST, " ".join(unknown)))
            return 2
    failed = False
    for name in names:
        print(name)
        try:
            print("  " + collect_one(name))
        except (CollectError, OSError) as e:
            failed = True
            print_error(e if isinstance(e, CollectError) else CollectError(str(e)))
    print("このリポジトリ全体の検査")
    try:
        hits = check_repo()
    except CollectError as e:
        print_error(e)
        return 1
    if hits:
        print_error(CollectError("公開できない記述があります。", hits))
        return 1
    print("  OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
