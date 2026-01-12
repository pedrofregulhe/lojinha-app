import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- CONFIGURAÇÕES ---
# Nome exato da aba onde os registros serão salvos
NOME_ABA = "vendas"  
USUARIO_ADMIN = "admin" # Defina quem é o admin

# Catálogo de Prêmios (Simulação dos itens disponíveis para resgate)
# Valor aqui seria 'pontos' ou 'custo'
CATALOGO = {
    "Garrafa Térmica": 50,
    "Mochila Executiva": 150,
    "Kit Escritório": 80,
    "Fone Bluetooth": 200
}

st.set_page_config(page_title="Portal de Resgates", layout="wide")

# --- CONEXÃO COM GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def ler_dados():
    # Lê os dados da aba 'vendas', garantindo que cache expire rápido para ver atualizações
    # ttl=0 garante que sempre pegamos o dado fresco do Google Sheets
    return conn.read(worksheet=NOME_ABA, ttl=0)

def salvar_resgate(usuario, item, valor):
    try:
        # 1. Carrega dados atuais
        df_atual = ler_dados()
        
        # 2. Cria a nova linha
        novo_registro = pd.DataFrame([{
            "Data": datetime.now().strftime("%Y-%m-%d"),
            "Usuario": usuario,
            "Item": item,
            "Valor": valor
        }])
        
        # 3. Adiciona a nova linha ao dataframe existente
        df_atualizado = pd.concat([df_atual, novo_registro], ignore_index=True)
        
        # 4. Envia tudo de volta para o Google Sheets
        conn.update(worksheet=NOME_ABA, data=df_atualizado)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# --- INTERFACE ---
def main():
    st.sidebar.title("Login Sistema")
    usuario_logado = st.sidebar.text_input("Digite seu Usuário:")

    if not usuario_logado:
        st.info("Faça login para continuar.")
        st.stop()

    # ---------------------------------------------------------
    # PERFIL: ADMINISTRADOR (Visão Consolidada)
    # ---------------------------------------------------------
    if usuario_logado.lower() == USUARIO_ADMIN:
        st.title("📊 Painel do Administrador")
        st.success(f"Logado como Admin: {usuario_logado}")
        
        df = ler_dados()
        
        if not df.empty:
            # Métricas
            total_resgatado = df["Valor"].sum()
            total_itens = len(df)
            
            c1, c2 = st.columns(2)
            c1.metric("Total de Pontos Resgatados", f"{total_resgatado}")
            c2.metric("Quantidade de Resgates", f"{total_itens}")
            
            st.markdown("---")
            
            # Gráficos
            col_g1, col_g2 = st.columns(2)
            
            # Mais resgatados
            graf_itens = px.bar(df, x="Item", y="Valor", title="Itens mais Populares", color="Item")
            col_g1.plotly_chart(graf_itens, use_container_width=True)
            
            # Tabela completa
            st.subheader("Log Geral de Resgates")
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("Ainda não há dados na planilha.")

    # ---------------------------------------------------------
    # PERFIL: USUÁRIO COMUM (Solicitar Resgate)
    # ---------------------------------------------------------
    else:
        st.title(f"Olá, {usuario_logado}!")
        st.subheader("🎁 Prêmios Disponíveis")
        
        # Exibe os prêmios em 'Cards'
        cols = st.columns(len(CATALOGO))
        
        for i, (item_nome, valor_item) in enumerate(CATALOGO.items()):
            with cols[i]:
                st.info(f"**{item_nome}**")
                st.metric("Valor", f"{valor_item} pts")
                
                # Botão de Resgate
                # Usamos uma chave única para cada botão
                if st.button(f"Resgatar", key=f"btn_{i}"):
                    with st.spinner("Processando resgate..."):
                        sucesso = salvar_resgate(usuario_logado, item_nome, valor_item)
                        if sucesso:
                            st.success(f"Parabéns! Você resgatou: {item_nome}")
                            st.balloons()
                        else:
                            st.error("Erro ao processar.")

        st.markdown("---")
        st.subheader("Seu Histórico de Resgates")
        
        # Mostra o histórico lendo da planilha filtra pelo usuario
        df = ler_dados()
        if not df.empty:
            meus_resgates = df[df["Usuario"] == usuario_logado]
            st.dataframe(meus_resgates, use_container_width=True)
        else:
            st.write("Nenhum histórico encontrado.")

if __name__ == "__main__":
    main()
