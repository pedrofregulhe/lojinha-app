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

# --- FUNÇÕES AUXILIARES ---

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
    
    .main-app-bg { background-color: #f4f8fb !important; background-image: none !important; }
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }

    [data-testid="stForm"] {
        background-color: #ffffff; padding: 40px; border-radius: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2); border: none;
    }
    
    .stTextInput input { background-color: #f7f9fc; color: #333; border: 1px solid #e0e0e0; }

    .header-style {
        background: linear-gradient(90deg, #005c97 0%, #363795 100%);
        padding: 20px 25px; border-radius: 15px; color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1); display: flex; flex-direction: column; justify-content: center; height: 100%;
    }

    [data-testid="stImage"] img { height: 150px !important; object-fit: contain !important; width: 100% !important; border-radius: 10px; }

    div.stButton > button[kind="secondary"] {
        background-color: #0066cc; color: white; border-radius: 8px; border: none; height: 40px; font-weight: bold; width: 100%; transition: 0.3s;
    }
    div.stButton > button[kind="secondary"]:hover { background-color: #004080; color: white; }
    
    div.stButton > button[kind="primary"] {
        background-color: #ff4b4b !important; color: white !important; border-radius: 8px; border: none; height: 40px; font-weight: bold; width: 100%;
    }
    div.stButton > button[kind="primary"]:hover { background-color: #c93030 !important; }
    
    .logo-container img { max-width: 100%; height: auto; }
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
def carregar_dados(aba): return conn.read(worksheet=aba, ttl=0)
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
        
        u_in = limpar_dado(user_input).lower()
        pass_in = limpar_dado(pass_input)
        
        usuario_encontrado = df[df['u_busca'] == u_in]
        
        if not usuario_encontrado.empty:
            linha = usuario_encontrado.iloc[0]
            hash_armazenado = limpar_dado(linha['senha'])
            
            if verificar_senha_hash(pass_in, hash_armazenado):
                nome = linha['nome'] if 'nome' in df.columns else u_in
                saldo = float(linha['saldo']) if 'saldo' in df.columns else 0.0
                tipo = "comum"
                if 'tipo' in df.columns:
                    if str(linha['tipo']).lower().strip() == 'admin':
                        tipo = 'admin'
                return True, nome, tipo, saldo
        return False, None, None, 0
    except Exception as e:
        st.error(f"Erro login: {e}"); return False, None, None, 0

def salvar_alteracoes_admin(aba, df_novo):
    try: conn.update(worksheet=aba, data=df_novo); return True
    except Exception as e: st.error(f"Erro ao salvar: {e}"); return False

def processar_resgate(usuario_cod, item_nome, custo):
    try:
        df_u = carregar_dados("usuarios")
        df_u['usuario_str'] = df_u['usuario'].astype(str).apply(lambda x: limpar_dado(x).lower())
        idx = df_u[df_u['usuario_str'] == usuario_cod.lower()].index
        if len(idx) == 0: return False
        
        saldo_banco = float(df_u.at[idx[0], 'saldo'])
        if saldo_banco < custo: st.toast(f"Saldo insuficiente!", icon="❌"); return False
            
        novo_saldo = saldo_banco - custo
        df_u.at[idx[0], 'saldo'] = novo_saldo
        if 'usuario_str' in df_u.columns: df_u = df_u.drop(columns=['usuario_str'])
        conn.update(worksheet="usuarios", data=df_u)
        
        # --- ATUALIZAÇÃO DO STATUS (AQUI MUDOU) ---
        df_v = carregar_dados("vendas")
        nova = pd.DataFrame([{
            "Data": datetime.now().strftime("%d/%m/%Y %H:%M"), 
            "Usuario": usuario_cod, 
            "Item": item_nome, 
            "Valor": custo,
            "Status": "Pendente"  # <--- Status Inicial
        }])
        conn.update(worksheet="vendas", data=pd.concat([df_v, nova], ignore_index=True))
        
        st.session_state['saldo_atual'] = novo_saldo
        return True
    except Exception as e: st.error(f"Erro: {e}"); return False

# --- MODAL ---
@st.dialog("🔐 Alterar Senha")
def abrir_modal_senha(usuario_cod):
    st.write("Digite sua nova senha:")
    nova = st.text_input("Nova Senha", type="password")
    conf = st.text_input("Confirmar Senha", type="password")
    if st.button("Confirmar", key="btn_conf_modal"):
        if nova == conf and len(nova) > 0:
            nova_hash = gerar_hash(nova)
            df = carregar_dados("usuarios")
            df['u_b'] = df['usuario'].astype(str).apply(lambda x: limpar_dado(x).lower())
            idx = df[df['u_b'] == usuario_cod.lower()].index
            if len(idx) > 0:
                df.at[idx[0], 'senha'] = nova_hash
                df = df.drop(columns=['u_b'])
                conn.update(worksheet="usuarios", data=df)
                st.success("Senha atualizada com segurança!"); time.sleep(1.5)
                st.session_state['logado'] = False; st.rerun()
        else: st.warning("Senhas não batem.")

# --- TELAS ---
def tela_login():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        with st.form("frm_login"):
            img_b64 = carregar_logo_base64(ARQUIVO_LOGO)
            st.markdown(f'<div style="text-align: center; margin-bottom: 25px;"><img src="{img_b64}" style="width: 220px;"></div>', unsafe_allow_html=True)
            u = st.text_input("Usuário", placeholder="Digite seu login")
            s = st.text_input("Senha", type="password", placeholder="Digite sua senha")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("ENTRAR", type="primary", use_container_width=True):
                ok, nome, tipo, saldo = validar_login(u, s)
                if ok:
                    st.session_state['logado'] = True
                    st.session_state['usuario_cod'] = u
                    st.session_state['usuario_nome'] = nome
                    st.session_state['tipo_usuario'] = tipo
                    st.session_state['saldo_atual'] = saldo
                    st.rerun()
                else: st.toast("Dados incorretos!", icon="❌")

def tela_admin():
    st.subheader("🛠️ Painel Super Admin")
    t1, t2, t3, t4 = st.tabs(["📊 Dashboard & Entregas", "👥 Usuários", "🎁 Prêmios", "🛠️ Ferramentas"])
    
    # --- ABA 1: DASHBOARD COM STATUS EDITÁVEL ---
    with t1:
        st.info("Aqui você pode mudar o status dos pedidos para 'Entregue'.")
        df_v = carregar_dados("vendas")
        
        if not df_v.empty:
            # Métricas
            c1, c2 = st.columns(2)
            c1.metric("Total Pontos", f"{df_v['Valor'].sum():,.0f}")
            c2.metric("Total Pedidos", len(df_v))
            
            st.markdown("---")
            st.markdown("### 🚚 Gerenciar Pedidos")
            
            # Garante que a coluna Status existe
            if "Status" not in df_v.columns:
                df_v["Status"] = "Pendente"

            # Tabela Editável
            edited_df = st.data_editor(
                df_v,
                column_config={
                    "Status": st.column_config.SelectboxColumn(
                        "Status do Pedido",
                        help="Atualize o status da entrega",
                        width="medium",
                        options=["Pendente", "Em Separação", "Entregue", "Cancelado"],
                        required=True,
                    ),
                    "Data": st.column_config.TextColumn("Data", disabled=True),
                    "Usuario": st.column_config.TextColumn("Usuário", disabled=True),
                    "Item": st.column_config.TextColumn("Item", disabled=True),
                    "Valor": st.column_config.NumberColumn("Valor", disabled=True),
                },
                use_container_width=True,
                hide_index=True,
                key="editor_vendas"
            )
            
            if st.button("💾 Salvar Alterações de Status", type="primary"):
                salvar_alteracoes_admin("vendas", edited_df)
                st.success("Status atualizados com sucesso!")
                time.sleep(1)
                st.rerun()
        else:
            st.info("Nenhuma venda realizada.")

    with t2:
        st.info("Edite os usuários abaixo:")
        df_u = carregar_dados("usuarios")
        df_edit = st.data_editor(df_u, use_container_width=True, num_rows="dynamic")
        if st.button("Salvar Usuários", type="primary"):
            salvar_alteracoes_admin("usuarios", df_edit)
            st.success("Salvo!"); time.sleep(1); st.rerun()
    with t3:
        st.info("Gerencie os prêmios:")
        df_p = carregar_dados("premios")
        df_p_edit = st.data_editor(df_p, use_container_width=True, num_rows="dynamic")
        if st.button("Salvar Prêmios", type="primary"):
            salvar_alteracoes_admin("premios", df_p_edit)
            st.success("Salvo!"); time.sleep(1); st.rerun()
    with t4:
        st.markdown("### 🔐 Gerador de Hash Seguro")
        st.info("Ferramenta para criar senhas seguras.")
        col_a, col_b = st.columns([1, 2])
        with col_a: senha_para_hash = st.text_input("Senha normal:", placeholder="Ex: culligan2026")
        with col_b:
            if senha_para_hash:
                st.markdown("**Copie o código:**")
                st.code(gerar_hash(senha_para_hash), language="text")

def tela_principal():
    st.markdown('<style>.stApp {background: #f4f8fb; animation: none;}</style>', unsafe_allow_html=True)
    u_cod = st.session_state['usuario_cod']
    u_nome = st.session_state['usuario_nome']
    tipo = st.session_state['tipo_usuario']
    saldo = st.session_state['saldo_atual']
    
    col_info, col_acoes = st.columns([3, 1.1])
    with col_info:
        st.markdown(f"""
            <div class="header-style">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="flex: 1; padding-right: 20px;">
                        <h2 style="margin:0; color: white; font-size: 24px;">Olá, {u_nome}! 👋</h2>
                        <p style="margin-top: 8px; opacity:0.9; font-size: 15px;">Bem Vindo (a) a Loja Culligan.</p>
                    </div>
                    <div style="text-align: right; min-width: 110px;">
                        <span style="font-size:12px; opacity:0.8;">SEU SALDO</span><br>
                        <span style="font-size:32px; font-weight:bold;">{saldo:,.0f}</span> <span style="font-size:18px;">pts</span>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)
    with col_acoes:
        img_b64 = carregar_logo_base64(ARQUIVO_LOGO)
        st.markdown(f'<div style="text-align:center; margin-bottom: 10px; padding-top: 5px;"><img src="{img_b64}" style="max-height: 70px;"></div>', unsafe_allow_html=True)
        c_senha, c_sair = st.columns([1, 1]) 
        with c_senha: 
            if st.button("Alterar Senha", key="b_senha", use_container_width=True): abrir_modal_senha(u_cod)
        with c_sair: 
            if st.button("Encerrar Sessão", type="primary", use_container_width=True): st.session_state['logado']=False; st.rerun()
    
    st.divider()
    
    if tipo == 'admin': tela_admin()
    else:
        t1, t2 = st.tabs(["🎁 Catálogo", "📜 Meus Resgates"])
        with t1:
            df_p = carregar_dados("premios")
            if not df_p.empty:
                busca = st.text_input("🔍 Buscar...", placeholder="Nome...")
                if busca: df_p = df_p[df_p['item'].str.contains(busca, case=False, na=False)]
                st.markdown("<br>", unsafe_allow_html=True)
                cols = st.columns(4, gap="small")
                for i, row in df_p.iterrows():
                    with cols[i%4]:
                        with st.container(border=True):
                            if pd.notna(row.get('imagem')) and str(row['imagem']).startswith('http'): st.image(row['imagem'])
                            else: st.image("https://via.placeholder.com/200?text=Sem+Imagem")
                            st.markdown(f"**{row['item']}**")
                            cor = "#0066cc" if saldo >= row['custo'] else "#999"
                            st.markdown(f"<div style='color:{cor}; font-weight:bold; margin-bottom:10px;'>{row['custo']} pts</div>", unsafe_allow_html=True)
                            if saldo >= row['custo']:
                                if st.button("RESGATAR", key=f"b_{row['id']}", use_container_width=True):
                                    with st.spinner("..."):
                                        if processar_resgate(u_cod, row['item'], row['custo']):
                                            st.balloons(); time.sleep(2); st.rerun()
                            else: st.button(f"Falta {row['custo']-saldo:.0f}", disabled=True, key=f"d_{row['id']}", use_container_width=True)
            else: st.warning("Vazio.")
        with t2:
            # --- MOSTRAR STATUS PARA O USUÁRIO ---
            df_v = carregar_dados("vendas")
            if not df_v.empty:
                df_v['Usuario'] = df_v['Usuario'].astype(str)
                meus_resgates = df_v[df_v['Usuario']==str(u_cod)]
                
                # Garante que coluna Status aparece
                colunas_mostrar = ['Data','Item','Valor']
                if 'Status' in meus_resgates.columns:
                    colunas_mostrar.append('Status')
                
                st.dataframe(meus_resgates[colunas_mostrar], use_container_width=True, hide_index=True)
            else:
                st.info("Você ainda não fez resgates.")

if __name__ == "__main__":
    if st.session_state['logado']: tela_principal()
    else: tela_login()
