# SocialVault v0.2-alpha — Fase B (Android)

**Status em 23/11/2026:** projeto Android implementado e testes Python locais executados. **Não é um APK pronto**: esta sessão não tem Android SDK/Gradle instalados nem acesso de rede do contêiner para baixar dependências. Portanto, **a compilação e os testes reais em aparelho estão pendentes**. O GitHub Actions incluído gera um APK de teste se todas as dependências forem resolvidas. Não apresentamos sucesso de build não observado.

## O que a Fase B implementou

- App Android nativo em Java, sem navegador, sem servidor externo próprio, sem anúncios e sem login.
- **TikTok → Compartilhar → SocialVault**: `ACTION_SEND`, `text/plain`, lê `Intent.EXTRA_TEXT`. Preenche o campo, mas **não baixa automaticamente**; o usuário decide o formato e confirma.
- Campo de link e checagem rigorosa de hosts oficiais TikTok, inclusive URLs curtas.
- MP4: baixa o melhor **MP4 progressivo com áudio** disponível por yt-dlp. Sem ffmpeg de shell ou transcodificação de vídeo.
- MP3: baixa a melhor fonte de áudio disponível e converte no celular para 192 kbps com FFmpegKit/`libmp3lame`.
- Progresso, cancelamento cooperativo, prevenção de downloads paralelos, armazenamento temporário isolado por tarefa e limpeza em caso de erro.
- Arquivos guardados via MediaStore sem solicitar acesso amplo a arquivos. **MP4** vai para `Filmes/SocialVault` (Movies/SocialVault), **MP3** para `Música/SocialVault` (Music/SocialVault).
- Botões **Abrir** e **Compartilhar** o último arquivo, inclusive após reabrir o app.

> **Qualidade:** o formato MP4 progressivo pode oferecer resolução menor que a melhor faixa de vídeo separada. A mesclagem de vídeo + áudio em streams separados, que poderá dar acesso a resoluções maiores, está planejada para a próxima revisão. Não é correto prometer 1080p em qualquer vídeo. Não há remoção de marca d'água nem contorno de bloqueios.

## Como obter o APK para instalar no celular

### Opção 1 — Windows 11 com Android Studio

1. Extraia este ZIP numa pasta, por exemplo `Documentos/SocialVault-FaseB`.
2. Instale **Android Studio** (versão com suporte a Android Gradle Plugin 8.9) e **Python 3.11**, além de um JDK 17, se não estiver incluído. É necessário acesso à internet na primeira compilação para baixar Android SDK, Chaquopy, yt-dlp e FFmpegKit.
3. No Android Studio: **Open** → selecione a pasta `SocialVault-FaseB` onde ficam `settings.gradle` e `app`.
4. Deixe o Gradle sincronizar. Se pedir, instale **Android SDK Platform 35** e **Build-Tools 35.0.0**.
5. No menu **Build → Build Bundle(s) / APK(s) → Build APK(s)**. O resultado de teste deve aparecer em `app/build/outputs/apk/debug/app-debug.apk`.
6. Envie o APK por cabo ou outro método ao celular e abra o arquivo para instalar. O Android pode pedir permissão para instalar APKs desta fonte; só instale APKs compilados a partir de código de sua confiança.

**Nota:** este projeto não inclui o `gradlew` nem o jar do Gradle Wrapper, pois não foi possível obtê-los neste ambiente. O Android Studio pode usar uma distribuição Gradle instalada ou gerar o Wrapper; a alternativa GitHub Actions usa uma distribuição Gradle explicitamente fixada e não depende de `gradlew`.

### Opção 2 — GitHub Actions (sem instalar Android Studio)

1. Crie um repositório GitHub pessoal (privado, se preferir) e envie **o conteúdo extraído do ZIP**, incluindo a pasta oculta `.github` com o arquivo `workflows/build-apk.yml` (não envie só o ZIP).
2. Depois do envio, abra a aba **Actions** → **Compilar APK SocialVault** → **Run workflow** (ou aguarde a execução automática pelo push na branch `main`).
3. Na execução concluída com sucesso, abra **Artifacts** e baixe `SocialVault-v0.2-alpha-debug-apk`. Extraia o APK que vem dentro do arquivo de artefato.
4. Copie para o Android e instale. **O arquivo de artefato é um ZIP, não o APK diretamente.**

O workflow já executa testes Python, compila APK de debug e executa testes JUnit do parser Java. **Ele não foi executado neste ambiente**, portanto pode revelar incompatibilidades não detectadas aqui.

## Teste funcional no aparelho

1. Instale o APK. Abra SocialVault, cole um **link de TikTok permitido para download**, escolha MP4 e clique **Baixar agora**. Verifique se o vídeo aparece em `Filmes/SocialVault`.
2. Repita com **MP3**. Verifique se o áudio aparece em `Música/SocialVault`.
3. Abra TikTok → vídeo permitido → **Compartilhar** → **SocialVault**. Confira se o campo já aparece preenchido e se o download só começa quando você confirmar.
4. Faça um download maior e teste **Cancelar**. Veja se não aparece arquivo incompleto na galeria.
5. Toque em **Abrir** ou **Compartilhar** no último arquivo salvo.

Se o app abrir mas a biblioteca não conseguir baixar, anote a mensagem exibida e a plataforma/versão do Android. Não envie senhas nem cookies.

## Dependências e arquitetura

- Android Gradle Plugin `8.9.2`, Gradle `8.11.1` na CI, JDK 17, Android SDK 35, `minSdk 29`, `targetSdk 35`.
- `com.chaquo.python:17.2.0` com Python 3.11, yt-dlp empacotado no APK.
- `dev.ffmpegkit-maintained:ffmpeg-kit-audio:8.1.7` para MP3 (não-GPL, com libmp3lame).
- Apenas ABI `arm64-v8a` para evitar empacotar arquiteturas desnecessárias no APK de teste.
- Java da tela chama `android_bridge.py` via Chaquopy. O adaptador importa a função de validação `socialvault.core.normalize_tiktok_url` da Fase A. FFmpegKit processa áudio pelo Java, e o MediaStore publica os arquivos.

Fontes técnicas: https://chaquo.com/chaquopy/doc/current/android.html , https://developer.android.com/training/sharing/receive , https://developer.android.com/training/data-storage/shared/media , https://github.com/ffmpegkit-maintained/ffmpeg .

## Limites conhecidos

- Um único download por vez. **Mantenha o app aberto** até concluir; ainda não há `ForegroundService` para download em segundo plano.
- A biblioteca yt-dlp e os formatos disponíveis mudam com o TikTok. Links privados, restringidos ou indisponíveis podem falhar.
- Não há filas, histórico completo nem atualização dinâmica do extrator.
- A resolução não é garantida: `best[ext=mp4]` procura melhor MP4 progressivo disponível, e algumas mídias só oferecem resoluções maiores em streams separados.
- Não assegura autorização de terceiros automaticamente. Use para mídias próprias ou cujo download seja permitido pelo criador; para redistribuição/repost, obtenha autorização quando necessário.
- Compatibilidade e desempenho com o Poco C75 **não testados**: precisamos do primeiro APK instalado para medir.

## Testar a parte Python sem Android

`python -m unittest discover -s tests -v` executa testes sem acesso à internet. A versão original de linha de comando da Fase A foi preservada na pasta `desktop-phase-a/`.
