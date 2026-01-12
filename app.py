import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Lojinha de Pontos", layout="centered")

# --- CONEXÃO COM GOOGLE SHEETS ---
def conectar_google_sheets():
    # Define o escopo de permissão
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # PEGA AS CREDENCIAIS DOS SEGREDOS DO STREAMLIT (NÃO DO ARQUIVO LOCAL)
    # Vamos configurar isso no passo seguinte
    creds_dict = st.secrets["gcp_service_account"]
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # Abre a planilha pelo nome
    sheet = client.open("Lojinha_DB")
    return sheet

def carregar_dados():
    try:
        sheet = conectar_google_sheets()
        # Pega todos os registros das abas
        usuarios = pd.DataFrame(sheet.worksheet("usuarios").get_all_records())
        premios = pd.DataFrame(sheet.worksheet("premios").get_all_records())
        return usuarios, premios, sheet
    except Exception as e:
        st.error(f"Erro ao conectar na planilha: {e}")
        return None, None, None

# --- INICIALIZAÇÃO DA SESSÃO ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

# --- TELA DE LOGIN ---
if not st.session_state['logado']:
    st.title("🔐 Login da Lojinha")
    usuario_input = st.text_input("Usuário")
    senha_input = st.text_input("Senha", type="password")
    
    if st.button("Entrar"):
        df_usuarios, _, _ = carregar_dados()
        
        if df_usuarios is not None:
            # Converte saldo para numero caso venha como texto
            df_usuarios['saldo'] = pd.to_numeric(df_usuarios['saldo'])
            
            # Verifica login
            user_match = df_usuarios[
                (df_usuarios['usuario'].astype(str) == usuario_input) & 
                (df_usuarios['senha'].astype(str) == senha_input)
            ]
            
            if not user_match.empty:
                st.session_state['logado'] = True
                st.session_state['usuario_atual'] = user_match.iloc[0].to_dict()
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

# --- TELA DA LOJA ---
else:
    df_usuarios, df_premios, sheet_obj = carregar_dados()
    
    # Atualiza dados do usuário logado com o que veio da planilha agora
    usuario_logado = st.session_state['usuario_atual']['usuario']
    dados_user_atual = df_usuarios[df_usuarios['usuario'].astype(str) == usuario_logado].iloc[0]
    saldo_user = int(dados_user_atual['saldo'])
    nome_user = dados_user_atual['nome']
    
    with st.sidebar:
        st.header(f"Olá, {nome_user}!")
        st.metric("Seu Saldo", f"{saldo_user} pts")
        if st.button("Sair"):
            st.session_state['logado'] = False
            st.rerun()

    st.title("🎁 Prêmios Disponíveis")
    
    for index, row in df_premios.iterrows():
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(row['imagem'], use_container_width=True)
        with col2:
            st.subheader(row['item'])
            st.write(f"**Custo:** {row['custo']} pontos")
            
            key_btn = f"btn_{row['id']}"
            if st.button(f"Resgatar {row['item']}", key=key_btn):
                custo = int(row['custo'])
                if saldo_user >= custo:
                    # --- LÓGICA DE ESCRITA NO GOOGLE SHEETS ---
                    novo_saldo = saldo_user - custo
                    
                    # Acha a linha correta na planilha para atualizar
                    # (Adiciona 2 porque o gspread conta a partir do 1 e tem o cabeçalho)
                    row_index = df_usuarios[df_usuarios['usuario'].astype(str) == usuario_logado].index[0] + 2
                    
                    try:
                        worksheet_users = sheet_obj.worksheet("usuarios")
                        # Atualiza a coluna 4 (Saldo) na linha do usuário
                        worksheet_users.update_cell(row_index, 4, novo_saldo)
                        
                        st.success(f"Resgatado! Seu novo saldo é {novo_saldo}")
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar na planilha: {e}")
                else:
                    st.error("Saldo insuficiente!")
        st.divider()
