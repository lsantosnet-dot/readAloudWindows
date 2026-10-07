# ReadAloud

App local para Windows 11 que transforma textos em **cards** e os **lê em voz alta**, 100% offline.

- **Ctrl+V** com a janela em foco cria um card com o texto da área de transferência
- **Importar** (ou arrastar para a janela) arquivos `.txt`, `.md`, `.markdown`, `.rst`, `.log`, `.csv`, `.json`, `.html`, `.srt`…
- **Detecção automática de idioma** (português / inglês) e escolha automática da voz
- **Play / pausar / continuar / parar** em cada card; textos longos são lidos em trechos, e o áudio começa logo
- **Velocidade da fala** (0,5× a 2×), ajustável inclusive durante a leitura
- **Voz por card** (ou "Automática", que usa a voz padrão do idioma)
- **Lixeira** em cada card e **Apagar tudo**
- Sem login e sem nuvem: os cards ficam num SQLite local

## Como funciona

| Parte | Tecnologia |
|---|---|
| Voz (TTS) | [Piper](https://github.com/OHF-Voice/piper1-gpl): vozes neurais que rodam na CPU, offline |
| Idioma | [py3langid](https://github.com/adbar/py3langid), offline |
| Backend | Python + FastAPI, escutando só em `127.0.0.1` |
| Janela | pywebview (usa o WebView2, que já vem no Windows 11) |
| Interface | HTML + CSS + JavaScript puro (`readaloud/static`) |
| Dados | `%LOCALAPPDATA%\ReadAloud\`: `cards.db`, `voices\`, `audio-cache\`, `readaloud.log` |

Antes de ler, o texto é limpo (remove marcações de markdown, links, URLs e HTML) e dividido em trechos de
até cerca de 450 caracteres. Cada trecho vira um WAV gerado pelo Piper e guardado em cache, então ouvir de novo é
instantâneo. Enquanto um trecho toca, o próximo já está sendo gerado. A velocidade é aplicada na reprodução,
sem alterar o tom da voz e sem precisar gerar o áudio de novo.

## Instalação (uma vez)

Requisitos: Windows 11 e **Python 3.10 a 3.13** (64 bits) instalado.

```bat
git clone https://github.com/lsantosnet-dot/readAloudWindows.git
cd readAloudWindows
setup.bat
```

O `setup.bat`:
1. cria o ambiente virtual `.venv` e instala as dependências;
2. baixa as vozes padrão (cerca de 60 MB cada) para `%LOCALAPPDATA%\ReadAloud\voices`:
   - PT-BR: `pt_BR-faber-medium`, `pt_BR-cadu-medium`, `pt_BR-jeff-medium`
   - EN: `en_US-lessac-medium`, `en_US-amy-medium`, `en_US-ryan-medium`

Esse é o único passo que usa internet. Se alguma voz falhar, rode de novo ou baixe só as que quiser:

```bat
.venv\Scripts\python -m readaloud --download-voices pt_BR-faber-medium en_US-lessac-high
```

A lista completa de vozes está em <https://huggingface.co/rhasspy/piper-voices/tree/main> e há amostras de áudio em
<https://rhasspy.github.io/piper-samples/>. Também dá para baixar manualmente os dois arquivos
(`.onnx` e `.onnx.json`) e copiá-los para a pasta de vozes. Depois, no app, use **⚙ → Recarregar vozes**.

## Usar sem gerar o .exe

```bat
run.bat
```

Para abrir no navegador em vez da janela do app: `.venv\Scripts\python -m readaloud --browser`.

## Gerar o .exe

```bat
build.bat
```

O resultado fica em `dist\ReadAloud\ReadAloud.exe`. Copie a **pasta `dist\ReadAloud` inteira** para onde quiser
(por exemplo, `C:\Apps\ReadAloud`) e crie um atalho do `.exe` na Área de Trabalho ou no Menu Iniciar.
As vozes e os cards não ficam dentro do executável; continuam em `%LOCALAPPDATA%\ReadAloud`.

> O build usa o modo "pasta" (`onedir`) do PyInstaller porque ele abre bem mais rápido que um `.exe` único.

## Dicas

- **Atalhos:** `Ctrl+V` cola um texto como novo card. `Tab` e `Enter`/`Espaço` navegam e acionam os botões.
- **Idioma errado?** Escolha uma voz do outro idioma no seletor do card; o idioma do card é corrigido junto.
- **Voz padrão por idioma** e o idioma usado quando a detecção não tem certeza (textos muito curtos)
  ficam em **⚙ Vozes e ajustes**.
- **Problemas?** Veja o log em `%LOCALAPPDATA%\ReadAloud\readaloud.log`.
- **Mudar a pasta de dados:** defina a variável de ambiente `READALOUD_HOME`.

## Desenvolvimento

```bat
.venv\Scripts\activate
python -m pytest
python -m readaloud --browser --debug
```

Estrutura:

```
readaloud/
  app.py              entrada: sobe a API numa porta livre e abre a janela
  server.py           rotas FastAPI (/api/cards, /api/voices, /api/settings)
  tts.py              vozes Piper instaladas, síntese e cache de áudio
  langdetect.py       detecção de idioma
  textproc.py         limpeza de markdown e divisão em trechos
  db.py               SQLite (cards e ajustes)
  voices_download.py  download das vozes padrão
  static/             interface (index.html, app.js, style.css)
tests/                testes (pytest)
ReadAloud.spec        configuração do PyInstaller
```

Para **adicionar outro idioma**, basta instalar uma voz Piper dele: a detecção passa a considerar
automaticamente os idiomas das vozes instaladas, além de PT e EN.
