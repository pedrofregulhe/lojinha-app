import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time  # <--- Adicionado para corrigir o erro do sleep

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="Lojinha de Prêmios", layout="wide")

# --- CONEXÃO COM GOOGLE SHEETS ---
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
    return conn.read(worksheet=aba, ttl=0)

def limpar_dado(dado):
    texto = str(dado).strip()
    if texto.endswith('.0'):
        texto = texto.replace('.0', '')
    return texto

def validar_login(user_input, pass_input):
    try:
        df = carregar_dados("usuarios")
        if df.empty: return False, None
        
        # Limpeza e Validação
        df['usuario'] = df['usuario'].astype(str)
        df['senha'] = df['senha'].astype(str)
        
        df['usuario_limpo'] = df['usuario'].apply(lambda x: limpar_dado(x).lower())
        df['senha_limpa'] = df['senha'].apply(lambda x: limpar_dado(x))
        
        u_clean = limpar_dado(user_input).lower()
        p_clean = limpar_dado(pass_input)
        
        user_found = df[
            (df['usuario_limpo'] == u_clean) & 
            (df['senha_limpa'] == p_clean)
        ]
        
        if not user_found.empty:
            tipo = "comum"
            if 'tipo' in df.columns:
                 tipo = str(user_found.iloc[0]['tipo']).lower()
            elif u_clean == "admin": # Fallback simples
                 tipo = "admin"
            return True, tipo
            
        return False, None
    except Exception as e:
        st.error(f"Erro na validação: {e}")
        return False, None

def salvar_resgate(usuario, item, valor):
    try:
        df_vendas = carregar_dados("vendas")
        
        novo = pd.DataFrame([{
            "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "Usuario": usuario,
            "Item": item,
            "Valor": valor
        }])
        
        df_final = pd.concat([df_vendas, novo], ignore_index=True)
        conn.update(worksheet="vendas", data=df_final)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# --- TELAS ---

def tela_login():
    st.markdown("### 🔐 Acesso à Lojinha")
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        with st.form("frm_login"):
            u = st.text_input("Usuário")
            s = st.text_input("Senha", type="password")
            btn = st.form_submit_button("Entrar")
            
            if btn:
                ok, tipo = validar_login(u, s)
                if ok:
                    st.session_state['logado'] = True
                    st.session_state['usuario_atual'] = u
                    st.session_state['tipo_usuario'] = tipo
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

def tela_principal():
    user = st.session_state['usuario_atual']
    tipo = st.session_state['tipo_usuario']
    
    # Header
    col_a, col_b = st.columns([6,1])
    col_a.title(f"Bem-vindo(a), {user}!")
    if col_b.button("Sair"):
        st.session_state['logado'] = False
        st.rerun()
        
    st.divider()

    # --- PERFIL: ADMIN ---
    if tipo == 'admin':
        st.info("Painel Gerencial (Admin)")
        df_v = carregar_dados("vendas")
        if not df_v.empty:
            st.dataframe(df_v, use_container_width=True)
            total = df_v['Valor'].sum()
            st.metric("Total de Pontos Resgatados", f"{total} pts")
        else:
            st.warning("Nenhum resgate encontrado.")

    # --- PERFIL: USUÁRIO COMUM ---
    else:
        # Criação das Abas
        tab_premios, tab_extrato = st.tabs(["🎁 Prêmios Disponíveis", "📜 Meus Resgates"])
        
        # --- ABA 1: CATÁLOGO ---
        with tab_premios:
            try:
                df_p = carregar_dados("premios")
                
                if not df_p.empty:
                    cols = st.columns(3)
                    for i, row in df_p.iterrows():
                        c = cols[i % 3]
                        with c:
                            with st.container(border=True):
                                # Imagem
                                if 'imagem' in df_p.columns and pd.notna(row['imagem']) and str(row['imagem']).startswith('http'):
                                    st.image(row['imagem'], use_container_width=True)
                                
                                st.markdown(f"**{row['item']}**")
                                st.caption(f"Custo: {row['custo']} pts")
                                
                                if st.button("Resgatar", key=f"b_{row['id']}"):
                                    with st.spinner("Processando..."):
                                        if salvar_resgate(user, row['item'], row['custo']):
                                            st.success("Resgate realizado!")
                                            st.balloons()
                                            time.sleep(2) # <--- Corrigido aqui
                                            st.rerun()
                else:
                    st.info("Nenhum prêmio disponível no momento.")
            except Exception as e:
                st.error(f"Erro ao carregar prêmios: {e}")

        # --- ABA 2: EXTRATO ---
        with tab_extrato:
            st.subheader("Seu Histórico")
            try:
                df_v = carregar_dados("vendas")
                if not df_v.empty:
                    # Filtra apenas o usuário atual
                    df_v['Usuario'] = df_v['Usuario'].astype(str)
                    meus = df_v[df_v['Usuario'] == str(user)]
                    
                    if not meus.empty:
                        # Mostra tabela limpa (sem índice feio)
                        st.dataframe(meus[['Data', 'Item', 'Valor']], use_container_width=True, hide_index=True)
                    else:
                        st.info("Você ainda não realizou nenhum resgate.")
                else:
                    st.info("Nenhum registro encontrado.")
            except Exception as e:
                st.error(f"Erro ao carregar histórico: {e}")

# --- MAIN ---
if __name__ == "__main__":
    if st.session_state['logado']:
        tela_principal()
    else:
        tela_login()
