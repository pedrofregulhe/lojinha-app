import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="Lojinha de Prêmios", layout="wide")

# --- CONEXÃO COM GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- GERENCIAMENTO DE SESSÃO (Mantém o usuário logado) ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
if 'usuario_atual' not in st.session_state:
    st.session_state['usuario_atual'] = ""
if 'tipo_usuario' not in st.session_state:
    st.session_state['tipo_usuario'] = "comum"

# --- FUNÇÕES DE BANCO DE DADOS ---

def carregar_dados(aba):
    """Carrega dados de uma aba específica garantindo atualização (ttl=0)."""
    try:
        return conn.read(worksheet=aba, ttl=0)
    except Exception as e:
        st.error(f"Erro ao ler a aba '{aba}'. Verifique se o nome está correto na planilha. Erro: {e}")
        return pd.DataFrame()

def validar_login(user_input, pass_input):
    """Valida usuário e senha com limpeza de dados (remove espaços e ignora maiúsculas no user)."""
    try:
        df = carregar_dados("usuarios")
        
        if df.empty:
            return False, None
        
        # 1. Converter tudo para string (texto) para evitar erro de número vs texto
        df['usuario'] = df['usuario'].astype(str)
        df['senha'] = df['senha'].astype(str)
        
        # 2. Limpeza (Remover espaços em branco extras)
        df['usuario'] = df['usuario'].str.strip().str.lower()
        df['senha'] = df['senha'].str.strip()
        
        # 3. Limpeza do input do usuário
        u_input_clean = str(user_input).strip().lower()
        p_input_clean = str(pass_input).strip()
        
        # 4. Busca correspondência
        user_found = df[
            (df['usuario'] == u_input_clean) & 
            (df['senha'] == p_input_clean)
        ]
        
        if not user_found.empty:
            # Lógica simples de Admin: se o nome for 'admin' ou tiver coluna 'tipo'
            tipo = "comum"
            if u_input_clean == "admin":
                tipo = "admin"
            return True, tipo
            
        return False, None

    except Exception as e:
        st.error(f"Erro na validação: {e}")
        return False, None

def salvar_resgate(usuario, item, valor):
    """Grava o resgate na aba 'vendas'."""
    try:
        df_vendas = carregar_dados("vendas")
        
        # Cria a nova linha respeitando as maiúsculas que definimos para essa aba
        nova_venda = pd.DataFrame([{
            "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "Usuario": usuario,
            "Item": item,
            "Valor": valor
        }])
        
        # Adiciona e salva
        df_atualizado = pd.concat([df_vendas, nova_venda], ignore_index=True)
        conn.update(worksheet="vendas", data=df_atualizado)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar resgate: {e}")
        return False

# --- TELAS DO SISTEMA ---

def tela_login():
    st.markdown("### 🔐 Acesso à Lojinha")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login_form"):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar")
            
            if submitted:
                sucesso, tipo = validar_login(usuario, senha)
                if sucesso:
                    st.session_state['logado'] = True
                    st.session_state['usuario_atual'] = usuario
                    st.session_state['tipo_usuario'] = tipo
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

def tela_principal():
    usuario = st.session_state['usuario_atual']
    tipo = st.session_state['tipo_usuario']
    
    # Barra lateral / Topo
    c1, c2 = st.columns([6, 1])
    c1.title(f"Olá, {usuario}!")
    if c2.button("Sair"):
        st.session_state['logado'] = False
        st.rerun()
    
    st.divider()

    # ---------------- VISÃO DO ADMINISTRADOR ----------------
    if tipo == 'admin':
        st.subheader("📊 Painel Gerencial (Admin)")
        
        df_vendas = carregar_dados("vendas")
        if not df_vendas.empty:
            # Métricas
            total_pontos = df_vendas['Valor'].sum()
            total_pedidos = len(df_vendas)
            
            m1, m2 = st.columns(2)
            m1.metric("Total de Pontos Resgatados", f"{total_pontos:,.0f}")
            m2.metric("Total de Itens Entregues", total_pedidos)
            
            st.markdown("### Histórico Completo")
            st.dataframe(df_vendas, use_container_width=True)
        else:
            st.info("Nenhum resgate realizado ainda.")

    # ---------------- VISÃO DO USUÁRIO COMUM ----------------
    else:
        st.subheader("🎁 Catálogo de Prêmios")
        
        df_premios = carregar_dados("premios")
        
        if not df_premios.empty:
            # Cria grid de produtos (3 por linha)
            colunas = st.columns(3)
            
            for index, row in df_premios.iterrows():
                # Calcula qual coluna usar (0, 1 ou 2)
                col_atual = colunas[index % 3]
                
                with col_atual:
                    with st.container(border=True):
                        # Se tiver imagem na planilha, mostra
                        if 'imagem' in row and pd.notna(row['imagem']) and str(row['imagem']).startswith('http'):
                            st.image(row['imagem'], use_container_width=True)
                        
                        st.markdown(f"**{row['item']}**")
                        st.markdown(f"💰 **{row['custo']} pontos**")
                        
                        # Botão de ação
                        if st.button("RESGATAR", key=f"btn_{row['id']}_{index}"):
                            with st.spinner("Processando..."):
                                ok = salvar_resgate(usuario, row['item'], row['custo'])
                                if ok:
                                    st.success("Resgate realizado com sucesso!")
                                    st.balloons()
                                    # Espera um pouco e recarrega para atualizar histórico
                                    st.sleep(2)
                                    st.rerun()
        else:
            st.warning("Nenhum prêmio disponível no momento.")
            
        st.divider()
        st.markdown("### 📜 Seus Resgates")
        df_vendas = carregar_dados("vendas")
        
        if not df_vendas.empty:
            # Filtra apenas o usuário atual (convertendo para garantir comparação)
            df_vendas['Usuario'] = df_vendas['Usuario'].astype(str)
            meus_pedidos = df_vendas[df_vendas['Usuario'] == str(usuario)]
            
            if not meus_pedidos.empty:
                st.dataframe(meus_pedidos[['Data', 'Item', 'Valor']], use_container_width=True)
            else:
                st.info("Você ainda não fez resgates.")

# --- INICIALIZAÇÃO ---
if __name__ == "__main__":
    if st.session_state['logado']:
        tela_principal()
    else:
        tela_login()
