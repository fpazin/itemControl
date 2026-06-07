# ITemControl

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

## Controle de versão / Version control

Este projeto usa Git Flow com versionamento SemVer.

- `main`: contém apenas versões estáveis tagueadas.
- `develop`: integra o trabalho em andamento antes de uma release.
- `feature/<nome>`: novas funcionalidades criadas a partir de `develop`.
- `release/x.y.z`: preparação de uma versão, incluindo ajuste de versão e validação final.
- `hotfix/x.y.z`: correção urgente criada a partir de `main` e depois integrada em `develop`.

As versões seguem SemVer (`MAJOR.MINOR.PATCH`) e devem manter `pyproject.toml` e
`src/itemcontrol/__init__.py` sincronizados antes de criar a tag Git.

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
