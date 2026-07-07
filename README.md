# EndNote Field Inserter

Batch-convert plaintext citation markers (e.g. `(1)`, `(2)`) in Word documents (.docx) to EndNote field codes, using bibliographic data fetched from PubMed.

This tool directly edits the OOXML inside the .docx file — no COM automation or EndNote desktop interaction required. After conversion, open the document in Word and run EndNote's "Update Citations and Bibliography" to finalize.

Also supports bulk punctuation/spacing adjustment when switching EndNote output styles (Direction A/B).

## Features

- Fetches bibliographic metadata from PubMed XML API (Unicode-safe — no ASCII mangling of author names like Yücel or Schröder)
- Generates full EndNote field codes (ADDIN EN.CITE) with author, title, journal, DOI, etc.
- String-based XML editing preserves all namespace declarations (no ElementTree serialization issues)
- Multi-citation markers (`(3, 4)` or `(3-5)`) handled via adjacent independent fields
- Auto-retry: detects unreplaced markers after each pass and retries up to 3 times
- Yellow highlight on inserted fields for easy visual identification
- XML validation before writing output

## Requirements

- Python 3.8+
- `lxml` (for XML validation only)

```bash
pip install lxml
```

## Usage

### As a Claude Code skill (recommended)

Copy the entire directory to `~/.claude/skills/endnote-insert/`. Claude Code will read `SKILL.md` and orchestrate the workflow — collecting marker-PMID mappings, editing the script's `__main__` block, running it, and reporting results.

See [SKILL.md](SKILL.md) for the full workflow specification.

### Standalone

1. Set your email for NCBI API compliance:

```bash
# Windows
set NCBI_EMAIL=you@example.com

# macOS/Linux
export NCBI_EMAIL=you@example.com
```

2. (Optional) Set your EndNote library's db-id if you have existing EndNote fields:

```bash
set ENDNOTE_DB_ID=your_db_id_here
```

To find your db-id, unzip the .docx and search for `db-id=` in `word/document.xml`.

3. Edit the `entries` list in `scripts/endnote_inserter.py`:

```python
entries = [
    {'pmid': '35985088', 'marker': '(1)'},
    {'pmid': '32184423', 'marker': '(2)'},
    # ...
]

process_batch(
    entries=entries,
    input_docx='path/to/input.docx',
    output_docx='path/to/output.docx',
)
```

4. Run:

```bash
python scripts/endnote_inserter.py
```

5. Open the output .docx in Word, then run EndNote > Update Citations and Bibliography.

## How it works

1. For each PMID, fetches metadata from PubMed's efetch XML API
2. Builds an EndNote XML record (`<EndNote><Cite>...</Cite></EndNote>`)
3. Wraps it in OOXML field code structure (`fldChar begin` / `instrText` / `separate` / `end`)
4. Finds the plaintext marker (e.g. `(1)`) inside `<w:t>` elements in `document.xml`
5. Replaces the marker's `<w:r>` with the field code runs
6. After all markers are processed, scans for any remaining unreplaced markers and retries
7. Validates the final XML with lxml, then writes the output .docx

## Field format

This tool generates **Format A** (ADDIN EN.CITE with instrText). Some newer Word documents use **Format B** (ADDIN EN.CITE.DATA with base64-encoded fldData). See the "EndNote Field Format" section in [SKILL.md](SKILL.md) for details on both formats.

## Related tools

- [PubMed2EndNote](https://github.com/matsuikentaro1/pubmed2endnote) — Chrome extension for interactive one-at-a-time citation insertion via clipboard
- [codex-refs](https://github.com/matsuikentaro1/codex-refs) — Claude Code skill for searching and building a verified reference CSV from PubMed

## License

MIT
