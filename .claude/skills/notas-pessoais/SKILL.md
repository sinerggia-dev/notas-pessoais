---
name: notas-pessoais
description: Trabalhar no app ROADMAP / Notas Pessoais (sinerggia-dev/notas-pessoais) — página única em index.html com login Microsoft, dados no OneDrive via Graph, publicada no GitHub Pages. Use ao alterar a tabela de tarefas, colunas, filtros, notas, anexos, tema, o script de alertas de vencimento, ou ao gerar o relatório de treinamentos a partir da exportação do ROADMAP. Traz o ciclo de publicação, como verificar sem conseguir abrir o app, e as armadilhas que já custaram bug.
---

# Notas Pessoais / ROADMAP

Espaço de notas e tarefas da Sinerggia. Páginas estilo Notion, banco de tarefas com
tabela/Kanban, calendário e dashboard — **tudo em um só arquivo**.

| | |
|---|---|
| Repo | `sinerggia-dev/notas-pessoais`, branch única `main` |
| No ar | https://sinerggia-dev.github.io/notas-pessoais/ |
| Clone | `Documentos\claude\notas-pessoais` |
| Dados | OneDrive do dono, pasta `Notas Pessoais - Dados` |
| Arquivo | `index.html` (~4.700 linhas: CSS + HTML + um `<script>` inline) |

Sem build, sem servidor. Duas bibliotecas de CDN: `@azure/msal-browser` (login) e
`xlsx`/SheetJS (exportar). Publicar é `git push`.

## Regra número um: você não vai conseguir abrir o app

O `redirectUri` do MSAL é `origin + pathname`, então o login Microsoft só funciona nas
URLs registradas no App Registration. `file://` e localhost não autenticam. **Não perca
tempo tentando rodar** — o ciclo real é editar, publicar, e o usuário confere.

O que dá para verificar sozinho, e deve ser feito sempre:

```bash
# 1. sintaxe do JS inline
python -c "import io,re; s=io.open('index.html',encoding='utf-8').read(); \
  open('/tmp/app.js','w',encoding='utf-8').write( \
  re.findall(r'<script(?![^>]*\ssrc=)[^>]*>(.*?)</script>', s, re.S)[0])"
node --check /tmp/app.js

# 2. CSS balanceado e sem cor malformada (ver armadilha 1)
# 3. IDs do markup sem duplicata, e os IDs novos presentes
# 4. o publicado é o que você comitou
curl -s "https://sinerggia-dev.github.io/notas-pessoais/index.html?cb=1" | diff - index.html
```

Para lógica pura (busca, datas, normalização, estado de vencimento), **extraia a função do
arquivo e teste no Node** com um `document` de mentira. É assim que os bugs de regra foram
pegos antes de publicar:

```js
const src = fs.readFileSync("index.html", "utf8");
function ex(n){ /* recorta a função contando chaves */ }
eval([ex("todayISO"), ex("dueState")].join("\n"));
```

## Ciclo de publicação

1. Editar `index.html` (e `scripts/enviar_alertas_vencimento.py` quando o formato da tarefa mudar).
2. Commit em `main`, mensagem em português descrevendo o efeito, não o arquivo.
3. `git push` → workflow *pages build and deployment* → ~1 min (às vezes 3, fica na fila).
4. Confirmar com `curl ... | grep -c <marcador novo>` antes de dizer que está no ar.
5. Avisar o usuário para recarregar com **Ctrl+Shift+R** — o `index.html` fica em cache com
   facilidade, e ele vai ver o bug antigo e achar que não funcionou.

## Como o arquivo é organizado

Procure pelo nome da seção, nunca por número de linha:

```
CSS         /* ---------- Nome ---------- */
JavaScript  /* ===== NOME ===== */
```

`CONFIG` · `ESTADO` · `HELPERS` · `LOGIN / TOKEN (MSAL)` · `MICROSOFT GRAPH — WORKSPACE` ·
`INICIALIZAÇÃO APÓS LOGIN` · `PÁGINAS — CRUD + ÁRVORE` · `MINI CALENDÁRIO` · `MENU MOBILE` ·
`EDITOR DE PÁGINA` · `BLOCOS` · `BARRA DE FORMATAÇÃO FLUTUANTE` · `BANCO DE TAREFAS` ·
`AGREGAÇÃO ENTRE PÁGINAS` · `DASHBOARD` · `CALENDÁRIO` · `MENU "/"` · `PAINEL DE ADMINISTRAÇÃO` · `BOOT`

## Dados

`_indice.json` (páginas), `_usuarios.json` (quem tem acesso e o papel), e um
`pagina_<id>.json` por página com `{ blocks, tasks, events }`.

Tarefa hoje:

```
id, title, status (Pendente|Iniciado|Concluído|Cancelado), priority,
assignees[]  ← lista de e-mails; assignee (singular) fica espelhado com o primeiro
company, dueDate (AAAA-MM-DD), items, links,
note  ← HTML, não texto
attachment { id, name, url, size }  ← arquivo na subpasta "Anexos" do OneDrive
createdAt, statusChangedAt, timeSpentSeconds, timerRunning, timerStartedAt
```

Autosave com debounce de 1,2 s por arquivo; erro tenta de novo a cada 5 s. `Ctrl+S` força.
`migrateTaskStatuses(content)` roda ao carregar e é onde vive toda migração de formato
(renomear status, virar `assignees` lista, limpar nome de empresa).

Preferências de layout ficam em `localStorage` (`np_task_*`), nunca conteúdo. Coluna nova
é anexada ao fim da ordem salva, então atualização não some com a coluna de quem já usava.

## A senha de edição

`TASK_PASSWORD` no código, num repo público: é **freio contra clique acidental**, não
segurança. O que controla acesso de verdade é o papel em `_usuarios.json` (`Editor` /
`Visualizador`, na variável `canEdit`) mais a permissão da pasta no OneDrive.

`guardTaskFieldEdit(task)` é o portão: pede senha, exceto nos 10 minutos após criar a
tarefa. Pede em: alterar campo, excluir tarefa, mover/ocultar/restaurar coluna, excluir
página. **Não** pede para: abrir nota, trocar status ou prioridade.

Regra de ouro nos campos: pergunte a senha **uma vez, quando a alteração é real** — nunca
a cada tecla. Ver armadilha 2.

## Receita: coluna nova na tabela

1. Entrada em `TASK_COLUMNS_DEF` + largura em `DEFAULT_COL_WIDTHS`.
2. `buildXCell(task)` e registro em `TASK_CELL_BUILDERS`.
3. Opcional: `SORT_ACCESSORS` (ordenar pelo cabeçalho), a linha do `exportTasksBtn`
   (sair no Excel), `taskSearchHaystack` (entrar na busca).

Mover, ocultar e restaurar já funcionam de graça — vêm da `TASK_COLUMNS_DEF`.

## Armadilhas que já custaram bug

**1. Substituição em massa de cor pega prefixo.** Trocar `background:#fff` por token também
casa o começo de `#fff3d6`, deixando `var(--surface)3d6` — regra inválida, elemento sem
fundo, e nada avisa. Cinco regras quebraram assim (pílula Iniciado, prioridade Média,
vencimento de hoje, faixa de somente-leitura, feriado facultativo). O sinal estava no
contador: 38 substituições contra 34 ocorrências no inventário. **Sempre** rode depois:

```python
for m in re.finditer(r'(background|color|border-color)\s*:\s*([^;{}]+)', css):
    if re.search(r'var\([^)]*\)[0-9a-zA-Z]', m.group(2)): print("MALFORMADA", m.group(2))
```

**2. `change` em `input type=date` dispara no meio da digitação.** Com a data já preenchida,
digitar só o dia monta uma data completa e válida — o evento sai e a senha era pedida antes
do usuário chegar no ano, três vezes por edição. Grave no **blur**, com Enter confirmando e
Esc desfazendo. Ver `bindDueInput`.

**3. Empresa duplicada é caractere invisível.** "Metropolitana" e "Metropolitana " são
strings diferentes num `Set` e idênticas na tela. `normalizeCompany` tira NFKC + hífen
suave + juntadores + largura zero + BOM; `companyKey` ainda ignora acento e caixa. Trate
nos quatro pontos: gravar, carregar (migração), listar no filtro, comparar no filtro.

**4. Media query não aumenta especificidade.** `#app.sidebar-collapsed #sidebar{width:0}`
(2 ids + classe) vencia o `#sidebar{width:85vw}` de dentro do `@media (max-width:768px)`.
Quem recolhia a barra no computador abria no celular com a lateral de largura zero e o
hambúrguer parecia morto. Desfaça a regra **dentro** do media query.

**5. Texto colado traz cor e fundo próprios.** Conteúdo de Outlook/Word vem com
`style="color:#333"`, invisível no tema claro e ilegível no escuro. Estilo inline vence
herança: só `!important` desfaz. Já coberto em `#noteEditor`, `.block-content` e `.task-title`.

**6. Mudou o formato da tarefa? O script de alertas também muda.** `enviar_alertas_vencimento.py`
lê os JSON direto do Graph. Quando `assignees` virou lista, ele ainda leria só `assignee` e
dois de três responsáveis nunca receberiam e-mail. Quando entrou `Cancelado`, ele ainda
cobraria tarefa cancelada. Ele tem teste de mesa fácil: importe e chame `extrair_responsaveis`.

**7. Filtro ativo com grupo recolhido esconde o resultado.** Ao agrupar por empresa, o
estado "recolhido" é ignorado enquanto há filtro (`anyTaskFilterActive()`), senão o atalho
"Hoje" acha 2 tarefas e mostra zero. Os botões Expandir/Recolher ficam desabilitados nesse
estado, com o motivo no tooltip, para não parecerem quebrados.

## Alertas de vencimento

`.github/workflows/alertas-vencimento.yml` roda `scripts/enviar_alertas_vencimento.py` às
11:00 UTC (08:00 de Brasília) e sob demanda. Autentica *app-only* (client credentials) com
`AZURE_CLIENT_SECRET` (secret do repo); precisa de `Files.ReadWrite.All` e `Mail.Send` com
consentimento de admin. Manda e-mail via Graph e WhatsApp via CallMeBot para quem tem
telefone e apikey na Administração. Ignora `Concluído` e `Cancelado`.

## Relatório de treinamentos

Gera a página de evolução dos treinamentos Sankhya a partir da exportação do ROADMAP.

```bash
# no app: ✕ Limpar filtros → ⬇️ Exportar   (cai em Downloads/ROADMAP.xlsx)
cd scripts/relatorio
python parse_roadmap.py  ~/Downloads/ROADMAP.xlsx  dados.json
python gerar_relatorio.py  dados.json  relatorio.html
```

Publique o `relatorio.html` como Artifact. O HTML é **gerado**, nunca escrito à mão: são
dezenas de participações e nenhum nome ou e-mail deve passar por transcrição.

O que o parser resolve, e por isso não pode ser simplificado:

- **Limpar filtros antes de exportar** — a exportação respeita o que está filtrado na tela.
- **O nome vem picado.** Nas notas o padrão é nome antes do e-mail, às vezes quebrado em
  duas ou três linhas ("Ronaldo" / "Bezerra De Araujo" / e-mail). A regra é acumular linhas
  até aparecer um e-mail; o acumulado é o nome daquele e-mail.
- **Texto colado no e-mail.** Existe `natanael.silva@sinerggia.com.brLINK DO VIDEOhttps://...`
  sem separador. A regex de e-mail engole o rabo e cria uma pessoa fantasma — `limpar_email`
  corta no fim plausível do domínio e joga a sobra em observação.
- **Presença não é escalação.** Quem estava escalado e não compareceu leva um marcador
  solto na própria nota, ao lado do nome: `Maria Cristina Gomes De Melo (Não participou)`.
  `RE_AUSENTE` aceita *não participou / não compareceu / não veio / não assistiu / faltou /
  ausente*, em qualquer linha do bloco da pessoa — o nome vem picado, então não existe
  posição única esperada. Uma seção `Não compareceram:` também funciona.
  Consequência: **"Realizado" significa compareceu**, e o percentual da pessoa é
  presença ÷ escalação. `feitos` / `ausentes` / `faltam` são três estados, não dois.
  Não inclua *não foi* nem *não estava* no marcador: casam com observação comum
  ("não foi enviado o link") e marcariam falta que ninguém escreveu.
- **`Cronograma de Treinamentos` não é turma** — é tarefa de controle, sem tema nem
  participantes. Fica fora da contagem.
- **Recorte é `Empresa = Sankhya`**, não "Sankhya no título". Existem os dois casos:
  "Sankhya - Usuário de acesso" está lançado como empresa Qdelícia e fica de fora.

## Convenções

- Comentário no código explica **por que**, não o que — e vale escrever quando a razão não
  é óbvia (o porquê do `position:fixed` num menu, o porquê do blur em vez do change).
- Mensagem de commit em português, descrevendo o efeito para quem usa.
- Nada de refatoração de arrasto: o arquivo é único e grande, mudança cirúrgica é o que
  mantém o diff legível.
