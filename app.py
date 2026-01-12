import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time

# --- CONFIGURAÇÕES GERAIS ---
st.set_page_config(page_title="Portal de Prêmios", layout="wide", page_icon="🎁")

# COLOCAR AQUI O LINK DA SUA LOGO (Pode ser do site da empresa ou Google Drive)
URL_LOGO = "logo.png" 

# --- ESTILIZAÇÃO (CSS PREMIUM) ---
st.markdown("""
    <style>
    /* Importando fonte mais moderna */
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Roboto', sans-serif;
    }

    /* Fundo Geral */
    .stApp {
        background-color: #f4f8fb; /* Cinza azulado bem claro */
    }

    /* Cabeçalho Personalizado */
    .header-style {
        background: linear-gradient(90deg, #005c97 0%, #363795 100%);
        padding: 25px;
        border-radius: 15px;
        color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        margin-bottom: 25px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* Cards dos Prêmios */
    [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
        background-color: white;
        border-radius: 15px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s, box-shadow 0.2s;
        border: 1px solid #e1e4e8;
    }

    /* Efeito Hover no Card */
    [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.1);
    }

    /* Imagens dos Prêmios */
    [data-testid="stImage"] img {
        height: 180px !important;
        object-fit: contain !important;
        width: 100% !important;
        border-radius: 10px;
        margin-bottom: 10px;
    }

    /* Botões */
    div.stButton > button {
        background-color: #0066cc;
        color: white;
        border-radius: 20px;
        border: none;
        padding: 10px 20px;
        font-weight: bold;
        width: 100%;
        transition: background-color 0.3s;
    }
    div.stButton > button:hover {
        background-color: #004080;
        color: white;
    }

    /* Inputs (Login e Busca) */
    .stTextInput input {
        border-radius: 10px;
        border: 1px solid #ced4da;
    }
    
    /* Títulos */
    h1, h2, h3 {
        color: #2c3e50;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONEXÃO ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- SESSÃO ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
if 'usuario_cod' not in st.session_state:
    st.session_state['usuario_cod'] = ""
if 'usuario_nome' not in st.session_state:
    st.session_state['usuario_nome'] = ""
if 'tipo_usuario' not in st.session_state:
    st.session_state['tipo_usuario'] = "comum"
if 'saldo_atual' not in st.session_state:
    st.session_state['saldo_atual'] = 0.0

# --- FUNÇÕES ---

def carregar_dados(aba):
    return conn.read(worksheet=aba, ttl=0)

def limpar_dado(dado):
    texto = str(dado).strip()
    if texto.endswith('.0'):
        texto = texto.replace('.0', '')
    return texto

def validar_login(user_input, pass_input):
    try:
        df = carregar_dados("usuarios")
        if df.empty: return False, None, None, 0
        
        df['usuario'] = df['usuario'].astype(str)
        df['senha'] = df['senha'].astype(str)
        
        # Cria colunas de busca limpas
        df['u_busca'] = df['usuario'].apply(lambda x: limpar_dado(x).lower())
        df['s_busca'] = df['senha'].apply(lambda x: limpar_dado(x))
        
        u_in = limpar_dado(user_input).lower()
        p_in = limpar_dado(pass_input)
        
        user_found = df[
            (df['u_busca'] == u_in) & 
            (df['s_busca'] == p_in)
        ]
        
        if not user_found.empty:
            linha = user_found.iloc[0]
            nome_real = linha['nome'] if 'nome' in df.columns else u_in
            saldo = float(linha['saldo']) if 'saldo' in df.columns else 0.0
            
            tipo = "comum"
            if 'tipo' in df.columns:
                 tipo = str(linha['tipo']).lower()
            elif u_in == "admin":
                 tipo = "admin"
                 
            return True, nome_real, tipo, saldo
            
        return False, None, None, 0
    except Exception as e:
        st.error(f"Erro login: {e}")
        return False, None, None, 0

def alterar_senha(usuario_cod, nova_senha):
    """Função para o usuário redefinir a própria senha"""
    try:
        df_users = carregar_dados("usuarios")
        
        # Localiza o usuário
        df_users['usuario_str'] = df_users['usuario'].astype(str).apply(lambda x: limpar_dado(x).lower())
        idx = df_users[df_users['usuario_str'] == usuario_cod.lower()].index
        
        if len(idx) == 0:
            return False
            
        # Atualiza a senha
        df_users.at[idx[0], 'senha'] = nova_senha
        
        # Remove coluna auxiliar e salva
        if 'usuario_str' in df_users.columns:
            df_users = df_users.drop(columns=['usuario_str'])
            
        conn.update(worksheet="usuarios", data=df_users)
        return True
    except Exception as e:
        st.error(f"Erro ao mudar senha: {e}")
        return False

def processar_resgate(usuario_cod, item_nome, custo):
    try:
        df_users = carregar_dados("usuarios")
        df_users['usuario_str'] = df_users['usuario'].astype(str).apply(lambda x: limpar_dado(x).lower())
        idx_usuario = df_users[df_users['usuario_str'] == usuario_cod.lower()].index
        
        if len(idx_usuario) == 0:
            return False
            
        indice = idx_usuario[0]
        saldo_atual_banco = float(df_users.at[indice, 'saldo'])
        
        if saldo_atual_banco < custo:
            st.toast(f"Saldo insuficiente! Faltam {custo - saldo_atual_banco} pts.", icon="❌")
            return False
            
        novo_saldo = saldo_atual_banco - custo
        df_users.at[indice, 'saldo'] = novo_saldo
        
        if 'usuario_str' in df_users.columns:
            df_users = df_users.drop(columns=['usuario_str'])
            
        conn.update(worksheet="usuarios", data=df_users)
        
        df_vendas = carregar_dados("vendas")
        nova_venda = pd.DataFrame([{
            "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "Usuario": usuario_cod,
            "Item": item_nome,
            "Valor": custo
        }])
        df_final_vendas = pd.concat([df_vendas, nova_venda], ignore_index=True)
        conn.update(worksheet="vendas", data=df_final_vendas)
        
        st.session_state['saldo_atual'] = novo_saldo
        return True

    except Exception as e:
        st.error(f"Erro na transação: {e}")
        return False

# --- TELAS ---

def tela_login():
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Layout centralizado para login
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        # Container com fundo branco e sombra para o login
        with st.container(border=True):
            # LOGO DA EMPRESA
            st.image(URL_LOGO, width=150, use_container_width=False) 
            st.markdown("<h3 style='text-align: center; color: #333;'>Portal de Prêmios</h3>", unsafe_allow_html=True)
            
            with st.form("frm_login"):
                u = st.text_input("Usuário", placeholder="Digite seu login")
                s = st.text_input("Senha", type="password", placeholder="Digite sua senha")
                st.markdown("<br>", unsafe_allow_html=True)
                btn = st.form_submit_button("ACESSAR SISTEMA", use_container_width=True)
                
                if btn:
                    with st.spinner("Verificando credenciais..."):
                        ok, nome, tipo, saldo = validar_login(u, s)
                        if ok:
                            st.session_state['logado'] = True
                            st.session_state['usuario_cod'] = u
                            st.session_state['usuario_nome'] = nome
                            st.session_state['tipo_usuario'] = tipo
                            st.session_state['saldo_atual'] = saldo
                            st.rerun()
                        else:
                            st.error("Login inválido.")

def tela_principal():
    user_cod = st.session_state['usuario_cod']
    user_nome = st.session_state['usuario_nome']
    tipo = st.session_state['tipo_usuario']
    saldo = st.session_state['saldo_atual']
    
    # --- CABEÇALHO MODERNO (HTML/CSS) ---
    st.markdown(f"""
        <div class="header-style">
            <div>
                <h2 style="margin:0; color: white; font-size: 24px;">Olá, {user_nome}! 👋</h2>
                <p style="margin:0; opacity: 0.9;">Bem-vindo ao Clube de Vantagens</p>
            </div>
            <div style="text-align: right;">
                <span style="font-size: 14px; opacity: 0.8;">SEU SALDO</span><br>
                <span style="font-size: 32px; font-weight: bold;">{saldo:,.0f}</span> <span style="font-size: 18px;">pts</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # --- MENU DE OPÇÕES (SIDEBAR) ---
    with st.sidebar:
        st.image(URL_LOGO, width=100)
        st.markdown(f"**Usuário:** {user_cod}")
        st.markdown("---")
        
        # Opção de Mudar Senha (Expander)
        with st.expander("🔐 Alterar Minha Senha"):
            nova_senha = st.text_input("Nova Senha", type="password")
            confirma_senha = st.text_input("Confirmar Senha", type="password")
            if st.button("Salvar Nova Senha"):
                if nova_senha == confirma_senha and len(nova_senha) > 0:
                    if alterar_senha(user_cod, nova_senha):
                        st.success("Senha alterada com sucesso!")
                        time.sleep(1.5)
                        st.session_state['logado'] = False # Força relogin por segurança
                        st.rerun()
                    else:
                        st.error("Erro ao atualizar.")
                else:
                    st.warning("As senhas não coincidem ou estão vazias.")
        
        st.markdown("---")
        if st.button("SAIR DO SISTEMA", type="primary"):
            st.session_state['logado'] = False
            st.rerun()

    # --- ADMIN VIEW ---
    if tipo == 'admin':
        st.subheader("📊 Visão do Administrador")
        df_v = carregar_dados("vendas")
        if not df_v.empty:
            c1, c2 = st.columns(2)
            c1.metric("Total Resgatado", f"{df_v['Valor'].sum():,.0f}")
            c2.metric("Quantidade de Pedidos", len(df_v))
            st.dataframe(df_v, use_container_width=True)
        else:
            st.info("Nenhum dado.")

    # --- USER VIEW ---
    else:
        tab_premios, tab_extrato = st.tabs(["🎁 Catálogo de Prêmios", "📜 Histórico de Resgates"])
        
        with tab_premios:
            try:
                df_p = carregar_dados("premios")
                
                if not df_p.empty:
                    # --- BARRA DE BUSCA ---
                    col_search, _ = st.columns([1, 1])
                    with col_search:
                        termo_busca = st.text_input("🔍 Buscar prêmio...", placeholder="Ex: Fone, Garrafa...")
                    
                    # Filtra o dataframe
                    if termo_busca:
                        # Filtra ignorando maiusculas/minusculas
                        df_p = df_p[df_p['item'].str.contains(termo_busca, case=False, na=False)]

                    # --- GRID DE PRODUTOS ---
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    if df_p.empty:
                        st.warning("Nenhum prêmio encontrado com esse nome.")
                    else:
                        cols = st.columns(3) # Grid de 3 colunas
                        for i, row in df_p.iterrows():
                            c = cols[i % 3] # Distribui entre as colunas
                            with c:
                                with st.container(): # Container vira um "Card" pelo CSS
                                    # Imagem
                                    if 'imagem' in df_p.columns and pd.notna(row['imagem']) and str(row['imagem']).startswith('http'):
                                        st.image(row['imagem'])
                                    else:
                                        st.image("https://via.placeholder.com/200?text=Sem+Imagem")
                                    
                                    # Info
                                    st.markdown(f"#### {row['item']}")
                                    st.caption(f"Valor para resgate:")
                                    
                                    # Destaque no preço
                                    cor_preco = "#0066cc" if saldo >= row['custo'] else "#999"
                                    st.markdown(f"<div style='font-size: 22px; color: {cor_preco}; font-weight: bold;'>{row['custo']} pts</div>", unsafe_allow_html=True)
                                    st.markdown("<br>", unsafe_allow_html=True)

                                    # Botão
                                    if saldo >= row['custo']:
                                        if st.button("RESGATAR AGORA", key=f"btn_{row['id']}"):
                                            with st.spinner("Processando..."):
                                                if processar_resgate(user_cod, row['item'], row['custo']):
                                                    st.success("🎉 Resgate Confirmado!")
                                                    st.balloons()
                                                    time.sleep(2)
                                                    st.rerun()
                                    else:
                                        falta = row['custo'] - saldo
                                        st.button(f"Faltam {falta:.0f} pts", disabled=True, key=f"d_{row['id']}")

                else:
                    st.info("Catálogo vazio.")
            except Exception as e:
                st.error(f"Erro no catálogo: {e}")

        with tab_extrato:
            st.subheader("Meus Pedidos")
            try:
                df_v = carregar_dados("vendas")
                if not df_v.empty:
                    df_v['Usuario'] = df_v['Usuario'].astype(str)
                    meus = df_v[df_v['Usuario'] == str(user_cod)]
                    if not meus.empty:
                        st.dataframe(meus[['Data', 'Item', 'Valor']], use_container_width=True, hide_index=True)
                    else:
                        st.info("Você ainda não fez nenhum resgate.")
            except:
                st.error("Erro ao carregar histórico.")

# --- MAIN ---
if __name__ == "__main__":
    if st.session_state['logado']:
        tela_principal()
    else:
        tela_login()
