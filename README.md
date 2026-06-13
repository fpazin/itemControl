# ItemControl

Aplicativo desktop em Python para controle de ativos de TI entre países e localidades.

Desktop application in Python for controlling IT assets across countries and locations.

## Como executar / How to run

```bash
python -m itemcontrol
```

## Testes / Tests

```bash
python -m unittest discover -s tests
```

## Versoes e downloads / Releases and downloads

Os executaveis Windows x64 portateis e as principais mudancas de cada versao
estao disponiveis em:

- https://github.com/fpazin/itemControl/releases
- [CHANGELOG.md](CHANGELOG.md)

O executavel nao precisa de instalacao. Baixe o arquivo da versao desejada e
execute-o diretamente.

## Bases protegidas / Protected databases

Ao iniciar, o app permite escolher uma base existente, criar uma nova base ou abrir
uma base protegida por senha. Bases novas podem ser criadas sem senha ou com
criptografia SQLCipher.

- Senhas nao sao salvas pelo app.
- Apenas caminhos de bases recentes sao gravados nas configuracoes locais.
- Bases SQLite antigas sem senha continuam abrindo normalmente.
- Use o menu `Base de dados > Proteger base...` para criar uma copia criptografada
  da base atual.
- Se a senha de uma base criptografada for perdida, a base nao podera ser aberta.

## Controle de versão / Version control

Este projeto usa Git Flow com versionamento SemVer.

- `main`: contém apenas versões estáveis tagueadas.
- `develop`: integra o trabalho em andamento antes de uma release.
- `feature/<nome>`: novas funcionalidades criadas a partir de `develop`.
- `release/x.y.z`: preparação de uma versão, incluindo ajuste de versão e validação final.
- `hotfix/x.y.z`: correção urgente criada a partir de `main` e depois integrada em `develop`.

As versões seguem SemVer (`MAJOR.MINOR.PATCH`). A fonte unica da versao e
`src/itemcontrol/__init__.py`; o `pyproject.toml` le esse valor dinamicamente.

### Comandos principais

```bash
git switch develop
git switch -c feature/minha-mudanca
python -m unittest discover -s tests
git switch develop
git merge --no-ff feature/minha-mudanca
```

### Criar release

```bash
git switch develop
git switch -c release/0.2.0
python -m unittest discover -s tests
git switch main
git merge --no-ff release/0.2.0
git tag -a v0.2.0 -m "Release v0.2.0"
git switch develop
git merge --no-ff release/0.2.0
```

### Criar hotfix

```bash
git switch main
git switch -c hotfix/0.1.1
python -m unittest discover -s tests
git switch main
git merge --no-ff hotfix/0.1.1
git tag -a v0.1.1 -m "Release v0.1.1"
git switch develop
git merge --no-ff hotfix/0.1.1
```

## Tecnologias / Technologies

- Python 3.10+
- PySide6
- SQLite
