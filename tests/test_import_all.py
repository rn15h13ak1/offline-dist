"""
import_all.bat・update_all.bat と定義の見本のテスト。bat は Windows でしか動かないため、ここでは
Windows で壊れる形（行末・文字・飛び先の無いラベル）と、見本がツールの一覧と揃っていることを確かめる。
"""

import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import collect  # noqa: E402

BATS = [os.path.join(ROOT, name) for name in ("import_all.bat", "update_all.bat")]
EXAMPLE = os.path.join(ROOT, "import_all.example.txt")


def read(path):
    with open(path, "rb") as f:
        return f.read()


def crlf_only(data):
    """行末がすべて CRLF で、最後の行も CRLF で終わる"""
    return data.endswith(b"\r\n") and data.count(b"\n") == data.count(b"\r\n")


class BatShapeTest(unittest.TestCase):
    def test_ascii(self):
        # どのコードページのコンソールでも読めるように
        for bat in BATS:
            with self.subTest(bat=os.path.basename(bat)):
                read(bat).decode("ascii")

    def test_crlf(self):
        # LF だけの行末では、cmd がラベルを見失うことがある
        for bat in BATS:
            with self.subTest(bat=os.path.basename(bat)):
                self.assertTrue(crlf_only(read(bat)))

    def test_labels_exist(self):
        for bat in BATS:
            with self.subTest(bat=os.path.basename(bat)):
                text = read(bat).decode("ascii")
                labels = {m.lower() for m in re.findall(r"^:(\w+)", text, re.M)}
                targets = re.findall(r"\b(?:goto|call)\s+:(\w+)", text, re.I)
                self.assertTrue(targets)
                for t in targets:
                    self.assertIn(t.lower(), labels, t)


class UpdateAllTest(unittest.TestCase):
    def test_runs_unattended(self):
        # update.bat は引数があると pause しない。undo_changes.bat は --yes で聞かずに退避して戻す
        text = read(BATS[1]).decode("ascii")
        self.assertIn('\\update.bat" unattended', text)
        self.assertIn('\\undo_changes.bat" --yes', text)


class ExampleTest(unittest.TestCase):
    def lines(self):
        return read(EXAMPLE).decode("utf-8").splitlines()

    def test_crlf_without_bom(self):
        data = read(EXAMPLE)
        self.assertTrue(crlf_only(data))
        self.assertFalse(data.startswith(b"\xef\xbb\xbf"))

    def test_tools_match_list(self):
        # 配るツールを足したら、見本にも足す
        names = [n for n, _ in collect.read_tools()]
        listed = [s.strip() for s in self.lines()
                  if s.strip() and not s.lstrip().startswith("#") and "=" not in s]
        self.assertEqual(listed, names)

    def test_root_is_set(self):
        self.assertTrue(any(s.startswith("ROOT=") for s in self.lines()))


class AttributesTest(unittest.TestCase):
    def test_not_converted(self):
        # 生のファイルを落としても CRLF のままであるように、Git に行末を変えさせない
        for rel in ("import_all.bat", "update_all.bat", "import_all.example.txt"):
            out = subprocess.run(["git", "check-attr", "text", "--", rel], cwd=ROOT, check=True,
                                 stdout=subprocess.PIPE).stdout.decode()
            self.assertTrue(out.strip().endswith("unset"), out)


if __name__ == "__main__":
    unittest.main()
