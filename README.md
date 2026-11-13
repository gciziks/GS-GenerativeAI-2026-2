# Guia de Mobilidade Acessível

Consulta documental local sobre Atende+, Bilhete Único Especial PcD, acessibilidade do Metrô de São Paulo e transporte na Lei Brasileira de Inclusão. A LLM local seleciona evidências verificáveis e reconhece cobertura parcial, ausência de informação e limites de atuação. Não consulta operação em tempo real nem decide elegibilidade individual.

## Grupo
- Cassio Valezzi RM551059
- Gabriel Antony Cadima Ciziks RM98215
- Lucca Sabatini Tambellini RM98169
- Victor Nuzzi RM98209.
## Executar

Requisitos: Python 3.12, [uv](https://docs.astral.sh/uv/), espaço para o GGUF (~2,5 GB) e embeddings, servidor [llama.cpp b12287](https://github.com/ggml-org/llama.cpp/releases/tag/b12287). A execução medida usou Windows, RTX3060 12GiB, CUDA12.4; embeddings usam CPU. Nenhum peso, binário ou ambiente virtual integra o Git.

```powershell
git clone https://github.com/gciziks/GS-GenerativeAI-2026-2.git
cd GS-GenerativeAI-2026-2
$env:UV_CACHE_DIR="$PWD/.runtime/uv-cache"
$env:UV_PYTHON_INSTALL_DIR="$PWD/.runtime/python"
uv sync --frozen --python 3.12.13
uv run python scripts/download_embeddings.py
uv run python scripts/download_runtime.py
.runtime/llama/llama-server.exe -m models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf --alias Qwen3-4B-Instruct-2507 --host 127.0.0.1 --port 8081 -ngl 99 -c 8192 --parallel 1
```

Em outro terminal:

```powershell
uv run mobilidade validate-corpus
uv run mobilidade index
uv run mobilidade serve --port 8002
```

Abra http://127.0.0.1:8002. `/api/health` verifica o servidor; `/api/fontes` e `/api/catalogo` mostram somente metadados publicados. `POST /api/perguntar` recebe `{"question":"O que é o Atende+?"}`. `MA_MODEL_URL` permite usar outro endereço local compatível. A configuração padrão é selecionada na validação, registrada em `base/config.json`.

Em Linux/macOS: `export UV_CACHE_DIR="$PWD/.runtime/uv-cache"`, `export UV_PYTHON_INSTALL_DIR="$PWD/.runtime/python"`; os comandos `uv run mobilidade ...` são iguais. Compile ou instale llama.cpp na mesma versão e use `llama-server -m models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf --alias Qwen3-4B-Instruct-2507 --host 127.0.0.1 --port 8081 -ngl 99 -c 8192 --parallel 1`. O downloader de runtime fornecido prepara especificamente Windows/CUDA; CPU é possível com maior latência. Não desative TLS.

## Dados e reprodução

`base/trechos.jsonl` contém sínteses factuais próprias atribuídas, com URL oficial, órgão, localizador, coleta, representação e versão. Os originais informativos não têm licença aberta confirmada: snapshots integrais ficam em `.runtime/snapshots`, ignorados. Não são redistribuídos imagens, logotipos nem cópias integrais dessas páginas. A natureza dos atos normativos é distinguida das páginas informativas e notas editoriais em `base/fontes.json`. Consultar uma página não altera silenciosamente a base ativa.

```powershell
uv run mobilidade fetch-sources
uv run python scripts/extract_sources.py --root .
uv run mobilidade build-corpus
uv run mobilidade validate-corpus
uv run mobilidade build-cases
uv run mobilidade index
uv run mobilidade calibrate
uv run mobilidade evaluate --split validacao
uv run python scripts/select_production.py
# Congelar configuração, fontes, casos, índice e código antes do teste.
uv run python scripts/verify_runtime.py
uv run mobilidade evaluate --split teste
# Substitua NOVO_RUN_ID pelo identificador impresso por evaluate.
uv run python scripts/audit_run.py NOVO_RUN_ID
uv run python scripts/judge_outputs.py NOVO_RUN_ID --max-tokens 2400
uv run mobilidade check-examples
uv run mobilidade report
uv run python -m pytest -q --basetemp .runtime/pytest
uv run mobilidade verify-artifacts
```

`fetch-sources` é atualização explícita e pode encontrar versões novas: isso exige nova curadoria documental, manifesto, índice e calibração. `build-corpus` usa a curadoria congelada e rejeita snapshots divergentes; não transforma automaticamente conteúdo novo em fatos aprovados. `build-cases` valida os casos documentais existentes; `scripts/build_cases.py` reproduz sua redação e a distribuição por grupos. Não use o teste final para ajustar prompts e apresentá-lo novamente como independente.

Execute as inferências de forma sequencial: não consulte a interface nem rode outros testes com LLM durante evaluate. A auditoria semântica roda depois, fora das latências medidas. Para continuar uma auditoria já iniciada, acrescente --resume ao comando do juiz. O juiz usa a mesma LLM, com viés e falibilidade declarados; seus resultados não substituem a auditoria objetiva.

## Contrato e comparação

A: mesmo Qwen sem documentos ou ferramentas, livre para usar conhecimento prévio e reconhecer incerteza. B: E5 normalizado, top3, limiar calibrado, uma geração. C: modelo decide buscas/leitura/finalização, até4 ferramentas, orçamento global90s, mesma recuperação e LLM. Não há treinamento LoRA. Há no máximo um reparo de contrato, com bruto e tentativa preservados. Limites de geração:900 tokens por resposta,180 por decisão; no máximo2520 tokens gerados em C incluindo reparo.

Respostas usam `status`, `answer`, `evidence:[{chunk_id,quote}]`, `missing_information`, `refusal_reason`. B/C só exibem extratos efetivamente vistos, contidos no trecho com normalização apenas de espaços. Prosa bruta é preservada para avaliação, sem ser apresentada como fundamentada. Recusas são renderizadas por mensagem segura fixa do status decidido pela LLM; anexos factuais da recusa não são publicados. O mesmo tratamento vale em A/B/C. Integridade da citação não garante relevância: a avaliação separa unidades, condições e suficiência. Ausência documental não significa inexistência de direito no mundo.

A API limita tamanho, fila, taxa, tempo e serializa inferências. Conversas não são persistidas por padrão. Não informe CPF, laudos, dados de saúde ou login. Testes de navegador usam Chrome instalado (desktop e viewport mobile emulado; sem validação em aparelho físico), com canal ajustável em `tests/test_browser.py`.

## Evidências

Snapshot entregue: 114 trechos de sete fontes oficiais, 100 casos e rodada final `20261112T061006Z-teste` com 180 execuções A/B/C (372 chamadas LLM medidas). Padrão B escolhido na validação; 42 testes aprovados e 20 exemplos reais conferidos. As metas não atingidas e as limitações do juiz estão no relatório.

- [Relatório em sete partes](docs/RELATORIO.md), [metodologia](docs/METODOLOGIA.md) e [operação](docs/OPERACAO.md).
- [Corpus e proveniência](base/manifesto.json), [partições](avaliacao/particoes.json), [calibração](avaliacao/calibracao/), [rodadas brutas](avaliacao/resultados/), [placar](avaliacao/placar.csv) e [cinco erros reais](avaliacao/erros_reais.md).
- Três [notebooks com outputs](notebooks/) e [evidências da interface/modelo](docs/evidencias/).

Resultados pertencem à nova base oficial. A auditoria automática é identificada e não representa revisão humana; campos não avaliáveis permanecem explícitos. Desempenho e limitações estão no relatório, sem garantia de nota. Repositório privado preservado. Vídeo: link pendente de gravação e fornecimento pelo usuário.


