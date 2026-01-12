import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- CONFIGURAÇÕES ---
st.set_page_config(page_title="Sistema de Resgates", layout="wide")

# Conexão
conn = st.connection("gsheets", type=GSheetsConnection)

# --- SESSÃO ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
if 'usuario_atual' not in st.session_state:
    st.session_state['usuario_atual'] = ""
if 'tipo_usuario' not in st.session_state:
    st.session_state['tipo_usuario'] = "comum"

# --- FUNÇÕES ---

def carregar_dados(aba):
    # ttl=0 para sempre pegar dados frescos
    return conn.read(worksheet=aba, ttl=0)

def validar_login(user_input, pass_input):
    try:
        # Lê a aba 'usuarios'
        df = carregar_dados("usuarios")
        
        # Garante que as colunas sejam lidas como texto (evita erro com números)
        df['usuario'] = df['usuario'].astype(str)
        df['senha'] = df['senha'].astype(str)
        
        # Filtra (Note que usamos 'usuario' e 'senha' em minúsculo conforme sua tabela)
        user_found = df[
            (df['usuario'] == user_input) & 
            (df['senha'] == pass_input)
        ]
        
        if not user_found.empty:
            # Verifica se é admin (Pode criar uma regra simples baseada no nome por enquanto)
            tipo = "admin" if user_input.lower() == "admin" else "comum"
            return True, tipo
        return False, None
    except Exception as e:
        st.error(f"Erro ao ler aba 'usuarios': {e}")
        return False, None

def salvar_resgate(usuario_nome, item_nome, valor_custo):
    try:
        df_vendas = carregar_dados("vendas")
        
        # Cria nova linha respeitando as colunas da aba VENDAS (Maiúsculas)
        novo = pd.DataFrame([{
            "Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Usuario": usuario_nome,
            "Item": item_nome,
            "Valor": valor_custo
        }])
        
        df_final = pd.concat([df_vendas, novo], ignore_index=True)
        conn.update(worksheet="vendas", data=df_final)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar na aba 'vendas': {e}")
        return False

# --- TELAS ---

def tela_login():
    st.title("🔐 Acesso")
    col1, col2 = st.columns([1,2])
    with col1:
        u = st.text_input("Usuário")
        s = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            ok, tipo = validar_login(u, s)
            if ok:
                st.session_state['logado'] = True
                st.session_state['usuario_atual'] = u
                st.session_state['tipo_usuario'] = tipo
                st.rerun()
            else:
                st.error("Dados incorretos.")

def tela_sistema():
    user = st.session_state['usuario_atual']
    tipo = st.session_state['tipo_usuario']
    
    # Barra Superior
    c1, c2 = st.columns([5,1])
    c1.subheader(f"Olá, {user}")
    if c2.button("Sair"):
        st.session_state['logado'] = False
        st.rerun()
        
    # --- ADMIN ---
    if tipo == 'admin':
        st.info("Painel Admin - Histórico Geral")
        df_v = carregar_dados("vendas")
        if not df_v.empty:
            st.dataframe(df_v, use_container_width=True)
            st.metric("Total Resgatado", f"{df_v['Valor'].sum():,.0f} pts")
    
    # --- USUARIO COMUM ---
    else:
        st.divider()
        st.subheader("🎁 Prêmios para Resgate")
        
        try:
            # Lê aba 'premios'
            df_p = carregar_dados("premios")
            
            if not df_p.empty:
                for idx, row in df_p.iterrows():
                    # Layout do Card
                    with st.container(border=True):
                        col_txt, col_btn = st.columns([3, 1])
                        
                        # Usa 'item' e 'custo' (minúsculo) conforme sua tabela
                        col_txt.markdown(f"**{row['item']}**")
                        col_txt.caption(f"Custo: {row['custo']} pontos")
                        
                        if col_btn.button("Resgatar", key=f"btn_{row['id']}"):
                            # Tenta salvar
                            ok = salvar_resgate(user, row['item'], row['custo'])
                            if ok:
                                st.success(f"Você resgatou: {row['item']}!")
                                st.balloons()
            else:
                st.warning("Nenhum prêmio disponível.")
                
        except Exception as e:
            st.error(f"Erro ao carregar prêmios. Verifique se as colunas 'item' e 'custo' existem. Detalhe: {e}")

# --- MAIN ---
if __name__ == "__main__":
    if st.session_state['logado']:
        tela_sistema()
    else:
        tela_login()
