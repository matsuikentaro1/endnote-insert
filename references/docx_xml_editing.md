# Word (.docx) ファイルの ZIP 解凍・XML 編集・再圧縮ガイド

EndNoteフィールド挿入・修正作業で docx を直接編集する際の参照資料。

## 1. .docx の実体

.docx ファイルは **ZIP アーカイブ**である。拡張子を `.zip` に変えれば通常のツールで解凍できる。
中身は複数の XML ファイルとリレーションシップ定義で構成されている（Office Open XML 形式）。

---

## 2. 内部ファイル構成

### 必須ファイル

| パス | 役割 |
|------|------|
| `[Content_Types].xml` | 各パーツの Content-Type を宣言。**ZIP ルート直下に必須** |
| `_rels/.rels` | パッケージレベルのリレーション（document.xml への参照等） |
| `word/document.xml` | **本文**。段落・テキスト・画像参照等すべてが入る |
| `word/_rels/document.xml.rels` | document.xml から他パーツ（画像、スタイル等）への参照 |
| `word/styles.xml` | スタイル定義（見出し、本文、フォント等） |

### 主要なオプションファイル

| パス | 役割 |
|------|------|
| `word/settings.xml` | 文書設定（言語、校正、互換性等） |
| `word/fontTable.xml` | 使用フォント一覧 |
| `word/numbering.xml` | 箇条書き・番号リストの定義 |
| `word/header1.xml`, `footer1.xml` | ヘッダー・フッター |
| `word/footnotes.xml` | 脚注 |
| `word/endnotes.xml` | 文末脚注 |
| `word/comments.xml` | コメント本体 |
| `word/media/image1.png` 等 | 埋め込み画像・メディア（バイナリ） |
| `word/theme/theme1.xml` | テーマ（配色・フォントテーマ） |
| `docProps/core.xml` | メタデータ（作成者、作成日時等） |
| `docProps/app.xml` | アプリケーション情報（Word バージョン等） |

---

## 3. document.xml の構造

### 名前空間

```xml
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">
```

- `w:` — WordprocessingML（本文の段落・テキスト・書式）
- `r:` — リレーションシップ参照（画像やハイパーリンクの ID）
- `wp:` — 描画オブジェクト配置

### テキストの階層構造

```xml
<w:body>
  <w:p>                              <!-- 段落 (paragraph) -->
    <w:pPr>                          <!-- 段落プロパティ（スタイル、配置等）-->
      <w:pStyle w:val="Heading1"/>
    </w:pPr>
    <w:r>                            <!-- ラン (run)：同一書式のテキスト単位 -->
      <w:rPr>                        <!-- ランプロパティ（太字、フォント等）-->
        <w:b/>                       <!-- 太字 -->
      </w:rPr>
      <w:t>テキスト内容</w:t>          <!-- テキスト本体 -->
    </w:r>
    <w:r>                            <!-- 書式が変わると新しい run になる -->
      <w:t xml:space="preserve"> 続きのテキスト</w:t>
    </w:r>
  </w:p>
</w:body>
```

### 主要な要素

| 要素 | 説明 |
|------|------|
| `<w:body>` | 文書本体のルート |
| `<w:p>` | 段落。改行は段落の区切りに相当 |
| `<w:pPr>` | 段落プロパティ（スタイル、インデント、配置） |
| `<w:r>` | ラン。同一書式が続くテキストの最小単位 |
| `<w:rPr>` | ランプロパティ（太字 `<w:b/>`、斜体 `<w:i/>`、フォント `<w:rFonts>` 等） |
| `<w:t>` | テキスト本体。`xml:space="preserve"` で先頭・末尾の空白を保持 |
| `<w:br/>` | 改行（段落内の強制改行） |
| `<w:tab/>` | タブ文字 |
| `<w:hyperlink>` | ハイパーリンク。`r:id` で `.rels` ファイル内の URL を参照 |
| `<w:tbl>` | 表 |
| `<w:sectPr>` | セクションプロパティ（ページサイズ、余白、段組み） |

### テキスト編集時の注意

- 1つの「見た目上の文」が**複数の `<w:r>` に分割**されていることが多い（書式変更、スペルチェック痕跡、編集履歴等による）
- テキスト置換時は `<w:t>` の中身のみ変更し、タグ構造は壊さない
- `xml:space="preserve"` がない `<w:t>` では先頭・末尾の空白が無視される
- `&`, `<`, `>` はXMLエンティティ（`&amp;`, `&lt;`, `&gt;`）としてエスケープが必要

---

## 4. [Content_Types].xml

すべてのパーツの Content-Type を宣言するファイル。新しいパーツ（XML ファイル）を追加した場合は、ここに Override を追加しないと Word が認識しない。

```xml
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml"
            ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml"
            ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>
```

### 代表的な ContentType 値

| パーツ | ContentType |
|--------|-------------|
| document.xml | `application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml` |
| styles.xml | `...wordprocessingml.styles+xml` |
| comments.xml | `...wordprocessingml.comments+xml` |
| numbering.xml | `...wordprocessingml.numbering+xml` |
| header/footer | `...wordprocessingml.header+xml` / `...footer+xml` |
| 画像 (png) | `image/png` |
| 画像 (jpeg) | `image/jpeg` |

---

## 5. リレーションシップファイル (.rels)

パーツ間の参照関係を定義する。`rId1`, `rId2` 等の ID で参照する。

### `_rels/.rels`（パッケージレベル）

```xml
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="...officeDocument" Target="word/document.xml"/>
</Relationships>
```

### `word/_rels/document.xml.rels`（文書レベル）

```xml
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="...styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="...image" Target="media/image1.png"/>
  <Relationship Id="rId3" Type="...hyperlink" Target="https://example.com" TargetMode="External"/>
</Relationships>
```

### 新しいパーツを追加する場合

1. XML ファイルを `word/` 以下に配置
2. `[Content_Types].xml` に Override を追加
3. `word/_rels/document.xml.rels` に Relationship を追加
4. document.xml 内で `r:id` を使って参照

---

## 6. ZIP 解凍・再圧縮の手順

### Python での操作

```python
import zipfile, shutil, os

# === 解凍 ===
with zipfile.ZipFile('input.docx', 'r') as z:
    z.extractall('work_dir')

# === XML 編集 ===
# work_dir/word/document.xml 等を編集

# === 再圧縮 ===
with zipfile.ZipFile('output.docx', 'w', zipfile.ZIP_DEFLATED) as zout:
    for root, dirs, files in os.walk('work_dir'):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, 'work_dir')
            zout.write(file_path, arcname)
```

### 既存 .docx のパーツを差し替える方法

```python
import zipfile

replacements = {
    'word/document.xml': modified_xml_bytes,
}
new_files = {
    'word/comments.xml': comments_xml_bytes,
}

with zipfile.ZipFile('base.docx', 'r') as zin:
    with zipfile.ZipFile('output.docx', 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename in replacements:
                zout.writestr(item, replacements[item.filename])
            else:
                zout.writestr(item, zin.read(item.filename))
        for name, content in new_files.items():
            zout.writestr(name, content)
```

### コマンドラインでの操作

```bash
# 解凍
mkdir work_dir && cd work_dir && unzip ../input.docx

# 編集後、再圧縮（ルートディレクトリに注意）
cd work_dir
zip -r ../output.docx . -x ".*"
```

---

## 7. よくある落とし穴

### ZIP 構造に関するもの

| 問題 | 原因と対策 |
|------|-----------|
| Word で開けない / 修復を求められる | `[Content_Types].xml` が ZIP のルート直下にない。Windows の「送る→圧縮」等で余計なフォルダ階層が入ることがある |
| 新規追加したパーツが無視される | `[Content_Types].xml` に Override を追加していない、または `document.xml.rels` に Relationship を追加していない |
| 画像が表示されない | `word/media/` 内のファイルと `document.xml.rels` の `Target` パスが一致していない |

### XML 編集に関するもの

| 問題 | 原因と対策 |
|------|-----------|
| テキストの先頭・末尾の空白が消える | `<w:t>` に `xml:space="preserve"` が付いていない |
| 特殊文字でパースエラー | `&`, `<`, `>` を XML エンティティにエスケープしていない |
| 書式が崩れる | `<w:r>` の分割を変えると `<w:rPr>` の適用範囲が変わる。元の run 構造を維持すること |
| Word が「修復」してデータが消える | XML の構造エラー（閉じタグ漏れ、不正なネスト等）。編集後に XML バリデーションを推奨 |

### .doc 形式に関するもの

| 問題 | 原因と対策 |
|------|-----------|
| .doc は ZIP ではない | .doc はバイナリ形式（OLE2）。XML 編集不可。先に .docx に変換が必要 |
| 変換方法 (Windows) | `win32com.client` で COM 経由変換：`doc.SaveAs2(path, FileFormat=16)` |
| 変換方法 (Linux/Mac) | LibreOffice: `soffice --headless --convert-to docx input.doc` |

### xml.etree.ElementTree の名前空間破損（致命的）

Python 標準ライブラリの `xml.etree.ElementTree`（以下 ET）で document.xml を **parse → 編集 → serialize** すると、**Word が開けない破損ファイル**が生成される。

#### 根本原因

ET は XML をパース・シリアライズする際に以下の問題を起こす：

1. **名前空間プレフィックスを `ns0`, `ns1`, `ns2`... に書き換える**
   - 元: `<w:document xmlns:w="..." xmlns:mc="..." xmlns:w14="...">`
   - ET 出力: `<ns0:document xmlns:ns0="..." xmlns:ns1="..." xmlns:ns2="...">`
2. **未使用の名前空間宣言を削除する**
   - 元の 30 以上の名前空間宣言が 3 つ程度に減る
3. **`mc:Ignorable` 属性の参照先が壊れる**
   - 元: `mc:Ignorable="w14 w15 w16se w16cid ..."`
   - ET 出力: `ns1:Ignorable="w14 w15 w16se ..."` — `w14` 等のプレフィックスが未定義のため Word が解読不能

`ET.register_namespace()` で主要なプレフィックスを登録しても、すべてのプレフィックスを網羅できず不完全。

#### 対策

**`lxml` を使用すること**。lxml は元の名前空間プレフィックスをそのまま保持する。

```python
from lxml import etree

# パース（名前空間プレフィックスを保持）
parser = etree.XMLParser(remove_blank_text=False)
root = etree.fromstring(doc_xml_bytes, parser)

# 編集...

# シリアライズ（プレフィックス保持）
modified = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
```

**ET を使ってはならないケース**: document.xml 全体をパース→シリアライズする処理全般。
**ET を使っても問題ないケース**: XML をパースして**読み取りのみ**行い、シリアライズしない場合。

#### `xml:space` 属性の重複

ET で `<w:t>` 要素に `xml:space="preserve"` を設定する際、
既に属性がある要素に `t.set("xml:space", "preserve")` とすると**属性が重複**し、
パースエラー（`duplicate attribute`）が発生する。

```python
# ❌ ET での誤った設定（重複の可能性）
t_elem.set("xml:space", "preserve")

# ✅ lxml なら問題なし（上書きされる）
t_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
```

#### lxml 要素の真偽値評価（`if element:` は使わない）

lxml 要素に対して `if element:` を使うと、**子要素の有無**で真偽を判定する（現行の lxml の挙動）。
`<w:t>テキスト</w:t>` はテキスト内容を持つが子要素はないため `False` と評価され、
要素が見つかっているにもかかわらずブロックがスキップされるバグになる。

```python
t = find_some_element(para, "...")

# ❌ 子要素がなければ False → ブロックをスキップしてしまう
if t:
    t.text = "新しいテキスト"   # 実行されない！

# ✅ None チェックに統一する
if t is not None:
    t.text = "新しいテキスト"   # 正しく実行される
```

> **補足**: lxml は将来のバージョンで `if element:` が常に `True` を返すよう変更予定（`FutureWarning` が出る）。
> 現時点では `if element is not None:` を使うことで現行・将来両方に対応できる。

---

### テキスト run の分割に関するもの

| 問題 | 原因と対策 |
|------|-----------|
| テキスト置換で文字列が見つからない | 1 つの「見た目上の文字列」が複数の `<w:r>` に分割されていることがある（スペルチェック、書式変更、編集履歴等による）。run をまたいで検索するか、個別の run を順に処理する |
| **見出し1単語が2 run に分割されて置換が効かない** | 例: `"Acknowledgement"` が `"A"` + `"cknowledgement"` に分割されており、`t.text.replace("Acknowledgement", ...)` がどの run にもマッチしない。**対策: `set_single_run_text(para, new_text)` で段落全体のテキストを1 run に置き換える（書式は pPr から継承）** |
| Endnote 更新でスペースや句読点が消える | スペース等をフィールドの表示テキスト（`separate` ～ `end`）内に入れてしまった。フィールド外（`begin` より前の run）に配置する。詳細はセクション 9 参照 |
| 同一ファイルの ZIP 同時読み書きでエラー | `zipfile.ZipFile` で同じパスを読み取り用と書き込み用で同時に開くと `BadZipFile` エラーになる。先に全データをメモリ（dict 等）に読み込んでからファイルを閉じ、その後で書き出す |
| **EndNoteフィールド挿入で置換回数が予想より多い** | docx 内に文献リスト（書誌情報）を含めていると、書誌情報中の巻号表記（例: `52(3):102` の `(3)`）が引用マーカーと誤マッチする。**対策: EndNoteフィールド挿入前の docx には文献リストを含めない**。EndNote の「Update Citations and Bibliography」で自動生成されるため手動リストは不要 |
| **接続詞を削除したのに次の run の前に残ってしまう** | 例: `Run A: "…関係にあることが明らかになってきた。加えて、"` / `Run B: "昨今の"` という分割の場合、Run B だけを書き換えても Run A 末尾の「加えて、」が残る。**対策: 後続 run を書き換えるときは、前の run 末尾のゴミ文字列も別途 `replace_in_t` で除去する** |

### ページブレーク（`<w:br type="page">`）と見出しの混在に関するもの

Word では「セクション境界」の前後を1つの `<w:p>` にまとめる場合がある。特に**ページブレーク + 次ページの見出し**が同一段落に収まっているケースが実在する。

```xml
<!-- よくある落とし穴: 1つの w:p に複数の論理ブロックが混在 -->
<w:p>
  <!-- 前のセクションのテキスト（例: Abstractの最終段落） -->
  <w:r><w:t>...Conclusion text...</w:t></w:r>

  <!-- ページブレーク -->
  <w:r><w:br w:type="page"/></w:r>

  <!-- 次のセクション見出し（例: INTRODUCTION） -->
  <w:r><w:rPr><w:b/></w:rPr><w:t>I</w:t></w:r>
  <w:r><w:rPr><w:b/></w:rPr><w:t>NTRODUCTION</w:t></w:r>
</w:p>
```

| 問題 | 原因と対策 |
|------|-----------|
| **段落を削除したら次ページの見出しも消えた** | `get_text(para)` でテキストを取得すると「Conclusion text...INTRODUCTION」のように連結されて見える。先頭テキストで段落を識別して `body.remove(para)` すると、後半の見出し（ページブレーク後）も一緒に消える |
| **対策: 削除前に段落内のページブレークを確認する** | 段落を削除する前に `para.iter(f"{W}br")` でページブレークの有無を確認。存在する場合はページブレーク後のコンテンツを別段落として分離してから削除する |

```python
def split_para_at_pagebreak(body, para):
    """
    w:br type="page" を含む段落を2つに分割する。
    前半(ページブレークまで)と後半(ページブレーク後)を別々の w:p として返す。
    元の para は body から削除される。
    """
    from copy import deepcopy
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    pPr = para.find(f"{W}pPr")
    before_runs, after_runs = [], []
    found_pb = False

    for child in para:
        if child.tag != f"{W}r":
            continue
        br = child.find(f"{W}br")
        if br is not None and br.get(f"{W}type") == "page":
            found_pb = True
            continue  # ページブレーク run はスキップ
        if found_pb:
            after_runs.append(child)
        else:
            before_runs.append(child)

    if not found_pb:
        return  # ページブレークなし → 分割不要

    # before 段落（元の para を再利用）
    for child in list(para):
        if child.tag == f"{W}r":
            para.remove(child)
    for r in before_runs:
        para.append(r)

    # after 段落（新規作成して元の para の直後に挿入）
    after_p = etree.Element(f"{W}p")
    if pPr is not None:
        after_p.append(deepcopy(pPr))
    for r in after_runs:
        after_p.append(deepcopy(r))

    idx = list(body).index(para)
    body.insert(idx + 1, after_p)
```

**推奨フロー**: 段落削除・置換の前に必ずページブレークの有無を確認し、混在している場合は `split_para_at_pagebreak()` で分離してから処理する。

### Windows の日本語パスに関するもの

| 問題 | 原因と対策 |
|------|-----------|
| **日本語パスを含む docx で `FileNotFoundError`** | Bash のコマンドラインに直接 Python コードを書く（`python -c "..."`）と、パス内の日本語が文字化けしてファイルが見つからないエラーになる。**対策: 必ずスクリプトファイル（`.py`）に書き出してから `python script.py` で実行する** |

---

## 8. XML 編集に便利なツール

| ツール | 用途 |
|--------|------|
| Python `lxml` | **推奨**。名前空間プレフィックスを保持したまま XML を読み書きできる。`xml.etree.ElementTree` はプレフィックスを破壊するため .docx 編集には**使用禁止**（セクション 7 参照） |
| Python `xml.etree.ElementTree` (標準) | **読み取り専用**に限定。シリアライズすると名前空間が壊れるため、編集→保存には使わないこと |
| Python `zipfile` (標準) | .docx の ZIP 解凍・圧縮 |
| Python `re` | 正規表現で `<w:t>` 内テキストを素早く抽出 |
| テキストエディタ (VSCode 等) | XML の手動確認・簡易編集 |
| 7-Zip | GUI で .docx の中身を直接閲覧・差し替え |

---

## 9. Endnote フィールドコードの構造と注意点

### フィールドコードの XML 構造

Endnote の引用は Word のフィールドコードとして document.xml に埋め込まれている。**2 種類の形式**があるので、対象 docx を確認してから編集方針を決めること。

#### 形式A: ADDIN EN.CITE（instrText 形式）

引用データを `instrText` に XML 文字列として直接埋め込む。

```xml
<w:r><w:fldChar w:fldCharType="begin"/></w:r>
<w:r><w:instrText xml:space="preserve"> ADDIN EN.CITE &lt;EndNote&gt;...&lt;/EndNote&gt;</w:instrText></w:r>
<w:r><w:fldChar w:fldCharType="separate"/></w:r>
<w:r><w:t>(Redeker et al., 2019)</w:t></w:r>
<w:r><w:fldChar w:fldCharType="end"/></w:r>
```

#### 形式B: ADDIN EN.CITE.DATA（fldData 形式）

引用データを `fldChar` 要素の子 `fldData` に **base64 エンコード**して保持する。`instrText` はラベルのみで中身なし。

```xml
<w:fldChar w:fldCharType="begin">
  <w:fldData xml:space="preserve">PEVuZE5vdGU+...（base64）</w:fldData>
</w:fldChar>
<w:instrText> ADDIN EN.CITE.DATA </w:instrText>  ← ラベルのみ、編集不要
...
<w:fldChar w:fldCharType="separate"/>
<w:t>(10)</w:t>
<w:fldChar w:fldCharType="end"/>
```

**見分け方**: `document.xml` 内で `<w:fldData` を検索。存在すれば形式B。

**形式Bの引用データを更新する場合**: `instrText` ではなく `fldData` の base64 を書き換える。フォーマットは **76文字/行・CRLF改行**。

```python
import base64

def b64_encode_flddata(xml_str: str) -> str:
    b64 = base64.b64encode(xml_str.encode('utf-8')).decode('ascii')
    lines = [b64[i:i+76] for i in range(0, len(b64), 76)]
    return '\r\n'.join(lines) + '\r\n'
```

### 重要な領域の区分

| 領域 | 位置 | Endnote 更新時 |
|------|------|----------------|
| `instrText` | `begin` ～ `separate` の間 | **保持される**（引用のメタデータ） |
| 表示テキスト | `separate` ～ `end` の間の `<w:t>` | **再生成される**（上書きされる） |
| フィールド外 | `begin` より前、`end` より後 | **影響なし** |

### フィールドのネスト

Endnote フィールドは内部に `EN.CITE.DATA` のネストされたフィールドを含む。フィールド境界を走査するときは **depth（深さ）を追跡** し、トップレベルの `begin`/`separate`/`end` のみを処理すること。

```python
field_depth = 0
for run in runs:
    fld_type = get_fld_char_type(run)
    if fld_type == 'begin':
        field_depth += 1
        if field_depth == 1:
            # トップレベルのフィールド開始
            ...
    elif fld_type == 'separate':
        if field_depth == 1:
            # トップレベルの表示テキスト開始
            ...
    elif fld_type == 'end':
        if field_depth == 1:
            # トップレベルのフィールド終了
            ...
        field_depth -= 1
```

### スペースの配置に関する落とし穴

**問題**: 引用前のスペース（例：`text (Author, 2020)`）を追加・修正する際、スペースをフィールド内の表示テキストに入れてしまうと、Endnote が引用を更新した際にスペースごと消えてしまう。

```xml
<!-- ❌ 悪い例：スペースがフィールド内 → Endnote 更新で消える -->
<w:r><w:t>productivity</w:t></w:r>
<w:r><w:fldChar w:fldCharType="begin"/></w:r>
...
<w:r><w:fldChar w:fldCharType="separate"/></w:r>
<w:r><w:t xml:space="preserve"> (Redeker et al., 2019)</w:t></w:r>
<w:r><w:fldChar w:fldCharType="end"/></w:r>

<!-- ✅ 正しい例：スペースがフィールド外 → Endnote 更新でも維持 -->
<w:r><w:t xml:space="preserve">productivity </w:t></w:r>
<w:r><w:fldChar w:fldCharType="begin"/></w:r>
...
<w:r><w:fldChar w:fldCharType="separate"/></w:r>
<w:r><w:t>(Redeker et al., 2019)</w:t></w:r>
<w:r><w:fldChar w:fldCharType="end"/></w:r>
```

**対策**: スペースや句読点を引用に付加するときは、必ず `fldChar type="begin"` **より前の run** に配置する。表示テキスト（`separate` ～ `end` の間）は Endnote が管理する領域であり、手動の変更は更新時に失われる。

### 一般原則

- フィールドの **表示テキスト**（`separate` ～ `end`）は読み取り専用と考える
- テキストの追加・修正はフィールド **外** で行う
- `xml:space="preserve"` を忘れると、追加したスペースが Word に無視される
- 同じファイルに対する ZIP の同時読み書きは不可。全データをメモリに読み込んでから書き出す

### EndNote 引用スタイル変更時の句読点・スペース一括修正

EndNoteの出力スタイルを変更すると、引用番号と周囲の句読点・スペースの位置関係がずれることがある。**方向A（句読点をフィールド前→後に移動）** と **方向B（句読点をフィールド後→前に移動）** の2パターンがあり、スタイル変更の内容に応じて使い分ける。

#### 方向A: 句読点をフィールド前→後に移動

引用番号の前に句読点が付いている状態を、引用番号の後に移す。

| 変更前 | 変更後 | 説明 |
|---|---|---|
| `sleepiness,(1)` | `sleepiness (1),` | カンマを後に移動 |
| `injuries.(3)` | `injuries (3).` | ピリオドを後に移動 |
| `guidelines;(18)` | `guidelines (18);` | セミコロンを後に移動 |
| `jetlag(4)` | `jetlag (4)` | スペース欠落の補完 |

**操作手順:**
1. フィールド前の `<w:t>` 末尾から句読点を除去し、スペースを付与
2. フィールド後の `<w:t>` 先頭に除去した句読点を挿入

#### 方向B: 句読点をフィールド後→前に移動

引用番号の後に句読点が付いている状態を、引用番号の前に移す。

| 変更前 | 変更後 | 説明 |
|---|---|---|
| `sleepiness (1),` | `sleepiness,(1)` | カンマを前に移動 |
| `injuries (3).` | `injuries.(3)` | ピリオドを前に移動 |
| `guidelines (18);` | `guidelines;(18)` | セミコロンを前に移動 |

**操作手順:**
1. フィールド後の `<w:t>` 先頭から句読点を除去
2. フィールド前の `<w:t>` 末尾のスペースを除去し、句読点を付与

#### 共通の原則

1. フィールド内（`begin` ～ `end`）は**一切触らない**（EndNoteが管理する領域）
2. `<w:t>` を書き換えたら `xml:space="preserve"` を必ず設定
3. 対象句読点: `,` `.` `;` — 必要に応じて追加（`:` `?` 等）

#### 自動修正スクリプトの実装方針（lxml 使用）

```python
from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
PUNCT_CHARS = (',', '.', ';')  # 移動対象の句読点。必要に応じて追加

# ── 共通: 段落ごとに「イベント列」を構築 ──
# 1つの <w:r> 内に複数の <w:fldChar> が存在する場合があるため、
# find() ではなく子要素を順に走査してフラット化する
events = []
for child in para:
    if child.tag == f"{W}r":
        for sub in child:
            if sub.tag == f"{W}fldChar":
                events.append(("fld", sub.get(f"{W}fldCharType"), child, sub))
            elif sub.tag == f"{W}instrText":
                events.append(("instr", sub.text or "", child, sub))
            elif sub.tag == f"{W}t":
                events.append(("text", sub.text or "", child, sub))

# ── EN.CITE フィールドを検出（depth 追跡でネスト対応） ──
# 各フィールドについて prev_t（直前の <w:t>）と after_t（直後の <w:t>）を特定

# ── 方向A: 句読点をフィールド前→後に移動 ──
# if prev_t.text.rstrip()[-1] in PUNCT_CHARS:
#     punct = prev_t.text.rstrip()[-1]
#     prev_t.text = prev_t.text.rstrip()[:-1] + " "   # 句読点除去、スペース付与
#     after_t.text = punct + after_t.text               # 句読点を先頭に挿入

# ── 方向B: 句読点をフィールド後→前に移動 ──
# if after_t.text.lstrip()[0] in PUNCT_CHARS:
#     punct = after_t.text.lstrip()[0]
#     after_t.text = after_t.text.lstrip()[1:]          # 句読点除去
#     prev_t.text = prev_t.text.rstrip() + punct        # 句読点を末尾に付与、スペース除去
```

#### 注意点・落とし穴

- **対象句読点の網羅**: `,` `.` だけでなく **`;`** も忘れずに含める。セミコロンは列挙的引用（`guidelines;(18) ILO recommendations;(19)`）で出現する
- **上付き文字スタイルの引用**: EndNoteの出力スタイルによっては `(N)` ではなく上付き数字 `³²` で表示されるフィールドが混在することがある。`<w:vertAlign w:val="superscript"/>` を持つ表示テキストがこれに該当する。これらは句読点パターンが異なる可能性があるため、自動修正後に目視確認を推奨
- **フィールド前後にテキストがない場合**: フィールドが段落先頭・末尾にある場合、対応する `<w:t>` が存在しない。この場合は新しい `<w:r>` を作成してフィールドの直前または直後に挿入し、句読点を格納する
- **表示テキストは読み取り専用**: `separate` ～ `end` 間のテキストは EndNote が「Update Citations and Bibliography」時に再生成するため、手動変更は上書きされる。句読点やスペースは必ずフィールド外に配置する
- **方向Bでのスペース除去**: 方向Bでは `text (1),` → `text,(1)` のように、フィールド前のスペースも除去する必要がある。`prev_t.text.rstrip()` で末尾スペースを除去してから句読点を付与すること

---

## 10. 編集後の検証チェックリスト

- [ ] `[Content_Types].xml` が ZIP ルート直下にある
- [ ] 追加したパーツの Override が `[Content_Types].xml` にある
- [ ] 追加したパーツの Relationship が対応する `.rels` にある
- [ ] XML が well-formed である（閉じタグ漏れがない）
- [ ] Word で開いて「修復」ダイアログが出ない
- [ ] テキスト内容が意図通りに表示される
- [ ] 書式（太字、フォント等）が維持されている
- [ ] 画像・ハイパーリンクが正常に機能する
