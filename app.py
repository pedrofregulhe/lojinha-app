import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="Lojinha de Prêmios", layout="wide")

# --- ESTILIZAÇÃO (CSS) ---
# Aqui definimos o tema Azul e arrumamos as imagens
st.markdown("""
    <style>
    /* Cores Globais - Tons de Azul */
    .stApp {
        background-color: #f0f8ff; /* AliceBlue (Fundo bem clarinho) */
    }
    h1, h2, h3 {
        color: #004080 !important; /* Azul Marinho */
    }
    
    /* Botões */
    div.stButton > button {
        background-color: #0066cc;
        color: white;
        border-radius: 8px;
        border: none;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #004c99;
        color: white;
    }
    
    /* Correção das Imagens dos Prêmios */
    /* Força todas as imagens a terem 200px de altura e não deformarem */
    [data-testid="stImage"] img {
        height: 200px !important;
        object-fit: contain !important; /* Garante que a imagem inteira apareça */
        width: 100% !important;
    }
    
    /* Card do Produto */
    [data-testid="stVerticalBlock"] {
        background-color: white;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONEXÃO ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- SESSÃO ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
if 'usuario_cod' not in st.session_state:
    st.session_state['usuario_cod'] = "" # O login (ex: bariane.balbino)
if 'usuario_nome' not in st.session_state:
    st.session_state['usuario_nome'] = "" # O nome real (ex: Ariane Balbino)
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
        
        # Limpeza para comparação
        df['usuario'] = df['usuario'].astype(str)
        df['senha'] = df['senha'].astype(str)
        
        # Cria colunas temporárias limpas para buscar
        df['u_busca'] = df['usuario'].apply(lambda x: limpar_dado(x).lower())
        df['s_busca'] = df['senha'].apply(lambda x: limpar_dado(x))
        
        u_in = limpar_dado(user_input).lower()
        p_in = limpar_dado(pass_input)
        
        # Busca
        user_found = df[
            (df['u_busca'] == u_in) & 
            (df['s_busca'] == p_in)
        ]
        
        if not user_found.empty:
            linha = user_found.iloc[0]
            
            # Pega dados reais
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

def processar_resgate(usuario_cod, item_nome, custo):
    """
    Realiza a transação completa:
    1. Verifica saldo no banco (para garantir que não mudou)
    2. Desconta saldo e atualiza aba 'usuarios'
    3. Registra na aba 'vendas'
    """
    try:
        # 1. Busca dados frescos dos usuários
        df_users = carregar_dados("usuarios")
        
        # Localiza o usuário pelo código (login)
        # Importante: Precisamos do índice para atualizar a linha certa
        df_users['usuario_str'] = df_users['usuario'].astype(str).apply(lambda x: limpar_dado(x).lower())
        idx_usuario = df_users[df_users['usuario_str'] == usuario_cod.lower()].index
        
        if len(idx_usuario) == 0:
            st.error("Usuário não encontrado na base para atualizar saldo.")
            return False
            
        indice = idx_usuario[0]
        saldo_atual_banco = float(df_users.at[indice, 'saldo'])
        
        # 2. Verifica Saldo
        if saldo_atual_banco < custo:
            st.error(f"Saldo insuficiente! Você tem {saldo_atual_banco}, mas o item custa {custo}.")
            return False
            
        # 3. Atualiza Saldo na Memória
        novo_saldo = saldo_atual_banco - custo
        df_users.at[indice, 'saldo'] = novo_saldo
        
        # Remove a coluna temporária que criamos antes de salvar
        if 'usuario_str' in df_users.columns:
            df_users = df_users.drop(columns=['usuario_str'])
            
        # 4. Salva ABA USUARIOS (Atualiza saldo)
        conn.update(worksheet="usuarios", data=df_users)
        
        # 5. Salva ABA VENDAS (Registra histórico)
        df_vendas = carregar_dados("vendas")
        nova_venda = pd.DataFrame([{
            "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "Usuario": usuario_cod, # Salva o login, não o nome, para manter chave única
            "Item": item_nome,
            "Valor": custo
        }])
        df_final_vendas = pd.concat([df_vendas, nova_venda], ignore_index=True)
        conn.update(worksheet="vendas", data=df_final_vendas)
        
        # Atualiza o saldo na sessão do navegador também
        st.session_state['saldo_atual'] = novo_saldo
        
        return True

    except Exception as e:
        st.error(f"Erro na transação: {e}")
        return False

# --- TELAS ---

def tela_login():
    st.markdown("<br><br><br>", unsafe_allow_html=True) # Espaço
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<h2 style='text-align: center;'>🔐 Acesso à Lojinha</h2>", unsafe_allow_html=True)
        with st.form("frm_login"):
            u = st.text_input("Usuário")
            s = st.text_input("Senha", type="password")
            btn = st.form_submit_button("Entrar")
            
            if btn:
                ok, nome, tipo, saldo = validar_login(u, s)
                if ok:
                    st.session_state['logado'] = True
                    st.session_state['usuario_cod'] = u # Guarda o login (chave)
                    st.session_state['usuario_nome'] = nome # Guarda o nome bonito
                    st.session_state['tipo_usuario'] = tipo
                    st.session_state['saldo_atual'] = saldo
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

def tela_principal():
    user_cod = st.session_state['usuario_cod']
    user_nome = st.session_state['usuario_nome']
    tipo = st.session_state['tipo_usuario']
    saldo = st.session_state['saldo_atual']
    
    # --- CABEÇALHO ---
    # Fundo azul claro para o header
    st.markdown(f"""
        <div style="background-color: #e6f2ff; padding: 20px; border-radius: 10px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h2 style="margin:0; color: #004080;">Olá, {user_nome}! 👋</h2>
                <p style="margin:0; font-size: 18px; color: #0066cc;">Seu saldo: <strong>{saldo:,.0f} pontos</strong></p>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("Sair", key='btn_sair'):
        st.session_state['logado'] = False
        st.rerun()

    # --- ADMIN ---
    if tipo == 'admin':
        st.info("Painel Gerencial (Admin)")
        df_v = carregar_dados("vendas")
        if not df_v.empty:
            st.dataframe(df_v, use_container_width=True)
            total = df_v['Valor'].sum()
            st.metric("Total de Pontos Resgatados", f"{total} pts")

    # --- USUÁRIO COMUM ---
    else:
        tab_premios, tab_extrato = st.tabs(["🎁 Prêmios Disponíveis", "📜 Meus Resgates"])
        
        with tab_premios:
            try:
                df_p = carregar_dados("premios")
                
                if not df_p.empty:
                    # Filtra prêmios que o usuário pode comprar (Opcional - se quiser mostrar tudo tire o if)
                    # df_p = df_p[df_p['custo'] <= saldo] 
                    
                    cols = st.columns(3)
                    for i, row in df_p.iterrows():
                        c = cols[i % 3]
                        with c:
                            with st.container(border=True):
                                # Imagem
                                if 'imagem' in df_p.columns and pd.notna(row['imagem']) and str(row['imagem']).startswith('http'):
                                    st.image(row['imagem'])
                                else:
                                    # Imagem padrão se não tiver link (placeholder cinza)
                                    st.markdown('<div style="height:200px; background-color:#eee; display:flex; align-items:center; justify-content:center;">Sem Imagem</div>', unsafe_allow_html=True)
                                
                                st.markdown(f"**{row['item']}**")
                                st.markdown(f"<h4 style='color: #0066cc;'>{row['custo']} pts</h4>", unsafe_allow_html=True)
                                
                                # Botão desabilita se não tiver saldo visualmente (opcional)
                                if saldo >= row['custo']:
                                    if st.button("RESGATAR", key=f"b_{row['id']}"):
                                        with st.spinner("Processando resgate..."):
                                            if processar_resgate(user_cod, row['item'], row['custo']):
                                                st.success("Resgate realizado com sucesso!")
                                                st.balloons()
                                                time.sleep(2)
                                                st.rerun()
                                else:
                                    st.button(f"Faltam {row['custo'] - saldo} pts", disabled=True, key=f"d_{row['id']}")

                else:
                    st.info("Nenhum prêmio disponível.")
            except Exception as e:
                st.error(f"Erro ao carregar prêmios: {e}")

        with tab_extrato:
            st.subheader("Histórico de Compras")
            try:
                df_v = carregar_dados("vendas")
                if not df_v.empty:
                    # Filtra pelo código de usuário
                    df_v['Usuario'] = df_v['Usuario'].astype(str)
                    meus = df_v[df_v['Usuario'] == str(user_cod)]
                    
                    if not meus.empty:
                        st.dataframe(meus[['Data', 'Item', 'Valor']], use_container_width=True, hide_index=True)
                    else:
                        st.info("Você ainda não realizou resgates.")
            except Exception as e:
                st.error(f"Erro histórico: {e}")

# --- MAIN ---
if __name__ == "__main__":
    if st.session_state['logado']:
        tela_principal()
    else:
        tela_login()
