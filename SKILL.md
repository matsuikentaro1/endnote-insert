---
name: endnote-insert
description: "Word文書(.docx)内のプレーンテキスト文献番号をEndNoteフィールドコードに変換する。PubMed APIから書誌情報を取得し、OOXMLフィールドコードを生成してマーカーを置換する。EndNoteスタイル変更時の句読点・スペース位置の一括修正（方向A/B）にも対応。トリガー: EndNoteフィールド挿入, 文献番号をEndNoteに変換, 句読点位置修正, /endnote-insert"
---

# EndNote Field Inserter

Word文書内のプレーンテキスト文献マーカー（例: `(4)`, `(11)`）を、EndNoteが認識するフィールドコードに自動変換する。EndNoteスタイル変更時の句読点・スペース位置調整にも対応。

> **関連ツール**: PubMedを見ながら1件ずつ対話的に引用を挿入する場合は、Chrome拡張 **PubMed2EndNote**（https://github.com/matsuikentaro1/pubmed2endnote）を使う。拡張機能はWordフレーバーHTMLをクリップボード経由で貼り付ける方式、本スキルはdocxのXMLを直接編集する方式で、「docx内の多数マーカーの一括変換」は本スキルの担当。

## 処理フロー（新規挿入）

1. ユーザーから対象情報を収集（docxパス、マーカーとPMIDの対応表）
2. `scripts/endnote_inserter.py` の `__main__` ブロックを編集
3. スクリプトを実行（PubMed API取得 → XML生成 → docx内マーカー置換 → バリデーション）
4. 出力docxをユーザーに報告

## ステップ1: 対象情報の収集

### 1a: 文献リスト（マーカーとPMIDの対応）の取得

まずプロジェクトフォルダ内にCSVファイルがないか確認する。

```
Glob pattern: **/*.csv
```

CSVが見つかった場合:
- `PubMed_ID` 列（または類似の列名）があるか確認する
- マーカー番号との対応が含まれているか確認する
- 含まれていれば、CSVからPMIDリストを読み取って使用する
- **★ `_tmp_refs_*.csv` が残っている場合、マージ未完了の可能性が高い。処理を中断し、codex-refsのマージ手順を先に実行するようユーザーに報告する**
- **★ PubMed_ID列が空欄の行がある場合、そのままendnote挿入に進まない。空欄の原因を調査し、PubMed APIまたはcodex-refsで補完する**

CSVがない場合、またはCSVにPMID情報がない場合:
- ユーザーに各マーカーとPMIDの対応表を確認する
- PMIDが不明な場合は、PubMedで著者名・年・タイトルから検索して特定する

### ★ PMIDハルシネーション防止ルール（絶対厳守）

過去にLLMがPMIDを「記憶」から捏造し、完全に間違った論文がEndNoteフィールドに挿入される重大事故が発生した。以下のルールを絶対に守ること。

1. **PMIDを「記憶」や「推測」で生成することは絶対に禁止** — PMIDは必ずCSVファイル（codex-refsの出力）またはPubMed APIの検索結果から取得する。著者名と年からPMIDを「思い出す」ことはできない
2. **entries配列の各PMIDに出典をコメントで明記する** — 例: `{'pmid': '37275982', 'marker': '[6]'},  # refs.csv row 4` のように、どのCSVの何行目から取得したかを書く。出典コメントを書けないPMIDは使用禁止
3. **スクリプト実行前にドライラン検証を行う** — 全PMIDについてPubMed APIを叩き、返ってきた著者名・年・タイトルをユーザーに提示して、意図した文献と一致することを確認してから本実行する
4. **CSVのPubMed_ID列が空欄のまま次工程に進まない** — 空欄は必ずマージ漏れか検索漏れ。原因を特定して補完する

### 1b: その他の確認事項

- 入力docxファイルのパス
- 出力docxファイルのパス
- EndNoteライブラリのdb-id（既存フィールドから取得、初回のみ）

### 1c: 対象外文献の除外

PubMedに収録されていない文献（FDA通知、行政文書、和文論文等）はスクリプトでは処理できない。対象から除外し、手動対応が必要な旨をユーザーに伝える。

## ステップ2: スクリプトの準備

`scripts/endnote_inserter.py` をプロジェクトフォルダにコピーし、`__main__` ブロックを編集する。

編集箇所:
1. `ENDNOTE_DB_ID`（スクリプト冒頭の定数）を対象EndNoteライブラリのdb-idに変更
2. `entries` リストにマーカーとPMIDの対応を記載
3. `input_docx` と `output_docx` のパスを設定

db-idの取得方法: docxをzipとして展開し、`word/document.xml` 内で `db-id=` を検索する。既存のEndNoteフィールドがない場合は任意の値でよい。

## ステップ3: 実行

```bash
python endnote_inserter.py
```

各文献について以下が出力される:
- タイトル（PubMedから取得）
- 置換箇所数
- 最終的なXMLバリデーション結果

## ステップ4: 確認とユーザーへの報告

報告する内容:
- 各マーカーの置換箇所数
- XMLバリデーション結果（valid / invalid）
- PubMedにない文献で手動対応が必要なもの
- 次の手順: Wordで開いてEndNoteの「Update Citations and Bibliography」を実行

---

## 絶対に守るべきルール

### 複数文献マーカーの処理（重要）

1箇所に複数文献を引用するマーカー（例: `[PMID 33150256; 37041858]` や `(1, 2)` や `(3-5)`）は、**multi-cite XML（`<EndNote><Cite>...<Cite>...</EndNote>`）を使わず、各PMIDごとに独立した EndNoteフィールドを生成し、スペースを空けずに隣接させる**。

```xml
<!-- ✅ 正しい: 個別フィールドをスペースなしで隣接 -->
<w:r><w:fldChar w:fldCharType="begin"/></w:r>
... ADDIN EN.CITE <文献A> ...
<w:r><w:fldChar w:fldCharType="end"/></w:r><w:r><w:fldChar w:fldCharType="begin"/></w:r>
... ADDIN EN.CITE <文献B> ...
<w:r><w:fldChar w:fldCharType="end"/></w:r>
```

**理由:** Word で EndNoteの「Update Citations and Bibliography」を実行すると、隣接するフィールドが自動的に結合されて `(1, 2)` のように表示される。multi-cite XML を手作りすると構造が複雑になりバグの原因になるが、個別フィールドの隣接なら `build_field_xml()` をそのまま使えて安全。

**実装パターン:**
```python
field_xml_parts = []
for pmid in pmids:
    nbib = pmid_data[pmid]
    en_xml = build_endnote_xml(nbib)
    display = f'({first_author}, {year})'
    field_xml_parts.append(build_field_xml(en_xml, display))
field_xml = ''.join(field_xml_parts)  # スペースなしで結合
```

### document.xml編集

- **ElementTree（ET）でのパース→シリアライズは絶対にしない** — `ET.tostring()` が未使用の名前空間宣言を削除し、docxが破損する（30以上の`xmlns:xx`宣言が3つ程度に減る）。文字列ベースで直接編集するか、`lxml` を使う。
- **lxml 使用時は `if element:` を使わず `if element is not None:` を使う** — lxml 要素の真偽値は **子要素の有無** で判定される。`<w:t>テキスト</w:t>` は子要素がないため `False` と評価され、要素が見つかっているのにブロックがスキップされる重大バグになる。
- **`<w:r>` 検索時は `<w:rPr>`, `<w:rFonts>` 等への誤マッチに注意**。タグ名直後の文字をチェック。
- **段落削除前にページブレーク（`<w:br type="page"/>`）の有無を確認** — 1つの `<w:p>` にページブレークと次ページの見出しが混在するケースがある。先頭テキストで識別して削除すると、後半の見出しまで消える。ページブレークを含む段落を削除する場合は `split_para_at_pagebreak()` で分離してから処理する（詳細は `references/docx_xml_editing.md` セクション7参照）。

### 書誌情報

- PMIDさえ正しければPubMed APIが正確な書誌情報を返すため、書誌情報のハルシネーションは混入しない。**ただし、PMID自体が間違っていれば全く別の論文が挿入される。PMIDの正しさは上流工程（CSV）で保証する必要がある。**
- API rate limit対策として文献間に0.5秒のスリープを入れる。
- `fetch_pubmed_xml()` はNCBI利用ポリシー準拠の `tool`/`email` パラメータ付与と、429/5xx・タイムアウト時の自動リトライ（最大3回、待機1s→2s）を実装済み。
- DOIは `ArticleIdList` に無い場合 `Article/ELocationID` からフォールバック取得する（一部文献はELocationIDにしかDOIが無い）。
- EDAT（custom4に入る日付）は `ArticleDate[DateType=Electronic]`（正式な電子出版日）を優先し、無ければ History の entrez date にフォールバックする。
- **PubMed APIはXML形式で取得すること**（`rettype=xml&retmode=xml`）。MEDLINE テキスト形式（`rettype=medline&retmode=text`）はウムラウト等の Unicode 文字を ASCII に変換して返すため、`Yücel → Yucel`、`Schröder → Schroder` のような文字化けが発生する。`endnote_inserter.py` は `fetch_pubmed_xml()` / `parse_pubmed_xml()` を使用しており対応済み。

### 文献リストを docx に含めてはいけない（重要）

**問題:** docx 内に文献リストを含めると、書誌情報中の巻号表記（例: `Sleep medicine. 52(3):102-110` の `(3)`）が引用マーカーと誤マッチし、本来とは無関係の箇所にEndNoteフィールドが挿入される。

**実例:** 引用マーカー `(3)` を処理する際、巻号 `52(3):...` の `(3)` にも誤マッチして置換回数が増加した。

**対策:** 引用マーカー挿入前のdocxには文献リストを含めない。EndNoteが「Update Citations and Bibliography」で自動生成するため、手動リストは不要。

### スクリプト実行方法（Windowsの日本語パス問題）

**問題:** Windowsで日本語を含むパスにあるdocxを操作する場合、Bashのコマンドラインに直接Pythonコードを書くと（`python -c "..."`）、パス文字列が文字化けして `FileNotFoundError` になることがある。

**対策:** 必ずスクリプトファイル（`.py`）に書き出してから実行する。

```bash
# ❌ 避ける
python -c "import zipfile; zipfile.ZipFile('C:\\日本語パス\\file.docx')"

# ✅ 正しい
# → スクリプトファイルに書き出してから実行
python script.py
```

---

## EndNote フィールド形式の違い（重要）

Word の EndNote 引用には **2種類のフィールド形式**がある。対象 docx を確認してからスクリプトを選択すること。

### 形式A: ADDIN EN.CITE（instrText 形式）

`endnote_inserter.py` が生成する標準形式。引用 XML は `instrText` に直接埋め込む。

```xml
<w:fldChar w:fldCharType="begin"/>
<w:instrText> ADDIN EN.CITE &lt;EndNote&gt;...&lt;/EndNote&gt;</w:instrText>
...
```

### 形式B: ADDIN EN.CITE.DATA（fldData 形式）

Word の新しい形式。引用 XML は `fldChar` の子要素 `fldData` に **base64 エンコード**して格納する。

```xml
<w:fldChar w:fldCharType="begin">
  <w:fldData xml:space="preserve">PEVuZE5v...（base64）</w:fldData>
</w:fldChar>
<w:instrText> ADDIN EN.CITE.DATA </w:instrText>  ← ただのラベル、中身なし
...
```

**見分け方**: `document.xml` 内で `fldData` タグを検索。あれば形式B。

**形式Bの既存文献を修正する場合**（過去プロジェクトで実績のある手順。専用スクリプトは同梱していないため、以下を参考に都度作成する）:
1. `fldData` の base64 をデコード → EndNote XML を取得
2. PubMed API で正しい書誌情報を取得して新 XML を構築
3. base64 エンコード（**76文字/行、CRLF改行**）して `fldData` を置き換え

```python
def b64_encode_flddata(xml_str: str) -> str:
    raw = xml_str.encode('utf-8')
    b64 = base64.b64encode(raw).decode('ascii')
    lines = [b64[i:i+76] for i in range(0, len(b64), 76)]
    return '\r\n'.join(lines) + '\r\n'
```

### フィールドのネスト — depth を追跡する

EndNote フィールドは内部に `EN.CITE.DATA` のネストされたフィールドを含む場合がある。フィールド境界を走査するときは **depth（深さ）を追跡** し、**トップレベルの `begin`/`separate`/`end` のみ** を処理すること。depth を追跡せずに処理すると、ネストされた内側のフィールドを独立したフィールドと誤認して壊す。

```python
field_depth = 0
for run in runs:
    fld_type = get_fld_char_type(run)
    if fld_type == 'begin':
        field_depth += 1
        if field_depth == 1:
            ...  # トップレベル開始のみ処理
    elif fld_type == 'separate':
        if field_depth == 1:
            ...  # トップレベルのみ処理
    elif fld_type == 'end':
        if field_depth == 1:
            ...  # トップレベル終了のみ処理
        field_depth -= 1
```

### スペース・句読点の配置（Endnote 更新で消える落とし穴）

**重要原則**: フィールドの **表示テキスト**（`separate` ～ `end` 間の `<w:t>`）は EndNote が「Update Citations and Bibliography」時に**再生成する**ため、手動変更は上書きされる。スペース・句読点は必ず **フィールド外**（`fldChar type="begin"` より前、または `type="end"` より後の run）に配置する。

```xml
<!-- ❌ 悪い例: スペースがフィールド内 → 更新で消える -->
<w:r><w:t>productivity</w:t></w:r>
<w:r><w:fldChar w:fldCharType="begin"/></w:r>
...
<w:r><w:fldChar w:fldCharType="separate"/></w:r>
<w:r><w:t xml:space="preserve"> (Redeker et al., 2019)</w:t></w:r>
<w:r><w:fldChar w:fldCharType="end"/></w:r>

<!-- ✅ 正しい例: スペースがフィールド外 → 更新でも維持 -->
<w:r><w:t xml:space="preserve">productivity </w:t></w:r>
<w:r><w:fldChar w:fldCharType="begin"/></w:r>
...
<w:r><w:fldChar w:fldCharType="separate"/></w:r>
<w:r><w:t>(Redeker et al., 2019)</w:t></w:r>
<w:r><w:fldChar w:fldCharType="end"/></w:r>
```

---

## EndNote スタイル変更時の句読点・スペース一括修正

EndNoteの出力スタイルを変更すると、引用番号と周囲の句読点・スペースの位置関係がずれる。**方向A** と **方向B** の2パターンを使い分ける。

### 方向A: 句読点をフィールド前→後に移動

| 変更前 | 変更後 |
|---|---|
| `sleepiness,(1)` | `sleepiness (1),` |
| `injuries.(3)` | `injuries (3).` |
| `guidelines;(18)` | `guidelines (18);` |
| `jetlag(4)` | `jetlag (4)` |

**操作:** フィールド前の `<w:t>` 末尾から句読点を除去しスペースを付与 → フィールド後の `<w:t>` 先頭に句読点を挿入。

### 方向B: 句読点をフィールド後→前に移動

| 変更前 | 変更後 |
|---|---|
| `sleepiness (1),` | `sleepiness,(1)` |
| `injuries (3).` | `injuries.(3)` |
| `guidelines (18);` | `guidelines;(18)` |

**操作:** フィールド後の `<w:t>` 先頭から句読点を除去 → フィールド前の `<w:t>` 末尾のスペースを除去し句読点を付与。

### 共通原則

1. フィールド内（`begin` ～ `end`）は**一切触らない**（EndNoteが管理する領域）
2. `<w:t>` を書き換えたら `xml:space="preserve"` を必ず設定（XML 名前空間は `{http://www.w3.org/XML/1998/namespace}space`）
3. 対象句読点は `,` `.` `;` を必須とし、必要に応じて `:` `?` 等を追加
4. **セミコロン `;` は列挙的引用**（例: `guidelines;(18) ILO;(19)`）で頻出するので忘れずに含める
5. 上付き文字スタイル（`<w:vertAlign w:val="superscript"/>`）の引用は句読点パターンが異なる可能性があるため、自動修正後に目視確認

### 実装テンプレート（lxml）

```python
from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
PUNCT_CHARS = (',', '.', ';')

# 段落ごとに「イベント列」を構築
# 1つの <w:r> 内に複数の <w:fldChar> が存在することがあるため、
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

# 各 EN.CITE フィールドを depth 追跡で検出し、
# prev_t（直前の <w:t>）と after_t（直後の <w:t>）を特定して句読点を移動する
```

詳細な実装例・注意点は `references/docx_xml_editing.md` セクション9を参照。

---

## 検証済み知見（PubMed2EndNote拡張機能開発, 2026-07）

Chrome拡張 PubMed2EndNote v3.0 の開発時に、Word COM自動操作による実験で確認した事実。本スキルの設計判断の根拠として記録する。

- **EndNote XMLの最小構造**: `foreign-keys`/`db-id` が無くてもEndNote（CWYW）はフィールドを引用として認識する（拡張機能は db-id なしで動作実証済み）。本スキルの `ENDNOTE_DB_ID` ハードコードは互換性のため維持しているが、必須ではない。
- **黄色ハイライトの配置**: ハイライトはフィールドを構成するrun自体の `w:rPr` に `w:highlight w:val="yellow"` として付ける（本スキルの現行方式が正しい）。フィールドの「外側」に付けた書式は表示部分に継承されない — RTFの `{\highlight7{\field...}}` のような外側指定は、Wordに読み込ませると実はハイライトが付かないことを実験で確認した。
- **クリップボード経由（拡張機能側）の制約**: Wordの貼り付け設定「他のプログラムからの貼り付け」が「書式を結合」だと、フィールドは生き残るがハイライト・フォント等の文字書式は除去される（太字・下線などの「強調」のみ生存）。**docxのXMLを直接編集する本スキルは貼り付けを経由しないため、この影響を受けない**。
- **DOI**: 一部文献では `ArticleIdList` にDOIが無く `Article/ELocationID[@EIdType='doi']` にのみ存在する。両対応が必要（実装済み）。
- **EDAT**: `ArticleDate[DateType=Electronic]` が正式な電子出版日。History の entrez date はPubMed登録日であり、両者は異なることがある。電子出版日を優先する（実装済み）。

---

## 詳細リファレンス

docx の構造、ZIP編集手順、lxml使用時の落とし穴、段落削除時の注意、EndNoteフィールドの全仕様については以下を参照：

- `references/docx_xml_editing.md` — docx ZIP解凍・XML編集・再圧縮ガイド（全10セクション）

特に以下のトピックを扱う場合は必読：
- 段落操作（削除・移動・分割）
- EndNoteフィールドの depth 追跡・ネスト処理
- 形式B（fldData base64）の修正
- 新しいパーツ（comments.xml等）の追加

---

## scripts/

- `endnote_inserter.py` — メインスクリプト。PubMed XML 取得、パース、EndNote XML 生成、OOXML フィールドコード生成（形式A）、docx 内マーカー置換、XML バリデーションを一括実行。

※ 過去のプロジェクトで使用した `fix_flddata_umlauts.py`（形式Bのウムラウト修正）や `fix_refs_10_24.py`（番号範囲の個別修正）は本ディレクトリには同梱していない。必要になったら本書の手順（形式Bのbase64エンコード仕様等）をもとに都度作成する。

---

## 隣接マーカーの置換漏れと自動リトライ（重要）

### 既知の問題

連番引用 `(3, 4)` をビルド時に `(3)(4)` に分割した場合、同一 `<w:t>` 要素内に隣接するマーカーが含まれる。最初のマーカー `(3)` を置換するとXML構造が大きく変化し、同じマーカー番号の2回目の出現（例: 後方の単独 `(3)`）が `find_run_boundaries` で正しく認識されずスキップされることがある。

### 対策（process_batch に実装済み）

`process_batch` は全エントリ処理後に `_scan_remaining_markers()` で未変換マーカーを自動検出し、残存があれば**最大3パスまで自動リトライ**する。PubMed APIデータはキャッシュされるため、リトライ時の追加API呼び出しは発生しない。

最終パス後もなお残存がある場合は WARNING を出力する。通常、2パス目で全マーカーが処理される。

### 呼び出し側での注意

- `process_batch` の戻り値が True でも、WARNING が出力されていないかログを確認する
- 手動で2回目のパスを走らせる必要はなくなった（以前は run_endnote_fix.py で対応していた）

---

## 編集後の検証チェックリスト

- [ ] XML が well-formed である（閉じタグ漏れがない）
- [ ] `process_batch` のログに「✓ All markers successfully replaced (verified)」が出力されている
- [ ] WARNING（未変換マーカー残存）が出力されていない
- [ ] Word で開いて「修復」ダイアログが出ない
- [ ] EndNote で「Update Citations and Bibliography」を実行して書誌情報が反映される
- [ ] 引用番号前後の句読点・スペースが意図通りの位置にある
- [ ] 書式（太字、上付き等）が維持されている
- [ ] ページブレーク・セクション構造が破損していない
