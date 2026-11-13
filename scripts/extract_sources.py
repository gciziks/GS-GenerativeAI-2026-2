"""Extração local reproduzível, sem rede e sem alterar o corpus curado.

Uso: python scripts/extract_sources.py --root .
Dependências de preparação: beautifulsoup4 e pypdf (incluídas no projeto).
Snapshots integrais e extrações ficam em .runtime, fora da distribuição.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup


def clean_text(node):
    return " ".join(node.get_text(" ", strip=True).split())


def expand_table(table):
    """Expande somente rowspan/colspan explícitos, com origem de cada célula."""
    pending = {}
    output = []
    for row_index, tr in enumerate(table.select("tr")):
        cells = {}
        inherited = []
        for col, (value, remaining, origin) in list(pending.items()):
            cells[col] = {"text": value, "origin_row": origin}
            inherited.append(col)
            if remaining == 1:
                del pending[col]
            else:
                pending[col] = (value, remaining - 1, origin)
        col = 0
        for cell in tr.find_all(["td", "th"], recursive=False):
            while col in cells:
                col += 1
            value = clean_text(cell)
            width, height = int(cell.get("colspan", 1)), int(cell.get("rowspan", 1))
            if width < 1 or height < 1 or width > 100 or height > 100:
                raise ValueError("Extensão de célula inválida")
            for offset in range(width):
                if col + offset in cells:
                    raise ValueError("Sobreposição de células mescladas")
                cells[col + offset] = {"text": value, "origin_row": row_index}
                if height > 1:
                    pending[col + offset] = (value, height - 1, row_index)
            col += width
        width = max(cells, default=-1) + 1
        output.append({"row_index": row_index, "cells": [cells.get(i, {"text": "", "origin_row": None}) for i in range(width)],
                       "inherited_columns": inherited})
    if pending:
        raise ValueError("Rowspan ultrapassa o final da tabela")
    return output


def parse_html(html, source_id, expected_topic=None):
    soup = BeautifulSoup(html, "html.parser")
    title = clean_text(soup.title) if soup.title else source_id
    if expected_topic:
        selected = soup.select_one(f'option[value="{expected_topic}"][selected]')
        if selected is None or selected.get("value") != expected_topic:
            raise ValueError("FAQ não confirma o assunto solicitado")
        block = soup.select_one("#duvidas")
        if block is None:
            raise ValueError("FAQ sem bloco de perguntas")
        questions = []
        for question in block.find_all("li", recursive=False):
            heading, answer = question.select_one("h3"), question.select_one(".panel-body")
            if heading is None or answer is None:
                raise ValueError("Pergunta sem par pergunta/resposta")
            questions.append({"question_id": question.get("id"), "locator": "#" + question.get("id", ""),
                              "question": clean_text(heading), "answer": clean_text(answer)})
        if not questions or len({q["question_id"] for q in questions}) != len(questions):
            raise ValueError("FAQ vazia ou com IDs duplicados")
        return {"source_id": source_id, "title": title, "topic": expected_topic, "questions": questions,
                "representation": "extracted_official_text_local_only"}
    content = soup.select_one(".entry-content") or soup.select_one("#conteudo") or soup.select_one("main")
    if content is None:
        raise ValueError("Conteúdo principal não encontrado")
    for noise in content.select("script, style, nav, header, footer, form, .cookie-banner"):
        noise.decompose()
    blocks = []
    for element in content.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        if element.find_parent("table") is None and not element.find_parent("li"):
            text = clean_text(element)
            if text:
                blocks.append({"tag": element.name, "text": text})
    tables = []
    for table_index, table in enumerate(content.select("table")):
        expanded = expand_table(table)
        headers = [c["text"] for c in expanded[0]["cells"]] if expanded else []
        line = None
        for previous in table.find_all_previous(["p", "h2", "h3", "h4"]):
            text = clean_text(previous)
            if len(text) <= 80 and re.match(r"^linha\s+\d+", text, re.I):
                line = text
                break
        rows = []
        for row in expanded[1:]:
            values = [c["text"] for c in row["cells"]]
            if len(values) != len(headers):
                raise ValueError("Tabela com número de colunas inconsistente")
            rows.append({"row_index": row["row_index"], "values": values,
                         "record": dict(zip(headers, values)), "inherited_columns": row["inherited_columns"],
                         "cell_origin_rows": [c["origin_row"] for c in row["cells"]]})
        tables.append({"table_index": table_index, "line": line, "headers": headers, "rows": rows})
    return {"source_id": source_id, "title": title, "blocks": blocks, "tables": tables,
            "representation": "extracted_official_text_local_only"}


def articles_from_pages(pages, wanted=range(46, 53)):
    """Extrai artigos completos, preservando a continuidade entre páginas físicas."""
    text = ""
    spans = []
    for page_number, page_text in enumerate(pages, start=1):
        start = len(text)
        text += page_text + "\n"
        spans.append((start, len(text), page_number))
    matches = list(re.finditer(r"(?m)^\s*Art\.\s*(\d+)\.", text))
    articles = []
    for index, match in enumerate(matches):
        number = int(match.group(1))
        if number not in wanted:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        article = text[match.start():end].strip()
        page_numbers = [number for start, stop, number in spans if start < end and stop > match.start()]
        articles.append({"article": number, "pages": page_numbers, "text": article,
                         "locator": "Art. " + str(number) + "; páginas " + ", ".join(map(str, page_numbers))})
    found = {a["article"] for a in articles}
    if found != set(wanted):
        raise ValueError("Artigos ausentes ou inesperados: " + str(sorted(set(wanted) - found)))
    return articles


def extract_pdf(path, source_id):
    from pypdf import PdfReader
    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return {"source_id": source_id, "page_count": len(pages), "articles": articles_from_pages(pages),
            "representation": "extracted_official_text_local_only",
            "review_warning": "Extração automatizada não substitui conferência visual; notas editoriais podem estar presentes."}


def extract_sources(root=Path.cwd()):
    root = Path(root)
    sources = json.loads((root / "base/fontes.json").read_text(encoding="utf8"))
    out = root / ".runtime/extracted"
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for source in sources:
        path = root / source["snapshot"]
        raw = path.read_bytes()
        raw_hash = hashlib.sha256(raw).hexdigest()
        if raw_hash != source["sha256_raw"]:
            raise ValueError("Snapshot diverge da versão curada: " + source["source_id"])
        sid = source["source_id"]
        if source["mime_type"] == "application/pdf":
            data = extract_pdf(path, sid)
        else:
            topic = {"F03": "atende", "F04": "bilhete-pcd"}.get(sid)
            data = parse_html(raw, sid, topic)
        data.update(requested_url=source["requested_url"], canonical_url=source["canonical_url"],
                    retrieved_at=source["retrieved_at"], sha256_raw=raw_hash)
        target = out / (sid + ".json")
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf8")
        manifest.append({"source_id": sid, "sha256_raw": raw_hash,
                         "sha256_extracted": hashlib.sha256(target.read_bytes()).hexdigest(),
                         "questions": len(data.get("questions", [])), "tables": len(data.get("tables", [])),
                         "articles": len(data.get("articles", []))})
        print(json.dumps(manifest[-1], ensure_ascii=True), flush=True)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    extract_sources(args.root)
