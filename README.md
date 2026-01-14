<p align="center">
  <img src="https://img.shields.io/badge/version-2.0-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/PySide6-Qt-41CD52?style=for-the-badge&logo=qt&logoColor=white" alt="PySide6">
  <img src="https://img.shields.io/badge/platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/github/license/Tsug07/libby?style=for-the-badge" alt="License">
</p>

<h1 align="center">Libby</h1>

<p align="center">
  <strong>Gerenciador de Programas e Automações RPA</strong>
</p>

<p align="center">
  Um hub centralizado para organizar, categorizar e executar todos os seus programas, scripts e automações em um só lugar.
</p>

---

## Funcionalidades

| Funcionalidade | Descrição |
|----------------|-----------|
| **Categorias Colapsáveis** | Organize seus programas em categorias personalizadas |
| **Sistema de Tags** | Classifique programas com tags coloridas (trabalho, pessoal, urgente, teste, produção) |
| **Favoritos** | Marque seus programas mais usados para acesso rápido |
| **Busca e Filtros** | Encontre programas rapidamente com busca em tempo real |
| **Temas Claro/Escuro** | Interface adaptável com suporte a tema dark |
| **Importação Automática** | Importe pastas inteiras de automações RPA automaticamente |
| **Ícones Personalizados** | Defina ícones/logos para cada programa |
| **Histórico de Execução** | Acompanhe contagem e data da última execução |
| **System Tray** | Minimize para bandeja do sistema |
| **Detecção de Logos** | Detecta automaticamente ícones em pastas importadas |

## Screenshot

```
┌─────────────────────────────────────────────────────────────┐
│  Libby                    [Buscar...]  [Filtro ▼]  📁 ➕ ↻ 🌙 │
├─────────────────────────────────────────────────────────────┤
│  > Automações RPA (5)                                       │
│    ├─ Bot WhatsApp       [trabalho]  Envio automático  BAT  │
│    ├─ Scraper Web        [produção]  Coleta de dados   PY   │
│    └─ Gerador Reports    [urgente]   Relatórios PDF    EXE  │
│                                                             │
│  > Ferramentas (3)                                          │
│    ├─ Editor Config                  Edita configs     BAT  │
│    └─ Monitor Sistema    [pessoal]   CPU/RAM monitor   EXE  │
└─────────────────────────────────────────────────────────────┘
```

## Instalação

### Pré-requisitos

- Python 3.8 ou superior
- Windows 10/11

### Instalação das Dependências

```bash
pip install PySide6
```

### Executando

```bash
python main.py
```

## Como Usar

### Primeiro Uso

1. Clique no botão **📁** para selecionar a pasta Hub onde seus programas serão organizados
2. Crie categorias com o botão **➕**
3. Adicione programas com o botão **📥** ou importe pastas existentes com **⬇**

### Importando Automações RPA

1. Clique em **⬇** (Importar pasta RPA)
2. Selecione a pasta contendo seus scripts/programas
3. O Libby detectará automaticamente arquivos `.py`, `.bat`, `.exe` e criará atalhos

### Gerenciando Programas

- **Clique esquerdo**: Executa o programa
- **Clique direito**: Menu de contexto (Editar, Favoritar, Remover)
- **Editar**: Personalize nome, descrição, tags e ícone

## Estrutura do Projeto

```
libby/
├── main.py              # Aplicação principal
├── README.md            # Documentação
└── %APPDATA%/MeuHub/
    ├── config.json      # Configurações e metadados
    └── icon_cache/      # Cache de ícones
```

## Formatos Suportados

| Extensão | Descrição |
|----------|-----------|
| `.exe`   | Executáveis Windows |
| `.bat`   | Scripts Batch |
| `.cmd`   | Scripts de Comando |
| `.py`    | Scripts Python |
| `.lnk`   | Atalhos do Windows |

## Tecnologias

- **Python 3** - Linguagem principal
- **PySide6 (Qt6)** - Framework de interface gráfica
- **JSON** - Armazenamento de configurações

## Roadmap

- [ ] Suporte a atalhos de teclado personalizados
- [ ] Agendamento de execução automática
- [ ] Logs de execução detalhados
- [ ] Sincronização em nuvem
- [ ] Suporte multiplataforma (Linux/macOS)

## Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou pull requests.

1. Fork o projeto
2. Crie sua branch de feature (`git checkout -b feature/NovaFuncionalidade`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/NovaFuncionalidade`)
5. Abra um Pull Request

## Autor

**Hugo L. Almeida**

- GitHub: [@Tsug07](https://github.com/Tsug07)

## Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

<p align="center">
  Feito com ❤️ para a comunidade RPA brasileira
</p>
