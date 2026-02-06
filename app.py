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

# --- ROBÔ DE ATUALIZAÇÃO DO BANCO (AUTO-MIGRATION) ---
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

# --- CSS DINÂMICO (CORREÇÃO DE ALTURA) ---
css_comum = """
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;800;900&display=swap');
    
    html, body, [class*="css"], .stMarkdown, .stText, p, h1, h2, h3, h4, span, div {
        font-family: 'Poppins', sans-serif;
        color: #31333F !important; 
    }
    input, textarea, select {
        color: #31333F !important;
        background-color: #ffffff !important;
    }
    .header-style h2, .header-style p, .header-style span, .header-style div {
        color: white !important;
    }

    header { visibility: hidden; }
    .stDeployButton { display: none; }
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
    
    [data-testid="stImage"] img { 
        height: 180px !important; 
        object-fit: contain !important; 
        border-radius: 10px; 
    }
    
    [data-testid="column"] {
        display: flex;
        flex-direction: column;
        justify-content: center;
        height: 100%;
    }

    /* === BANNER ESTILIZADO === */
    .header-style { 
        background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); 
        background-size: 400% 400%; 
        animation: gradient 10s ease infinite; 
        padding: 0 25px; 
        border-radius: 15px; 
        color: white; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.1); 
        display: flex; 
        flex-direction: column; 
        justify-content: center; 
        height: 110px !important; 
        margin: 0 !important;
    }

    .header-style h2 { font-size: 20px !important; font-weight: 700 !important; margin: 0 !important; }
    .header-style p { font-size: 12px !important; line-height: 1.3 !important; opacity: 0.9 !important; margin: 2px 0 0 0 !important; }
    .header-style .saldo-label { font-size: 10px !important; font-weight: 600 !important; }
    .header-style .saldo-valor { font-size: 30px !important; font-weight: 900 !important; }

    /* === BOTÕES DO HEADER (ALINHAMENTO 1:1) === */
    div.stButton > button[kind="secondary"] { 
        background-color: #ffffff !important; 
        color: #003366 !important; 
        border-radius: 12px !important; 
        border: 2px solid #eef2f6 !important; 
        height: 110px !important; /* Altura idêntica ao Banner */
        font-weight: 600; 
        width: 100%; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); 
        margin: 0 !important; /* Remove qualquer margem que cause desalinhamento */
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    /* Corrige o espaçamento interno do Streamlit que as vezes reduz o botão */
    div.stButton {
        height: 110px !important;
    }

    /* === VITRINE & RIFA (Botões Menores nas Abas) === */
    [data-testid="stTabs"] div.stButton > button { height: 50px !important; min-height: 50px !important; border-radius: 8px !important; margin-top: auto; }
    [data-testid="stTabs"] button[kind="primary"] { background-color: transparent !important; border: 2px solid #0066cc !important; color: #0066cc !important; box-shadow: none !important; }
    [data-testid="stTabs"] button[kind="primary"]:hover { background-color: #e6f0ff !important; transform: translateY(-2px); }
    [data-testid="stTabs"] button[kind="secondary"] { height: 50px !important; border: 1px solid #e0e0e0 !important; }

    /* RIFA E HALL DA FAMA */
    .rifa-card, .winner-card { padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .rifa-card { border: 2px solid #FFD700; background: linear-gradient(to bottom right, #fffdf0, #ffffff); }
    .winner-card { border: 2px solid #28a745; background: linear-gradient(to bottom right, #f0fff4, #ffffff); }

    @media only screen and (max-width: 600px) {
        .header-style { height: auto !important; padding: 15px !important; text-align: center !important; }
        div.stButton > button[kind="secondary"] { height: 60px !important; }
    }
"""

if not st.session_state.get('logado', False):
    estilo_especifico = """
    .stApp { background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); background-size: 400% 400%; animation: gradient 15s ease infinite; }
    [data-testid="stForm"] { background-color: #ffffff; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
    """
else:
    estilo_especifico = ".stApp { background-color: #f4f8fb; }"

st.markdown(f"<style>{css_comum} {estilo_especifico}</style>", unsafe_allow_html=True)

# --- FUNÇÕES ---
def verificar_senha_hash(senha_digitada, hash_armazenado):
    try:
        if not hash_armazenado.startswith("$2b$"): return senha_digitada == hash_armazenado
        return bcrypt.checkpw(senha_digitada.encode('utf-8'), hash_armazenado.encode('utf-8'))
    except Exception: return False

def gerar_hash(senha):
    return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def formatar_telefone(tel):
    apenas_numeros = re.sub(r'\D', '', str(tel))
    return apenas_numeros

def run_query(query, params=None): return conn.query(query, params=params, ttl=0)
def run_transaction(query, params=None):
    with conn.session as s: s.execute(text(query), params or {}); s.commit()

def realizar_logout():
    st.query_params.clear(); st.session_state.clear(); st.rerun()

def comprar_ticket_rifa(rifa_id, custo, usuario_cod):
    custo_real = float(custo)
    with conn.session as s:
        s.execute(text("UPDATE usuarios SET saldo = saldo - :custo WHERE LOWER(usuario) = LOWER(:u)"), {"custo": custo_real, "u": usuario_cod})
        s.execute(text("INSERT INTO rifa_tickets (rifa_id, usuario) VALUES (:rid, :u)"), {"rid": int(rifa_id), "u": usuario_cod})
        s.commit()
    st.session_state['saldo_atual'] -= custo_real
    return True, "Ticket comprado!"

# --- MODAIS ---
@st.dialog("🎟️ Comprar Ticket")
def confirmar_compra_ticket(rifa_id, item_nome, custo, usuario_cod):
    st.write(f"Sorteio: **{item_nome}** | Custo: **{custo} pts**")
    if st.button("CONFIRMAR COMPRA", type="primary", use_container_width=True):
        ok, msg = comprar_ticket_rifa(rifa_id, custo, usuario_cod)
        if ok: st.balloons(); st.success(msg); time.sleep(2); st.rerun()

@st.dialog("🎉 TEMOS UM VENCEDOR!")
def mostrar_vencedor_dialog(nome, item, img):
    st.balloons()
    if img: st.image(processar_link_imagem(img), width=300)
    st.markdown(f"<h2 style='text-align:center; color:#28a745;'>{nome}</h2>", unsafe_allow_html=True)
    st.success(f"Ganhou: {item}")

# --- TELAS ---
def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        with st.form("f_login"):
            st.markdown("<h1 style='text-align:center;'>Lojinha Culli's</h1>", unsafe_allow_html=True)
            u = st.text_input("Usuário"); s = st.text_input("Senha", type="password")
            if st.form_submit_button("ENTRAR", type="primary", use_container_width=True):
                df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": u.strip()})
                if not df.empty and verificar_senha_hash(s, df.iloc[0]['senha']):
                    r = df.iloc[0]
                    st.session_state.update({'logado': True, 'usuario_cod': r['usuario'], 'usuario_nome': r['nome'], 'tipo_usuario': str(r['tipo']).lower(), 'saldo_atual': float(r['saldo']), 'valor_ponto_usuario': float(r.get('valor_ponto', 0.50) or 0.50)})
                    st.rerun()
                else: st.error("Usuário ou senha incorretos")

def tela_admin():
    t1, t2, t3, t4, t5 = st.tabs(["📊 Entregas", "👥 Usuários", "🎁 Prêmios", "🛠️ Logs", "🎟️ Sorteio"])
    with t2:
        with st.expander("💎 Configurar Valor do Ponto Individualizado"):
            df_u = run_query("SELECT id, usuario, nome, valor_ponto FROM usuarios ORDER BY nome")
            if not df_u.empty:
                opcoes = {f"{row['nome']} ({row['usuario']})": row['id'] for _, row in df_u.iterrows()}
                sel = st.selectbox("Selecione o Usuário:", list(opcoes.keys()))
                id_u = opcoes[sel]
                atual = df_u[df_u['id'] == id_u]['valor_ponto'].iloc[0] or 0.50
                novo = st.number_input("Novo Valor (R$):", value=float(atual), step=0.01)
                if st.button("Salvar Valor Personalizado", type="primary"):
                    run_transaction("UPDATE usuarios SET valor_ponto = :vp WHERE id = :id", {"vp": novo, "id": id_u})
                    st.cache_data.clear(); st.success("Atualizado!"); time.sleep(1.5); st.rerun()

def tela_principal():
    u_cod, u_nome, sld, tipo = st.session_state.usuario_cod, st.session_state.usuario_nome, st.session_state.saldo_atual, st.session_state.tipo_usuario
    v_ponto = st.session_state.get('valor_ponto_usuario', 0.50)

    # HEADER COM COLUNAS ALINHADAS
    if tipo == 'admin':
        cols = st.columns([3, 0.6, 1.2, 0.6, 0.6], gap="small")
        c_banner, c_refresh, c_toggle, c_senha, c_sair = cols
    else:
        cols = st.columns([3, 1, 1], gap="medium")
        c_banner, c_senha, c_sair = cols; c_refresh = c_toggle = None

    with c_banner:
        st.markdown(f'''<div class="header-style"><div style="display:flex; justify-content:space-between; align-items:center;"><div><h2 style="margin:0; color:white;">Olá, {u_nome}! 👋</h2><p style="margin:0; opacity:0.9; color:white;">Agora você pode trocar seus pontos por prêmios incríveis!</p></div><div style="text-align:right; color:white;"><span class="saldo-label">SEU SALDO</span><br><span class="saldo-valor">{sld:,.0f}</span> pts</div></div></div>''', unsafe_allow_html=True)
    
    if c_refresh:
        with c_refresh:
            if st.button("🔄", help="Atualizar", type="secondary", use_container_width=True): st.cache_data.clear(); st.rerun()

    if c_toggle:
        with c_toggle:
            label = "👁️ Ver Loja" if st.session_state.admin_mode else "🛠️ Voltar"
            if st.button(label, type="secondary", use_container_width=True):
                st.session_state.admin_mode = not st.session_state.admin_mode; st.rerun()

    with c_senha:
        if st.button("🔐", help="Senha", type="secondary", use_container_width=True): pass # Abre modal
    with c_sair:
        if st.button("❌", help="Sair", type="secondary", use_container_width=True): realizar_logout()

    st.divider()
    
    if tipo == 'admin' and st.session_state.admin_mode:
        tela_admin()
    else:
        t1, t2, t3, t4 = st.tabs(["🎁 Catálogo", "🍀 Sorteio", "📜 Meus Resgates", "🏆 Ranking"])
        with t1:
            df_p = run_query("SELECT * FROM premios ORDER BY id")
            if not df_p.empty:
                cols = st.columns(4)
                for i, row in df_p.iterrows():
                    with cols[i % 4]:
                        with st.container(border=True):
                            if row['imagem']: st.image(processar_link_imagem(row['imagem']))
                            custo = int(row['custo'] * (0.50 / v_ponto))
                            st.markdown(f"**{row['item']}**")
                            st.markdown(f"<h3 style='color:#0066cc;'>{custo} pts</h3>", unsafe_allow_html=True)
                            if sld >= custo:
                                if st.button("RESGATAR", key=f"b_{row['id']}", type="primary", use_container_width=True): pass
        with t2:
            st.info("Aba de Sorteios ativa.")

if __name__ == "__main__":
    if st.session_state.get('logado', False): tela_principal()
    else: tela_login()
