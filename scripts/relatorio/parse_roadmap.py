# -*- coding: utf-8 -*-
"""Le a exportacao do ROADMAP e estrutura os treinamentos da empresa Sankhya.

Uso: python parse_roadmap.py [caminho/ROADMAP.xlsx] [saida/dados.json]

Formato da nota, como esta gravado hoje:

    Tema:
    <uma ou mais linhas de tema>
    Participantes:
    <nome, as vezes quebrado em 2-3 linhas>
    <email>
    ...
    <linhas soltas de observacao>

O nome vem picado ("Ronaldo" / "Bezerra De Araujo" / email), entao a regra e:
acumula linhas ate aparecer um e-mail; o acumulado e o nome daquele e-mail.
"""
import openpyxl, io, json, re, sys, os

RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# Em algumas notas o texto seguinte esta colado no e-mail, sem espaco:
#   "natanael.silva@sinerggia.com.brLINK DO VIDEOhttps://..."
# A regex de e-mail engole esse rabo. Isto corta no fim plausivel do dominio.
RE_FIM_DOMINIO = re.compile(
    r"^([\w.+-]+@[\w-]+(?:\.[\w-]+)*?\.(?:com\.br|gov\.br|edu\.br|org\.br|com|net|org|br|io|dev))",
    re.I)


def limpar_email(bruto):
    """Devolve (email, sobra_colada)."""
    m = RE_FIM_DOMINIO.match(bruto)
    if not m:
        return bruto, ""
    return m.group(1), bruto[len(m.group(1)):]
CAB_TEMA = re.compile(r"^tema[s]?\s*:+\s*$", re.I)
CAB_PART = re.compile(r"^participantes\s*:+\s*$", re.I)


def parse_nota(nota):
    tema, participantes, obs = [], [], []
    onde = "inicio"
    acumulado = []
    for linha in [l.strip() for l in (nota or "").split("\n")]:
        if not linha:
            continue
        if CAB_TEMA.match(linha):
            onde = "tema"; continue
        if CAB_PART.match(linha):
            onde = "participantes"; continue

        if onde == "tema":
            tema.append(linha); continue

        if onde == "participantes":
            achados = RE_EMAIL.findall(linha)
            if achados:
                bruto = achados[0]
                email, sobra = limpar_email(bruto)
                # Nome: o que veio antes do e-mail nesta linha, senao o acumulado.
                antes = linha[:linha.index(bruto)].strip(" -–—:\t")
                nome = antes if antes else " ".join(acumulado).strip(" -–—:")
                # Cauda colada no e-mail (ex.: "...com.brLINK DO VIDEOhttps://...")
                depois = (sobra + linha[linha.index(bruto) + len(bruto):]).strip()
                participantes.append({"nome": re.sub(r"\s+", " ", nome), "email": email})
                if depois:
                    obs.append(depois)
                acumulado = []
            else:
                acumulado.append(linha)
        else:
            obs.append(linha)

    # Sobrou texto sem e-mail depois do ultimo participante: e observacao.
    if acumulado:
        obs.extend(acumulado)
    return tema, participantes, obs


def s(v):
    return "" if v is None else str(v).strip()


ENTRADA = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(r"~\Downloads\ROADMAP.xlsx")
SAIDA = sys.argv[2] if len(sys.argv) > 2 else "dados.json"
if not os.path.exists(ENTRADA):
    print("Nao achei a exportacao:", ENTRADA)
    print("Uso: python parse_roadmap.py [ROADMAP.xlsx] [dados.json]")
    sys.exit(1)

wb = openpyxl.load_workbook(ENTRADA, read_only=True)
ws = wb.active
linhas = list(ws.iter_rows(values_only=True))
cab = [str(c) for c in linhas[0]]
regs = [dict(zip(cab, l)) for l in linhas[1:]]

col_resp = next((c for c in cab if c.lower().startswith("respons")), "Responsável")

itens = []
for r in regs:
    if s(r.get("Empresa")).lower() != "sankhya":
        continue
    tema, parts, obs = parse_nota(s(r.get("Nota")))
    itens.append({
        "tarefa": s(r.get("Tarefa")),
        "status": s(r.get("Status")),
        "vencimento": s(r.get("Vencimento")),
        "prioridade": s(r.get("Prioridade")),
        "responsavel": s(r.get(col_resp)),
        "tema": tema,
        "participantes": parts,
        "observacoes": obs,
    })

# Cursos de outras empresas, para a secao final (qualquer status, para poder
# dizer com precisao o que existe fora da Sankhya).
outros = []
for r in regs:
    if s(r.get("Empresa")).lower() == "sankhya":
        continue
    if re.search(r"curso|treinamento|capacita|workshop|palestra", s(r.get("Tarefa")), re.I):
        tema, parts, obs = parse_nota(s(r.get("Nota")))
        outros.append({
            "tarefa": s(r.get("Tarefa")), "empresa": s(r.get("Empresa")),
            "status": s(r.get("Status")), "vencimento": s(r.get("Vencimento")),
            "tema": tema, "participantes": parts, "observacoes": obs,
        })

dados = {"sankhya": itens, "outros": outros}
io.open(SAIDA, "w", encoding="utf-8").write(json.dumps(dados, ensure_ascii=False, indent=1))

# ---- conferencia ----
por_status = {}
for i in itens:
    por_status[i["status"]] = por_status.get(i["status"], 0) + 1
pessoas = {}
for i in itens:
    for p in i["participantes"]:
        pessoas.setdefault(p["email"].lower(), set()).add(p["nome"])

print("Sankhya: %d treinamentos" % len(itens))
print("por status:", por_status)
print("participacoes:", sum(len(i["participantes"]) for i in itens))
print("pessoas distintas (por e-mail):", len(pessoas))
print("sem participante:", [i["tarefa"][:40] for i in itens if not i["participantes"]])
print("sem tema:", [i["tarefa"][:40] for i in itens if not i["tema"]])
print()
print("outros cursos fora da Sankhya:", [(o["tarefa"][:40], o["empresa"], o["status"]) for o in outros])
print()
print("e-mails com mais de uma grafia de nome:")
for e, nomes in pessoas.items():
    if len(nomes) > 1:
        print("  ", e, "->", sorted(nomes))
