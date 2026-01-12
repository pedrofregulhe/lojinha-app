import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(layout="wide")
st.title("🕵️ Tela de Diagnóstico")

# Conexão
conn = st.connection("gsheets", type=GSheetsConnection)

st.write("### Tentando ler a aba 'usuarios'...")

try:
    # Tenta ler a aba exata "usuarios" (sem acento)
    # Se sua aba tiver acento, mude aqui para "usuários"
    df = conn.read(worksheet="usuarios", ttl=0)
    
    st.success("✅ Sucesso ao ler a aba!")
    
    st.write("### 1. Colunas encontradas (Verifique se há espaços extras):")
    # Mostra os nomes exatos das colunas entre aspas para ver espaços
    st.code(list(df.columns))
    
    st.write("### 2. Dados brutos na planilha:")
    st.dataframe(df)
    
    st.write("### 3. Teste de Login Manual:")
    usuario_teste = "bariane.balbino"
    senha_teste = "1234"
    
    st.info(f"Testando login para: {usuario_teste} / {senha_teste}")
    
    # Simula a limpeza que fazemos no código principal
    # Se a coluna não existir, vai dar erro aqui
    try:
        # Pega a coluna de usuário (tenta achar mesmo se for Maiúscula)
        col_user = [c for c in df.columns if c.lower().strip() == 'usuario'][0]
        col_pass = [c for c in df.columns if c.lower().strip() == 'senha'][0]
        
        st.write(f"Coluna de Usuário identificada como: `{col_user}`")
        st.write(f"Coluna de Senha identificada como: `{col_pass}`")
        
        # Converte para string para comparar
        df[col_user] = df[col_user].astype(str).str.strip().str.lower()
        df[col_pass] = df[col_pass].astype(str).str.strip()
        
        achou = df[
            (df[col_user] == usuario_teste) & 
            (df[col_pass] == senha_teste)
        ]
        
        if not achou.empty:
            st.balloons()
            st.success("✅ LOGIN FUNCIONOU neste teste!")
            st.write("Dados encontrados:")
            st.write(achou)
        else:
            st.error("❌ Login falhou na comparação.")
            st.write("Dica: Verifique se a senha '1234' não está como '1234.0' na tabela acima.")
            
    except IndexError:
        st.error("❌ Não encontrei as colunas 'usuario' ou 'senha'. Verifique os nomes no item 1 acima.")
        
except Exception as e:
    st.error(f"❌ Erro Crítico ao abrir a aba: {e}")
    st.warning("Dica: Verifique se o nome da aba na planilha é exatamente 'usuarios' (sem acento e minúsculo).")
