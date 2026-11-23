# SocialVault Fase C1 — atualização do seu repositório

Esta entrega é um PATCH da Fase B atual, não um projeto Android novo.

1. Extraia `SocialVault-FaseC1-PATCH.zip`.
2. No GitHub, abra o repositório `Ryanzin3331/SocialVault` na branch `main`.
3. Abra `Add file → Upload files`.
4. No Windows Explorer, abra a pasta `SocialVault-C1` EXTRAÍDA e arraste **o conteúdo dela** (`app`, `tests`, `LEIA-ANTES.md`, `NOTAS-FASE-C1.md`) para o GitHub.
5. Confira se os caminhos aparecem como `app/src/main/python/android_bridge.py`, `app/src/main/java/br/com/socialvault/app/MainActivity.java`, `app/src/main/res/layout/activity_main.xml`, `app/src/main/res/layout/quality_spinner_item.xml`, `app/build.gradle` e `tests/test_quality_c1.py`. Não devem ficar dentro de outra pasta `SocialVault-C1/` no repositório.
6. Confirme **Commit changes** na branch `main`. GitHub Actions deve executar o workflow existente e testar a compilação.
7. Abra Actions. Se ficar verde, baixe o APK na área `Artifacts` e instale no Android.

* Mantemos `.github/workflows/build-apk.yml` original que já compilava; não precisa reenviar pasta oculta.
* Testes locais: 17 testes do Android/Python e 15 da Fase A passaram. Teste de mesclagem sintética com FFmpeg passou.
* Não houve compilação Android real nesta entrega. Verifique o CI antes de substituir seu APK v0.2.
* A opção automática requer consulta de metadados no início e pode começar mais lentamente que a v0.2; a melhoria de velocidade afeta sobretudo transferências fragmentadas (até três simultâneas), não todos os links.
