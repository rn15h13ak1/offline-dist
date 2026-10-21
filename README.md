# offline-dist

インターネットに接続できない環境へ持ち込む、業務ツールの zip を置くリポジトリです。
ツールごとに zip が 1 つあり、持ち込むのはその zip だけです。

## 目次

1. [置いているツール](#置いているツール)
2. [持ち込む手順](#持ち込む手順)
3. [まとめて取り込む](#まとめて取り込む)
4. [まとめて更新する](#まとめて更新する)
5. [zip を集める（配る人向け）](#zip-を集める配る人向け)
6. [ファイル構成](#ファイル構成)
7. [ライセンス](#ライセンス)

---

## 置いているツール

| ツール | zip |
|---|---|
| backlog_issue_sheet | `backlog_issue_sheet/backlog_issue_sheet-offline.zip` |
| backlog_issue_cloner | `backlog_issue_cloner/backlog_issue_cloner-offline.zip` |
| backlog_change_log | `backlog_change_log/backlog_change_log-offline.zip` |
| backlog_report | `backlog_report/backlog_report-offline.zip` |
| excel_to_backlog | `excel_to_backlog/excel_to_backlog-offline.zip` |
| docmold | `docmold/docmold-offline.zip` |
| tool_launcher | `tool_launcher/tool_launcher-offline.zip` |
| file_sync_checker | `file_sync_checker/file_sync_checker-offline.zip` |
| path_lister | `path_lister/path_lister-offline.zip` |

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

## まとめて取り込む

いくつものツールを持ち込んだときは、`import_all.bat` で各ツールの `import.bat` を順に動かせます。

1. `import_all.bat` と `import_all.example.txt` を、持ち込む zip と一緒に落として、持ち込む先の 1 つのフォルダに置きます。
   zip は展開しません
2. `import_all.bat` をダブルクリックします。初回は `import_all.example.txt` を写した `import_all.txt` を作り、
   メモ帳で開いて止まります
3. `import_all.txt` を書き換えて保存し、もう一度 `import_all.bat` をダブルクリックします

`import_all.txt` が、持ち込み先で書き換える定義です。行頭が `#` の行は読みません（行の途中の `#` は注釈になりません）。

```
# Git のリポジトリの置き場（各ツールの import.bat に渡す）
ROOT=\\fileserver\share\git
# zip を置いたフォルダ。省けば import_all.bat と同じフォルダ
ZIPDIR=D:\持ち込み
# ROOT に取り込む
path_lister
# このツールだけ別の置き場に取り込む
docmold=\\other\share\git
# 行頭に # を付けたツールは取り込まない
# tool_launcher
```

- ツールは書いた順に取り込みます。zip が見つからないツールは飛ばすので、更新したツールの zip だけを持ち込めば足ります
- zip は `<ツール名>-offline.zip` と `<ツール名>\<ツール名>-offline.zip` の順に探します
- zip は一時フォルダに展開し、終われば消します
- 置き場を作ってよいか（`Y`）や、競合したときの `KEEP` は、各ツールの `import.bat` がそのまま聞きます
- 最後に、取り込めたもの・失敗したもの・飛ばしたものを並べます
- `import_all.txt` は見本から作った後は書き換えません。新しい見本を持ち込んでも、書き換えた定義は残ります。
  見本にツールが増えたら、`import_all.txt` に行を足します

---

## まとめて更新する

いくつものツールを clone して使っているときは、`update_all.bat` で各ツールの `update.bat` を順に動かせます。

1. `update_all.bat` を落として、ツールを clone したフォルダの隣（同じ親フォルダ）に置きます
2. `update_all.bat` をダブルクリックします

```
C:\tools\
├── update_all.bat
├── docmold\        git clone したもの
└── path_lister\    git clone したもの
```

- 隣のフォルダのうち、`.git`・`update.bat`・`undo_changes.bat` があるものを、名前の順に更新します
- 更新に失敗したツールがあれば並べて、`Y` を入力するか聞きます。`Y` なら、そのツールごとに `undo_changes.bat` を動かし
  （変えたファイルを、そのツールのフォルダの `backup\<日時>\` に退避してから元に戻す）、もう一度 `update.bat` を動かします。
  Git が扱わないファイル（設定・`.venv\` など）には触れません
- 最後に、更新できたもの・失敗したものを並べます
- 引数にツールの名前を書くと、そのツールだけを更新します（例 `update_all.bat docmold path_lister`）
- 名前に空白を含むフォルダは飛ばします

---

## zip を集める（配る人向け）

各ツールのリポジトリを、このリポジトリと同じフォルダに並べて置きます（Python 3.10 以上が要ります）。

```bash
python3 collect.py                    # tools.txt のすべて
python3 collect.py backlog_issue_sheet  # 名前を付けたものだけ
python3 collect.py --check            # 集めずに、このリポジトリ全体の検査だけ
```

ツールのリポジトリを別の所に並べているときは、環境変数 `OFFLINE_DIST_TOOLS` にそのフォルダを入れます。

`tools.txt` には 1 行に 1 つ、ツールの名前を書きます。名前は zip を置くフォルダ名を兼ねます。
2 列目に、集める場所を書けます。兄弟のフォルダ（このリポジトリの親フォルダ）から見た、`/` で区切った相対パスです。
いくつかのツールをまとめたリポジトリの、サブフォルダも指せます。省けば、名前と同じ兄弟のフォルダから集めます。

```
sample_tool                                 # 兄弟の sample_tool/ から
other_tool    tool-suite/tools/other_tool   # 兄弟の tool-suite/ の中の tools/other_tool/ から
```

絶対パス・`..`・`\` を含む場所は拒みます（このリポジトリは公開するため、絶対パスを書かない）。

ツールごとに次を行い、どれかで止まったら、そのツールの zip は書き換えません。

1. ツールのリポジトリが、push 済みの `main` であることを確かめる（作業ツリーがきれい・`main`・`origin/main` と同じ）。
   配る版を、ツールのリポジトリの履歴でたどれるようにするためです。集める場所がサブフォルダなら、それを含むリポジトリ全体を見ます
2. 集める場所の `scripts/export_offline.py` で、一時フォルダへ zip を書き出す。ツールのリポジトリには書きません
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
├── import_all.bat          持ち込み先で、各ツールの import.bat をまとめて動かす
├── import_all.example.txt  import_all.bat の定義の見本
├── update_all.bat          clone したツールの update.bat をまとめて動かす
├── tests/
│   ├── test_collect.py     collect.py のテスト
│   └── test_import_all.py  import_all.bat・update_all.bat と見本のテスト
└── <ツール名>/
    └── <ツール名>-offline.zip
```

---

## ライセンス

[MIT License](LICENSE)。置いている zip の中身にも及びます（zip には `LICENSE` を入れていません）。
