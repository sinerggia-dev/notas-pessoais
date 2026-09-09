# -*- coding: utf-8 -*-
"""Gera o relatorio HTML a partir do dados.json do parse_roadmap.py.

O HTML sai daqui, e nao escrito a mao, para nenhum nome ou e-mail passar por
transcricao: sao dezenas de participacoes.

Uso: python gerar_relatorio.py [dados.json] [relatorio.html]"""
import json, io, html, re, sys, os
from datetime import date

ENTRADA = sys.argv[1] if len(sys.argv) > 1 else "dados.json"
SAIDA = sys.argv[2] if len(sys.argv) > 2 else "relatorio.html"
if not os.path.exists(ENTRADA):
    print("Nao achei", ENTRADA, "- rode antes o parse_roadmap.py")
    print("Uso: python gerar_relatorio.py [dados.json] [relatorio.html]")
    sys.exit(1)
d = json.load(io.open(ENTRADA, encoding="utf-8"))

def e(x): return html.escape(str(x or ""))

import unicodedata
def norm(txt):
    """Texto de busca: sem acento, minusculo. Vai no atributo data-busca para o
    filtro no navegador nao precisar normalizar 18 blocos a cada tecla."""
    sem = unicodedata.normalize("NFD", str(txt or ""))
    sem = "".join(c for c in sem if unicodedata.category(c) != "Mn")
    return " ".join(sem.lower().split())

def chave_busca(t):
    """Tudo pelo que uma turma pode ser encontrada: titulo, tema e as pessoas."""
    partes = [t["tarefa"]] + t["tema"]
    for pa in t["participantes"]:
        partes += [pa["nome"], pa["email"]]
    return norm(" ".join(partes))

itens = d["sankhya"]
# "Cronograma de Treinamentos" e tarefa de controle: sem tema e sem participante.
treinos = [i for i in itens if i["participantes"] or i["tema"]]
controle = [i for i in itens if i not in treinos]
conc = [i for i in treinos if i["status"] == "Concluído"]
pend = [i for i in treinos if i["status"] == "Pendente"]

def dt(v):
    if not v: return None
    dd, mm, yy = v.split("/")
    return (int(yy), int(mm), int(dd))

conc.sort(key=lambda i: dt(i["vencimento"]) or (0, 0, 0))
pend.sort(key=lambda i: (0, dt(i["vencimento"])) if i["vencimento"] else (1, (0, 0, 0)))

vagas_c = sum(len(i["participantes"]) for i in conc)
vagas_p = sum(len(i["participantes"]) for i in pend)
sem_data = [i for i in pend if not i["vencimento"]]

# Ordem unica para todo o relatorio: realizado do mais antigo ao mais recente,
# depois o que falta (com data primeiro, sem data no fim). As listas por pessoa
# seguiam a ordem da exportacao, que vinha decrescente.
cronologia = conc + pend

pessoas = {}
for i in cronologia:
    for p in i["participantes"]:
        r = pessoas.setdefault(p["email"], {"nome": p["nome"], "feitos": [], "faltam": []})
        (r["feitos"] if i["status"] == "Concluído" else r["faltam"]).append(i)
for r in pessoas.values():
    r["c"], r["p"] = len(r["feitos"]), len(r["faltam"])
    r["tot"] = r["c"] + r["p"]
    r["pct"] = round(100 * r["c"] / r["tot"]) if r["tot"] else 0
# Mais adiantados primeiro; empate pelo tamanho da trilha, depois nome.
ordem = sorted(pessoas.items(), key=lambda x: (-x[1]["pct"], -x[1]["tot"], x[1]["nome"]))
max_total = max(v["tot"] for _, v in ordem)

def pc(parte, todo):
    return ("%d%%" % round(100 * parte / todo)) if todo else "—"

pct_trilha = pc(len(conc), len(treinos))
pct_vagas = pc(vagas_c, vagas_c + vagas_p)
pct_falta_trilha = pc(len(pend), len(treinos))
pct_falta_vagas = pc(vagas_p, vagas_c + vagas_p)

def limpar_tema(linhas):
    """Tira o titulo repetido e junta o resto como topicos."""
    fora = []
    for l in linhas:
        if re.match(r"^treinamento sankhya", l, re.I):   # repete o titulo da tarefa
            continue
        fora.append(l)
    return fora

def titulo_curto(t):
    t = re.sub(r"^Treinamento(\s+Sankhya)?\s*[-–]?\s*", "", t).strip()
    t = re.sub(r"\s*[-–]\s*(segunda|ter[çc]a|quarta|quinta|sexta)-feira.*$", "", t, flags=re.I)
    t = re.sub(r"\s*[-–]\s*(Ter[çc]a|Quinta|Sexta),.*$", "", t, flags=re.I)
    # "Treinamento Especifico -" deixava um "Especifico -" orfao no comeco.
    t = re.sub(r"^Espec[íi]fico\s*[-–]\s*", "", t, flags=re.I)
    # Faixa de horario sai do titulo: a coluna da data ja diz quando foi.
    t = re.sub(r"\s*\d{1,2}:\d{2}\s*[-–until até]*\s*\d{1,2}:\d{2}.*$", "", t, flags=re.I)
    return t.strip(" -–·:") or t

def data_longa(v):
    if not v: return ""
    dd, mm, yy = v.split("/")
    meses = ["", "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    return "%s %s" % (dd, meses[int(mm)])

def roster(parts):
    if not parts: return ""
    li = "".join(
        '<li><span class="pnome">%s</span><span class="pmail">%s</span></li>' % (e(p["nome"]), e(p["email"]))
        for p in parts)
    return '<ul class="roster">%s</ul>' % li

def temas(linhas):
    if not linhas: return ""
    return '<ul class="temas">%s</ul>' % "".join("<li>%s</li>" % e(l) for l in linhas)

def obs(linhas):
    if not linhas: return ""
    return '<p class="obs">%s</p>' % e(" ".join(linhas))

# ---------------------------------------------------------------- concluidos
blocos_c = []
for i in conc:
    blocos_c.append("""
      <article class="reg" data-busca="%s">
        <div class="reg-data"><time>%s</time><span>2026</span></div>
        <div class="reg-corpo">
          <h3>%s</h3>
          %s
          <div class="reg-pes"><span class="rot">%d participantes</span>%s</div>
          %s
        </div>
      </article>""" % (
        chave_busca(i), e(data_longa(i["vencimento"])), e(titulo_curto(i["tarefa"])),
        temas(limpar_tema(i["tema"])), len(i["participantes"]),
        roster(i["participantes"]), obs(i["observacoes"])))

# ---------------------------------------------------------------- pendentes
blocos_p = []
for i in pend:
    marca = ('<span class="chip chip-data">%s</span>' % e(i["vencimento"])) if i["vencimento"] \
            else '<span class="chip chip-vazio">sem data</span>'
    blocos_p.append("""
      <article class="card" data-busca="%s">
        <header><h3>%s</h3>%s</header>
        %s
        <div class="reg-pes"><span class="rot">%d participantes</span>%s</div>
        %s
      </article>""" % (
        chave_busca(i), e(titulo_curto(i["tarefa"])), marca, temas(limpar_tema(i["tema"])),
        len(i["participantes"]), roster(i["participantes"]), obs(i["observacoes"])))

# ---------------------------------------------------------------- pessoas
def lista_tarefas(itens_, classe):
    if not itens_:
        return '<p class="nada">—</p>'
    li = "".join(
        '<li><span class="tit">%s</span><span class="quando%s">%s</span></li>' % (
            e(titulo_curto(t["tarefa"])),
            "" if t["vencimento"] else " sem",
            e(t["vencimento"]) if t["vencimento"] else "sem data")
        for t in itens_)
    return '<ul class="tarefas %s">%s</ul>' % (classe, li)

blocos_pes = []
for email, v in ordem:
    blocos_pes.append("""
      <article class="pes" data-busca="%s">
        <header class="pes-topo">
          <h3>%s</h3>
          <span class="pmail">%s</span>
          <span class="pes-vao"></span>
          <span class="pct">%d%%</span>
          <span class="frac">%d de %d</span>
          <div class="barra" role="img" aria-label="%d de %d realizados">
            <span class="b-c" style="flex:%d"></span><span class="b-p" style="flex:%d"></span>
            <span class="b-vazio" style="flex:%d"></span>
          </div>
        </header>
        <div class="pes-listas">
          <div class="col">
            <span class="rot rot-c">✓ Realizado · %d</span>
            %s
          </div>
          <div class="col">
            <span class="rot rot-p">○ A realizar · %d</span>
            %s
          </div>
        </div>
      </article>""" % (
        norm(v["nome"] + " " + email), e(v["nome"]), e(email),
        v["pct"], v["c"], v["tot"], v["c"], v["tot"],
        v["c"], v["p"], max(0, max_total - v["tot"]),
        v["c"], lista_tarefas(v["feitos"], "feito"),
        v["p"], lista_tarefas(v["faltam"], "falta")))

opcoes_nomes = "".join('<option value="%s"></option>' % e(v["nome"]) for _, v in ordem)

hoje = date.today().strftime("%d/%m/%Y")

HTML = """<title>Trilha Sankhya na Qdelícia</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,500;6..72,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
  :root{
    --paper:#faf9f4; --surface:#ffffff; --sunk:#f2f1e8;
    --ink:#1c211c; --ink-2:#3c4239; --muted:#6d7264;
    --rule:#e3e2d5;
    --accent:#2c6049;
    --warn:#9a6a15; --warn-fraco:#f6ecd8;
    --sombra:0 1px 2px rgba(28,33,28,.06), 0 8px 24px rgba(28,33,28,.05);
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]){
      --paper:#151814; --surface:#1c201b; --sunk:#232720;
      --ink:#eceee6; --ink-2:#c6cabc; --muted:#8f9486;
      --rule:#333829;
      --accent:#7fc39f;
      --warn:#d8a24a; --warn-fraco:#33291a;
      --sombra:0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.35);
    }
  }
  :root[data-theme="dark"]{
    --paper:#151814; --surface:#1c201b; --sunk:#232720;
    --ink:#eceee6; --ink-2:#c6cabc; --muted:#8f9486;
    --rule:#333829;
    --accent:#7fc39f;
    --warn:#d8a24a; --warn-fraco:#33291a;
    --sombra:0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.35);
  }

  *{box-sizing:border-box}
  body{
    background:var(--paper); color:var(--ink);
    font-family:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    font-size:15.5px; line-height:1.62; margin:0;
    -webkit-font-smoothing:antialiased;
  }
  .doc{max-width:1000px;margin:0 auto;padding:56px 28px 96px;}
  .prosa{max-width:66ch}

  h1,h2,h3{font-family:Newsreader,Georgia,serif;font-weight:600;text-wrap:balance;margin:0}
  h1{font-size:clamp(32px,4.6vw,46px);line-height:1.08;letter-spacing:-.015em}
  h2{font-size:25px;line-height:1.2}
  h3{font-size:18.5px;line-height:1.3}
  p{margin:0}
  .mono,.pmail,.num,time{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}

  /* ---------- capa ---------- */
  .capa{border-bottom:2px solid var(--ink);padding-bottom:26px}
  .eyebrow{
    font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);
    font-weight:600;margin-bottom:14px
  }
  .capa p.sub{margin-top:14px;color:var(--ink-2);font-size:17px;max-width:62ch}
  .fonte{margin-top:20px;font-size:12.5px;color:var(--muted);display:flex;flex-wrap:wrap;gap:6px 20px}

  /* ---------- painel ---------- */
  .painel{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;
    background:var(--rule);border:1px solid var(--rule);margin:34px 0 0}
  .cel{background:var(--surface);padding:16px 18px}
  .cel .v{font-family:"IBM Plex Mono",monospace;font-size:30px;font-weight:500;line-height:1.1;
    font-variant-numeric:tabular-nums;display:block}
  .cel .r{font-size:12px;color:var(--muted);margin-top:5px;display:block;line-height:1.4}
  .cel .r b{color:var(--ink-2);font-weight:500;font-family:"IBM Plex Mono",monospace;font-size:11.5px}
  .cel.destaque .v{color:var(--warn)}
  .cel.bom .v{color:var(--accent)}

  section{margin-top:52px}
  .cab-sec{display:flex;align-items:baseline;gap:14px;border-bottom:1px solid var(--rule);
    padding-bottom:10px;margin-bottom:8px;flex-wrap:wrap}
  .cab-sec .conta{font-family:"IBM Plex Mono",monospace;font-size:12.5px;color:var(--muted)}
  .nota-sec{color:var(--ink-2);font-size:14.5px;margin:14px 0 26px;max-width:64ch}

  /* ---------- razao cronologica (concluidos) ---------- */
  .reg{display:grid;grid-template-columns:82px 1fr;gap:20px;padding:22px 0;
    border-bottom:1px solid var(--rule)}
  .reg-data{text-align:right;padding-top:2px}
  .reg-data time{display:block;font-size:15px;font-weight:500;color:var(--accent);white-space:nowrap}
  .reg-data span{display:block;font-size:11.5px;color:var(--muted);font-family:"IBM Plex Mono",monospace}
  .reg-corpo{min-width:0}

  .temas{margin:8px 0 0;padding:0;list-style:none;display:flex;flex-wrap:wrap;gap:6px}
  .temas li{font-size:12.5px;color:var(--ink-2);background:var(--sunk);
    border-radius:3px;padding:3px 9px;line-height:1.45}

  .reg-pes{margin-top:14px}
  .rot{display:block;font-size:11px;letter-spacing:.1em;text-transform:uppercase;
    color:var(--muted);font-weight:600;margin-bottom:8px}
  .roster{margin:0;padding:0;list-style:none;display:grid;
    grid-template-columns:repeat(auto-fit,minmax(255px,1fr));gap:2px 22px}
  .roster li{display:flex;flex-direction:column;padding:4px 0;border-top:1px solid var(--rule);min-width:0}
  .pnome{font-size:14px;font-weight:500}
  .pmail{font-size:11.5px;color:var(--muted);overflow-wrap:anywhere}
  .obs{margin-top:12px;font-size:13px;color:var(--ink-2);border-left:2px solid var(--warn);
    padding-left:12px;overflow-wrap:anywhere}

  /* ---------- pendentes ---------- */
  .grade{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}
  .card{background:var(--surface);border:1px solid var(--rule);border-radius:6px;
    padding:18px 20px 20px;box-shadow:var(--sombra)}
  .card header{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:2px}
  .chip{font-family:"IBM Plex Mono",monospace;font-size:11px;padding:3px 8px;border-radius:3px;
    white-space:nowrap;font-weight:500;flex:0 0 auto}
  .chip-data{background:var(--warn-fraco);color:var(--warn)}
  .chip-vazio{background:var(--sunk);color:var(--muted)}
  .card .roster{grid-template-columns:1fr}

  .barra{display:flex;height:9px;border-radius:2px;overflow:hidden;background:var(--sunk);margin-top:5px}

  /* ---------- pessoa: numeros + as tarefas dela ---------- */
  .pes{padding:20px 0;border-bottom:1px solid var(--rule)}
  /* Nome, e-mail e numeros ocupam a linha inteira: numa coluna estreita o nome
     quebrava em duas linhas e o e-mail partia no meio da palavra. */
  .pes-topo{display:flex;align-items:baseline;gap:4px 14px;flex-wrap:wrap;margin-bottom:14px}
  .pes-topo h3{font-size:16.5px;white-space:nowrap}
  .pes-topo .pmail{white-space:nowrap;overflow-wrap:normal}
  .pes-vao{flex:1 1 auto}
  .pes-topo .pct{font-family:"IBM Plex Mono",monospace;font-size:22px;font-weight:500;
    line-height:1;font-variant-numeric:tabular-nums;white-space:nowrap}
  .pes-topo .frac{font-size:11.5px;color:var(--muted);font-family:"IBM Plex Mono",monospace;
    white-space:nowrap}
  .pes-topo .barra{width:110px;margin-top:0;flex:0 0 auto;align-self:center}
  .pes-listas{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:8px 24px;min-width:0}
  .col{min-width:0}
  .rot-c{color:var(--accent)} .rot-p{color:var(--warn)}
  .tarefas{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:3px}
  .tarefas li{font-size:13.2px;line-height:1.4;padding-left:14px;position:relative;
    display:flex;justify-content:space-between;gap:10px}
  .tarefas li::before{content:"";position:absolute;left:0;top:.52em;width:6px;height:6px;
    border-radius:50%;flex:0 0 auto}
  .tarefas.feito li::before{background:var(--accent)}
  .tarefas.falta li::before{background:var(--warn)}
  .tarefas .tit{min-width:0}
  .tarefas .quando{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--muted);
    white-space:nowrap;flex:0 0 auto}
  .tarefas .quando.sem{font-style:italic;color:var(--warn);opacity:.8}
  .nada{font-size:13px;color:var(--muted)}
  .b-c{background:var(--accent)} .b-p{background:var(--warn)} .b-vazio{background:transparent}
  .legenda{display:flex;gap:18px;flex-wrap:wrap;margin-top:14px;font-size:12.5px;color:var(--muted)}
  .legenda span{display:flex;align-items:center;gap:7px}
  .quad{width:10px;height:10px;border-radius:2px;flex:0 0 auto}

  /* ---------- busca por funcionario ---------- */
  .busca{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 26px;
    padding:14px 16px;background:var(--surface);border:1px solid var(--rule);border-radius:6px}
  .busca-rot{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
    font-weight:600;flex:0 0 auto}
  #buscaFunc{flex:1 1 220px;min-width:0;height:36px;padding:0 12px;font-size:14.5px;
    font-family:inherit;color:var(--ink);background:var(--paper);
    border:1px solid var(--rule);border-radius:5px}
  #buscaFunc:focus{outline:2px solid var(--accent);outline-offset:1px;border-color:var(--accent)}
  #buscaFunc::placeholder{color:var(--muted)}
  #limparBusca{height:36px;padding:0 14px;font-size:13px;font-family:inherit;cursor:pointer;
    color:var(--ink);background:var(--sunk);border:1px solid var(--rule);border-radius:5px}
  #limparBusca:hover{border-color:var(--accent);color:var(--accent)}
  #limparBusca:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
  .busca-status{flex:1 1 100%;font-size:12.5px;color:var(--muted);
    font-family:"IBM Plex Mono",monospace}
  .busca-status:empty{display:none}
  .vazio-busca{font-size:14px;color:var(--muted);padding:18px 0;font-style:italic}
  [hidden]{display:none !important}

  /* ---------- achados ---------- */
  .achados{display:grid;gap:2px;margin-top:22px}
  .achado{background:var(--surface);border:1px solid var(--rule);padding:16px 18px}
  .achado h3{font-size:16px;margin-bottom:5px}
  .achado p{font-size:14px;color:var(--ink-2);max-width:70ch}
  .achado.grave{border-left:3px solid var(--warn)}

  footer{margin-top:56px;padding-top:20px;border-top:1px solid var(--rule);
    font-size:12.5px;color:var(--muted);max-width:70ch}
  a{color:var(--accent)}
  @media (max-width:560px){
    .doc{padding:36px 18px 72px}
    .reg{grid-template-columns:1fr;gap:8px}
    .reg-data{text-align:left;display:flex;gap:8px;align-items:baseline}
    .pes-topo h3{white-space:normal}
    .pes-topo .pmail{white-space:normal;overflow-wrap:anywhere}
  }
  @media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style>

<div class="doc">

  <header class="capa">
    <div class="eyebrow">Implantação Sankhya · Qdelícia Frutas</div>
    <h1>Trilha Sankhya na Qdelícia</h1>
    <p class="sub">Situação de cada treinamento da trilha, com tema e participantes lidos das
      notas do ROADMAP. Seis turmas aconteceram entre 20 de agosto e 4 de setembro; treze
      seguem pendentes, e doze delas ainda não têm data.</p>
    <div class="fonte">
      <span>Fonte: ROADMAP · empresa Sankhya · __TREINOS__ turmas</span>
      <span>Extraído em __HOJE__</span>
    </div>
  </header>

  <div class="painel">
    <div class="cel bom"><span class="v">__PCT_T__</span>
      <span class="r">da trilha realizada<br><b>__NC__ de __TREINOS__</b> treinamentos</span></div>
    <div class="cel destaque"><span class="v">__PCT_FT__</span>
      <span class="r">a realizar<br><b>__NP__</b> pendentes</span></div>
    <div class="cel bom"><span class="v">__PCT_V__</span>
      <span class="r">das participações realizadas<br><b>__VC__ de __VT__</b> lugares em turma</span></div>
    <div class="cel destaque"><span class="v">__PCT_FV__</span>
      <span class="r">das participações a realizar<br><b>__VP__</b> lugares</span></div>
    <div class="cel destaque"><span class="v">__NSD__</span>
      <span class="r">pendentes <b>sem data</b> marcada<br>de __NP__</span></div>
    <div class="cel"><span class="v">__NPE__</span>
      <span class="r">pessoas na trilha</span></div>
  </div>

  <section>
    <div class="cab-sec"><h2>Participação por pessoa</h2><span class="conta">__NPE__ pessoas · __VT__ participações · __PCT_V__ realizadas</span></div>
    <p class="nota-sec">Cada pessoa com o que já realizou e o que ainda tem a realizar, em ordem
      cronológica: da turma mais antiga para a mais recente, e por último as que ainda
      não têm data. O percentual é sobre a trilha dela, não sobre a trilha inteira — quem foi
      escalado para duas turmas e fez uma está em 50%. Da mais adiantada para a menos adiantada.</p>
    <div class="busca">
      <label class="busca-rot" for="buscaFunc">Buscar funcionário</label>
      <input id="buscaFunc" type="search" list="nomesFunc" autocomplete="off"
             placeholder="Digite um nome, ex.: Ronaldo">
      <datalist id="nomesFunc">__OPCOES__</datalist>
      <button type="button" id="limparBusca" hidden>Limpar</button>
      <p id="statusBusca" class="busca-status" role="status" aria-live="polite"></p>
    </div>
    <div id="listaPessoas">
      __PESSOAS__
      <p class="vazio-busca" id="vazioPessoas" hidden>Nenhum funcionário com esse nome.</p>
    </div>
    <div class="legenda">
      <span><i class="quad" style="background:var(--accent)"></i>realizado</span>
      <span><i class="quad" style="background:var(--warn)"></i>a realizar</span>
    </div>
  </section>

  <section>
    <div class="cab-sec"><h2>Turmas realizadas</h2><span class="conta">__NC__ turmas · da mais antiga à mais recente · 20 ago – 4 set 2026</span></div>
    <p class="nota-sec">Em ordem de realização. As seis turmas couberam em dezesseis dias — um ritmo
      que a fase pendente não repete, porque quase nada ali está agendado.</p>
    <div id="listaRealizadas">
      __CONC__
      <p class="vazio-busca" id="vazioRealizadas" hidden>Nenhuma turma realizada com esse funcionário.</p>
    </div>
  </section>

  <section>
    <div class="cab-sec"><h2>Turmas a realizar</h2><span class="conta">__NP__ treinamentos · __VP__ participações</span></div>
    <p class="nota-sec">Um único pendente tem data: <strong>Configurações, Cadastros e Controle de
      Acessos</strong>, em 15/09/2026. Os outros __NSD__ estão sem vencimento, então não entram em
      nenhum alerta de prazo e não aparecem no filtro de vencimento do ROADMAP.</p>
    <div class="grade" id="listaPendentes">__PEND__</div>
    <p class="vazio-busca" id="vazioPendentes" hidden>Nenhuma turma a realizar com esse funcionário.</p>
  </section>

  <section>
    <div class="cab-sec"><h2>Achados</h2></div>
    <div class="achados">
      <div class="achado grave">
        <h3>O gargalo é agendamento, não conteúdo</h3>
        <p>A trilha está em <strong>__PCT_T__</strong> concluída e os treze pendentes já têm tema
          definido e turma montada — falta marcar data. Doze deles sem vencimento significam
          <strong>__VPSD__ participações</strong> que nenhum alerta vai cobrar, porque tarefa sem
          vencimento não entra em filtro de prazo nem no e-mail diário.</p>
      </div>
      <div class="achado grave">
        <h3>Natanael está em todas as turmas</h3>
        <p>Seis concluídas e doze pendentes, mais a tarefa de cronograma. É um ponto único de
          dependência: qualquer indisponibilidade dele para a trilha inteira.</p>
      </div>
      <div class="achado">
        <h3>Duas gravações registradas, uma em dúvida</h3>
        <p>Cotação e Navegando com Maestria (Turma 01) têm link do Drive na nota. A nota da Turma 02
          diz “gravação não solicitado mas não realizada” — a frase se contradiz e vale confirmar
          se existe ou não o vídeo.</p>
      </div>
      <div class="achado">
        <h3>Emendas nas notas atrapalham a leitura</h3>
        <p>Faltam quebras de linha em alguns temas: “Inventário básicoRequisição interna”,
          “Distribuição básicoAcerto de ordem de carga”, e um link de vídeo colado no fim de um
          e-mail. Reproduzi como está gravado, sem corrigir o dado.</p>
      </div>
    </div>
  </section>

  <footer>
    Montado a partir da exportação do ROADMAP de __HOJE__, coluna NOTA. Nomes e e-mails vieram das
    notas exatamente como estão lá; nas notas o nome aparece antes do e-mail, às vezes quebrado em
    duas linhas, e a leitura respeitou essa ordem. Contagem de participações soma pessoa por turma,
    então uma pessoa em seis turmas conta seis vezes.
  </footer>

</div>

<script>
(function () {
  var campo = document.getElementById('buscaFunc');
  var limpar = document.getElementById('limparBusca');
  var status = document.getElementById('statusBusca');
  if (!campo) return;

  // Uma busca move as tres listas: a pessoa, as turmas que ela ja fez e as que faltam.
  var grupos = [
    { sel: '#listaPessoas > .pes',      vazio: 'vazioPessoas',    um: 'funcionário',        vv: 'funcionários' },
    { sel: '#listaRealizadas > .reg',   vazio: 'vazioRealizadas', um: 'turma realizada',    vv: 'turmas realizadas' },
    { sel: '#listaPendentes > .card',   vazio: 'vazioPendentes',  um: 'turma a realizar',   vv: 'turmas a realizar' }
  ];

  function limpaAcento(t) {
    return t.normalize('NFD').replace(/[^\\x00-\\x7F]/g, '').toLowerCase().trim();
  }

  function filtrar() {
    var termos = limpaAcento(campo.value).split(/\\s+/).filter(Boolean);
    var resumo = [];

    grupos.forEach(function (g) {
      var itens = document.querySelectorAll(g.sel);
      var achados = 0;
      Array.prototype.forEach.call(itens, function (el) {
        var alvo = el.getAttribute('data-busca') || '';
        var bate = termos.every(function (t) { return alvo.indexOf(t) !== -1; });
        el.hidden = !bate;
        if (bate) achados++;
      });
      var aviso = document.getElementById(g.vazio);
      if (aviso) aviso.hidden = achados > 0 || termos.length === 0;
      resumo.push(achados + ' ' + (achados === 1 ? g.um : g.vv));
    });

    status.textContent = termos.length ? 'Mostrando ' + resumo.join('  ·  ') : '';
    limpar.hidden = termos.length === 0;
  }

  campo.addEventListener('input', filtrar);
  campo.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape') { campo.value = ''; filtrar(); }
  });
  limpar.addEventListener('click', function () { campo.value = ''; filtrar(); campo.focus(); });
})();
</script>
"""

subs = {
    "__TOT__": len(itens), "__HOJE__": hoje,
    "__NC__": len(conc), "__NP__": len(pend), "__NSD__": len(sem_data),
    "__NPE__": len(pessoas), "__VC__": vagas_c, "__VP__": vagas_p,
    "__VT__": vagas_c + vagas_p,
    "__VPSD__": sum(len(i["participantes"]) for i in sem_data),
    "__CONC__": "".join(blocos_c), "__PEND__": "".join(blocos_p),
    "__PESSOAS__": "".join(blocos_pes), "__OPCOES__": opcoes_nomes,
    "__TREINOS__": len(treinos),
    "__PCT_T__": pct_trilha, "__PCT_FT__": pct_falta_trilha,
    "__PCT_V__": pct_vagas, "__PCT_FV__": pct_falta_vagas,
}
for k, v in subs.items():
    HTML = HTML.replace(k, str(v))

io.open(SAIDA, "w", encoding="utf-8", newline="").write(HTML)
print("gerado. concluidos=%d pendentes=%d sem_data=%d pessoas=%d vagas=%d/%d"
      % (len(conc), len(pend), len(sem_data), len(pessoas), vagas_c, vagas_p))
print("placeholders restantes:", re.findall(r"__[A-Z]+__", HTML) or "nenhum")
