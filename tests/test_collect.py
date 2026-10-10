"""
collect.py のテスト。一時フォルダに偽のツール（小さな export_offline.py を持つリポジトリ）と
その push 先、配布用のリポジトリを作って動かす。本物のツールのリポジトリには触れない。
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import collect  # noqa: E402

# 偽のツールの書き出しの道具。content/ の下を <ツール名>/ の下に入れ、直下に決まった 3 つを置く
FAKE_EXPORT = r'''
import hashlib, os, sys, zipfile
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
name = os.path.basename(root)
if os.path.exists(os.path.join(root, "FAIL")):
    print("NG: 書き出せません")
    sys.exit(1)
files = {}
base = os.path.join(root, "content")
for dirpath, _, names in os.walk(base):
    for n in names:
        p = os.path.join(dirpath, n)
        files[os.path.relpath(p, base).replace(os.sep, "/")] = open(p, "rb").read()
h = hashlib.sha256()
for rel in sorted(files):
    h.update(rel.encode() + b"\0" + files[rel])
digest = h.hexdigest()[:7]
entries = {"import.bat": b"@echo off\r\n",
           "SOURCE.txt": ("tool=%s\r\ncontent=%s\r\nkeep=\r\n" % (name, digest)).encode(),
           "COMMIT_MSG.txt": ("import %s\n" % digest).encode()}
for rel in files:
    entries[name + "/" + rel] = files[rel]
os.makedirs(sys.argv[1], exist_ok=True)
with zipfile.ZipFile(os.path.join(sys.argv[1], name + "-offline.zip"), "w") as z:
    for rel in sorted(entries):
        z.writestr(zipfile.ZipInfo(rel, (1980, 1, 1, 0, 0, 0)), entries[rel])
'''

EMAIL = "someone@example.test"
FAKE_HOME = "/home/someone-test"  # check-privacy:ignore 架空のホーム
WORDS = ["someone@example.test", "someone-test", FAKE_HOME] + list(collect.FORBIDDEN)


def git(cwd, *args):
    return subprocess.run(["git"] + list(args), cwd=cwd, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE).stdout.decode("utf-8")


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def read(path):
    with open(path, "rb") as f:
        return f.read()


def fake_xlsx(core):
    """docProps/core.xml を持つ、xlsx に似た zip"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("docProps/core.xml", core)
    return buf.getvalue()


class Base(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        gitconfig = os.path.join(self.tmp, "gitconfig")
        write(gitconfig, "[user]\n\tname = t\n\temail = {}\n[init]\n\tdefaultBranch = main\n".format(EMAIL))
        env = mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": gitconfig, "GIT_CONFIG_NOSYSTEM": "1",
                                           "HOME": FAKE_HOME, "USER": "someone-test"})
        env.start()
        self.addCleanup(env.stop)
        self.home = os.path.join(self.tmp, "tools")
        self.dist = os.path.join(self.tmp, "dist")
        os.makedirs(self.dist)
        git(self.dist, "init", "-q")
        git(self.dist, "commit", "-q", "--allow-empty", "-m", "init")
        self.src = self.make_tool("fake")

    def make_tool(self, name):
        src = os.path.join(self.home, name)
        remote = os.path.join(self.tmp, name + ".git")
        os.makedirs(src)
        git(self.tmp, "init", "-q", "--bare", remote)
        git(src, "init", "-q")
        write(os.path.join(src, "scripts", "export_offline.py"), FAKE_EXPORT)
        write(os.path.join(src, "content", "README.md"), "# fake\n\n使い方\n")
        git(src, "add", "-A")
        git(src, "commit", "-q", "-m", "first")
        git(src, "remote", "add", "origin", remote)
        git(src, "push", "-q", "-u", "origin", "main")
        return src

    def commit_and_push(self, rel, data, push=True):
        write(os.path.join(self.src, rel), data)
        git(self.src, "add", "-A")
        git(self.src, "commit", "-q", "-m", "change")
        if push:
            git(self.src, "push", "-q")

    def collect(self, name="fake"):
        return collect.collect_one(name, repo=self.dist, home=self.home, words=WORDS)

    def commits(self):
        return int(git(self.dist, "rev-list", "--count", "HEAD").strip())

    def zip_path(self, name="fake"):
        return os.path.join(self.dist, name, name + "-offline.zip")

    def assert_refused(self, title_part):
        before = self.commits()
        old = read(self.zip_path()) if os.path.exists(self.zip_path()) else None
        with self.assertRaises(collect.CollectError) as cm:
            self.collect()
        self.assertIn(title_part, cm.exception.title)
        self.assertEqual(self.commits(), before)
        now = read(self.zip_path()) if os.path.exists(self.zip_path()) else None
        self.assertEqual(now, old)
        return cm.exception


class CollectTest(Base):

    def test_first_collect_commits_zip(self):
        self.assertEqual(self.collect(), "更新")
        self.assertTrue(os.path.isfile(self.zip_path()))
        msg = git(self.dist, "log", "-1", "--format=%B")
        head = git(self.src, "rev-parse", "HEAD").strip()
        digest = collect.source_field(collect.read_entries(read(self.zip_path())), "content")
        self.assertTrue(msg.startswith("chore(fake): 配る zip を中身 {} にする\n".format(digest)))
        self.assertIn("元のコミット: " + head, msg)
        self.assertEqual(git(self.dist, "status", "--porcelain"), "")

    def test_same_content_makes_no_commit(self):
        self.collect()
        before = self.commits()
        self.assertEqual(self.collect(), "変わりなし")
        self.assertEqual(self.commits(), before)
        self.assertEqual(git(self.dist, "status", "--porcelain"), "")

    def test_same_content_after_unrelated_commit_makes_no_commit(self):
        self.collect()
        before = self.commits()
        self.commit_and_push("tests/test_x.py", "pass\n")   # zip に入らないものだけを変える
        self.assertEqual(self.collect(), "変わりなし")
        self.assertEqual(self.commits(), before)

    def test_changed_content_commits_again(self):
        self.collect()
        before = self.commits()
        self.commit_and_push("content/README.md", "# fake\n\n変えた\n")
        self.assertEqual(self.collect(), "更新")
        self.assertEqual(self.commits(), before + 1)

    def test_source_is_not_changed(self):
        head = git(self.src, "rev-parse", "HEAD")
        self.collect()
        self.assertEqual(git(self.src, "rev-parse", "HEAD"), head)
        self.assertEqual(git(self.src, "status", "--porcelain", "--ignored"), "")


class SourceStateTest(Base):

    def test_not_pushed(self):
        self.commit_and_push("content/README.md", "# fake\n\nまだ push していない\n", push=False)
        e = self.assert_refused("origin/main と一致しません")
        self.assertTrue(any(line.startswith("origin/main") for line in e.lines))

    def test_no_origin_main(self):
        git(self.src, "remote", "remove", "origin")
        self.assert_refused("origin/main がありません")

    def test_dirty_tracked(self):
        write(os.path.join(self.src, "content", "README.md"), "# fake\n\nコミットしていない\n")
        e = self.assert_refused("汚れています")
        self.assertIn(" M content/README.md", e.lines)

    def test_dirty_untracked(self):
        write(os.path.join(self.src, "content", "new.md"), "足しただけ\n")
        self.assert_refused("汚れています")

    def test_not_main(self):
        git(self.src, "switch", "-q", "-c", "other")
        self.assert_refused("main ではありません")

    def test_dirty_is_refused_even_after_a_good_collect(self):
        self.collect()
        write(os.path.join(self.src, "content", "README.md"), "# fake\n\n汚した\n")
        self.assert_refused("汚れています")

    def test_export_fails(self):
        self.commit_and_push("FAIL", "")
        e = self.assert_refused("書き出しが失敗しました")
        self.assertIn("NG: 書き出せません", e.lines)

    def test_missing_tool(self):
        with self.assertRaises(collect.CollectError):
            self.collect("missing")


class LeakTest(Base):

    def test_forbidden_words(self):
        for i, word in enumerate(collect.FORBIDDEN):
            with self.subTest(word=word):
                self.commit_and_push("content/doc{}.md".format(i), "前置き\n" + word.upper() + " を指す\n")
                e = self.assert_refused("公開できない記述")
                self.assertTrue(any("doc{}.md:2".format(i) in line for line in e.lines), e.lines)
                git(self.src, "rm", "-q", "content/doc{}.md".format(i))
                git(self.src, "commit", "-q", "-m", "戻す")
                git(self.src, "push", "-q")

    def test_email_user_home(self):
        for text in (EMAIL, "作った人 someone-test", FAKE_HOME + "/ws/x"):
            with self.subTest(text=text):
                self.commit_and_push("content/a.md", text + "\n")
                self.assert_refused("公開できない記述")

    def test_leak_inside_nested_zip(self):
        self.commit_and_push("content/templates/sheet.xlsx", fake_xlsx("<dc:creator>someone-test</dc:creator>"))
        e = self.assert_refused("公開できない記述")
        self.assertTrue(any("sheet.xlsx!docProps/core.xml" in line for line in e.lines), e.lines)

    def test_leak_in_binary(self):
        self.commit_and_push("content/bin.dat", b"\0\1" + collect.FORBIDDEN[0].encode() + b"\0")
        self.assert_refused("公開できない記述")

    def test_leak_keeps_previous_zip(self):
        self.collect()
        self.commit_and_push("content/a.md", EMAIL + "\n")
        self.assert_refused("公開できない記述")

    def test_leak_words_from_environment(self):
        git(self.dist, "config", "user.email", "Other@Example.test")
        words = collect.leak_words(self.dist)
        for w in ("other@example.test", "someone-test", FAKE_HOME) + collect.FORBIDDEN:
            self.assertIn(w, words)

    def test_forbidden_words_are_not_written_as_is(self):
        # 検査が collect.py 自身に掛からないよう、語を分けて書いていること
        with open(os.path.join(ROOT, "collect.py"), encoding="utf-8") as f:
            source = f.read().lower()
        for w in collect.FORBIDDEN:
            self.assertNotIn(w, source)


class RepoCheckTest(Base):

    def test_repo_with_leak(self):
        write(os.path.join(self.dist, "README.md"), "# x\n\n" + collect.FORBIDDEN[2] + "\n")
        hits = collect.check_repo(self.dist, WORDS)
        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0].startswith("README.md:3:"))

    def test_ignored_files_are_not_checked(self):
        write(os.path.join(self.dist, ".gitignore"), "local.md\n")
        write(os.path.join(self.dist, "local.md"), collect.FORBIDDEN[0] + "\n")
        self.assertEqual(collect.check_repo(self.dist, WORDS), [])

    def test_license_holder_is_allowed(self):
        write(os.path.join(self.dist, "LICENSE"), "MIT License\n\nCopyright (c) 2026 someone-test\n")
        self.assertEqual(collect.check_repo(self.dist, WORDS), [])
        write(os.path.join(self.dist, "LICENSE"), "MIT License\n\nby someone-test\n")
        self.assertEqual(len(collect.check_repo(self.dist, WORDS)), 1)

    def test_collected_zip_is_checked(self):
        write(self.zip_path(), fake_xlsx("someone@example.test"))
        hits = collect.check_repo(self.dist, WORDS)
        self.assertTrue(any("fake-offline.zip!docProps/core.xml" in h for h in hits), hits)


class MainTest(Base):
    """collect.py を配布用のリポジトリに置いて、コマンドとして動かす"""

    def setUp(self):
        Base.setUp(self)
        shutil.copy(os.path.join(ROOT, "collect.py"), self.dist)
        write(os.path.join(self.dist, "tools.txt"), "# 一覧\nfake\n")
        write(os.path.join(self.dist, ".gitignore"), "__pycache__/\n")
        git(self.dist, "add", "-A")
        git(self.dist, "commit", "-q", "-m", "tools")

    def run_collect(self, *args):
        env = dict(os.environ, OFFLINE_DIST_TOOLS=self.home)
        r = subprocess.run([sys.executable, "-B", os.path.join(self.dist, "collect.py")] + list(args),
                           cwd=self.dist, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return r.returncode, r.stdout.decode("utf-8")

    def test_collect_twice(self):
        code, out = self.run_collect()
        self.assertEqual(code, 0, out)
        self.assertIn("更新", out)
        before = self.commits()
        code, out = self.run_collect("fake")
        self.assertEqual(code, 0, out)
        self.assertIn("変わりなし", out)
        self.assertEqual(self.commits(), before)

    def test_failure_exits_1(self):
        write(os.path.join(self.src, "content", "README.md"), "汚した\n")
        code, out = self.run_collect()
        self.assertEqual(code, 1, out)
        self.assertIn("汚れています", out)

    def test_unknown_name(self):
        code, out = self.run_collect("other")
        self.assertEqual(code, 2, out)

    def test_bad_place_exits_2(self):
        write(os.path.join(self.dist, "tools.txt"), "fake ../fake\n")
        code, out = self.run_collect()
        self.assertEqual(code, 2, out)
        self.assertIn("相対パス", out)

    def test_check_only(self):
        code, out = self.run_collect("--check")
        self.assertEqual(code, 0, out)
        self.assertFalse(os.path.exists(self.zip_path()))


class SubfolderTest(Base):
    """いくつかのツールをまとめたリポジトリの、サブフォルダから集める"""

    def setUp(self):
        Base.setUp(self)
        self.mono = os.path.join(self.home, "suite")
        remote = os.path.join(self.tmp, "suite.git")
        os.makedirs(self.mono)
        git(self.tmp, "init", "-q", "--bare", remote)
        git(self.mono, "init", "-q")
        for name in ("one", "two"):
            write(os.path.join(self.mono, "tools", name, "scripts", "export_offline.py"), FAKE_EXPORT)
            write(os.path.join(self.mono, "tools", name, "content", "README.md"), "# {}\n".format(name))
        git(self.mono, "add", "-A")
        git(self.mono, "commit", "-q", "-m", "first")
        git(self.mono, "remote", "add", "origin", remote)
        git(self.mono, "push", "-q", "-u", "origin", "main")

    def collect_sub(self, name="one"):
        return collect.collect_one(name, repo=self.dist, home=self.home, words=WORDS,
                                   where="suite/tools/" + name)

    def test_collect_from_subfolder(self):
        self.assertEqual(self.collect_sub(), "更新")
        entries = collect.read_entries(read(self.zip_path("one")))
        self.assertEqual(collect.source_field(entries, "tool"), "one")
        self.assertIn("one/README.md", entries)
        msg = git(self.dist, "log", "-1", "--format=%B")
        self.assertIn("元のコミット: " + git(self.mono, "rev-parse", "HEAD").strip(), msg)
        self.assertEqual(self.collect_sub(), "変わりなし")
        self.assertEqual(git(self.mono, "status", "--porcelain", "--ignored"), "")

    def test_dirty_outside_subfolder_is_refused(self):
        # 集めるサブフォルダの外（同じリポジトリの別のツール）が汚れていても集めない
        write(os.path.join(self.mono, "tools", "two", "content", "README.md"), "# 汚した\n")
        before = self.commits()
        with self.assertRaises(collect.CollectError) as cm:
            self.collect_sub("one")
        self.assertIn("汚れています", cm.exception.title)
        self.assertIn(" M tools/two/content/README.md", cm.exception.lines)
        self.assertEqual(self.commits(), before)
        self.assertFalse(os.path.exists(self.zip_path("one")))

    def test_not_pushed_is_refused(self):
        write(os.path.join(self.mono, "tools", "two", "content", "README.md"), "# まだ push していない\n")
        git(self.mono, "commit", "-q", "-am", "change")
        with self.assertRaises(collect.CollectError) as cm:
            self.collect_sub("one")
        self.assertIn("origin/main と一致しません", cm.exception.title)

    def test_command_reads_second_column(self):
        shutil.copy(os.path.join(ROOT, "collect.py"), self.dist)
        write(os.path.join(self.dist, "tools.txt"), "fake\none  suite/tools/one\n")
        write(os.path.join(self.dist, ".gitignore"), "__pycache__/\n")
        git(self.dist, "add", "-A")
        git(self.dist, "commit", "-q", "-m", "tools")
        r = subprocess.run([sys.executable, "-B", os.path.join(self.dist, "collect.py"), "one"], cwd=self.dist,
                           env=dict(os.environ, OFFLINE_DIST_TOOLS=self.home),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = r.stdout.decode("utf-8")
        self.assertEqual(r.returncode, 0, out)
        self.assertTrue(os.path.isfile(self.zip_path("one")), out)
        self.assertFalse(os.path.exists(self.zip_path("fake")), out)

    def test_without_second_column_collects_from_sibling(self):
        self.assertEqual(collect.collect_one("fake", repo=self.dist, home=self.home, words=WORDS, where=None),
                         "更新")


class ToolsListTest(unittest.TestCase):

    def read(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, collect.TOOLS_LIST), text)
            return collect.read_tools(tmp)

    def test_columns(self):
        tools = self.read("# 一覧\nalpha\nbeta   suite/tools/beta  # まとめた方\n\n  gamma\tother/gamma\n")
        self.assertEqual(tools, [("alpha", "alpha"), ("beta", "suite/tools/beta"), ("gamma", "other/gamma")])

    def test_refuses_unsafe_places(self):
        for where in ("/abs/tools/x", "../x", "suite/../x", "suite/./x", "suite\\x", "C:/x", "c:x",
                      "suite//x", "suite/x/", "~/x"):
            with self.subTest(where=where):
                with self.assertRaises(collect.CollectError) as cm:
                    self.read("x " + where + "\n")
                self.assertIn("相対パス", cm.exception.title)

    def test_refuses_extra_columns_and_bad_names(self):
        for line in ("x a b", "../x", "a\\b", ".."):
            with self.subTest(line=line):
                with self.assertRaises(collect.CollectError):
                    self.read(line + "\n")

    def test_this_repo_list_is_valid(self):
        names = [n for n, _ in collect.read_tools(ROOT)]
        self.assertEqual(len(names), len(set(names)))


class ThisRepoTest(unittest.TestCase):

    def test_this_repo_has_no_leak(self):
        self.assertEqual(collect.check_repo(ROOT), [])


if __name__ == "__main__":
    unittest.main()
