# Operação local

O servidor LLM deve responder em `/health` antes da API. Verifique a porta antes de iniciar processos; use8002 se8000estiver ocupada. No Windows, se iniciar em segundo plano use `Start-Process -WindowStyle Hidden`. Encerre somente processos que iniciou e cuja linha de comando foi conferida. Logs de desenvolvimento ficam em `.runtime`, fora da entrega.

A interface mostra o órgão responsável, URL oficial, localizador, data de coleta, versão SHA256 e natureza de síntese curada. O link abre o documento oficial em nova aba. As perguntas do catálogo são exemplos de desenvolvimento; a digitação livre continua disponível. Exemplos de limites são diferenciados dos positivos.

Fila máxima3, taxa10 requisições/minuto por cliente e uma inferência por vez. Timeout HTTP da API100s; o slot não é liberado prematuramente enquanto o trabalho em execução termina. Falha técnica usa indisponivel, sem contabilizar como recusa correta. Não expor a API local a redes públicas sem revisão adicional de autenticação e limites.

Para atualizar as fontes, preserve a rodada atual e execute coleta explícita. Confira termos, mudanças de conteúdo, tabelas e exceções; gere nova curadoria/versionamento, reconstrua índice, recalibre e use teste independente se resultados anteriores orientaram mudanças.
