import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="Lojinha de Prêmios", layout="wide")

# --- CONEXÃO COM GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- SESSÃO (Mantém o login ativo) ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
if 'usuario_atual' not in st.session_state:
    st.session_state['usuario_atual'] = ""
if 'tipo_usuario' not in st.session_state:
    st.session_state['tipo_usuario'] = "comum"

# --- FUNÇÕES ---

def carregar_dados(aba):
    # ttl=0 garante que os dados não ficam velhos no cache
    return conn.read(worksheet=aba, ttl=0)

def limpar_dado(dado):
    """Função auxiliar para limpar números que viram 1234.0"""
    texto = str(dado).strip()
    if texto.endswith('.0'):
        texto = texto.replace('.0', '')
    return texto

def validar_login(user_input, pass_input):
    try:
        df = carregar_dados("usuarios")
        
        if df.empty:
            return False, None
        
        # --- LIMPEZA PESADA DOS DADOS ---
        # 1. Garante que usuario e senha sejam strings (texto)
        df['usuario'] = df['usuario'].astype(str)
        df['senha'] = df['senha'].astype(str)
        
        # 2. Aplica a limpeza linha a linha para remover espaços e o ".0"
        df['usuario_limpo'] = df['usuario'].apply(lambda x: limpar_dado(x).lower())
        df['senha_limpa'] = df['senha'].apply(lambda x: limpar_dado(x))
        
        # 3. Limpa o que o usuário digitou na tela
        user_input_clean = limpar_dado(user_input).lower()
        pass_input_clean = limpar_dado(pass_input)
        
        # 4. Busca correspondência exata nos dados limpos
        user_found = df[
            (df['usuario_limpo'] == user_input_clean) & 
            (df['senha_limpa'] == pass_input_clean)
        ]
        
        if not user_found.empty:
            # Verifica se é admin (baseado no nome ou coluna tipo se existir)
            tipo = "comum"
            # Se quiser forçar admin para um usuário específico, descomente abaixo:
            # if user_input_clean == "admin" or user_input_clean == "bariane.balbino":
            #     tipo = "admin"
            
            # Se tiver coluna 'tipo' na planilha, usa ela
            if 'tipo' in df.columns:
                 tipo = str(user_found.iloc[0]['tipo']).lower()
                 
            return True, tipo
            
        return False, None

    except Exception as e:
        st.error(f"Erro na validação: {e}")
        return False, None

def salvar_resgate(usuario, item, valor):
    try:
        df_vendas = carregar_dados("vendas")
        
        # Cria nova linha (respeitando as colunas Data, Usuario, Item, Valor)
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
        st.error(f"Erro ao salvar na aba 'vendas': {e}")
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

    # --- ADMIN ---
    if tipo == 'admin':
        st.info("Painel Admin")
        df_v = carregar_dados("vendas")
        if not df_v.empty:
            st.dataframe(df_v, use_container_width=True)
            total = df_v['Valor'].sum()
            st.metric("Total Resgatado", f"{total} pts")
        else:
            st.warning("Sem vendas.")

    # --- COMUM ---
    else:
        st.subheader("🎁 Prêmios Disponíveis")
        try:
            df_p = carregar_dados("premios")
            
            if not df_p.empty:
                # Grid de 3 colunas
                cols = st.columns(3)
                for i, row in df_p.iterrows():
                    # Usa modulo para distribuir nos cards
                    c = cols[i % 3]
                    with c:
                        with st.container(border=True):
                            # Se tiver imagem
                            if 'imagem' in df_p.columns and pd.notna(row['imagem']) and str(row['imagem']).startswith('http'):
                                st.image(row['imagem'], use_container_width=True)
                                
                            st.markdown(f"**{row['item']}**")
                            st.caption(f"Custo: {row['custo']} pts")
                            
                            if st.button("Resgatar", key=f"b_{row['id']}"):
                                with st.spinner("Processando..."):
                                    if salvar_resgate(user, row['item'], row['custo']):
                                        st.success("Sucesso!")
                                        st.balloons()
                                        st.sleep(2)
                                        st.rerun()
            else:
                st.info("Nenhum prêmio cadastrado.")
        except Exception as e:
            st.error(f"Erro ao carregar premios: {e}")
            
        st.divider()
        st.subheader("Meus Resgates")
        df_v = carregar_dados("vendas")
        if not df_v.empty:
            # Filtra string com string para evitar erro
            df_v['Usuario'] = df_v['Usuario'].astype(str)
            meus = df_v[df_v['Usuario'] == str(user)]
            st.dataframe(meus, use_container_width=True)

# --- MAIN ---
if __name__ == "__main__":
    if st.session_state['logado']:
        tela_principal()
    else:
        tela_login()
