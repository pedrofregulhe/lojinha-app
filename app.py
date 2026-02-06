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

# --- INICIALIZAÇÃO DA SESSÃO ---
if 'logado' not in st.session_state: st.session_state['logado'] = False
if 'usuario_cod' not in st.session_state: st.session_state['usuario_cod'] = ""
if 'usuario_nome' not in st.session_state: st.session_state['usuario_nome'] = ""
if 'tipo_usuario' not in st.session_state: st.session_state['tipo_usuario'] = "comum"
if 'saldo_atual' not in st.session_state: st.session_state['saldo_atual'] = 0.0
if 'valor_ponto_user' not in st.session_state: st.session_state['valor_ponto_user'] = 0.50
if 'em_verificacao_2fa' not in st.session_state: st.session_state['em_verificacao_2fa'] = False
if 'codigo_2fa_esperado' not in st.session_state: st.session_state['codigo_2fa_esperado'] = ""
if 'dados_usuario_temp' not in st.session_state: st.session_state['dados_usuario_temp'] = {}

# --- CSS DINÂMICO ---
css_comum = """
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;800;900&display=swap');
    
    html, body, [class*="css"], .stMarkdown, .stText, p, h1, h2, h3, h4, span, div {
        font-family: 'Poppins', sans-serif;
        color: #31333F !important; 
    }
    input, textarea, select { color: #31333F !important; background-color: #ffffff !important; }
    .header-style h2, .header-style p, .header-style span, .header-style div { color: white !important; }
    button[kind="primary"] p, button[kind="primary"] div { color: white !important; }
    header { visibility: hidden; }
    .stDeployButton { display: none; }
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
    [data-testid="stImage"] { display: flex; justify-content: center; }
    [data-testid="stImage"] img { height: 180px !important; width: auto !important; max-width: 100%; object-fit: contain !important; border-radius: 10px; }
    .header-style h2 { font-size: 20px !important; font-weight: 700 !important; margin-bottom: 2px !important; }
    .header-style p { font-size: 12px !important; line-height: 1.3 !important; opacity: 0.9 !important; }
    .header-style .saldo-valor { font-size: 30px !important; font-weight: 900 !important; text-shadow: 0 2px 4px rgba(0,0,0,0.15); }

    div.stButton > button[kind="primary"] { background-color: #0066cc !important; color: white !important; border-radius: 12px; border: none; height: 55px; font-weight: 600; width: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    div.stButton > button[kind="secondary"] { background-color: #ffffff !important; color: #003366 !important; border-radius: 12px !important; border: 2px solid #eef2f6 !important; height: 110px !important; font-weight: 600; width: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }

    .rifa-card { border: 2px solid #FFD700; background: linear-gradient(to bottom right, #fffdf0, #ffffff); padding: 20px; border-radius: 15px; text-align: center; }
    .winner-card { border: 2px solid #28a745; background: linear-gradient(to bottom right, #f0fff4, #ffffff); padding: 20px; border-radius: 15px; text-align: center; }
"""

if not st.session_state.get('logado', False):
    estilo_especifico = ".stApp { background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); background-size: 400% 400%; animation: gradient 15s ease infinite; } @keyframes gradient { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } } [data-testid='stForm'] { background-color: #ffffff; padding: 40px; border-radius: 20px; }"
else:
    estilo_especifico = ".stApp { background-color: #f4f8fb; } .header-style { background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); padding: 20px 30px; border-radius: 15px; color: white; }"

st.markdown(f"<style>{css_comum} {estilo_especifico}</style>", unsafe_allow_html=True)

# --- FUNÇÕES BÁSICAS ---
def verificar_senha_hash(senha_digitada, hash_armazenado):
    try:
        if not hash_armazenado.startswith("$2b$"): return senha_digitada == hash_armazenado
        return bcrypt.checkpw(senha_digitada.encode('utf-8'), hash_armazenado.encode('utf-8'))
    except: return False

def gerar_hash(senha): return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
def gerar_senha_aleatoria(tamanho=6): return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(tamanho))

def processar_link_imagem(url):
    url = str(url).strip()
    if "github.com" in url and "/blob/" in url: return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url

def formatar_telefone(tel_bruto):
    texto = re.sub(r'\D', '', str(tel_bruto))
    if 10 <= len(texto) <= 11: texto = "55" + texto
    return texto

# --- BANCO DE DADOS ---
def run_query(query_str, params=None): return conn.query(query_str, params=params, ttl=0)
def run_transaction(query_str, params=None):
    with conn.session as s: s.execute(text(query_str), params if params else {}); s.commit()

def registrar_log(acao, detalhes):
    try: run_transaction("INSERT INTO logs (data, responsavel, acao, detalhes) VALUES (NOW(), :resp, :acao, :det)", {"resp": st.session_state.get('usuario_nome', 'Sistema'), "acao": acao, "det": detalhes})
    except: pass

# --- GERENCIAMENTO DE SESSÃO ---
def criar_sessao_persistente(usuario_id):
    token = str(uuid.uuid4())
    run_transaction("UPDATE usuarios SET token_sessao = :t WHERE id = :id", {"t": token, "id": usuario_id})
    st.query_params["sessao"] = token

def verificar_sessao_automatica():
    if st.session_state.get('logado', False): return
    token_url = st.query_params.get("sessao")
    if token_url:
        df = run_query("SELECT * FROM usuarios WHERE token_sessao = :t", {"t": token_url})
        if not df.empty:
            row = df.iloc[0]
            st.session_state.update({
                'logado': True, 'usuario_cod': row['usuario'], 'usuario_nome': row['nome'],
                'tipo_usuario': str(row['tipo']).lower().strip(), 'saldo_atual': float(row['saldo']),
                'valor_ponto_user': float(row.get('valor_ponto_individual', 0.50))
            })
            st.rerun()

def realizar_logout():
    run_transaction("UPDATE usuarios SET token_sessao = NULL WHERE usuario = :u", {"u": st.session_state.get('usuario_cod', '')})
    st.query_params.clear(); st.session_state.clear(); st.rerun()

# --- ENVIOS ---
def enviar_sms(telefone, mensagem):
    try:
        url = f"{st.secrets['INFOBIP_BASE_URL'].rstrip('/')}/sms/2/text/advanced"
        payload = { "messages": [ { "from": "InfoSMS", "destinations": [{"to": formatar_telefone(telefone)}], "text": mensagem } ] }
        headers = { "Authorization": f"App {st.secrets['INFOBIP_API_KEY']}", "Content-Type": "application/json" }
        requests.post(url, json=payload, headers=headers)
        return True, "Enviado", "200"
    except Exception as e: return False, str(e), "ERR"

# --- LÓGICA DE NEGÓCIO ---
def validar_login(user_input, pass_input):
    df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": user_input.strip()})
    if df.empty: return False, None, None, 0, None, 0, 0.50
    linha = df.iloc[0]
    if verificar_senha_hash(pass_input.strip(), linha['senha']):
        return True, linha['nome'], str(linha['tipo']).lower().strip(), float(linha['saldo']), str(linha['telefone']), int(linha['id']), float(linha.get('valor_ponto_individual', 0.50))
    return False, None, None, 0, None, 0, 0.50

def salvar_venda(usuario_cod, item_nome, custo, email, tel):
    if st.session_state['saldo_atual'] < custo: return False
    run_transaction("UPDATE usuarios SET saldo = saldo - :custo WHERE LOWER(usuario) = LOWER(:u)", {"custo": custo, "u": usuario_cod})
    run_transaction("INSERT INTO vendas (data, usuario, item, valor, status, email, nome_real, telefone) VALUES (NOW(), :u, :item, :valor, 'Pendente', :e, :n, :t)",
        {"u": usuario_cod, "item": item_nome, "valor": custo, "e": email, "n": st.session_state.usuario_nome, "t": tel})
    st.session_state['saldo_atual'] -= custo
    return True

# --- MODAIS ---
@st.dialog("🎁 Confirmar Resgate")
def confirmar_resgate_dialog(item_nome, custo, usuario_cod):
    st.write(f"Resgatando: **{item_nome}** por **{custo} pts**.")
    with st.form("form_resgate"):
        email = st.text_input("E-mail:"); tel = st.text_input("WhatsApp (DDD+Num):")
        if st.form_submit_button("CONFIRMAR", type="primary"):
            if salvar_venda(usuario_cod, item_nome, custo, email, formatar_telefone(tel)):
                st.balloons(); st.success("Sucesso!"); time.sleep(2); st.rerun()

# --- TELAS ---
def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        if st.session_state.get('em_verificacao_2fa', False):
            with st.form("f_2fa"):
                st.write("### 🔒 Código de Segurança")
                cod = st.text_input("Digite o código SMS")
                if st.form_submit_button("VALIDAR"):
                    if cod == st.session_state.codigo_2fa_esperado:
                        d = st.session_state.dados_usuario_temp
                        st.session_state.update({'logado': True, 'usuario_cod': d['u'], 'usuario_nome': d['n'], 'tipo_usuario': d['t'], 'saldo_atual': d['s'], 'valor_ponto_user': d['v']})
                        criar_sessao_persistente(d['id']); st.rerun()
        else:
            with st.form("f_login"):
                st.markdown("<h1 style='text-align:center;'>Lojinha Culli's</h1>", unsafe_allow_html=True)
                u = st.text_input("Usuário"); s = st.text_input("Senha", type="password")
                if st.form_submit_button("ENTRAR", type="primary"):
                    ok, n, t, sld, tel, uid, v_ponto = validar_login(u, s)
                    if ok:
                        codigo = str(random.randint(100000, 999999))
                        enviar_sms(tel, f"Seu codigo Culli: {codigo}")
                        st.session_state.update({'em_verificacao_2fa': True, 'codigo_2fa_esperado': codigo, 'dados_usuario_temp': {'u':u,'n':n,'t':t,'s':sld,'id':uid, 'v': v_ponto}})
                        st.rerun()

def tela_admin():
    t1, t2, t3 = st.tabs(["👥 Usuários", "🎁 Prêmios", "📊 Vendas"])
    with t1:
        df_u = run_query("SELECT * FROM usuarios ORDER BY id")
        edit_u = st.data_editor(df_u, use_container_width=True, key="ed_u", column_config={
            "valor_ponto_individual": st.column_config.NumberColumn("Valor Ponto (R$)", format="%.2f", min_value=0.01)
        })
        if st.button("Salvar Alterações"):
            for _, row in edit_u.iterrows():
                run_transaction("UPDATE usuarios SET saldo=:s, pontos_historico=:ph, valor_ponto_individual=:v WHERE id=:id", 
                                {"s": row['saldo'], "ph": row['pontos_historico'], "v": row['valor_ponto_individual'], "id": row['id']})
            st.success("Salvo!"); st.rerun()

def tela_principal():
    u_nome, sld = st.session_state.usuario_nome, st.session_state.saldo_atual
    valor_ponto_user = st.session_state.get('valor_ponto_user', 0.50)
    
    # Lógica de Reprecificação Individual
    fator_ajuste = 0.50 / valor_ponto_user if valor_ponto_user > 0 else 1.0
    
    st.markdown(f'''<div class="header-style"><h2>Olá, {u_nome}! 👋</h2><p>Saldo: <b>{sld:,.0f} pts</b></p></div>''', unsafe_allow_html=True)
    if st.button("Sair"): realizar_logout()

    if st.session_state.tipo_usuario == 'admin': tela_admin()
    else:
        df_p = run_query("SELECT * FROM premios ORDER BY id")
        cols = st.columns(4)
        for i, row in df_p.iterrows():
            custo_customizado = int(row['custo'] * fator_ajuste)
            with cols[i % 4]:
                with st.container(border=True):
                    if row['imagem']: st.image(processar_link_imagem(row['imagem']))
                    st.write(f"**{row['item']}**")
                    st.write(f"💎 {custo_customizado} pts")
                    if sld >= custo_customizado:
                        if st.button("RESGATAR", key=f"p_{row['id']}", type="primary"):
                            confirmar_resgate_dialog(row['item'], custo_customizado, st.session_state.usuario_cod)

if __name__ == "__main__":
    verificar_sessao_automatica()
    if st.session_state.logado: tela_principal()
    else: tela_login()
