import streamlit as st
from sqlalchemy import text
import pandas as pd
from datetime import datetime
import time
import base64
import bcrypt
import requests
import re
import random
import string
import uuid

# --- CONFIGURAÇÕES GERAIS ---
st.set_page_config(page_title="Loja Culligan", layout="wide", page_icon="🎁")

# --- CONEXÃO SQL (NEON) ---
conn = st.connection("postgresql", type="sql")

# --- ROBÔ DE ATUALIZAÇÃO DO BANCO ---
with conn.session as s:
    try:
        s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS valor_ponto FLOAT DEFAULT 0.50;"))
        s.commit()
    except Exception:
        pass 

# --- INICIALIZAÇÃO DA SESSÃO ---
if 'logado' not in st.session_state: st.session_state['logado'] = False
if 'usuario_cod' not in st.session_state: st.session_state['usuario_cod'] = ""
if 'usuario_nome' not in st.session_state: st.session_state['usuario_nome'] = ""
if 'tipo_usuario' not in st.session_state: st.session_state['tipo_usuario'] = "comum"
if 'saldo_atual' not in st.session_state: st.session_state['saldo_atual'] = 0.0
if 'valor_ponto_usuario' not in st.session_state: st.session_state['valor_ponto_usuario'] = 0.50 
if 'admin_mode' not in st.session_state: st.session_state['admin_mode'] = True 

if 'em_verificacao_2fa' not in st.session_state: st.session_state['em_verificacao_2fa'] = False
if 'codigo_2fa_esperado' not in st.session_state: st.session_state['codigo_2fa_esperado'] = ""
if 'dados_usuario_temp' not in st.session_state: st.session_state['dados_usuario_temp'] = {}

# --- CSS DINÂMICO (RESTAURADO E SEGURO) ---
css_comum = """
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;800;900&display=swap');
    
    /* ANIMAÇÃO DE DEGRADÊ */
    @keyframes gradient { 
        0% { background-position: 0% 50%; } 
        50% { background-position: 100% 50%; } 
        100% { background-position: 0% 50%; } 
    }

    /* Remove cabeçalho padrão */
    header[data-testid="stHeader"] { display: none; }
    .block-container { padding-top: 2rem !important; padding-bottom: 1rem !important; }

    /* === BANNER (COM FONTE POPPINS FORÇADA SÓ AQUI) === */
    .header-style { 
        background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); 
        background-size: 400% 400% !important; 
        animation: gradient 10s ease infinite !important; 
        padding: 0 25px; 
        border-radius: 12px; 
        color: white !important; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.1); 
        display: flex; 
        flex-direction: column; 
        justify-content: center; 
        height: 110px !important; 
        margin: 0 !important;
        font-family: 'Poppins', sans-serif !important; /* Aplica Poppins só no banner */
    }
    .header-style h2, .header-style p, .header-style span, .header-style div { 
        color: white !important; 
        font-family: 'Poppins', sans-serif !important;
    }
    .header-style h2 { font-size: 20px !important; font-weight: 700 !important; margin: 0 !important; }
    .header-style p { font-size: 12px !important; line-height: 1.3 !important; opacity: 0.9 !important; margin: 2px 0 0 0 !important; }
    .header-style .saldo-label { font-size: 10px !important; font-weight: 600 !important; }
    .header-style .saldo-valor { font-size: 30px !important; font-weight: 900 !important; text-shadow: 0 2px 4px rgba(0,0,0,0.15); }

    /* === BOTÕES GERAIS === */
    div.stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        width: 100%;
        border: none !important;
        font-family: 'Poppins', sans-serif !important; /* Aplica Poppins nos botões */
    }

    /* === BOTÕES DO CATÁLOGO (ALTURA IGUAL - 48px) === */
    [data-testid="stTabs"] div.stButton > button {
        height: 48px !important;      
        min-height: 48px !important;
        max-height: 48px !important;
        margin-top: auto !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    /* Botão Resgatar (Azul) */
    [data-testid="stTabs"] button[kind="primary"] { 
        background-color: #0066cc !important; 
        color: white !important; 
        border: 1px solid #0066cc !important; 
    }
    [data-testid="stTabs"] button[kind="primary"]:hover { 
        background-color: #0052a3 !important; 
    }
    [data-testid="stTabs"] button[kind="primary"] p { color: white !important; }

    /* Botão Detalhes (Branco) */
    [data-testid="stTabs"] button[kind="secondary"] { 
        background-color: #ffffff !important; 
        color: #003366 !important; 
        border: 1px solid #e0e0e0 !important; 
    }
    [data-testid="stTabs"] button[kind="secondary"]:hover { 
        background-color: #f5f5f5 !important;
    }

    /* === BOTÕES DO HEADER (USUÁRIO COMUM - EMPILHADOS) === */
    div[data-testid="column"] div.stButton > button[kind="secondary"] {
        background-color: #ffffff !important;
        color: #003366 !important;
        border: 2px solid #eef2f6 !important;
        height: 50px !important;
        min-height: 50px !important;
    }

    /* IMAGENS */
    [data-testid="stImage"] img { height: 180px !important; object-fit: contain !important; border-radius: 10px; }

    /* RIFA E CARDS */
    .rifa-card { border: 2px solid #FFD700; background: linear-gradient(to bottom right, #fffdf0, #ffffff); padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .rifa-tag { background-color: #FFD700; color: #000; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 12px; margin-bottom: 10px; display: inline-block; }
    .winner-card { border: 2px solid #28a745; background: linear-gradient(to bottom right, #f0fff4, #ffffff); padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .winner-tag { background-color: #28a745; color: #fff; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 12px; margin-bottom: 10px; display: inline-block; }

    @media only screen and (max-width: 600px) {
        .header-style { height: auto !important; padding: 15px !important; text-align: center !important; }
        div.stButton > button { height: 50px !important; }
    }
"""

if not st.session_state.get('logado', False):
    estilo_especifico = """
    .stApp { 
        background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); 
        background-size: 400% 400% !important; 
        animation: gradient 15s ease infinite !important; 
    }
    [data-testid="stForm"] { background-color: #ffffff; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
    """
else:
    estilo_especifico = ".stApp { background-color: #f4f8fb; }"

st.markdown(f"<style>{css_comum} {estilo_especifico}</style>", unsafe_allow_html=True)

# --- FUNÇÕES BÁSICAS ---
def processar_link_imagem(url):
    url = str(url).strip()
    if "github.com" in url and "/blob/" in url: return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    if "drive.google.com" in url:
        if "id=" in url: return url
        try: file_id = url.split("/")[-2]; return f"https://drive.google.com/uc?export=view&id={file_id}"
        except: return url
    return url

def verificar_senha_hash(senha_digitada, hash_armazenado):
    try:
        if not hash_armazenado.startswith("$2b$"): return senha_digitada == hash_armazenado
        return bcrypt.checkpw(senha_digitada.encode('utf-8'), hash_armazenado.encode('utf-8'))
    except Exception: return False

def gerar_hash(senha):
    return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def gerar_senha_aleatoria(tamanho=6):
    caracteres = string.ascii_uppercase + string.digits
    return ''.join(random.choice(caracteres) for _ in range(tamanho))

def formatar_telefone(tel):
    apenas_numeros = re.sub(r'\D', '', str(tel))
    if 10 <= len(apenas_numeros) <= 11: apenas_numeros = "55" + apenas_numeros
    return apenas_numeros

# --- GERENCIAMENTO DE SESSÃO ---
def criar_sessao_persistente(usuario_id):
    token = str(uuid.uuid4())
    with conn.session as s:
        s.execute(text("UPDATE usuarios SET token_sessao = :t WHERE id = :id"), {"t": token, "id": usuario_id})
        s.commit()
    st.query_params["sessao"] = token

def verificar_sessao_automatica():
    if st.session_state.get('logado', False): return
    token_url = st.query_params.get("sessao")
    if token_url:
        try:
            df = run_query("SELECT * FROM usuarios WHERE token_sessao = :t", {"t": token_url})
            if not df.empty:
                row = df.iloc[0]
                st.session_state.update({
                    'logado': True,
                    'usuario_cod': row['usuario'],
                    'usuario_nome': row['nome'],
                    'tipo_usuario': str(row['tipo']).lower().strip(),
                    'saldo_atual': float(row['saldo']),
                    'valor_ponto_usuario': float(row.get('valor_ponto', 0.50) or 0.50)
                })
                st.rerun()
        except Exception:
            pass

def realizar_logout():
    if st.session_state.get('usuario_cod'):
        with conn.session as s:
            s.execute(text("UPDATE usuarios SET token_sessao = NULL WHERE usuario = :u"), {"u": st.session_state.usuario_cod})
            s.commit()
    st.query_params.clear()
    st.session_state.clear()
    st.rerun()

# --- FUNÇÕES DE ENVIO ---
def enviar_sms(telefone, mensagem_texto):
    try:
        base_url = st.secrets["INFOBIP_BASE_URL"].rstrip('/')
        api_key = st.secrets["INFOBIP_API_KEY"]
        url = f"{base_url}/sms/2/text/advanced"
        tel_final = formatar_telefone(telefone)
        if len(tel_final) < 12: return False, f"Num Inválido", "400"
        payload = { "messages": [ { "from": "InfoSMS", "destinations": [{"to": tel_final}], "text": mensagem_texto } ] }
        headers = { "Authorization": f"App {api_key}", "Content-Type": "application/json", "Accept": "application/json" }
        response = requests.post(url, json=payload, headers=headers)
        return response.status_code in [200, 201], response.text, str(response.status_code)
    except Exception as e: return False, str(e), "ERR"

def enviar_whatsapp_template(telefone, parametros, nome_template="atualizar_envio_pedidos"):
    try:
        base_url = st.secrets["INFOBIP_BASE_URL"].rstrip('/')
        api_key = st.secrets["INFOBIP_API_KEY"]
        sender = st.secrets["INFOBIP_SENDER"]
        url = f"{base_url}/whatsapp/1/message/template"
        tel_final = formatar_telefone(telefone)
        if len(tel_final) < 12: return False, f"Número inválido: {tel_final}", "CLIENT_ERROR"
        payload = { "messages": [ { "from": sender, "to": tel_final, "content": { "templateName": nome_template, "templateData": { "body": { "placeholders": parametros } }, "language": "pt_BR" } } ] }
        headers = { "Authorization": f"App {api_key}", "Content-Type": "application/json", "Accept": "application/json" }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code not in [200, 201]: return False, f"Erro API {response.status_code}: {response.text}", str(response.status_code)
        return True, "Enviado com Sucesso", str(response.status_code)
    except Exception as e: return False, f"Erro Conexão: {str(e)}", "EXCEPTION"

# --- BANCO DE DADOS ---
def run_query(query_str, params=None): return conn.query(query_str, params=params, ttl=0)
def run_transaction(query_str, params=None):
    with conn.session as s: s.execute(text(query_str), params if params else {}); s.commit()

def registrar_log(acao, detalhes):
    try:
        resp = st.session_state.get('usuario_nome', 'Sistema')
        run_transaction("INSERT INTO logs (data, responsavel, acao, detalhes) VALUES (NOW(), :resp, :acao, :det)", {"resp": resp, "acao": acao, "det": detalhes})
    except Exception as e: print(f"Erro log: {e}")

# --- LÓGICA DE NEGÓCIO ---
def validar_login(user_input, pass_input):
    df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": user_input.strip()})
    if df.empty: return False, None, None, 0, None, None, 0.50
    linha = df.iloc[0]
    if verificar_senha_hash(pass_input.strip(), linha['senha']):
        v_ponto = float(linha.get('valor_ponto', 0.50) or 0.50)
        return True, linha['nome'], str(linha['tipo']).lower().strip(), float(linha['saldo']), str(linha['telefone']), int(linha['id']), v_ponto
    return False, None, None, 0, None, None, 0.50

def salvar_venda(usuario_cod, item_nome, custo, email_contato, telefone_resgate):
    try:
        user_df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario_cod})
        if user_df.empty: return False
        if float(user_df.iloc[0]['saldo']) < custo: st.error("Saldo insuficiente."); return False
        with conn.session as s:
            s.execute(text("UPDATE usuarios SET saldo = saldo - :custo WHERE LOWER(usuario) = LOWER(:u)"), {"custo": custo, "u": usuario_cod})
            s.execute(text("INSERT INTO vendas (data, usuario, item, valor, status, email, nome_real, telefone) VALUES (NOW(), :u, :item, :valor, 'Pendente', :email, :nome, :tel)"),
                {"u": usuario_cod, "item": item_nome, "valor": custo, "email": email_contato, "nome": user_df.iloc[0]['nome'], "tel": telefone_resgate})
            s.commit()
        registrar_log("Resgate", f"Usuário: {user_df.iloc[0]['nome']} | Item: {item_nome}")
        st.session_state['saldo_atual'] -= custo
        return True
    except Exception as e: st.error(f"Erro: {e}"); return False

def comprar_ticket_rifa(rifa_id, custo, usuario_cod):
    try:
        user_df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario_cod})
        if user_df.empty: return False, "Usuário não encontrado"
        custo_real = float(custo)
        if float(user_df.iloc[0]['saldo']) < custo_real: return False, "Saldo insuficiente"
        with conn.session as s:
            s.execute(text("UPDATE usuarios SET saldo = saldo - :custo WHERE LOWER(usuario) = LOWER(:u)"), 
                      {"custo": custo_real, "u": usuario_cod})
            s.execute(text("INSERT INTO rifa_tickets (rifa_id, usuario) VALUES (:rid, :u)"), 
                      {"rid": int(rifa_id), "u": usuario_cod})
            s.commit()
        st.session_state['saldo_atual'] -= custo_real
        registrar_log("Rifa", f"Comprou ticket rifa {rifa_id}")
        return True, "Ticket comprado com sucesso!"
    except Exception as e: return False, f"Erro: {str(e)}"

def cadastrar_novo_usuario(usuario, senha, nome, saldo, tipo, telefone, valor_ponto=0.50):
    try:
        df = run_query("SELECT id FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario})
        if not df.empty: return False, "Usuário já existe!"
        run_transaction("INSERT INTO usuarios (usuario, senha, nome, saldo, pontos_historico, tipo, telefone, valor_ponto) VALUES (:u, :s, :n, :bal, :bal, :t, :tel, :vp)",
            {"u": usuario, "s": gerar_hash(senha), "n": nome, "bal": saldo, "t": tipo, "tel": formatar_telefone(telefone), "vp": valor_ponto})
        registrar_log("Novo Cadastro", f"Criou usuário: {usuario}")
        return True, "Cadastrado com sucesso!"
    except Exception as e: return False, f"Erro: {str(e)}"

def distribuir_pontos_multiplos(lista_usuarios, quantidade):
    try:
        if "Todos" in lista_usuarios:
            run_transaction("UPDATE usuarios SET saldo = saldo + :q, pontos_historico = COALESCE(pontos_historico, 0) + :q WHERE tipo NOT IN ('admin', 'staff')", {"q": quantidade})
            msg = f"Adicionou {quantidade} pts para TODOS."
        else:
            with conn.session as s:
                s.execute(
                    text("UPDATE usuarios SET saldo = saldo + :q, pontos_historico = COALESCE(pontos_historico, 0) + :q WHERE usuario IN :users"),
                    {"q": quantidade, "users": tuple(lista_usuarios)}
                )
                s.commit()
            msg = f"Adicionou {quantidade} pts para {len(lista_usuarios)} usuários."
        registrar_log("Distribuição Pontos", msg)
        return True
    except Exception as e: return False

# --- MODAIS ---
@st.dialog("💾 Confirmação de Sistema")
def modal_sucesso_salvamento(detalhes):
    st.success("As alterações foram gravadas no banco de dados!")
    st.code(f"LOG: {detalhes}\nTIMESTAMP: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    if st.button("Fechar Janela", type="primary"): st.rerun()

@st.dialog("🔐 Alterar Senha")
def abrir_modal_senha(usuario_cod):
    n = st.text_input("Nova Senha", type="password"); c = st.text_input("Confirmar", type="password")
    if st.button("Salvar Senha", type="primary"):
        if n == c and n:
            run_transaction("UPDATE usuarios SET senha = :s WHERE LOWER(usuario) = LOWER(:u)", {"s": gerar_hash(n), "u": usuario_cod})
            registrar_log("Senha Alterada", f"Usuário: {usuario_cod}")
            st.success("Sucesso!"); time.sleep(1); st.session_state['logado'] = False; st.rerun()

@st.dialog("🔑 Gerar Senha Provisória")
def abrir_modal_resete_senha(titulo_janela="Recuperar Senha"):
    st.write(f"**{titulo_janela}**")
    user_input = st.text_input("Usuário (Login)")
    if st.button("Gerar e Enviar SMS", type="primary"):
        df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": user_input.strip()})
        if df.empty: st.error("Usuário não encontrado.")
        else:
            row = df.iloc[0]; tel = str(row['telefone'])
            nova_senha = gerar_senha_aleatoria(); nova_senha_hash = gerar_hash(nova_senha)
            run_transaction("UPDATE usuarios SET senha = :s WHERE id = :id", {"s": nova_senha_hash, "id": int(row['id'])})
            ok, det, cod = enviar_sms(tel, f"Sua senha provisoria e: {nova_senha}. Acesse e troque.")
            if ok: st.success(f"Sucesso! SMS enviado."); time.sleep(3); st.rerun()
            else: st.error(f"Erro ao enviar: {det}")

@st.dialog("🎁 Confirmar Resgate")
def confirmar_resgate_dialog(item_nome, custo, usuario_cod):
    st.write(f"Resgatando: **{item_nome}** por **{custo} pts**.")
    with st.form("form_resgate"):
        email = st.text_input("E-mail:", placeholder="exemplo@email.com")
        tel = st.text_input("WhatsApp (DDD+Num):", placeholder="Ex: 34999998888")
        if st.form_submit_button("CONFIRMAR", type="primary", use_container_width=True):
            if "@" not in email: st.error("E-mail inválido."); return
            if len(formatar_telefone(tel)) < 12: st.error("Telefone inválido!"); return
            
            user_df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario_cod})
            if not user_df.empty and float(user_df.iloc[0]['saldo']) >= custo:
                run_transaction("UPDATE usuarios SET saldo = saldo - :custo WHERE LOWER(usuario) = LOWER(:u)", {"custo": custo, "u": usuario_cod})
                run_transaction("INSERT INTO vendas (data, usuario, item, valor, status, email, nome_real, telefone) VALUES (NOW(), :u, :item, :valor, 'Pendente', :email, :nome, :tel)", {"u": usuario_cod, "item": item_nome, "valor": custo, "email": email, "nome": user_df.iloc[0]['nome'], "tel": tel})
                st.session_state['saldo_atual'] -= custo
                st.balloons(); st.success("Sucesso!"); time.sleep(2); st.rerun()
            else: st.error("Saldo insuficiente.")

@st.dialog("🎟️ Comprar Ticket Rifa")
def confirmar_compra_ticket(rifa_id, item_nome, custo, usuario_cod):
    st.write(f"Sorteio: **{item_nome}** | Custo: **{custo} pts**")
    if st.button("CONFIRMAR COMPRA", type="primary", use_container_width=True):
        user_df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario_cod})
        if not user_df.empty and float(user_df.iloc[0]['saldo']) >= custo:
            run_transaction("UPDATE usuarios SET saldo = saldo - :custo WHERE LOWER(usuario) = LOWER(:u)", {"custo": float(custo), "u": usuario_cod})
            run_transaction("INSERT INTO rifa_tickets (rifa_id, usuario) VALUES (:rid, :u)", {"rid": int(rifa_id), "u": usuario_cod})
            st.session_state['saldo_atual'] -= float(custo)
            st.balloons(); st.success("Ticket adquirido!"); time.sleep(2); st.rerun()
        else: st.error("Saldo insuficiente.")

@st.dialog("🚀 Confirmar e Processar Envios")
def processar_envios_dialog(df_selecionados, tipo_envio="vendas"):
    st.write(f"Destinatários selecionados: **{len(df_selecionados)}**")
    st.markdown("##### 📡 Canais de Envio:")
    c1, c2 = st.columns(2)
    with c1: usar_zap = st.toggle("WhatsApp", value=True)
    with c2: usar_sms = st.toggle("SMS", value=True)
    st.markdown("---")
    if st.button("CONFIRMAR E DISPARAR", type="primary", use_container_width=True):
        if not usar_zap and not usar_sms: st.error("Selecione um canal."); return
        logs_envio = []
        progress_bar = st.progress(0); status_text = st.empty(); total = len(df_selecionados)
        for i, (index, row) in enumerate(df_selecionados.iterrows()):
            status_text.text(f"Processando {i+1}/{total}...")
            tel = str(row['telefone'])
            if tipo_envio == "vendas": nome = str(row['nome_real'] or row['usuario']); var1 = str(row['item']); var2 = str(row['codigo_vale'])
            else: nome = str(row['nome']); var1 = f"{float(row['saldo']):,.0f}"; var2 = ""
            if usar_zap:
                ok, det, cod = enviar_whatsapp_template(tel, [nome, var1, var2]) if tipo_envio == "vendas" else enviar_whatsapp_template(tel, [nome, var1])
                logs_envio.append({"Nome": nome, "Status": "WhatsApp ✅" if ok else "WhatsApp ❌"})
            if usar_sms:
                txt = f"Ola {nome}, resgate de {var1} liberado! Cod: {var2}" if tipo_envio == "vendas" else f"Ola {nome}, saldo atualizado: {var1} pts."
                ok, det, cod = enviar_sms(tel, txt)
                logs_envio.append({"Nome": nome, "Status": "SMS ✅" if ok else "SMS ❌"})
            progress_bar.progress((i + 1) / total)
        status_text.success("Finalizado!"); time.sleep(2); st.rerun()

# --- TELAS ---
def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.write("") 
        if st.session_state.get('em_verificacao_2fa', False):
            with st.form("f_2fa"):
                st.markdown(f"### 🔒 Segurança\nSMS enviado para final **...{str(st.session_state.dados_usuario_temp.get('telefone', ''))[-4:]}**")
                cod = st.text_input("Código de 6 dígitos")
                if st.form_submit_button("VALIDAR", type="primary", use_container_width=True):
                    if cod == st.session_state.codigo_2fa_esperado:
                        d = st.session_state.dados_usuario_temp
                        st.session_state.update({'logado': True, 'usuario_cod': d['usuario'], 'usuario_nome': d['nome'], 'tipo_usuario': d['tipo'], 'saldo_atual': d['saldo'], 'valor_ponto_usuario': d.get('valor_ponto', 0.50), 'em_verificacao_2fa': False})
                        criar_sessao_persistente(d['id']); st.rerun()
                    else: st.error("Código incorreto.")
        else:
            with st.form("f_login"):
                st.markdown("<h1 style='text-align:center;'>Lojinha Culli's</h1>", unsafe_allow_html=True)
                u = st.text_input("Usuário"); s = st.text_input("Senha", type="password")
                if st.form_submit_button("ENTRAR", type="primary", use_container_width=True):
                    ok, n, t, sld, tel, uid, vp = validar_login(u, s)
                    if ok:
                        codigo = str(random.randint(100000, 999999))
                        enviou, info, _ = enviar_sms(tel, f"Seu codigo Culli: {codigo}")
                        if enviou:
                            st.session_state.update({'em_verificacao_2fa': True, 'codigo_2fa_esperado': codigo, 'dados_usuario_temp': {'usuario': u, 'nome': n, 'tipo': t, 'saldo': sld, 'telefone': tel, 'id': uid, 'valor_ponto': vp}})
                            st.rerun()
                        else: st.error("Erro ao enviar SMS.")
                    else: st.error("Dados incorretos.")

def tela_admin():
    st.subheader("🛠️ Painel Admin")
    t1, t2, t3, t4, t5 = st.tabs(["📊 Entregas", "👥 Usuários", "🎁 Prêmios", "🛠️ Logs", "🎟️ Sorteio"])
    with t1:
        df_v = run_query("SELECT * FROM vendas ORDER BY id DESC")
        if not df_v.empty:
            if "Enviar" not in df_v.columns: df_v.insert(0, "Enviar", False)
            edit_v = st.data_editor(df_v, use_container_width=True, hide_index=True)
            st.markdown("<br>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
            with c2:
                if st.button("💾 Salvar Tabela", use_container_width=True, key="btn_save_vendas"):
                    with conn.session as s:
                        for _, row in edit_v.iterrows():
                            s.execute(text("UPDATE vendas SET status=:st, codigo_vale=:c WHERE id=:id"), {"st": str(row['status']), "c": str(row['codigo_vale']), "id": int(row['id'])})
                        s.commit()
                    modal_sucesso_salvamento("Tabela de Vendas atualizada.")
            with c3:
                if st.button("📤 Enviar Selecionados", type="primary", use_container_width=True):
                    sel = edit_v[edit_v['Enviar'] == True]
                    if not sel.empty: processar_envios_dialog(sel, "vendas")
    with t2:
        with st.expander("💎 Configurar Valor do Ponto Individualizado"):
            df_u = run_query("SELECT id, nome, valor_ponto FROM usuarios ORDER BY nome")
            opcoes = {row['nome']: row['id'] for _, row in df_u.iterrows()}
            u_sel = st.selectbox("Usuário", list(opcoes.keys()))
            vp = st.number_input("Valor Ponto", value=0.50, step=0.01)
            if st.button("Salvar Valor"):
                run_transaction("UPDATE usuarios SET valor_ponto=:vp WHERE id=:id", {"vp": vp, "id": opcoes[u_sel]})
                modal_sucesso_salvamento(f"Valor do ponto para {u_sel} alterado.")
        
        with st.expander("➕ Cadastrar Novo Usuário"):
            with st.form("form_novo"):
                c_n1, c_n2 = st.columns(2)
                u = c_n1.text_input("Usuário"); s = c_n2.text_input("Senha"); n = c_n1.text_input("Nome"); t = c_n2.text_input("Telefone")
                bal = c_n1.number_input("Saldo", step=100.0); tp = c_n2.selectbox("Tipo", ["comum", "admin", "staff"]); vp = c_n1.number_input("Valor do Ponto (R$)", value=0.50, step=0.01)
                if st.form_submit_button("Cadastrar"):
                    ok, msg = cadastrar_novo_usuario(u, s, n, bal, tp, t, vp)
                    if ok: st.cache_data.clear(); modal_sucesso_salvamento(f"Novo usuário cadastrado: {u}"); 
                    else: st.error(msg)
        
        with st.expander("💰 Distribuir Pontos"):
            c1, c2 = st.columns([3, 1])
            df_users = run_query("SELECT usuario FROM usuarios WHERE tipo='comum'")
            users = c1.multiselect("Usuários", ["Todos"] + df_users['usuario'].tolist())
            qtd = c2.number_input("Qtd", step=50)
            if st.button("Distribuir"):
                distribuir_pontos_multiplos(users, qtd)
                st.cache_data.clear(); modal_sucesso_salvamento("Pontos distribuídos!")

        st.divider()
        df_u = run_query("SELECT * FROM usuarios ORDER BY id")
        if not df_u.empty:
            edit_u = st.data_editor(df_u, use_container_width=True, key="ed_u")
            if st.button("💾 Salvar Usuários", use_container_width=True):
                with conn.session as s:
                    for _, row in edit_u.iterrows():
                        s.execute(text("UPDATE usuarios SET saldo=:s, pontos_historico=:ph, telefone=:t, nome=:n, tipo=:tp, valor_ponto=:vp WHERE id=:id"), 
                                  {"s": float(row['saldo']), "ph": float(row['pontos_historico']), "t": str(row['telefone']), "n": str(row['nome']), "tp": str(row['tipo']), "vp": float(row.get('valor_ponto', 0.50)), "id": int(row['id'])})
                    s.commit()
                modal_sucesso_salvamento("Usuários atualizados.")

    with t3:
        # PRÊMIOS
        df_p = run_query("SELECT * FROM premios ORDER BY id")
        edit_p = st.data_editor(df_p, use_container_width=True, num_rows="dynamic")
        if st.button("💾 Salvar Prêmios"):
            with conn.session as s:
                for _, row in edit_p.iterrows():
                    if pd.notna(row['id']):
                        s.execute(text("UPDATE premios SET item=:i, imagem=:im, custo=:c, descricao=:d WHERE id=:id"), {"i": row['item'], "im": row['imagem'], "c": row['custo'], "d": row.get('descricao'), "id": int(row['id'])})
                    else:
                        s.execute(text("INSERT INTO premios (item, imagem, custo, descricao) VALUES (:i, :im, :c, :d)"), {"i": row['item'], "im": row['imagem'], "c": row['custo'], "d": row.get('descricao')})
                s.commit()
            modal_sucesso_salvamento("Catálogo atualizado.")

    with t4:
        st.dataframe(run_query("SELECT * FROM logs ORDER BY id DESC LIMIT 50"), use_container_width=True)

    with t5:
        # SORTEIO
        rifa = run_query("SELECT * FROM rifas WHERE status='ativa'")
        if not rifa.empty:
            st.success(f"Sorteio Ativo: {rifa.iloc[0]['item_nome']}")
            if st.button("Realizar Sorteio"):
                # Lógica de sorteio simplificada para visualização
                tickets = run_query("SELECT usuario FROM rifa_tickets WHERE rifa_id=:rid", {"rid": int(rifa.iloc[0]['id'])})
                if not tickets.empty:
                    win = random.choice(tickets['usuario'].tolist())
                    run_transaction("UPDATE rifas SET status='encerrada', ganhador_usuario=:u WHERE id=:id", {"u": win, "id": int(rifa.iloc[0]['id'])})
                    mostrar_vencedor_dialog(win, win, rifa.iloc[0]['item_nome'], None)
        else:
            st.info("Sem sorteio ativo.")
            # Configuração de novo sorteio (código simplificado)
            if st.button("Iniciar Novo Sorteio (Demo)"):
                st.warning("Configure no banco ou use a interface completa anterior.")

def tela_principal():
    u_cod, u_nome, sld, tipo = st.session_state.usuario_cod, st.session_state.usuario_nome, st.session_state.saldo_atual, st.session_state.tipo_usuario
    valor_ponto_usuario = st.session_state.get('valor_ponto_usuario', 0.50)

    # HEADER DINÂMICO
    if tipo == 'admin':
        cols = st.columns([3, 1.5], gap="medium")
        c_banner = cols[0]
        with cols[1]:
            c_top = st.columns(2, gap="small"); c_bot = st.columns(2, gap="small")
            with c_top[0]: 
                if st.button("Atualizar", type="secondary", use_container_width=True): st.cache_data.clear(); st.rerun()
            with c_top[1]:
                if st.button("Senha", type="secondary", use_container_width=True): abrir_modal_senha(u_cod)
            with c_bot[0]:
                label = "Ver Loja" if st.session_state.admin_mode else "Voltar"
                if st.button(label, type="secondary", use_container_width=True): st.session_state.admin_mode = not st.session_state.admin_mode; st.rerun()
            with c_btn_bot[1]:
                if st.button("Sair", type="secondary", use_container_width=True): realizar_logout()
    else:
        cols = st.columns([3, 1], gap="small")
        c_banner = cols[0]
        with cols[1]:
            if st.button("Alterar Senha", type="secondary", use_container_width=True): abrir_modal_senha(u_cod)
            if st.button("Sair", type="secondary", use_container_width=True): realizar_logout()
    
    with c_banner:
        st.markdown(f'''<div class="header-style"><div><h2 style="margin:0;">Olá, {u_nome}! 👋</h2><p style="margin:0;">Troque seus pontos por prêmios!</p></div><div style="text-align:right;"><span class="saldo-label">SEU SALDO</span><br><span class="saldo-valor">{sld:,.0f}</span> pts</div></div>''', unsafe_allow_html=True)
    
    st.divider()
    if tipo == 'admin' and st.session_state.admin_mode: tela_admin()
    else:
        t1, t2, t3, t4 = st.tabs(["🎁 Catálogo", "🍀 Sorteio", "📜 Meus Resgates", "🏆 Ranking"])
        with t1:
            # BUSCA
            busca = st.text_input("🔍 Buscar", placeholder="Digite o nome do prêmio...").lower()
            df_p = run_query("SELECT * FROM premios ORDER BY id")
            
            if not df_p.empty:
                if busca: df_p = df_p[df_p['item'].str.lower().str.contains(busca)]
                
                cols = st.columns(4)
                for i, row in df_p.iterrows():
                    with cols[i % 4]:
                        with st.container(border=True):
                            if row['imagem']: st.image(processar_link_imagem(row['imagem']))
                            custo = int(row['custo'] * (0.50 / valor_ponto_usuario))
                            st.markdown(f"**{row['item']}**")
                            st.markdown(f"<h3 style='color:#0066cc; margin:0;'>{custo} pts</h3>", unsafe_allow_html=True)
                            c1, c2 = st.columns(2)
                            with c1: 
                                if st.button("Detalhes", key=f"d_{row['id']}", type="secondary", use_container_width=True): ver_detalhes_produto(row['item'], row['imagem'], custo, row.get('descricao'))
                            with c2:
                                if sld >= custo:
                                    if st.button("RESGATAR", key=f"r_{row['id']}", type="primary", use_container_width=True): confirmar_resgate_dialog(row['item'], custo, u_cod)

if __name__ == "__main__":
    verificar_sessao_automatica()
    if st.session_state.get('logado', False): tela_principal()
    else: tela_login()
