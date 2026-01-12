import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- CONFIGURAÇÕES ---
st.set_page_config(page_title="Sistema de Resgates", layout="wide")

# Conexão com o Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# --- GERENCIAMENTO DE SESSÃO (Para manter o login ativo) ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
if 'usuario_atual' not in st.session_state:
    st.session_state['usuario_atual'] = ""
if 'tipo_usuario' not in st.session_state:
    st.session_state['tipo_usuario'] = "comum"

# --- FUNÇÕES DE LEITURA E ESCRITA ---

def carregar_dados(aba):
    # ttl=0 garante que os dados não ficam velhos no cache
    return conn.read(worksheet=aba, ttl=0)

def validar_login(usuario, senha):
    try:
        df_users = carregar_dados("usuarios")
        
        # Converte para string para evitar erro de comparação
        df_users['Usuario'] = df_users['Usuario'].astype(str)
        df_users['Senha'] = df_users['Senha'].astype(str)
        
        # Procura o usuário e senha correspondentes
        usuario_encontrado = df_users[
            (df_users['Usuario'] == usuario) & 
            (df_users['Senha'] == senha)
        ]
        
        if not usuario_encontrado.empty:
            # Retorna True e o tipo do usuário (se tiver coluna Tipo, senão assume comum)
            tipo = "comum"
            if 'Tipo' in usuario_encontrado.columns:
                tipo = usuario_encontrado.iloc[0]['Tipo']
            elif usuario.lower() == 'admin': # Fallback simples
                tipo = 'admin'
            return True, tipo
        else:
            return False, None
    except Exception as e:
        st.error(f"Erro ao validar login. Verifique a aba 'usuarios'. Erro: {e}")
        return False, None

def salvar_resgate(usuario, item, valor):
    try:
        df_vendas = carregar_dados("vendas")
        
        novo_registro = pd.DataFrame([{
            "Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Usuario": usuario,
            "Item": item,
            "Valor": valor
        }])
        
        df_atualizado = pd.concat([df_vendas, novo_registro], ignore_index=True)
        conn.update(worksheet="vendas", data=df_atualizado)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# --- TELA DE LOGIN ---
def tela_login():
    st.markdown("## 🔐 Acesso ao Sistema")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        
        if st.button("Entrar"):
            sucesso, tipo = validar_login(usuario, senha)
            if sucesso:
                st.session_state['logado'] = True
                st.session_state['usuario_atual'] = usuario
                st.session_state['tipo_usuario'] = tipo
                st.rerun() # Recarrega a página para entrar no sistema
            else:
                st.error("Usuário ou senha incorretos.")

# --- TELA PRINCIPAL (SISTEMA) ---
def tela_sistema():
    usuario = st.session_state['usuario_atual']
    tipo = st.session_state['tipo_usuario']
    
    # Cabeçalho com botão de Sair
    c1, c2 = st.columns([4,1])
    c1.title(f"Bem-vindo(a), {usuario}")
    if c2.button("Sair"):
        st.session_state['logado'] = False
        st.session_state['usuario_atual'] = ""
        st.rerun()

    # --- ÁREA DO ADMINISTRADOR ---
    if tipo.lower() == 'admin':
        st.markdown("---")
        st.subheader("📊 Painel Administrativo - Extrato Geral")
        
        df_vendas = carregar_dados("vendas")
        if not df_vendas.empty:
            st.dataframe(df_vendas, use_container_width=True)
            
            # Resumo rápido
            total = df_vendas['Valor'].sum()
            st.metric("Total Resgatado (Pontos)", f"{total:,.0f}")
        else:
            st.info("Nenhuma venda registrada ainda.")

    # --- ÁREA DO USUÁRIO COMUM (Catálogo) ---
    else:
        st.markdown("---")
        st.subheader("🎁 Prêmios Disponíveis")
        
        # Lê os prêmios da aba 'premios' do Google Sheets
        try:
            df_premios = carregar_dados("premios")
            
            if df_premios.empty:
                st.warning("Nenhum prêmio cadastrado na aba 'premios'.")
            else:
                # Exibe os prêmios em um grid
                for index, row in df_premios.iterrows():
                    with st.container():
                        c_item, c_valor, c_botao = st.columns([3, 1, 1])
                        c_item.markdown(f"**{row['Item']}**")
                        c_valor.text(f"{row['Valor']} pts")
                        
                        # Chave única para o botão
                        if c_botao.button("Resgatar", key=f"btn_{index}"):
                            sucesso = salvar_resgate(usuario, row['Item'], row['Valor'])
                            if sucesso:
                                st.success(f"Resgate de '{row['Item']}' realizado com sucesso!")
                                st.balloons()
        except Exception as e:
            st.error(f"Erro ao carregar prêmios: {e}")

        st.markdown("---")
        st.subheader("Seus Resgates Anteriores")
        
        # Histórico pessoal
        df_vendas = carregar_dados("vendas")
        if not df_vendas.empty:
            meus = df_vendas[df_vendas['Usuario'] == usuario]
            st.dataframe(meus, use_container_width=True)

# --- CONTROLE DE FLUXO ---
def main():
    if st.session_state['logado']:
        tela_sistema()
    else:
        tela_login()

if __name__ == "__main__":
    main()
