# offline-dist

インターネットに接続できない環境へ持ち込む、業務ツールの zip を置くリポジトリです。
ツールごとに zip が 1 つあり、持ち込むのはその zip だけです。

## 目次

1. [置いているツール](#置いているツール)
2. [持ち込む手順](#持ち込む手順)
3. [zip を集める（配る人向け）](#zip-を集める配る人向け)
4. [ファイル構成](#ファイル構成)
5. [ライセンス](#ライセンス)

---

## 置いているツール

| ツール | zip |
|---|---|
| backlog_issue_sheet | `backlog_issue_sheet/backlog_issue_sheet-offline.zip` |
| backlog_issue_cloner | `backlog_issue_cloner/backlog_issue_cloner-offline.zip` |
| file_sync_checker | `file_sync_checker/file_sync_checker-offline.zip` |

一覧の元は [`tools.txt`](tools.txt) です。

---

## 持ち込む手順

1. GitHub のこのリポジトリの画面で、持ち込むツールの `<ツール名>/<ツール名>-offline.zip` を開き、
   「Download raw file」で落とします。公開しているので、ログインは要りません
2. 落とした zip を、持ち込む先へ移します
3. 持ち込んだ先で zip を展開し、中の `import.bat` をダブルクリックします（Git for Windows が要ります）
4. Git のリポジトリの置き場を聞かれるので、入力して Enter を押します（例 `\\fileserver\share\git`）。
   初回は `<ツール名>.git` を作ってよいかを聞かれるので、`Y` を入力します。
   2 回目からは、前回との差分を 1 つのコミットにして積みます

取り込んだ後の clone と更新の手順は、zip の中の `<ツール名>/README.md` にあります。

**zip の名前は変わりません。** 新しい版を集めると、同じ名前の zip を置き換えます。
版は、zip の中の `SOURCE.txt` の `content=`（中身のハッシュ）で分かります。
更新したツールの zip だけを持ち込めば足ります。

---

## zip を集める（配る人向け）

各ツールのリポジトリを、このリポジトリと同じフォルダに並べて置きます（Python 3.10 以上が要ります）。

```bash
python3 collect.py                    # tools.txt のすべて
python3 collect.py backlog_issue_sheet  # 名前を付けたものだけ
python3 collect.py --check            # 集めずに、このリポジトリ全体の検査だけ
```

ツールのリポジトリを別の所に並べているときは、環境変数 `OFFLINE_DIST_TOOLS` にそのフォルダを入れます。

ツールごとに次を行い、どれかで止まったら、そのツールの zip は書き換えません。

1. ツールのリポジトリが、push 済みの `main` であることを確かめる（作業ツリーがきれい・`main`・`origin/main` と同じ）。
   配る版を、ツールのリポジトリの履歴でたどれるようにするためです
2. ツールのリポジトリの `scripts/export_offline.py` で、一時フォルダへ zip を書き出す。ツールのリポジトリには書きません
3. zip を展開した中身に、作業環境を指す決まった語・実行した人のメールアドレス（`git config user.email`）・
   ユーザー名・ホームのパスが無いことを確かめる。xlsx のように中が zip のファイルは、その中も見ます
4. 中身が今の zip と同じなら何もしない。違えば置き換えて、`chore(<ツール名>): 配る zip を中身 <ハッシュ> にする` でコミットする。
   本文に、ツールのリポジトリの元のコミットを書きます

最後に、このリポジトリ全体（置いた zip は展開した中身）にも同じ検査を掛けます。
`collect.py` は push しません。

テストは標準ライブラリだけで動きます。一時フォルダに偽のツールを作って確かめます。

```bash
python3 -m unittest discover -s tests
```

---

## ファイル構成

```
offline-dist/
├── README.md               この文書
├── LICENSE                 MIT ライセンス。置いている zip にも及びます
├── CHANGELOG.md            変更履歴
├── tools.txt               集めるツールの一覧
├── collect.py              zip を集める
├── tests/
│   └── test_collect.py     collect.py のテスト
└── <ツール名>/
    └── <ツール名>-offline.zip
```

---

## ライセンス

[MIT License](LICENSE)。置いている zip の中身にも及びます（zip には `LICENSE` を入れていません）。
