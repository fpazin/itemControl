# ItemControl

Aplicativo desktop em Python para controle de ativos de TI entre países e localidades.

## Versão atual

**ItemControl 0.2.0**

Principais recursos desta versão:

- múltiplas bases de dados;
- bases protegidas por senha com criptografia SQLCipher;
- lista de bases abertas recentemente, sem armazenar senhas;
- página `Sobre` com versão, desenvolvedor, repositório e downloads;
- executável portátil para Windows x64.

Consulte todas as alterações no [CHANGELOG.md](CHANGELOG.md).

## Download

Os executáveis portáteis e as notas de cada versão estão disponíveis na página:

- [GitHub Releases](https://github.com/fpazin/itemControl/releases)

O executável Windows não precisa de instalação. Baixe o arquivo
`ItemControl-vX.Y.Z-windows-x64.exe` da versão desejada e execute-o diretamente.
Versões anteriores permanecem disponíveis na mesma página.

## Como executar pelo código-fonte

Requisitos:

- Python 3.10 ou superior;
- Windows, Linux ou macOS com suporte ao PySide6.

```bash
python -m pip install -e .
python -m itemcontrol
```

Para consultar a versão instalada:

```bash
python -m itemcontrol --version
```

## Bases de dados

Ao iniciar, o aplicativo permite escolher uma base existente ou criar uma nova.
Bases novas podem ser comuns ou protegidas por senha com SQLCipher.

- Senhas nunca são salvas pelo aplicativo.
- Apenas os caminhos das bases recentes são armazenados localmente.
- Bases SQLite antigas sem senha continuam compatíveis.
- O menu `Base de dados > Proteger base...` cria uma cópia criptografada.
- A base original não é sobrescrita durante a proteção.
- Não existe recuperação de senha para bases criptografadas.

## Sobre

A aba `Sobre` apresenta:

- versão atual do ItemControl;
- desenvolvedor: [Felipe Pazin](https://github.com/fpazin);
- [repositório do projeto](https://github.com/fpazin/itemControl);
- acesso às versões e downloads.

## Testes

```bash
python -m unittest discover -s tests
```

## Controle de versão

O projeto usa versionamento semântico (`MAJOR.MINOR.PATCH`).

- `develop`: branch de desenvolvimento e integração.
- `main`: versões estáveis publicadas.
- tags `vX.Y.Z`: identificam cada versão disponibilizada.

A fonte única da versão é `src/itemcontrol/__init__.py`. O `pyproject.toml`
lê esse valor dinamicamente.

O workflow de release executa os testes, gera o executável Windows portátil e
publica as notas extraídas do `CHANGELOG.md` no GitHub Releases.

## Tecnologias

- Python 3.10+
- PySide6
- SQLite
- SQLCipher
- PyInstaller
