# SocialVault v0.4.0-c2ab — TikTok Photo Mode

**Base:** v0.3.0-c1 aprovada pelo usuário em aparelho Android. Atualização incremental, sem alterar `android_bridge.py` ou o motor de vídeos/áudios.

## O que entra

- O botão **Ver fotos da publicação** abre a nova tela de fotos.
- Quando um link compartilhado já contém `/photo/`, essa tela abre diretamente. Em links curtos `vt.tiktok.com`/`vm.tiktok.com`, use o botão, pois a URL não revela o tipo sem consulta à rede.
- `gallery-dl==1.32.11` consulta o TikTok; o app diferencia publicação de vídeo e publicação de imagens. Não coleta automaticamente perfis, feeds ou conteúdo privado.
- Fotos listadas na ordem da publicação, com miniaturas, ampliação ao tocar, caixas de seleção, marcar todas/desmarcar.
- **Salvar fotos selecionadas** publica os arquivos em `Imagens/SocialVault` via Android MediaStore (JPEG/PNG/WebP). Nenhuma permissão ampla de arquivos.
- Imagens baixadas via HTTPS com limite de 32 MiB cada; prévias limitadas a 8 MiB e dois trabalhos concorrentes para reduzir o uso de memória.
- Cancela o restante da seleção sem apagar fotos completas já salvas; arquivos parciais são descartados.
- O motor de MP4, MP3, seletor de qualidade, progresso e FFmpeg da v0.3 não foram alterados.

## Ainda não implementado

- Gerar slideshow MP4 com duração das fotos e áudio original (C2-D/E).
- Histórico completo de fotos, fila, processamento em segundo plano.
- O reconhecimento de toda e qualquer publicação real não é garantido: o TikTok pode bloquear o extrator; a URL pode expirar.
- O botão de qualidade de vídeo continua pertencendo ao modo MP4, não ao Photo Mode.

## Validação executada neste ambiente (sem rede de download / Android SDK)

- 36 testes de integração/contrato Python (`tests/`): aprovados.
- 15 testes da Fase A (`desktop-phase-a/tests/`): aprovados com PYTHONPATH correto.
- 10 verificações JVM para a política de URLs de fotos: aprovadas.
- `javac`: `PhotoUrl.java` e `TikTokLink.java` compilados.
- Validação de XML dos recursos e referências `R.id` Java: aprovada.
- Código Python verificado por `compileall`.

**Não foi possível compilar o APK neste ambiente nem testar acesso ao TikTok/galeria em Android real.** O GitHub Actions ainda precisa executar `:app:assembleDebug :app:testDebugUnitTest` e os testes reais no telefone.

## Atualização do GitHub

1. Extraia o ZIP `SocialVault-C2AB-PATCH.zip`.
2. Abra `SocialVault-C2AB` e arraste **o conteúdo** (pastas `app`, `tests` e este arquivo de notas) para **Add file → Upload files** na raiz do repositório.
3. Confirme que os arquivos irão para `app/src/...` e `tests/...`, sem uma pasta extra `SocialVault-C2AB` no repositório; confirme substituições.
4. Faça **Commit changes**. O workflow existente de compilação executa automaticamente; a pasta `.github` **não precisa ser alterada**.
5. No GitHub Actions, baixe o artefato do workflow. **O nome ainda será `SocialVault-v0.2-alpha-debug-apk`, pois preservamos o workflow existente**. O número real da versão dentro do app passa a ser `0.4.0-c2ab`.
6. Antes de instalar, guarde o APK anterior. Builds de debug do GitHub Actions podem ter assinaturas diferentes entre execuções e exigir remover o app antigo antes de instalar a atualização. Arquivos já salvos no armazenamento compartilhado continuam na galeria, mas preferências privadas do aplicativo podem ser perdidas na reinstalação.

## Testes manuais no Android

1. Teste novamente um vídeo em MP4 (automático e resolução escolhida) e um MP3.
2. Compartilhe uma publicação **com fotos** com o SocialVault e toque em **Ver fotos** caso o aplicativo não abra essa tela automaticamente.
3. Confira a ordem e as miniaturas, desmarque duas fotos, salve apenas as selecionadas.
4. Confira os arquivos em `Imagens/SocialVault`. Teste abrir os arquivos pelo gerenciador de fotos.
5. Teste o link curto, publicação com somente uma foto, publicação sem imagens e cancelar em meio ao download.
6. Se o TikTok recusar o acesso, envie **somente a mensagem de erro** (nunca cookies, credenciais ou dados privados).

## Licenças e permissões

`gallery-dl` é um projeto de código aberto sob GNU GPL-2.0; ao redistribuir APKs que o incorporam, respeite as condições da licença e disponibilize as fontes exigidas. Consulte https://github.com/mikf/gallery-dl/blob/master/LICENSE . Esta atualização não inclui remoção de marcas, acesso a perfis privados ou contorno de restrições.
