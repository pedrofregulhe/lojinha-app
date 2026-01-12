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

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
    header { visibility: hidden; }
    .stDeployButton { display: none; }
    .stApp {
        background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2);
        background-size: 400% 400%;
        animation: gradient 15s ease infinite;
    }
    @keyframes gradient {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .header-style {
        background: linear-gradient(90deg, #005c97 0%, #363795 100%);
        padding: 20px 25px; border-radius: 15px; color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    [data-testid="stForm"] { background-color: white; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
    [data-testid="stImage"] img { height: 150px !important; object-fit: contain !important; border-radius: 10px; }
    div.stButton > button[kind="secondary"] { background-color: #0066cc; color: white; border-radius: 8px; font-weight: bold; height: 40px; width: 100%; }
    div.stButton > button[kind="primary"] { background-color: #ff4b4b !important; color: white !important; border-radius: 8px; font-weight: bold; height: 40px; width: 100%; }
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
    try:
        return conn.read(worksheet=aba, ttl=0)
    except:
        return pd.DataFrame()

def limpar_dado(dado): 
    texto = str(dado).strip()
    if texto.endswith('.0'): texto = texto.replace('.0', '')
    return texto

def validar_login(user_input, pass_input):
    df = carregar_dados("usuarios")
    if df.empty: return False, None, None, 0
    u_in = limpar_dado(user_input).lower()
    pass_in = limpar_dado(pass_input)
    
    # Criamos uma cópia para não mexer no original da planilha
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

def processar_resgate(usuario_cod, item_nome, custo):
    try:
        df_u = carregar_dados("usuarios")
        df_u_temp = df_u.copy()
        df_u_temp['u_s'] = df_u_temp['usuario'].astype(str).apply(lambda x: limpar_dado(x).lower())
        
        idx = df_u_temp[df_u_temp['u_s'] == usuario_cod.lower()].index
        if len(idx) == 0: return False
        
        saldo_b = float(df_u.at[idx[0], 'saldo'])
        if saldo_b < custo: return False
        
        df_u.at[idx[0], 'saldo'] = saldo_b - custo
        conn.update(worksheet="usuarios", data=df_u)
        
        df_v = carregar_dados("vendas")
        nova = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Usuario": usuario_cod, "Item": item_nome, "Valor": custo, "Status": "Pendente"}])
        conn.update(worksheet="vendas", data=pd.concat([df_v, nova], ignore_index=True))
        
        st.session_state['saldo_atual'] = saldo_b - custo
        return True
    except: return False

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
                else: st.toast("Erro de login!", icon="❌")

def tela_admin():
    st.subheader("🛠️ Painel Super Admin")
    t1, t2, t3, t4 = st.tabs(["📊 Dashboard & Entregas", "👥 Usuários", "🎁 Prêmios", "🛠️ Ferramentas"])
    
    with t1:
        st.markdown("### 🚚 Gerenciar Pedidos")
        df_v = carregar_dados("vendas")
        if not df_v.empty:
            if "Status" not in df_v.columns: df_v["Status"] = "Pendente"
            edit_v = st.data_editor(df_v, use_container_width=True, hide_index=True, key="ed_vendas_admin")
            if st.button("Salvar Status das Entregas", type="primary", key="btn_v"):
                conn.update(worksheet="vendas", data=edit_v)
                st.success("Status atualizados!"); time.sleep(1); st.rerun()
        else: st.info("Nenhuma venda encontrada.")

    with t2:
        st.markdown("### 👥 Gerenciar Usuários")
        df_u = carregar_dados("usuarios")
        if not df_u.empty:
            edit_u = st.data_editor(df_u, use_container_width=True, num_rows="dynamic", key="ed_usuarios_admin")
            if st.button("Salvar Lista de Usuários", type="primary", key="btn_u"):
                conn.update(worksheet="usuarios", data=edit_u)
                st.success("Usuários salvos!"); time.sleep(1); st.rerun()
        else: st.warning("Não foi possível carregar os usuários.")

    with t3:
        st.markdown("### 🎁 Gerenciar Catálogo")
        df_p = carregar_dados("premios")
        if not df_p.empty:
            edit_p = st.data_editor(df_p, use_container_width=True, num_rows="dynamic", key="ed_premios_admin")
            if st.button("Salvar Catálogo de Prêmios", type="primary", key="btn_p"):
                conn.update(worksheet="premios", data=edit_p)
                st.success("Prêmios salvos!"); time.sleep(1); st.rerun()
        else: st.warning("Não foi possível carregar os prêmios.")

    with t4:
        st.markdown("### 🔐 Gerador de Hash")
        sh = st.text_input("Digite a senha para gerar o código seguro")
        if sh: st.code(gerar_hash(sh))

def tela_principal():
    st.markdown('<style>.stApp {background: #f4f8fb; animation: none;}</style>', unsafe_allow_html=True)
    u_cod, u_nome, sld, tipo = st.session_state.usuario_cod, st.session_state.usuario_nome, st.session_state.saldo_atual, st.session_state.tipo_usuario
    
    c_info, c_acoes = st.columns([3, 1.1])
    with c_info:
        st.markdown(f'<div class="header-style"><div style="display:flex; justify-content:space-between; align-items:center;"><div><h2 style="margin:0; color:white;">Olá, {u_nome}! 👋</h2><p style="margin:0; opacity:0.9; color:white;">Bem Vindo (a) a Loja Culligan.</p></div><div style="text-align:right; color:white;"><span style="font-size:12px; opacity:0.8;">SEU SALDO</span><br><span style="font-size:32px; font-weight:bold;">{sld:,.0f}</span> pts</div></div></div>', unsafe_allow_html=True)
    with c_acoes:
        img_b64 = carregar_logo_base64(ARQUIVO_LOGO)
        st.markdown(f'<center><img src="{img_b64}" height="70"></center>', unsafe_allow_html=True)
        cs, cl = st.columns(2)
        if cs.button("Senha", use_container_width=True): abrir_modal_senha(u_cod)
        if cl.button("Sair", type="primary", use_container_width=True): st.session_state.logado=False; st.rerun()

    st.divider()
    if tipo == 'admin':
        tela_admin()
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
                            if img and img != "0" and len(img) > 10: st.image(converter_link_drive(img))
                            else: st.image("https://via.placeholder.com/200?text=Sem+Imagem")
                            st.markdown(f"**{row['item']}**")
                            cor = "#0066cc" if sld >= row['custo'] else "#999"
                            st.markdown(f"<div style='color:{cor}; font-weight:bold;'>{row['custo']} pts</div>", unsafe_allow_html=True)
                            if sld >= row['custo'] and st.button("RESGATAR", key=f"b_{row['id']}", use_container_width=True):
                                if processar_resgate(u_cod, row['item'], row['custo']):
                                    st.balloons(); time.sleep(1.5); st.rerun()
            else: st.warning("Catálogo vazio.")
        with t2:
            df_v = carregar_dados("vendas")
            if not df_v.empty:
                df_v['Usuario'] = df_v['Usuario'].astype(str)
                meus = df_v[df_v['Usuario']==str(u_cod)]
                st.dataframe(meus[['Data','Item','Valor','Status']], use_container_width=True, hide_index=True)

if __name__ == "__main__":
    if st.session_state.logado: tela_principal()
    else: tela_login()
