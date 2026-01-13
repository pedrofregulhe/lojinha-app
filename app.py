import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import base64
import bcrypt

# --- CONFIGURAÇÕES GERAIS ---
st.set_page_config(page_title="Loja Culligan", layout="wide", page_icon="🎁")

ARQUIVO_LOGO = "logo.png"

# --- FUNÇÕES DE SUPORTE ---

def carregar_logo_base64(caminho_arquivo):
    try:
        with open(caminho_arquivo, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        return f"data:image/png;base64,{encoded_string}"
    except Exception:
        return "https://cdn-icons-png.flaticon.com/512/6213/6213388.png"

def verificar_senha_hash(senha_digitada, hash_armazenado):
    try:
        return bcrypt.checkpw(senha_digitada.encode('utf-8'), hash_armazenado.encode('utf-8'))
    except ValueError:
        return senha_digitada == hash_armazenado

def gerar_hash(senha):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha.encode('utf-8'), salt).decode('utf-8')

def converter_link_drive(url):
    url = str(url).strip()
    if "drive.google.com" in url:
        if "id=" in url: return url
        try:
            file_id = url.split("/")[-2]
            return f"https://drive.google.com/uc?export=view&id={file_id}"
        except: return url
    return url

# --- ESTILIZAÇÃO (CSS) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
    
    header { visibility: hidden; }
    .stDeployButton { display: none; }
    
    /* ANIMAÇÃO DE GRADIENTE (DEFINIÇÃO GLOBAL) */
    @keyframes gradient {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    /* FUNDO DA TELA DE LOGIN */
    .stApp {
        background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2);
        background-size: 400% 400%;
        animation: gradient 15s ease infinite;
    }
    
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }

    /* CARD LOGIN */
    [data-testid="stForm"] {
        background-color: #ffffff; padding: 40px; border-radius: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2); border: none;
    }
    
    .stTextInput input { background-color: #f7f9fc; color: #333; border: 1px solid #e0e0e0; }

    /* HEADER INTERNO COM GRADIENTE ANIMADO (NOVIDADE) */
    .header-style {
        background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2);
        background-size: 400% 400%;
        animation: gradient 10s ease infinite; /* Animação exclusiva para a caixa */
        padding: 20px 25px; border-radius: 15px; color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1); display: flex; flex-direction: column; justify-content: center; height: 100%;
    }

    [data-testid="stImage"] img { height: 150px !important; object-fit: contain !important; border-radius: 10px; }

    div.stButton > button[kind="secondary"] {
        background-color: #0066cc; color: white; border-radius: 8px; border: none; height: 40px; font-weight: bold; width: 100%; transition: 0.3s;
    }
    div.stButton > button[kind="secondary"]:hover { background-color: #004080; color: white; }
    
    div.stButton > button[kind="primary"] {
        background-color: #ff4b4b !important; color: white !important; border-radius: 8px; border: none; height: 40px; font-weight: bold; width: 100%;
    }
    div.stButton > button[kind="primary"]:hover { background-color: #c93030 !important; }

    .btn-container-alinhado { margin-top: -10px; }
    </style>
""", unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

# --- SESSÃO ---
if 'logado' not in st.session_state: st.session_state['logado'] = False
if 'usuario_cod' not in st.session_state: st.session_state['usuario_cod'] = ""
if 'usuario_nome' not in st.session_state: st.session_state['usuario_nome'] = ""
if 'tipo_usuario' not in st.session_state: st.session_state['tipo_usuario'] = "comum"
if 'saldo_atual' not in st.session_state: st.session_state['saldo_atual'] = 0.0

# --- LÓGICA DE DADOS ---
def carregar_dados(aba):
    try: return conn.read(worksheet=aba, ttl=0)
    except: return pd.DataFrame()

def limpar_dado(dado): 
    texto = str(dado).strip()
    if texto.endswith('.0'): texto = texto.replace('.0', '')
    return texto

def validar_login(user_input, pass_input):
    df = carregar_dados("usuarios")
    if df.empty: return False, None, None, 0
    u_in = limpar_dado(user_input).lower()
    pass_in = limpar_dado(pass_input)
    df_temp = df.copy()
    df_temp['u_busca'] = df_temp['usuario'].astype(str).apply(lambda x: limpar_dado(x).lower())
    user_row = df_temp[df_temp['u_busca'] == u_in]
    if not user_row.empty:
        linha = user_row.iloc[0]
        if verificar_senha_hash(pass_in, limpar_dado(linha['senha'])):
            nome = linha['nome'] if 'nome' in df.columns else u_in
            saldo = float(linha['saldo']) if 'saldo' in df.columns else 0.0
            tipo = str(linha['tipo']).lower().strip() if 'tipo' in df.columns else "comum"
            return True, nome, tipo, saldo
    return False, None, None, 0

def salvar_venda(usuario_cod, item_nome, custo, email_contato):
    try:
        df_u = carregar_dados("usuarios")
        df_u_temp = df_u.copy()
        df_u_temp['u_s'] = df_u_temp['usuario'].astype(str).apply(lambda x: limpar_dado(x).lower())
        idx = df_u_temp[df_u_temp['u_s'] == usuario_cod.lower()].index
        
        saldo_b = float(df_u.at[idx[0], 'saldo'])
        df_u.at[idx[0], 'saldo'] = saldo_b - custo
        conn.update(worksheet="usuarios", data=df_u)
        
        df_v = carregar_dados("vendas")
        nova = pd.DataFrame([{
            "Data": datetime.now().strftime("%d/%m/%Y %H:%M"), 
            "Usuario": usuario_cod, 
            "Item": item_nome, 
            "Valor": custo, 
            "Status": "Pendente",
            "Email": email_contato
        }])
        conn.update(worksheet="vendas", data=pd.concat([df_v, nova], ignore_index=True))
        st.session_state['saldo_atual'] = saldo_b - custo
        return True
    except: return False

# --- MODAIS ---
@st.dialog("🔐 Alterar Senha")
def abrir_modal_senha(usuario_cod):
    n = st.text_input("Nova Senha", type="password")
    c = st.text_input("Confirmar", type="password")
    if st.button("Salvar Senha"):
        if n == c and n:
            df = carregar_dados("usuarios")
            df.loc[df['usuario'].astype(str).str.strip().str.lower() == usuario_cod.lower(), 'senha'] = gerar_hash(n)
            conn.update(worksheet="usuarios", data=df)
            st.success("Senha alterada!"); time.sleep(1); st.session_state['logado'] = False; st.rerun()

@st.dialog("🎁 Confirmar Resgate")
def confirmar_resgate_dialog(item_nome, custo, usuario_cod):
    st.write(f"Você está resgatando: **{item_nome}** por **{custo} pts**.")
    email_contato = st.text_input("Informe o e-mail para envio do vale-presente:", placeholder="exemplo@email.com")
    if st.button("CONFIRMAR RESGATE", type="primary", use_container_width=True):
        if "@" in email_contato and "." in email_contato:
            if salvar_venda(usuario_cod, item_nome, custo, email_contato):
                st.success("Pedido realizado!")
                st.balloons()
                time.sleep(2); st.rerun()
        else: st.warning("E-mail inválido.")

# --- TELAS ---
def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        with st.form("f_login"):
            img_b64 = carregar_logo_base64(ARQUIVO_LOGO)
            st.markdown(f'<center><img src="{img_b64}" width="220"></center><br>', unsafe_allow_html=True)
            u = st.text_input("Usuário"); s = st.text_input("Senha", type="password")
            if st.form_submit_button("ENTRAR", type="primary", use_container_width=True):
                ok, n, t, sld = validar_login(u, s)
                if ok:
                    st.session_state.update({'logado':True, 'usuario_cod':u, 'usuario_nome':n, 'tipo_usuario':t, 'saldo_atual':sld})
                    st.rerun()
                else: st.toast("Erro!", icon="❌")

def tela_admin():
    st.subheader("🛠️ Painel Super Admin")
    t1, t2, t3, t4 = st.tabs(["📊 Dashboard & Entregas", "👥 Usuários", "🎁 Prêmios", "🛠️ Ferramentas"])
    with t1:
        df_v = carregar_dados("vendas")
        if not df_v.empty:
            edit_v = st.data_editor(df_v, use_container_width=True, hide_index=True, key="ed_vendas_admin")
            if st.button("Salvar Status", type="primary"):
                conn.update(worksheet="vendas", data=edit_v); st.success("Salvo!"); time.sleep(1); st.rerun()
    with t2:
        df_u = carregar_dados("usuarios"); edit_u = st.data_editor(df_u, use_container_width=True, num_rows="dynamic", key="ed_usuarios")
        if st.button("Salvar Usuários", type="primary"):
            conn.update(worksheet="usuarios", data=edit_u); st.success("Salvo!"); time.sleep(1); st.rerun()
    with t3:
        df_p = carregar_dados("premios"); edit_p = st.data_editor(df_p, use_container_width=True, num_rows="dynamic", key="ed_premios")
        if st.button("Salvar Prêmios", type="primary"):
            conn.update(worksheet="premios", data=edit_p); st.success("Salvo!"); time.sleep(1); st.rerun()
    with t4:
        sh = st.text_input("Gerar Hash:"); st.code(gerar_hash(sh)) if sh else None

def tela_principal():
    # FUNDO LIMPO PARA O RESTANTE DO APP
    st.markdown('<style>.stApp {background: #f4f8fb; animation: none;}</style>', unsafe_allow_html=True)
    u_cod, u_nome, sld, tipo = st.session_state.usuario_cod, st.session_state.usuario_nome, st.session_state.saldo_atual, st.session_state.tipo_usuario
    
    col_info, col_acoes = st.columns([3, 1.1])
    with col_info:
        st.markdown(f'<div class="header-style"><div style="display:flex; justify-content:space-between; align-items:center;"><div><h2 style="margin:0; color:white;">Olá, {u_nome}! 👋</h2><p style="margin:0; opacity:0.9; color:white;">Bem Vindo (a) a Loja Culligan.</p></div><div style="text-align:right; color:white;"><span style="font-size:12px; opacity:0.8;">SEU SALDO</span><br><span style="font-size:32px; font-weight:bold;">{sld:,.0f}</span> pts</div></div></div>', unsafe_allow_html=True)
    
    with col_acoes:
        img_b64 = carregar_logo_base64(ARQUIVO_LOGO)
        st.markdown(f'<center><img src="{img_b64}" style="max-height: 80px;"></center>', unsafe_allow_html=True)
        st.markdown('<div class="btn-container-alinhado">', unsafe_allow_html=True)
        cs, cl = st.columns([1.1, 1])
        if cs.button("Alterar Senha", use_container_width=True): abrir_modal_senha(u_cod)
        if cl.button("Encerrar Sessão", type="primary", use_container_width=True): st.session_state.logado=False; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    if tipo == 'admin': tela_admin()
    else:
        t1, t2 = st.tabs(["🎁 Catálogo", "📜 Meus Resgates"])
        with t1:
            df_p = carregar_dados("premios")
            if not df_p.empty:
                cols = st.columns(4, gap="small")
                for i, row in df_p.iterrows():
                    with cols[i % 4]:
                        with st.container(border=True):
                            img = str(row.get('imagem', ''))
                            st.image(converter_link_drive(img)) if img and img != "0" else st.image("https://via.placeholder.com/200")
                            st.markdown(f"**{row['item']}**")
                            cor = "#0066cc" if sld >= row['custo'] else "#999"
                            st.markdown(f"<div style='color:{cor}; font-weight:bold;'>{row['custo']} pts</div>", unsafe_allow_html=True)
                            if sld >= row['custo'] and st.button("RESGATAR", key=f"b_{row['id']}", use_container_width=True):
                                confirmar_resgate_dialog(row['item'], row['custo'], u_cod)
        with t2:
            st.info("### 📜 Acompanhamento\nEntrega em até **5 dias úteis** via e-mail.")
            df_v = carregar_dados("vendas")
            if not df_v.empty:
                meus = df_v[df_v['Usuario'].astype(str)==str(u_cod)]
                st.dataframe(meus[['Data','Item','Valor','Status','Email']], use_container_width=True, hide_index=True)

if __name__ == "__main__":
    if st.session_state.logado: tela_principal()
    else: tela_login()
