# ARASAKA RELIC

Backups com o visual da Arasaka para **Zorin OS e Ubuntu**. Guarda os seus documentos e os dados dos apps
Arasaka (inclusive a chave do Holo) num HD externo, pendrive ou outra pasta, e restaura o que você precisar.

## Como funciona

Cada backup é uma **foto da data** (`DESTINO/ArasakaRelic/<pc>/2026-11-19_083000`) que parece uma cópia
completa: dá para abrir no gerenciador de arquivos e copiar de volta sem o Relic. Os arquivos que não mudaram
desde o backup anterior são **hardlinks** para ele, então só o que mudou ocupa espaço novo.

Por baixo, é o **rsync**, a ferramenta de cópia mais usada no Linux. Nada sai do seu PC.

## Abas

| Aba | O que tem |
|---|---|
| **01 Backups** | Último backup, espaço livre no destino, **fazer backup agora** com progresso, lista das fotos, **restaurar** (no lugar original ou em outra pasta), abrir a pasta e excluir |
| **02 O que salvar** | Documentos, Imagens, Músicas, Vídeos, Área de Trabalho, a chave do Holo, as configurações dos apps Arasaka, os dados dos módulos da Central, chaves SSH e Git. Opcionais: Downloads, programas do Bridge e as VMs do Blackwall. Mais pastas suas e o que **não** salvar (`*.iso`, `node_modules/`...) |
| **03 Destino e agenda** | Onde guardar, quantos backups manter (os mais antigos são apagados) e o **backup diário** automático |

## Backup diário

Usa um *timer* do systemd do seu usuário (sem senha de administrador). Se o PC estiver desligado no
horário, o backup é feito quando ele ligar. Se o HD do destino não estiver conectado, o Relic avisa e tenta
no dia seguinte. Pela linha de comando:

```bash
arasaka-relic --run
```

## Instalar

Pela **Arasaka Central** (Loja → Apps), ou:

```bash
./install.sh
```

Rode **sem sudo**; ele pede a senha só para instalar o rsync, se faltar. Para remover: `./uninstall.sh`
(os backups que você fez continuam no destino).

## Restaurar sem o Relic

Os backups são pastas normais. Num sistema novo, abra a foto mais recente no gerenciador de arquivos e copie
o que quiser de volta para a pasta pessoal. A chave do Holo fica em `.config/arasaka-holo/identity.key`.

---

Arasaka é marca da CD PROJEKT RED (projeto de fã, sem fins comerciais). A fonte `cedge1` usa a licença
FontStruct Non-Commercial.
