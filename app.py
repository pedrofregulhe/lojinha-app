import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import base64

# --- CONFIGURAÇÕES GERAIS ---
st.set_page_config(page_title="Loja Culligan", layout="wide", page_icon="🎁")

# NOME DO ARQUIVO DA SUA LOGO
ARQUIVO_LOGO = "logo.png"

# --- FUNÇÃO AUXILIAR PARA IMAGEM LOCAL ---
def carregar_logo_base64(caminho_arquivo):
    try:
        with open(caminho_arquivo, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        return f"data:image/png;base64,{encoded_string}"
    except Exception:
        return "https://cdn-icons-png.flaticon.com/512/6213/6213388.png"

# --- ESTILIZAÇÃO (CSS) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
    
    .block-container { padding-top: 2rem; }
    .stApp { background-color: #f4f8fb; }

    /* Header Degradê (Bloco Azul) */
    .header-style {
        background: linear-gradient(90deg, #005c97 0%, #363795 100%);
        padding: 25px;
        border-radius: 15px;
        color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        height: 100%; /* Ocupa altura total para alinhar */
        display: flex;
        flex-direction: column;
        justify-content: center;
    }

    /* Estilo dos Produtos */
    [data-testid="stImage"] img {
        height: 180px !important;
        object-fit: contain !important;
        width: 100% !important;
        border-radius: 10px;
    }

    /* Botões */
    div.stButton > button {
        background-color: #0066cc; color: white; border-radius: 8px; border: none;
        padding: 0px 10px; /* Padding reduzido para caber melhor */
        height: 40px; /* Altura fixa para alinhar com inputs */
        font-weight: bold; width: 100%; transition: 0.3s;
    }
    div.stButton > button:hover { background-color: #004080; color: white; }
    
    /* Botão Sair (Vermelho discreto e alinhado) */
    .btn-sair > button {
        background-color: #ff4b4b !important;
        margin-top: 2px; /* Pequeno ajuste visual para alinhar com o expander */
    }
    .btn-sair > button:hover { background-color: #c93030 !important; }

    /* Ajuste do Expander para ficar compacto */
    [data-testid="stExpander"] {
        background-color: white;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONEXÃO ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- SESSÃO ---
if 'logado' not in st.session_state: st.session_state['logado'] = False
if 'usuario_cod' not in st.session_state: st.session_state['usuario_cod'] = ""
if 'usuario_nome' not in st.session_state: st.session_state['usuario_nome'] = ""
if 'tipo_usuario' not in st.session_state: st.session_state['tipo_usuario'] = "comum"
if 'saldo_atual' not in st.session_state: st.session_state['saldo_atual'] = 0.0

# --- FUNÇÕES ---
def carregar_dados(aba):
    return conn.read(worksheet=aba, ttl=0)

def limpar_dado(dado):
    texto = str(dado).strip()
    if texto.endswith('.0'): texto = texto.replace('.0', '')
    return texto

def validar_login(user_input, pass_input):
    try:
        df = carregar_dados("usuarios")
        if df.empty: return False, None, None, 0
        df['usuario'] = df['usuario'].astype(str)
        df['senha'] = df['senha'].astype(str)
        df['u_busca'] = df['usuario'].apply(lambda x: limpar_dado(x).lower())
        df['s_busca'] = df['senha'].apply(lambda x: limpar_dado(x))
        u_in = limpar_dado(user_input).lower()
        p_in = limpar_dado(pass_input)
        
        found = df[(df['u_busca'] == u_in) & (df['s_busca'] == p_in)]
        if not found.empty:
            linha = found.iloc[0]
            nome = linha['nome'] if 'nome' in df.columns else u_in
            saldo = float(linha['saldo']) if 'saldo' in df.columns else 0.0
            tipo = str(linha['tipo']).lower() if 'tipo' in df.columns else ("admin" if u_in == "admin" else "comum")
            return True, nome, tipo, saldo
        return False, None, None, 0
    except Exception as e:
        st.error(f"Erro login: {e}"); return False, None, None, 0

def alterar_senha(usuario_cod, nova_senha):
    try:
        df = carregar_dados("usuarios")
        df['usuario_str'] = df['usuario'].astype(str).apply(lambda x: limpar_dado(x).lower())
        idx = df[df['usuario_str'] == usuario_cod.lower()].index
        if len(idx) == 0: return False
        df.at[idx[0], 'senha'] = nova_senha
        if 'usuario_str' in df.columns: df = df.drop(columns=['usuario_str'])
        conn.update(worksheet="usuarios", data=df)
        return True
    except: return False

def processar_resgate(usuario_cod, item_nome, custo):
    try:
        df_u = carregar_dados("usuarios")
        df_u['usuario_str'] = df_u['usuario'].astype(str).apply(lambda x: limpar_dado(x).lower())
        idx = df_u[df_u['usuario_str'] == usuario_cod.lower()].index
        if len(idx) == 0: return False
        
        saldo_banco = float(df_u.at[idx[0], 'saldo'])
        if saldo_banco < custo:
            st.toast(f"Saldo insuficiente!", icon="❌"); return False
            
        df_u.at[idx[0], 'saldo'] = saldo_banco - custo
        if 'usuario_str' in df_u.columns: df_u = df_u.drop(columns=['usuario_str'])
        conn.update(worksheet="usuarios", data=df_u)
        
        df_v = carregar_dados("vendas")
        nova = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Usuario": usuario_cod, "Item": item_nome, "Valor": custo}])
        conn.update(worksheet="vendas", data=pd.concat([df_v, nova], ignore_index=True))
        st.session_state['saldo_atual'] = saldo_banco - custo
        return True
    except Exception as e: st.error(f"Erro: {e}"); return False

# --- TELAS ---
def tela_login():
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.container(border=True):
            img_b64 = carregar_logo_base64(ARQUIVO_LOGO)
            st.markdown(f'<div style="text-align: center;"><img src="{img_b64}" style="width: 180px;"></div>', unsafe_allow_html=True)
            st.markdown("<h3 style='text-align: center; color: #333;'>Portal de Prêmios</h3>", unsafe_allow_html=True)
            with st.form("frm_login"):
                u = st.text_input("Usuário"); s = st.text_input("Senha", type="password")
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("ACESSAR SISTEMA", use_container_width=True):
                    ok, nome, tipo, saldo = validar_login(u, s)
                    if ok:
                        st.session_state['logado'] = True
                        st.session_state['usuario_cod'] = u
                        st.session_state['usuario_nome'] = nome
                        st.session_state['tipo_usuario'] = tipo
                        st.session_state['saldo_atual'] = saldo
                        st.rerun()
                    else: st.error("Login inválido.")

def tela_principal():
    u_cod = st.session_state['usuario_cod']
    u_nome = st.session_state['usuario_nome']
    tipo = st.session_state['tipo_usuario']
    saldo = st.session_state['saldo_atual']
    
    # --- LAYOUT DO TOPO ---
    # AJUSTE: Mudei para [2, 1] para dar mais espaço à direita e não cortar a logo
    col_info, col_acoes = st.columns([2, 1])
    
    # Coluna 1: Bloco Azul (Texto atualizado)
    with col_info:
        st.markdown(f"""
            <div class="header-style">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="flex: 1;">
                        <h2 style="margin:0; color: white; font-size: 26px;">Olá, {u_nome}! 👋</h2>
                        <p style="margin-top: 5px; opacity:0.9; font-size: 16px; line-height: 1.4;">
                            Bem Vindo (a) a Loja de Prêmios Culligan. Aproveite a lista de prêmios incríveis que você pode resgatar!
                        </p>
                    </div>
                    <div style="text-align: right; min-width: 120px; margin-left: 15px;">
                        <span style="font-size:14px; opacity:0.8;">SEU SALDO</span><br>
                        <span style="font-size:36px; font-weight:bold;">{saldo:,.0f}</span> <span style="font-size:20px;">pts</span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # Coluna 2: Logo e Botões (Lado a Lado)
    with col_acoes:
        # 1. Logo (Centralizada e com max-width para não cortar)
        img_b64 = carregar_logo_base64(ARQUIVO_LOGO)
        st.markdown(
            f'<div style="text-align:center; margin-bottom: 15px;">'
            f'<img src="{img_b64}" style="max-width: 100%; height: auto; max-height: 80px;">'
            f'</div>', 
            unsafe_allow_html=True
        )
        
        # 2. Botões lado a lado (Alterar Senha | Sair)
        c_senha, c_sair = st.columns([1.5, 0.8]) # Proporção para caber o expander e o botão
        
        with c_senha:
            # Expander de Senha
            with st.expander("🔐 Alterar Senha"):
                nova_s = st.text_input("Nova senha", type="password", key="ns", label_visibility="collapsed", placeholder="Nova Senha")
                conf_s = st.text_input("Confirmar", type="password", key="cs", label_visibility="collapsed", placeholder="Confirmar")
                if st.button("Salvar", key="btn_salvar_senha"):
                    if nova_s == conf_s and len(nova_s) > 0:
                        if alterar_senha(u_cod, nova_s):
                            st.success("Alterada!")
                            time.sleep(1)
                            st.session_state['logado'] = False
                            st.rerun()
                        else: st.error("Erro.")
                    else: st.warning("Verifique.")
        
        with c_sair:
            # Botão Sair
            st.markdown('<div class="btn-sair">', unsafe_allow_html=True)
            if st.button("Sair"):
                st.session_state['logado'] = False
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    st.divider()

    # --- CONTEÚDO ---
    if tipo == 'admin':
        st.subheader("Painel Admin")
        df_v = carregar_dados("vendas")
        if not df_v.empty: st.dataframe(df_v, use_container_width=True)
        else: st.info("Sem dados.")
    else:
        tab1, tab2 = st.tabs(["🎁 Catálogo", "📜 Meus Resgates"])
        with tab1:
            df_p = carregar_dados("premios")
            if not df_p.empty:
                busca = st.text_input("🔍 Buscar prêmio...", placeholder="Ex: Fone...")
                if busca: df_p = df_p[df_p['item'].str.contains(busca, case=False, na=False)]
                
                st.markdown("<br>", unsafe_allow_html=True)
                cols = st.columns(3)
                for i, row in df_p.iterrows():
                    with cols[i % 3]:
                        with st.container():
                            if pd.notna(row.get('imagem')) and str(row['imagem']).startswith('http'):
                                st.image(row['imagem'])
                            else: st.image("https://via.placeholder.com/200?text=Sem+Imagem")
                            
                            st.markdown(f"#### {row['item']}")
                            cor = "#0066cc" if saldo >= row['custo'] else "#999"
                            st.markdown(f"<div style='color:{cor}; font-weight:bold; font-size:20px;'>{row['custo']} pts</div>", unsafe_allow_html=True)
                            
                            if saldo >= row['custo']:
                                if st.button("RESGATAR", key=f"b_{row['id']}"):
                                    with st.spinner("..."):
                                        if processar_resgate(u_cod, row['item'], row['custo']):
                                            st.balloons(); time.sleep(2); st.rerun()
                            else: st.button(f"Falta {row['custo']-saldo:.0f}", disabled=True, key=f"d_{row['id']}")
            else: st.warning("Vazio.")
        
        with tab2:
            df_v = carregar_dados("vendas")
            if not df_v.empty:
                df_v['Usuario'] = df_v['Usuario'].astype(str)
                st.dataframe(df_v[df_v['Usuario']==str(u_cod)][['Data','Item','Valor']], use_container_width=True, hide_index=True)

if __name__ == "__main__":
    if st.session_state['logado']: tela_principal()
    else: tela_login()
