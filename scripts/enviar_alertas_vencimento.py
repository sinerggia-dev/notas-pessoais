# -*- coding: utf-8 -*-
"""
Envia alertas (e-mail + WhatsApp) de tarefas com vencimento proximo (hoje, amanha
ou em 2 dias), lendo os dados do app "Notas Pessoais" direto do OneDrive do dono
via Microsoft Graph (client credentials / app-only — roda sozinho, sem login).

Requer a variavel de ambiente AZURE_CLIENT_SECRET (segredo do App Registration
"Gestao Financeira Claude", reaproveitado do CAP). Nao roda localmente sem isso
definido no ambiente — pensado para rodar via GitHub Actions (secret do repositorio).

Permissoes de aplicativo necessarias no App Registration (com consentimento de
administrador ja concedido): Files.ReadWrite.All, Mail.Send.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

TENANT_ID = "0ea62e2f-152a-4380-bf4b-497083aa0326"
CLIENT_ID = "9291254e-8c79-4641-8d7d-c5771d82ccde"
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
OWNER_UPN = "natanael.silva@sinerggia.com.br"
FOLDER_NAME = "Notas Pessoais - Dados"

JANELAS = {0: "vence hoje", 1: "vence amanhã", 2: "vence em 2 dias"}


def get_token():
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))["access_token"]


def graph_request(token, method, url, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def get_json_by_path(token, folder_id, filename):
    encoded = urllib.parse.quote(filename)
    url = f"https://graph.microsoft.com/v1.0/users/{OWNER_UPN}/drive/items/{folder_id}:/{encoded}:/content"
    status, body = graph_request(token, "GET", url)
    if status == 404:
        return None
    if status >= 300:
        raise RuntimeError(f"Erro ao ler {filename}: {status} {body!r}")
    return json.loads(body) if body else None


def montar_contatos(usuarios_doc):
    contatos = {}
    dono_contato = usuarios_doc.get("donoContato") or {}
    contatos[OWNER_UPN.lower()] = {
        "telefone": dono_contato.get("telefone", ""),
        "apikey": dono_contato.get("whatsappApiKey", ""),
    }
    for u in usuarios_doc.get("usuarios", []):
        email = (u.get("email") or "").strip().lower()
        if not email:
            continue
        contatos[email] = {
            "telefone": u.get("telefone", ""),
            "apikey": u.get("whatsappApiKey", ""),
        }
    return contatos


def extrair_responsaveis(tarefa):
    """Responsaveis da tarefa, sem repeticao e em minusculas.

    O app grava a lista em "assignees". Tarefas antigas tem so "assignee" (um
    e-mail), e esse formato continua sendo aceito.
    """
    brutos = tarefa.get("assignees")
    if not isinstance(brutos, list):
        brutos = []
    if not brutos and tarefa.get("assignee"):
        brutos = [tarefa.get("assignee")]

    pessoas = []
    for item in brutos:
        email = (item or "").strip().lower()
        if email and email not in pessoas:
            pessoas.append(email)
    return pessoas


def coletar_tarefas_por_pessoa(token, folder_id, indice):
    hoje = date.today()
    por_pessoa = {}

    for page in indice.get("pages", []):
        if page.get("kind") != "tarefas":
            continue
        conteudo = get_json_by_path(token, folder_id, f"pagina_{page['id']}.json") or {"tasks": []}
        for tarefa in conteudo.get("tasks", []):
            # Concluida ou cancelada nao gera alerta de vencimento.
            if tarefa.get("status") in ("Concluído", "Cancelado"):
                continue
            due = tarefa.get("dueDate")
            pessoas = extrair_responsaveis(tarefa)
            if not due or not pessoas:
                continue
            try:
                due_date = date.fromisoformat(due)
            except ValueError:
                continue
            dias = (due_date - hoje).days
            if dias not in JANELAS:
                continue
            # Uma atividade pode ter varios responsaveis: todos recebem o alerta.
            for pessoa in pessoas:
                por_pessoa.setdefault(pessoa, []).append({
                    "titulo": tarefa.get("title") or "Sem título",
                    "pagina": page.get("title") or "Sem título",
                    "rotulo": JANELAS[dias],
                })

    return por_pessoa


def enviar_email(token, destinatario, texto):
    payload = {
        "message": {
            "subject": "Notas Pessoais — Tarefas com vencimento próximo",
            "body": {"contentType": "Text", "content": texto},
            "toRecipients": [{"emailAddress": {"address": destinatario}}],
        },
        "saveToSentItems": "false",
    }
    status, body = graph_request(
        token, "POST", f"https://graph.microsoft.com/v1.0/users/{OWNER_UPN}/sendMail", payload
    )
    if status >= 300:
        print(f"Falha ao enviar e-mail para {destinatario}: {status} {body!r}")
    else:
        print(f"E-mail enviado para {destinatario}")


def enviar_whatsapp(destinatario, telefone, apikey, texto):
    call_url = (
        "https://api.callmebot.com/whatsapp.php"
        f"?phone={urllib.parse.quote(telefone)}"
        f"&text={urllib.parse.quote(texto)}"
        f"&apikey={urllib.parse.quote(apikey)}"
    )
    try:
        urllib.request.urlopen(call_url, timeout=15)
        print(f"WhatsApp enviado para {destinatario}")
    except Exception as e:
        print(f"Falha ao enviar WhatsApp para {destinatario}: {e}")


def main():
    if not CLIENT_SECRET:
        print("AZURE_CLIENT_SECRET não definido no ambiente — abortando.")
        sys.exit(1)

    token = get_token()

    status, body = graph_request(
        token, "GET",
        f"https://graph.microsoft.com/v1.0/users/{OWNER_UPN}/drive/root:/{urllib.parse.quote(FOLDER_NAME)}"
    )
    if status != 200:
        print(f"Não encontrei a pasta '{FOLDER_NAME}': {status} {body!r}")
        sys.exit(1)
    folder_id = json.loads(body)["id"]

    indice = get_json_by_path(token, folder_id, "_indice.json") or {"pages": []}
    usuarios_doc = get_json_by_path(token, folder_id, "_usuarios.json") or {"usuarios": [], "donoContato": {}}
    contatos = montar_contatos(usuarios_doc)

    por_pessoa = coletar_tarefas_por_pessoa(token, folder_id, indice)

    if not por_pessoa:
        print("Nenhum alerta de vencimento para hoje.")
        return

    for email, itens in por_pessoa.items():
        linhas = [f"- {it['titulo']} ({it['pagina']}) — {it['rotulo']}" for it in itens]
        texto = "Você tem tarefas com vencimento próximo:\n\n" + "\n".join(linhas)

        enviar_email(token, email, texto)

        contato = contatos.get(email)
        if contato and contato.get("telefone") and contato.get("apikey"):
            enviar_whatsapp(email, contato["telefone"], contato["apikey"], texto)


if __name__ == "__main__":
    main()
