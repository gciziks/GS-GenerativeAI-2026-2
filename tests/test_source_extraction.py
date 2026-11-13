"""Testes do parser em HTML mínimo e nos snapshots oficiais, quando presentes."""
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("extract_sources", ROOT/"scripts/extract_sources.py")
extract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extract)


def test_faq_selects_topic_and_removes_menu():
    html = '<nav>Menu falso</nav><option selected value="trajeto">Rota</option><select><option selected value="atende">Atende</option></select><ul id="duvidas"><li id="pergunta_1"><h3>Como cancelar?</h3><div class="panel-body">Site <b>ou 156</b>.</div></li></ul>'
    result = extract.parse_html(html, "F03", "atende")
    assert result["topic"] == "atende"
    assert result["questions"] == [{"question_id":"pergunta_1", "locator":"#pergunta_1", "question":"Como cancelar?", "answer":"Site ou 156 ."}]
    assert "Menu falso" not in str(result)
    with pytest.raises(ValueError, match="assunto"):
        extract.parse_html(html, "F04", "bilhete-pcd")


def test_rowspan_never_leaks_into_next_station():
    html = '<main><p>LINHA 1-AZUL</p><table><tr><th>Estação</th><th>Local</th><th>Horário</th></tr><tr><td rowspan="2">Estação A</td><td>Sul</td><td>6h às 22h</td></tr><tr><td>Norte</td><td>24h, pedir ao vigilante entre 22h e 6h</td></tr><tr><td>Estação B</td><td>Área paga</td><td>5h à 0h</td></tr></table></main>'
    table = extract.parse_html(html, "X")["tables"][0]
    assert table["line"] == "LINHA 1-AZUL"
    rows = table["rows"]
    assert rows[1]["record"]["Estação"] == "Estação A"
    assert rows[1]["inherited_columns"] == [0]
    assert rows[1]["cell_origin_rows"][0] == 1
    assert "vigilante" in rows[1]["record"]["Horário"]
    assert rows[2]["record"]["Estação"] == "Estação B"
    assert rows[2]["inherited_columns"] == []
    assert rows[2]["record"]["Horário"] == "5h à 0h"


def test_rowspan_overrun_rejected():
    from bs4 import BeautifulSoup
    table = BeautifulSoup('<table><tr><td rowspan="2">X</td></tr></table>', 'html.parser').table
    with pytest.raises(ValueError, match="final"):
        extract.expand_table(table)


def test_pdf_article_crosses_physical_page_without_importing_next_article():
    articles = extract.articles_from_pages(['Art. 46. Texto.\nArt. 47. Primeiro trecho', 'continuação do art47.\nArt. 48. Próximo artigo.'], wanted=[46,47,48])
    article = next(a for a in articles if a["article"] == 47)
    assert article["pages"] == [1,2]
    assert "continuação" in article["text"]
    assert "Próximo artigo" not in article["text"]
    with pytest.raises(ValueError, match="ausentes"):
        extract.articles_from_pages(['Art. 46. Texto.'], wanted=[46,47])


def test_actual_snapshots_faq_tables_and_pdf():
    snapshots = ROOT/".runtime/snapshots"
    if not (snapshots/"F03.html").exists():
        pytest.skip("Snapshots não distribuídos; executar fetch_sources.py para integração documental")
    faq = extract.parse_html((snapshots/"F03.html").read_bytes(), "F03", "atende")
    assert len(faq["questions"]) == 26
    question = next(q for q in faq["questions"] if q["question_id"] == "pergunta_16773")
    assert "18 anos" in question["answer"]
    tables = extract.parse_html((snapshots/"F06.html").read_bytes(), "F06")["tables"]
    records = [row["record"] for table in tables for row in table["rows"]]
    artur = [r for r in records if r["Estação"] == "ARTUR ALVIM"]
    assert len(artur) == 2
    assert any("norte" in r["Local"] and "vigilante" in r["Horário de funcionamento"] for r in artur)
    pdf = extract.extract_pdf(snapshots/"F07.pdf", "F07")
    assert [a["article"] for a in pdf["articles"]] == list(range(46,53))
    art47 = next(a for a in pdf["articles"] if a["article"] == 47)
    assert art47["pages"] == [16,17]
    assert "2%" in art47["text"] and "território nacional" in art47["text"]
