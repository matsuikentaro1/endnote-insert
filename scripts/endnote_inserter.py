#!/usr/bin/env python3
"""
PubMed-to-Word EndNote Inserter
文字列ベースでdocument.xmlを直接編集し、名前空間を完全に保持する
"""

import re
import sys
import io
import time
import zipfile
import urllib.error
import urllib.parse
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import os

ENDNOTE_DB_ID = os.environ.get('ENDNOTE_DB_ID', 'rzar25tsaxa9pvevtw3psfrssetwatfpez29')
NCBI_EMAIL = os.environ.get('NCBI_EMAIL', '')

# ============================================================
# 1. PubMed 取得・パース
# ============================================================

# 推奨: XML API（Unicode安全。ウムラウト等が ASCII 化されない）
import xml.etree.ElementTree as _ET


def fetch_pubmed_xml(pmid):
    """PubMed efetch APIから書誌情報をXMLで取得する。
    NBIB形式 (rettype=medline) は ASCII化される (Bögels→Bogels) ため、こちらを使う。
    NCBI利用ポリシー準拠のため tool/email を付加。
    429/5xx/タイムアウトは待機 1s→2s→4s で最大3回リトライする。
    """
    url = (f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
           f"?db=pubmed&id={pmid}&rettype=xml&retmode=xml"
           f"&tool=endnote-insert&email={urllib.parse.quote(NCBI_EMAIL)}")
    last_err = None
    for attempt in range(3):
        if attempt > 0:
            time.sleep(2 ** (attempt - 1))  # 1s, 2s
        try:
            with urllib.request.urlopen(urllib.request.Request(url), timeout=30) as resp:
                return resp.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                last_err = e  # 一時的エラーはリトライ
            else:
                raise  # 404等はリトライしても無駄なので即座に報告
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
    raise last_err


def parse_pubmed_xml(xml_text):
    """PubMed XMLレスポンスを NBIB 互換 dict にパースする。
    build_endnote_xml が参照するキー（PMID, FAU, TI, TA, JT, DP, PG, VI, IP,
    LID, IS, EDAT, PT, PL, SO, AD, MH, OT, OWN, LA）を可能な限り埋める。
    """
    root = _ET.fromstring(xml_text)
    article = root.find('.//PubmedArticle')
    if article is None:
        return {}

    data = {}

    # PMID
    pmid_node = article.find('.//MedlineCitation/PMID')
    if pmid_node is not None and pmid_node.text:
        data['PMID'] = pmid_node.text

    # MedlineCitation Owner (OWN)
    mc = article.find('.//MedlineCitation')
    if mc is not None and mc.get('Owner'):
        data['OWN'] = mc.get('Owner')

    # Title (TI) — 子要素のテキストも結合
    ti_node = article.find('.//ArticleTitle')
    if ti_node is not None:
        ti = ''.join(ti_node.itertext()).strip()
        if ti:
            data['TI'] = ti

    # Journal abbreviation (TA) / full title (JT)
    iso = article.find('.//ISOAbbreviation')
    if iso is not None and iso.text:
        data['TA'] = iso.text
    journal_title = article.find('.//Journal/Title')
    if journal_title is not None and journal_title.text:
        data['JT'] = journal_title.text

    # Publication date (DP) — NBIB形式 "Year Month Day"
    pubdate = article.find('.//JournalIssue/PubDate')
    if pubdate is not None:
        year = pubdate.findtext('Year', '') or ''
        month = pubdate.findtext('Month', '') or ''
        day = pubdate.findtext('Day', '') or ''
        medline_date = pubdate.findtext('MedlineDate', '') or ''
        parts = [p for p in [year, month, day] if p]
        if parts:
            data['DP'] = ' '.join(parts)
        elif medline_date:
            data['DP'] = medline_date

    # Volume / Issue / Pages
    vol = article.find('.//JournalIssue/Volume')
    if vol is not None and vol.text:
        data['VI'] = vol.text
    issue = article.find('.//JournalIssue/Issue')
    if issue is not None and issue.text:
        data['IP'] = issue.text
    pages = article.find('.//Pagination/MedlinePgn')
    if pages is not None and pages.text:
        data['PG'] = pages.text

    # Authors (FAU / AU) + Affiliations (AD)
    fau_list, au_list, ad_list = [], [], []
    for au in article.findall('.//AuthorList/Author'):
        collective = au.findtext('CollectiveName', '') or ''
        if collective:
            fau_list.append(collective)
            au_list.append(collective)
            continue
        last = au.findtext('LastName', '') or ''
        fore = au.findtext('ForeName', '') or ''
        initials = au.findtext('Initials', '') or ''
        if last:
            fau_list.append(f"{last}, {fore}" if fore else last)
            au_list.append(f"{last} {initials}".strip() if initials else last)
        for aff in au.findall('AffiliationInfo/Affiliation'):
            if aff.text:
                ad_list.append(aff.text)
    if fau_list:
        data['FAU'] = fau_list
    if au_list:
        data['AU'] = au_list
    if ad_list:
        data['AD'] = ad_list

    # LID (DOI / PII) — NBIB形式 "10.1234/foo [doi]"
    lid_list = []
    for aid in article.findall('.//ArticleIdList/ArticleId'):
        id_type = aid.get('IdType', '')
        if id_type == 'doi' and aid.text:
            lid_list.append(f"{aid.text} [doi]")
        elif id_type == 'pii' and aid.text:
            lid_list.append(f"{aid.text} [pii]")
    # フォールバック: ArticleIdList に無い識別子は Article/ELocationID から取得
    # （一部の文献はDOIがELocationIDにしか入っていない）
    for eid_type in ('doi', 'pii'):
        if not any(f'[{eid_type}]' in x for x in lid_list):
            for eloc in article.findall('.//Article/ELocationID'):
                if eloc.get('EIdType') == eid_type and eloc.text:
                    lid_list.append(f"{eloc.text.strip()} [{eid_type}]")
                    break
    if lid_list:
        data['LID'] = lid_list

    # ISSN (IS) — NBIB形式 "1234-5678 (Linking)" / "(Electronic)"
    is_list = []
    for issn in article.findall('.//ISSN'):
        issn_type = issn.get('IssnType', '')
        if issn.text:
            if issn_type == 'Print':
                is_list.append(f"{issn.text} (Linking)")
            elif issn_type == 'Electronic':
                is_list.append(f"{issn.text} (Electronic)")
            else:
                is_list.append(issn.text)
    if is_list:
        data['IS'] = is_list

    # Abstract (AB)
    abstract_parts = []
    for at in article.findall('.//Abstract/AbstractText'):
        txt = ''.join(at.itertext()).strip()
        label = at.attrib.get('Label', '')
        if label and txt:
            abstract_parts.append(f"{label}: {txt}")
        elif txt:
            abstract_parts.append(txt)
    if abstract_parts:
        data['AB'] = ' '.join(abstract_parts)

    # Publication Type (PT)
    pt_list = [pt.text for pt in article.findall('.//PublicationTypeList/PublicationType') if pt.text]
    if pt_list:
        data['PT'] = pt_list

    # MeSH Headings (MH)
    mh_list = [mh.text for mh in article.findall('.//MeshHeadingList/MeshHeading/DescriptorName') if mh.text]
    if mh_list:
        data['MH'] = mh_list

    # Keywords (OT)
    ot_list = [kw.text for kw in article.findall('.//KeywordList/Keyword') if kw.text]
    if ot_list:
        data['OT'] = ot_list

    # Country (PL)
    country = article.find('.//MedlineJournalInfo/Country')
    if country is not None and country.text:
        data['PL'] = country.text

    # Language (LA)
    lang = article.find('.//Language')
    if lang is not None and lang.text:
        data['LA'] = lang.text

    # Source string (SO) — "TA. DP;VI(IP):PG." を再構成
    so_parts = []
    if data.get('TA'):
        so_parts.append(data['TA'] + '.')
    if data.get('DP'):
        dp_seg = data['DP']
        if data.get('VI'):
            vi_part = data['VI'] + (f"({data['IP']})" if data.get('IP') else '')
            pg_part = f":{data['PG']}" if data.get('PG') else ''
            dp_seg = f"{dp_seg};{vi_part}{pg_part}"
        so_parts.append(dp_seg + '.')
    if so_parts:
        data['SO'] = ' '.join(so_parts)

    # EDAT — Article/ArticleDate(DateType=Electronic, 正式な電子出版日)を優先し、
    # 無ければ History の entrez date（PubMed登録日）にフォールバック
    for ad in article.findall('.//Article/ArticleDate'):
        if ad.get('DateType') == 'Electronic':
            y = ad.findtext('Year', '') or ''
            m = ad.findtext('Month', '') or ''
            d = ad.findtext('Day', '') or ''
            if y and m and d:
                data['EDAT'] = f"{y}/{m.zfill(2)}/{d.zfill(2)} 00:00"
            break
    if 'EDAT' not in data:
        # 注意: タグ名は PubmedData（小文字m）。旧コードは PubMedData と誤記しており
        # entrez date が一度も取得できていなかった（2026-07修正）
        for pmd in article.findall('.//PubmedData/History/PubMedPubDate'):
            if pmd.get('PubStatus') == 'entrez':
                y = pmd.findtext('Year', '') or ''
                m = pmd.findtext('Month', '') or ''
                d = pmd.findtext('Day', '') or ''
                hr = pmd.findtext('Hour', '') or ''
                mi = pmd.findtext('Minute', '') or ''
                if y and m and d:
                    data['EDAT'] = f"{y}/{m.zfill(2)}/{d.zfill(2)} {hr.zfill(2) if hr else '00'}:{mi.zfill(2) if mi else '00'}"
                break

    return data


# DEPRECATED: NBIB形式 (rettype=medline) はASCII化される問題があるため、
# 新規スクリプトは fetch_pubmed_xml / parse_pubmed_xml を使うこと。
# 過去スクリプトとの互換性のため残置。
def fetch_nbib(pmid):
    url = (f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
           f"?db=pubmed&id={pmid}&rettype=medline&retmode=text")
    with urllib.request.urlopen(urllib.request.Request(url), timeout=30) as resp:
        return resp.read().decode('utf-8')

LIST_FIELDS = {'FAU', 'AU', 'AD', 'OT', 'MH', 'PT', 'RN', 'AID', 'IS', 'LID'}

def parse_nbib(text):
    data = {}
    current_tag = None
    tag_re = re.compile(r'^([A-Z]{2,4})\s*-\s*(.*)')
    for line in text.split('\n'):
        m = tag_re.match(line)
        if m:
            current_tag = m.group(1).strip()
            value = m.group(2).strip()
            if current_tag in LIST_FIELDS:
                data.setdefault(current_tag, []).append(value)
            else:
                data[current_tag] = data.get(current_tag, '') + (' ' + value if current_tag in data else value)
        elif line.startswith('      ') and current_tag:
            cont = line.strip()
            if current_tag in LIST_FIELDS and data.get(current_tag):
                data[current_tag][-1] += ' ' + cont
            elif current_tag not in LIST_FIELDS:
                data[current_tag] = data.get(current_tag, '') + ' ' + cont
    return data

# ============================================================
# 2. データ変換ユーティリティ
# ============================================================
def convert_author_name(fau_name):
    if ',' not in fau_name:
        return fau_name
    last, first = fau_name.split(',', 1)
    initials = []
    for p in first.strip().split():
        if '-' in p:
            initials.append('-'.join(s[0].upper() + '.' for s in p.split('-') if s))
        else:
            initials.append(p[0].upper() + '.')
    return f"{last.strip()}, {' '.join(initials)}"

def sentence_case(text):
    if not text:
        return text
    return text[0].upper() + text[1:].lower() if text == text.upper() else text

def extract_doi(lid_list):
    for lid in (lid_list or []):
        if '[doi]' in lid:
            return lid.replace('[doi]', '').strip()
    return None

def extract_issn(is_list):
    linking = electronic = None
    for e in (is_list or []):
        if '(Linking)' in e:
            linking = e.replace('(Linking)', '').strip()
        elif '(Electronic)' in e:
            electronic = e.replace('(Electronic)', '').strip()
    return linking, electronic

# ============================================================
# 3. XML エスケープ
# ============================================================
def xesc(text):
    if not text:
        return ''
    return (text.replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;'))

# ============================================================
# 4. EndNote XML 生成
# ============================================================
def build_endnote_xml(nbib_data):
    pmid = nbib_data.get('PMID', '')
    authors = [convert_author_name(f) for f in nbib_data.get('FAU', [])]
    first_author_last = authors[0].split(',')[0] if authors else ''

    title = nbib_data.get('TI', '').rstrip('.')
    ta = nbib_data.get('TA', '')
    jt = sentence_case(nbib_data.get('JT', ''))

    dp = nbib_data.get('DP', '')
    dp_parts = dp.split()
    year = dp_parts[0] if dp_parts else ''
    month = dp_parts[1] if len(dp_parts) > 1 else ''

    doi = extract_doi(nbib_data.get('LID', []))
    linking_issn, electronic_issn = extract_issn(nbib_data.get('IS', []))

    edat = nbib_data.get('EDAT', '')
    edat_date = edat.split()[0] if edat else ''

    notes_parts = []
    if electronic_issn:
        notes_parts.append(electronic_issn)
    notes_parts.extend(nbib_data.get('FAU', []))
    notes_parts.extend(nbib_data.get('PT', []))
    if nbib_data.get('PL'):
        notes_parts.append(nbib_data['PL'])
    if nbib_data.get('SO'):
        notes_parts.append(nbib_data['SO'])
    notes = '&#xA;'.join(xesc(p) for p in notes_parts)

    ad_list = nbib_data.get('AD', [])
    author_addr = xesc(' '.join(ad_list)) if ad_list else ''

    keywords = nbib_data.get('MH', []) + nbib_data.get('OT', [])
    timestamp = str(int(time.time()))

    r = []
    r.append(f'<rec-number>{xesc(pmid)}</rec-number>')
    r.append(f'<foreign-keys><key app="EN" db-id="{ENDNOTE_DB_ID}" timestamp="{timestamp}">{xesc(pmid)}</key></foreign-keys>')
    r.append('<ref-type name="Journal Article">17</ref-type>')
    r.append('<contributors><authors>' + ''.join(f'<author>{xesc(a)}</author>' for a in authors) + '</authors></contributors>')
    r.append(f'<titles><title>{xesc(title)}</title><secondary-title>{xesc(ta)}</secondary-title>')
    if jt:
        r.append(f'<alt-title>{xesc(jt)}</alt-title>')
    r.append('</titles>')
    if jt:
        r.append(f'<alt-periodical><full-title>{xesc(jt)}</full-title></alt-periodical>')
    if nbib_data.get('PG'):
        r.append(f'<pages>{xesc(nbib_data["PG"])}</pages>')
    if nbib_data.get('VI'):
        r.append(f'<volume>{xesc(nbib_data["VI"])}</volume>')
    if nbib_data.get('IP'):
        r.append(f'<number>{xesc(nbib_data["IP"])}</number>')
    if keywords:
        r.append('<keywords>' + ''.join(f'<keyword>{xesc(k)}</keyword>' for k in keywords) + '</keywords>')
    if author_addr:
        r.append(f'<author-address>{author_addr}</author-address>')
    if notes:
        r.append(f'<notes>{notes}</notes>')
    if year:
        date_inner = f'<year>{xesc(year)}</year>'
        if month:
            date_inner += f'<pub-dates><date>{xesc(month)}</date></pub-dates>'
        r.append(f'<dates>{date_inner}</dates>')
    if linking_issn:
        r.append(f'<isbn>{xesc(linking_issn)}</isbn>')
    r.append(f'<accession-num>{xesc(pmid)}</accession-num>')
    r.append('<urls></urls>')
    if nbib_data.get('OWN'):
        r.append(f'<custom3>{xesc(nbib_data["OWN"])}</custom3>')
    if edat_date:
        r.append(f'<custom4>{xesc(edat_date)}</custom4>')
    if doi:
        r.append(f'<electronic-resource-num>{xesc(doi)}</electronic-resource-num>')
    if nbib_data.get('LA'):
        r.append(f'<language>{xesc(nbib_data["LA"])}</language>')

    record = ''.join(r)
    display = f'({xesc(first_author_last)}, {xesc(year)})'

    return (f'<EndNote><Cite>'
            f'<Author>{xesc(first_author_last)}</Author>'
            f'<Year>{xesc(year)}</Year>'
            f'<RecNum>{xesc(pmid)}</RecNum>'
            f'<DisplayText>{display}</DisplayText>'
            f'<record>{record}</record>'
            f'</Cite></EndNote>')

# ============================================================
# 5. OOXMLフィールドコード（文字列）生成
# ============================================================
def double_escape(xml_str):
    return (xml_str.replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))

def build_field_xml(endnote_xml, display_text):
    """フィールドコードのOOXML文字列を生成（w:名前空間プレフィックス付き）"""
    instr = f' ADDIN EN.CITE {double_escape(endnote_xml)}'
    # instrText内のテキストはXML属性値ではないが、XMLコンテンツなので
    # &, <, > をエスケープする必要がある（double_escapeで実施済み）

    return (
        '<w:r><w:rPr><w:highlight w:val="yellow"/></w:rPr>'
        '<w:fldChar w:fldCharType="begin"/></w:r>'
        f'<w:r><w:rPr><w:highlight w:val="yellow"/></w:rPr>'
        f'<w:instrText xml:space="preserve">{instr}</w:instrText></w:r>'
        '<w:r><w:rPr><w:highlight w:val="yellow"/></w:rPr>'
        '<w:fldChar w:fldCharType="separate"/></w:r>'
        f'<w:r><w:rPr><w:noProof/><w:highlight w:val="yellow"/></w:rPr>'
        f'<w:t>{xesc(display_text)}</w:t></w:r>'
        '<w:r><w:rPr><w:highlight w:val="yellow"/></w:rPr>'
        '<w:fldChar w:fldCharType="end"/></w:r>'
    )

# ============================================================
# 6. document.xml 内のマーカー置換（文字列ベース）
# ============================================================
def find_run_boundaries(xml, pos_in_t):
    """
    <w:t>内の位置posから、その<w:t>を含む<w:r>...</w:r>の開始・終了位置を特定。
    <w:rPr>...</w:rPr>も抽出して返す。
    """
    # <w:t の開始を見つける
    t_open = xml.rfind('<w:t', 0, pos_in_t)
    if t_open == -1:
        return None
    # <w:t>の閉じ>
    t_tag_end = xml.find('>', t_open)
    if t_tag_end == -1 or t_tag_end >= pos_in_t:
        return None
    # </w:t>を見つける
    t_close = xml.find('</w:t>', pos_in_t)
    if t_close == -1:
        return None
    # <w:t>と位置の間に</w:t>がないことを確認
    if '</w:t>' in xml[t_tag_end+1:pos_in_t]:
        return None

    # <w:r の開始を見つける（<w:rPr>, <w:rFonts>等ではなく<w:r>か<w:r ...>のみ）
    # t_open より前方に向かって検索
    search_pos = t_open
    r_open = -1
    while search_pos > 0:
        candidate = xml.rfind('<w:r', 0, search_pos)
        if candidate == -1:
            break
        # <w:r> or <w:r ... > であることを確認（<w:rPr>, <w:rFonts>等を除外）
        after_tag = xml[candidate+4:candidate+5] if candidate+4 < len(xml) else ''
        if after_tag in ('>', ' ', '\n', '\r', '\t'):
            r_open = candidate
            break
        search_pos = candidate

    if r_open == -1:
        return None

    # </w:r>を見つける（</w:t>の後の最初の</w:r>）
    r_close_start = xml.find('</w:r>', t_close + 6)
    if r_close_start == -1:
        return None
    r_close = r_close_start + 6  # '</w:r>'の長さ

    # <w:rPr>...</w:rPr>を抽出
    rpr_xml = ''
    rpr_match = re.search(r'<w:rPr>.*?</w:rPr>', xml[r_open:t_open], re.DOTALL)
    if rpr_match:
        rpr_xml = rpr_match.group(0)

    # <w:t>の中身
    t_content = xml[t_tag_end+1:t_close]

    return {
        'r_open': r_open,
        'r_close': r_close,
        't_tag': xml[t_open:t_tag_end+1],
        't_content': t_content,
        't_content_start': t_tag_end + 1,
        'rpr_xml': rpr_xml,
    }


def replace_markers_in_xml(doc_xml, marker_text, field_xml):
    """
    document.xml文字列内のプレーンテキストマーカーをフィールドコードに置換。
    <w:t>要素内のテキストのみを対象とし、フィールドコード内は無視。
    """
    result = doc_xml
    replaced = 0
    search_start = 0

    while True:
        idx = result.find(marker_text, search_start)
        if idx == -1:
            break

        # フィールドコード内かチェック
        before_text = result[:idx]
        n_begins = before_text.count('fldCharType="begin"')
        n_ends = before_text.count('fldCharType="end"')
        if n_begins > n_ends:
            search_start = idx + len(marker_text)
            continue

        # <w:r>の境界を特定
        bounds = find_run_boundaries(result, idx)
        if bounds is None:
            search_start = idx + len(marker_text)
            continue

        # マーカーのt_content内での位置
        rel_idx = idx - bounds['t_content_start']
        before = bounds['t_content'][:rel_idx]
        after = bounds['t_content'][rel_idx + len(marker_text):]
        rpr = bounds['rpr_xml']

        # 置換XMLを構築
        replacement = ''
        if before:
            space_attr = ' xml:space="preserve"' if (before[0] == ' ' or before[-1] == ' ') else ''
            replacement += f'<w:r>{rpr}<w:t{space_attr}>{before}</w:t></w:r>'
        replacement += field_xml
        if after:
            space_attr = ' xml:space="preserve"' if (after[0] == ' ' or after[-1] == ' ') else ''
            replacement += f'<w:r>{rpr}<w:t{space_attr}>{after}</w:t></w:r>'

        # 元のrun全体を置換
        result = result[:bounds['r_open']] + replacement + result[bounds['r_close']:]
        replaced += 1
        print(f"  Replaced '{marker_text}' (occurrence {replaced})")
        search_start = bounds['r_open'] + len(replacement)

    return result, replaced

# ============================================================
# メイン
# ============================================================
def process_single(pmid, marker_text, input_docx, output_docx):
    print(f"\n--- Processing PMID {pmid}, marker '{marker_text}' ---")

    nbib = parse_pubmed_xml(fetch_pubmed_xml(pmid))
    print(f"  Title: {nbib.get('TI', '')[:80]}")

    en_xml = build_endnote_xml(nbib)
    print(f"  EndNote XML: {len(en_xml)} chars")

    first_author = nbib.get('FAU', [''])[0].split(',')[0] if nbib.get('FAU') else ''
    year = nbib.get('DP', '').split()[0] if nbib.get('DP') else ''
    display = f'({first_author}, {year})'

    field_xml = build_field_xml(en_xml, display)

    # docxをメモリに読み込み
    all_files = {}
    with zipfile.ZipFile(input_docx, 'r') as zin:
        for item in zin.infolist():
            all_files[item.filename] = zin.read(item.filename)

    doc_xml = all_files['word/document.xml'].decode('utf-8')

    # 文字列ベースで置換
    new_doc_xml, count = replace_markers_in_xml(doc_xml, marker_text, field_xml)
    print(f"  Replaced {count} occurrence(s)")

    # XMLバリデーション（書き出し前に必ず実行）
    print("  Validating XML...")
    from lxml import etree
    try:
        etree.fromstring(new_doc_xml.encode('utf-8'))
        print("  XML is valid.")
    except etree.XMLSyntaxError as e:
        print(f"  ERROR: Generated XML is invalid: {e}")
        print("  Aborting - output file NOT written.")
        return False

    all_files['word/document.xml'] = new_doc_xml.encode('utf-8')

    # docxを書き出し
    with zipfile.ZipFile(output_docx, 'w', zipfile.ZIP_DEFLATED) as zout:
        for fn, data in all_files.items():
            zout.writestr(fn, data)

    print(f"  Saved: {output_docx}")
    return count > 0


def _scan_remaining_markers(doc_xml, entries):
    """フィールド外のプレーンテキストに残存するマーカーを検出。
    戻り値: [(marker, pmid), ...] 未変換マーカーのリスト。
    """
    import xml.etree.ElementTree as _ET2
    root = _ET2.fromstring(doc_xml)
    _ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    plain_text_parts = []
    for p in root.iter(f'{{{_ns}}}p'):
        parts = []
        in_field = False
        for child in p.iter():
            if child.tag == f'{{{_ns}}}fldChar':
                ft = child.get(f'{{{_ns}}}fldCharType')
                if ft == 'begin':
                    in_field = True
                elif ft == 'end':
                    in_field = False
            elif child.tag == f'{{{_ns}}}t' and child.text and not in_field:
                parts.append(child.text)
        plain_text_parts.append(''.join(parts))
    full_plain = ' '.join(plain_text_parts)

    marker_to_pmid = {e['marker']: e['pmid'] for e in entries}
    remaining = []
    for marker, pmid in marker_to_pmid.items():
        num = re.search(r'\d+', marker)
        if not num:
            continue
        n = int(num.group())
        if re.search(rf'\({n}\)', full_plain):
            remaining.append((marker, pmid))
    return remaining


def process_batch(entries, input_docx, output_docx, max_passes=3):
    """複数文献を順次処理。メモリ上でdocument.xmlを引き継ぐ。
    隣接マーカー置換後の構造変化で漏れが生じうるため、
    自動検証＋最大max_passesまでリトライする。
    """
    from lxml import etree

    # docxをメモリに読み込み
    all_files = {}
    with zipfile.ZipFile(input_docx, 'r') as zin:
        for item in zin.infolist():
            all_files[item.filename] = zin.read(item.filename)

    doc_xml = all_files['word/document.xml'].decode('utf-8')
    total_replaced = 0

    # PubMedデータをキャッシュ（リトライ時にAPI再呼び出し不要）
    pmid_cache = {}

    for entry in entries:
        pmid = entry['pmid']
        marker = entry['marker']
        print(f"\n{'='*60}")
        print(f"Processing PMID {pmid}, marker '{marker}'")
        print(f"{'='*60}")

        try:
            if pmid not in pmid_cache:
                nbib = parse_pubmed_xml(fetch_pubmed_xml(pmid))
                pmid_cache[pmid] = nbib
                time.sleep(0.5)
            else:
                nbib = pmid_cache[pmid]
        except Exception as e:
            print(f"  ERROR fetching PMID {pmid}: {e}")
            continue

        title = nbib.get('TI', '')
        print(f"  Title: {title[:80]}")

        en_xml = build_endnote_xml(nbib)
        print(f"  EndNote XML: {len(en_xml)} chars")

        first_author = nbib.get('FAU', [''])[0].split(',')[0] if nbib.get('FAU') else ''
        year = nbib.get('DP', '').split()[0] if nbib.get('DP') else ''
        display = f'({first_author}, {year})'

        field_xml = build_field_xml(en_xml, display)
        doc_xml, count = replace_markers_in_xml(doc_xml, marker, field_xml)
        print(f"  Replaced {count} occurrence(s)")
        total_replaced += count

    # --- 自動検証＋リトライ ---
    for pass_num in range(2, max_passes + 1):
        remaining = _scan_remaining_markers(doc_xml, entries)
        if not remaining:
            break
        print(f"\n{'='*60}")
        print(f"⚠ Pass {pass_num}: {len(remaining)} marker(s) still remain — retrying")
        print(f"{'='*60}")
        for marker, pmid in remaining:
            print(f"  Retrying {marker} (PMID {pmid})")
            nbib = pmid_cache.get(pmid)
            if not nbib:
                continue
            en_xml = build_endnote_xml(nbib)
            first_author = nbib.get('FAU', [''])[0].split(',')[0] if nbib.get('FAU') else ''
            year = nbib.get('DP', '').split()[0] if nbib.get('DP') else ''
            display = f'({first_author}, {year})'
            field_xml = build_field_xml(en_xml, display)
            doc_xml, count = replace_markers_in_xml(doc_xml, marker, field_xml)
            print(f"    Replaced {count} occurrence(s)")
            total_replaced += count

    # 最終検証
    final_remaining = _scan_remaining_markers(doc_xml, entries)

    print(f"\n{'='*60}")
    print(f"Total replacements: {total_replaced}")
    if final_remaining:
        print(f"⚠ WARNING: {len(final_remaining)} marker(s) could not be replaced:")
        for marker, pmid in final_remaining:
            print(f"    {marker} (PMID {pmid})")
    else:
        print(f"✓ All markers successfully replaced (verified)")
    print(f"Validating final XML...")

    try:
        etree.fromstring(doc_xml.encode('utf-8'))
        print("XML is valid.")
    except etree.XMLSyntaxError as e:
        print(f"ERROR: Generated XML is invalid: {e}")
        print("Aborting - output file NOT written.")
        return False

    all_files['word/document.xml'] = doc_xml.encode('utf-8')

    with zipfile.ZipFile(output_docx, 'w', zipfile.ZIP_DEFLATED) as zout:
        for fn, data in all_files.items():
            zout.writestr(fn, data)

    print(f"Saved: {output_docx}")
    return True


if __name__ == '__main__':
    if not NCBI_EMAIL:
        print("ERROR: Set NCBI_EMAIL environment variable (NCBI usage policy requires contact info)")
        print("  e.g.: set NCBI_EMAIL=you@example.com")
        sys.exit(1)

    # Edit the entries below to match your document
    entries = [
        {'pmid': '35985088', 'marker': '(1)'},
        {'pmid': '32184423', 'marker': '(2)'},
    ]

    process_batch(
        entries=entries,
        input_docx='input.docx',
        output_docx='output_endnote.docx',
    )
