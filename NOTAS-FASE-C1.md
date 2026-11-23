# SocialVault v0.3.0-c1 — Qualidades e desempenho

## Melhorias implementadas

- Listagem das resoluções MP4 disponíveis para cada vídeo, em ordem decrescente. A consulta é opcional, evitando atrasar a operação com um toque.
- Modo automático seleciona a maior altura MP4 compatível exposta ao extrator; a lista inclui vídeos separados de áudio quando houver uma faixa M4A adequada.
- Extração de MP4 progressivo sem conversão. Quando a resolução exigir vídeo e áudio separados, FFmpegKit tenta juntá-los usando `-c:v copy -c:a copy` sem recodificação.
- Barra de progresso com bytes transferidos, velocidade instantânea e ETA, quando fornecidos pela plataforma.
- Otimizações conservadoras: buffer maior e até 3 fragmentos simultâneos **somente para protocolos segmentados**, sem forçar conexões múltiplas para MP4s diretos.
- MP3 continua convertido localmente em 192 kbps, como na v0.2.

## Limitações e segurança

- Resoluções são aquelas que o `yt-dlp` detecta no momento da consulta, não resoluções inventadas; alguns vídeos oferecerão poucas opções ou nenhuma altura conhecida.
- Arquivos MKV, WebM ou codec incompatível com contêiner MP4 não são oferecidos no seletor desta revisão.
- A operação de consultar resoluções realiza uma requisição de metadados; a transferência posterior pode consultar metadados novamente. Isso pode aumentar o tempo até o início.
- Não há garantia de mais MB/s: desempenho depende da rede, CDN e formatos disponíveis; antes/depois deve ser medido no celular.
- Junção de faixas de vídeo/áudio e atualização do yt-dlp estão sujeitas às limitações de suporte real do TikTok e FFmpegKit no Android. Se a junção falhar, tentar uma resolução progressiva inferior.
- Não contorna restrições de privacidade, permissão ou DRM. Utilize com mídias que possa baixar.
- Etapas de fila, histórico e segundo plano ainda não fazem parte da C1.

## Testes

```sh
python -m unittest discover -s tests -v
PYTHONPATH=desktop-phase-a python -m unittest discover -s desktop-phase-a/tests -v
```

- Android/Python: 16 testes aprovados, com extratores simulados.
- Fase A: 15 testes aprovados.
- XML e sintaxe Python verificados localmente.
- Comando de junção FFmpeg validado com arquivos sintéticos; **não substitui** teste com a biblioteca FFmpegKit embarcada no Android.
- APK real ainda precisa compilar no CI e ser validado no Poco C75.
