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

# --- ESTILIZAÇÃO (CSS PREMIUM) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
    
    /* BACKGROUND GRADIENTE NA TELA DE LOGIN */
    .stApp {
        background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
        background-size: 400% 400%;
        animation: gradient 15s ease infinite;
    }
    @keyframes gradient {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* Se estiver logado, fundo volta ao cinza claro profissional */
    .main-app-bg {
        background-color: #f4f8fb !important;
        background-image: none !important;
    }

    .block-container { padding-top: 3rem !important; }

    /* CARD DE LOGIN */
    .login-card {
        background-color: white;
        padding: 40px;
        border-radius: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.2);
        text-align: center;
    }

    /* HEADER INTERNO (Bloco Azul) */
    .header-style {
        background: linear-gradient(90deg, #005c97 0%, #363795 100%);
        padding: 20px 25px;
        border-radius: 15px;
        color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        display: flex; flex-direction: column; justify-content: center;
        height: 100%;
    }

    /* IMAGENS DOS PRODUTOS (Mais compactas) */
    [data-testid="stImage"] img {
        height: 150px !important; /* Reduzi um pouco */
        object-fit: contain !important;
        width: 100% !important;
        border-radius: 10px;
    }

    /* BOTÕES GERAIS */
    div.stButton > button[kind="secondary"] {
        background-color: #0066cc; color: white; border-radius: 8px; border: none;
        height: 40px; font-weight: bold; width: 100%; transition: 0.3s;
    }
    div.stButton > button[kind="secondary"]:hover { background-color: #004080; color: white; }
    
    /* BOTÃO PRIMÁRIO (VERMELHO/SALVAR) */
    div.stButton > button[kind="primary"] {
        background-color: #ff4b4b !important; color: white !important;
        border-radius: 8px; border: none; height: 40px; font-weight: bold; width: 100%;
    }
    div.stButton > button[kind="primary"]:hover { background-color: #c93030 !important; }
    
    /* AJUSTE PARA O CARD DE PRODUTO FICAR MAIS "APERTADO" */
    [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
        padding: 10px;
    }
    
    .logo-container img { max-width: 100%; height: auto; }
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

def alterar_senha_banco(usuario_cod, nova_senha):
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

def salvar_alteracoes_admin(aba, df_novo):
    """Função genérica para salvar edições do Admin"""
    try:
        conn.update(worksheet=aba, data=df_novo)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

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

# --- MODAL ---
@st.dialog("🔐 Alterar Senha")
def abrir_modal_senha(usuario_cod):
    st.write("Digite sua nova senha abaixo:")
    nova = st.text_input("Nova Senha", type="password")
    conf = st.text_input("Confirmar Senha", type="password")
    
    if st.button("Confirmar Alteração", key="btn_confirm_modal"):
        if nova == conf and len(nova) > 0:
            with st.spinner("Atualizando..."):
                if alterar_senha_banco(usuario_cod, nova):
                    st.success("Senha alterada com sucesso!")
                    time.sleep(1.5)
                    st.session_state['logado'] = False
                    st.rerun()
                else: st.error("Erro ao conectar.")
        else: st.warning("Senhas não conferem.")

# --- TELAS ---

def tela_login():
    # Centralização Vertical e Horizontal com Colunas
    col_vazia1, col_login, col_vazia2 = st.columns([1, 1, 1])
    
    with col_login:
        st.markdown("<br><br><br>", unsafe_allow_html=True) # Empurrar para baixo
        
        # INICIO DO CARD CSS
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        
        # LOGO
        img_b64 = carregar_logo_base64(ARQUIVO_LOGO)
        st.markdown(f'<img src="{img_b64}" style="width: 150px; margin-bottom: 20px;">', unsafe_allow_html=True)
        st.markdown("<h2 style='color: #333; margin-bottom: 5px;'>Portal Culligan</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color: #666; font-size: 14px; margin-bottom: 20px;'>Faça login para acessar seus prêmios</p>", unsafe_allow_html=True)
        
        # FORMULÁRIO
        with st.form("frm_login"):
            u = st.text_input("Usuário", placeholder="Seu login")
            s = st.text_input("Senha", type="password", placeholder="Sua senha")
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Botão primário para login
            if st.form_submit_button("ENTRAR", type="primary", use_container_width=True):
                ok, nome, tipo, saldo = validar_login(u, s)
                if ok:
                    st.session_state['logado'] = True
                    st.session_state['usuario_cod'] = u
                    st.session_state['usuario_nome'] = nome
                    st.session_state['tipo_usuario'] = tipo
                    st.session_state['saldo_atual'] = saldo
                    st.rerun()
                else:
                    st.toast("Usuário ou senha incorretos!", icon="❌")
        
        st.markdown('</div>', unsafe_allow_html=True) # FIM CARD

def tela_admin():
    """Tela Exclusiva do Administrador com Poderes de Edição"""
    st.subheader("🛠️ Painel de Controle - Super Admin")
    
    tab_dash, tab_users, tab_premios = st.tabs(["📊 Visão Geral", "👥 Gerenciar Usuários", "🎁 Gerenciar Prêmios"])
    
    # 1. VISÃO GERAL
    with tab_dash:
        df_v = carregar_dados("vendas")
        if not df_v.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Resgatado (Pontos)", f"{df_v['Valor'].sum():,.0f}")
            c2.metric("Total de Pedidos", len(df_v))
            c3.metric("Último Resgate", df_v.iloc[-1]['Data'] if 'Data' in df_v else "-")
            
            st.markdown("### Extrato Completo de Resgates")
            st.dataframe(df_v, use_container_width=True)
        else:
            st.info("Sem dados de vendas ainda.")

    # 2. GERENCIAR USUÁRIOS (EDITÁVEL)
    with tab_users:
        st.info("💡 Edite os valores diretamente na tabela e clique em 'Salvar Alterações'.")
        df_u = carregar_dados("usuarios")
        
        # Data Editor permite editar como Excel
        df_u_editado = st.data_editor(df_u, num_rows="dynamic", use_container_width=True, key="editor_users")
        
        if st.button("💾 Salvar Alterações em Usuários", type="primary"):
            if salvar_alteracoes_admin("usuarios", df_u_editado):
                st.success("Banco de dados de usuários atualizado!")
                time.sleep(1)
                st.rerun()

    # 3. GERENCIAR PRÊMIOS (EDITÁVEL)
    with tab_premios:
        st.info("💡 Adicione, remova ou edite prêmios aqui.")
        df_p = carregar_dados("premios")
        
        df_p_editado = st.data_editor(df_p, num_rows="dynamic", use_container_width=True, key="editor_premios")
        
        if st.button("💾 Salvar Alterações em Prêmios", type="primary"):
            if salvar_alteracoes_admin("premios", df_p_editado):
                st.success("Catálogo de prêmios atualizado!")
                time.sleep(1)
                st.rerun()

def tela_principal():
    # Injeta CSS para fundo branco interno
    st.markdown('<style>.stApp {background: #f4f8fb; animation: none;}</style>', unsafe_allow_html=True)
    
    u_cod = st.session_state['usuario_cod']
    u_nome = st.session_state['usuario_nome']
    tipo = st.session_state['tipo_usuario']
    saldo = st.session_state['saldo_atual']
    
    # HEADER (Mantido o design bonito)
    col_info, col_acoes = st.columns([3, 1.1])
    with col_info:
        st.markdown(f"""
            <div class="header-style">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="flex: 1; padding-right: 20px;">
                        <h2 style="margin:0; color: white; font-size: 24px;">Olá, {u_nome}! 👋</h2>
                        <p style="margin-top: 8px; opacity:0.9; font-size: 15px; line-height: 1.3;">
                            Bem Vindo (a) a Loja de Prêmios Culligan. Aproveite!
                        </p>
                    </div>
                    <div style="text-align: right; min-width: 110px;">
                        <span style="font-size:12px; opacity:0.8; letter-spacing: 1px;">SEU SALDO</span><br>
                        <span style="font-size:32px; font-weight:bold;">{saldo:,.0f}</span> <span style="font-size:18px;">pts</span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with col_acoes:
        img_b64 = carregar_logo_base64(ARQUIVO_LOGO)
        st.markdown(f'<div style="text-align:center; margin-bottom: 10px; padding-top: 5px;"><img src="{img_b64}" style="max-height: 70px;"></div>', unsafe_allow_html=True)
        
        c_vazio1, c_senha, c_sair, c_vazio2 = st.columns([0.05, 1, 1, 0.05], gap="small")
        with c_senha:
            if st.button("Alterar Senha", key="btn_abre_modal"): abrir_modal_senha(u_cod)
        with c_sair:
            if st.button("Sair", key="btn_sair", type="primary"):
                st.session_state['logado'] = False
                st.rerun()

    st.divider()

    # ROTEAMENTO DE TELAS
    if tipo == 'admin':
        tela_admin()
    else:
        # TELA USUÁRIO COMUM
        tab1, tab2 = st.tabs(["🎁 Catálogo", "📜 Meus Resgates"])
        with tab1:
            df_p = carregar_dados("premios")
            if not df_p.empty:
                col_busca, _ = st.columns([1, 2])
                with col_busca:
                    busca = st.text_input("🔍 Buscar...", placeholder="Nome do prêmio")
                if busca: df_p = df_p[df_p['item'].str.contains(busca, case=False, na=False)]
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # ALTERAÇÃO: 4 Colunas + Gap Pequeno para reduzir espaçamento
                cols = st.columns(4, gap="small") 
                
                for i, row in df_p.iterrows():
                    with cols[i % 4]:
                        with st.container(border=True): # Container com borda nativa do Streamlit fica mais clean
                            if pd.notna(row.get('imagem')) and str(row['imagem']).startswith('http'):
                                st.image(row['imagem'])
                            else: st.image("https://via.placeholder.com/200?text=Sem+Imagem")
                            
                            st.markdown(f"**{row['item']}**")
                            cor = "#0066cc" if saldo >= row['custo'] else "#999"
                            st.markdown(f"<div style='color:{cor}; font-weight:bold; font-size:18px; margin-bottom: 10px;'>{row['custo']} pts</div>", unsafe_allow_html=True)
                            
                            if saldo >= row['custo']:
                                if st.button("RESGATAR", key=f"b_{row['id']}", use_container_width=True):
                                    with st.spinner("..."):
                                        if processar_resgate(u_cod, row['item'], row['custo']):
                                            st.balloons(); time.sleep(2); st.rerun()
                            else: st.button(f"Falta {row['custo']-saldo:.0f}", disabled=True, key=f"d_{row['id']}", use_container_width=True)
            else: st.warning("Catálogo vazio.")
        
        with tab2:
            df_v = carregar_dados("vendas")
            if not df_v.empty:
                df_v['Usuario'] = df_v['Usuario'].astype(str)
                st.dataframe(df_v[df_v['Usuario']==str(u_cod)][['Data','Item','Valor']], use_container_width=True, hide_index=True)

if __name__ == "__main__":
    if st.session_state['logado']: tela_principal()
    else: tela_login()
