# Instalação SocialVault C2-A/B (TikTok Photo Mode)

O ZIP contém somente **arquivos alterados/novos** sobre a versão C1 já publicada no GitHub.

- Envie o **conteúdo** da pasta `SocialVault-C2AB` para a **raiz** do repositório.
- O GitHub deverá mostrar arquivos sob `app/` e `tests/`. **Não** crie uma pasta de nível superior chamada `SocialVault-C2AB` no repositório.
- A pasta `.github` **não precisa ser reenviada**.
- O Actions recompilará; o nome do artefato continuará sendo o antigo até renomearmos o workflow numa etapa posterior.
- `app/build.gradle` é atualizado para instalar `gallery-dl==1.32.11` e subir a versão do aplicativo para `0.4.0-c2ab`.
- Comece os testes com um post de fotos público e autorizado. Use **Ver fotos da publicação** para links curtos.

Consulte `NOTAS-FASE-C2AB.md` para testes, limitações e regressões.
