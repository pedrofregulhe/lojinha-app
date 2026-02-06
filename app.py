import streamlit as st
from sqlalchemy import text
import pandas as pd
from datetime import datetime
import time
import base64
import bcrypt
import requests
import re
import random
import string
import uuid

# --- CONFIGURAÇÕES GERAIS ---
st.set_page_config(page_title="Loja Culligan", layout="wide", page_icon="🎁")

# --- CONEXÃO SQL (NEON) ---
conn = st.connection("postgresql", type="sql")

# --- ROBÔ DE ATUALIZAÇÃO DO BANCO (AUTO-MIGRATION) ---
with conn.session as s:
    try:
        s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS valor_ponto FLOAT DEFAULT 0.50;"))
        s.commit()
    except Exception:
        pass 

# --- INICIALIZAÇÃO DA SESSÃO ---
if 'logado' not in st.session_state: st.session_state['logado'] = False
if 'usuario_cod' not in st.session_state: st.session_state['usuario_cod'] = ""
if 'usuario_nome' not in st.session_state: st.session_state['usuario_nome'] = ""
if 'tipo_usuario' not in st.session_state: st.session_state['tipo_usuario'] = "comum"
if 'saldo_atual' not in st.session_state: st.session_state['saldo_atual'] = 0.0
if 'valor_ponto_usuario' not in st.session_state: st.session_state['valor_ponto_usuario'] = 0.50 
if 'admin_mode' not in st.session_state: st.session_state['admin_mode'] = True 

if 'em_verificacao_2fa' not in st.session_state: st.session_state['em_verificacao_2fa'] = False
if 'codigo_2fa_esperado' not in st.session_state: st.session_state['codigo_2fa_esperado'] = ""
if 'dados_usuario_temp' not in st.session_state: st.session_state['dados_usuario_temp'] = {}

# --- CSS DINÂMICO (CORREÇÃO DEFINITIVA DE BOTÕES E LAYOUT) ---
css_comum = """
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;800;900&display=swap');
    
    html, body, [class*="css"], .stMarkdown, .stText, p, h1, h2, h3, h4, span, div {
        font-family: 'Poppins', sans-serif;
        color: #31333F !important; 
    }
    input, textarea, select {
        color: #31333F !important;
        background-color: #ffffff !important;
    }
    .header-style h2, .header-style p, .header-style span, .header-style div {
        color: white !important;
    }
    button[kind="primary"] p, button[kind="primary"] div {
        color: white !important;
    }

    header { visibility: hidden; }
    .stDeployButton { display: none; }
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
    
    [data-testid="stImage"] img { 
        height: 180px !important; 
        object-fit: contain !important; 
        border-radius: 10px; 
    }
    
    [data-testid="column"] {
        display: flex;
        flex-direction: column;
        justify-content: center;
        height: 100%;
    }

    /* === BANNER === */
    .header-style { 
        background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); 
        background-size: 400% 400%; 
        animation: gradient 10s ease infinite; 
        padding: 0 25px; 
        border-radius: 15px; 
        color: white; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.1); 
        display: flex; 
        flex-direction: column; 
        justify-content: center; 
        height: 110px !important; 
        margin: 0 !important;
    }
    .header-style h2 { font-size: 20px !important; font-weight: 700 !important; margin: 0 !important; }
    .header-style p { font-size: 12px !important; line-height: 1.3 !important; opacity: 0.9 !important; margin: 2px 0 0 0 !important; }
    .header-style .saldo-label { font-size: 10px !important; font-weight: 600 !important; }
    .header-style .saldo-valor { font-size: 30px !important; font-weight: 900 !important; text-shadow: 0 2px 4px rgba(0,0,0,0.15); }

    /* === BOTÕES DO HEADER (FORÇA BRUTA 110px) === */
    /* Aplica a todos os botões secundários da tela principal para alinhar com o banner */
    div.stButton > button[kind="secondary"] { 
        background-color: #ffffff !important; 
        color: #003366 !important; 
        border-radius: 12px !important; 
        border: 2px solid #eef2f6 !important; 
        height: 110px !important; 
        min-height: 110px !important; /* Garante que não encolha */
        font-weight: 600; 
        width: 100%; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); 
        margin: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 0 !important;
    }
    
    /* Garante que o container do botão também tenha a altura certa */
    div.stButton {
        height: 110px !important;
        min-height: 110px !important;
    }

    /* === CORREÇÃO: BOTÕES DA VITRINE/ABAS (DEVEM SER PEQUENOS) === */
    /* Aqui sobrescrevemos a regra de 110px para dentro das abas, voltando para 50px */
    [data-testid="stTabs"] div.stButton, 
    [data-testid="stTabs"] div.stButton > button { 
        height: 50px !important; 
        min-height: 50px !important; 
        border-radius: 8px !important; 
        margin-top: auto; 
    }
    
    [data-testid="stTabs"] button[kind="primary"] { 
        background-color: transparent !important; 
        border: 2px solid #0066cc !important; 
        color: #0066cc !important; 
        box-shadow: none !important; 
    }
    [data-testid="stTabs"] button[kind="primary"]:hover { 
        background-color: #e6f0ff !important; 
        transform: translateY(-2px); 
    }
    [data-testid="stTabs"] button[kind="secondary"] { 
        border: 1px solid #e0e0e0 !important; 
        color: #555 !important;
    }

    /* === CORREÇÃO: BOTÕES DO LOGIN (DEVEM SER NORMAIS) === */
    [data-testid="stForm"] div.stButton,
    [data-testid="stForm"] div.stButton > button {
        height: 50px !important;
        min-height: 50px !important;
    }

    /* ESTILOS DA RIFA */
    .rifa-card { border: 2px solid #FFD700; background: linear-gradient(to bottom right, #fffdf0, #ffffff); padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .rifa-tag { background-color: #FFD700; color: #000; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 12px; margin-bottom: 10px; display: inline-block; }
    .winner-card { border: 2px solid #28a745; background: linear-gradient(to bottom right, #f0fff4, #ffffff); padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .winner-tag { background-color: #28a745; color: #fff; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 12px; margin-bottom: 10px; display: inline-block; }

    /* MOBILE */
    @media only screen and (max-width: 600px) {
        .header-style { height: auto !important; padding: 15px !important; text-align: center !important; }
        div.stButton > button[kind="secondary"], div.stButton { height: 60px !important; min-height: 60px !important; }
    }
"""

if not st.session_state.get('logado', False):
    estilo_especifico = """
    .stApp { background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); background-size: 400% 400%; animation: gradient 15s ease infinite; }
    [data-testid="stForm"] { background-color: #ffffff; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
    """
else:
    estilo_especifico = ".stApp { background-color: #f4f8fb; }"

st.markdown(f"<style>{css_comum} {estilo_especifico}</style>", unsafe_allow_html=True)

# --- FUNÇÕES BÁSICAS (AGORA NO TOPO PARA EVITAR ERROS) ---
def processar_link_imagem(url):
    url = str(url).strip()
    if "github.com" in url and "/blob/" in url: return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    if "drive.google.com" in url:
        if "id=" in url: return url
        try: file_id = url.split("/")[-2]; return f"https://drive.google.com/uc?export=view&id={file_id}"
        except: return url
    return url

def verificar_senha_hash(senha_digitada, hash_armazenado):
    try:
        if not hash_armazenado.startswith("$2b$"): return senha_digitada == hash_armazenado
        return bcrypt.checkpw(senha_digitada.encode('utf-8'), hash_armazenado.encode('utf-8'))
    except Exception: return False

def gerar_hash(senha):
    return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def gerar_senha_aleatoria(tamanho=6):
    caracteres = string.ascii_uppercase + string.digits
    return ''.join(random.choice(caracteres) for _ in range(tamanho))

def formatar_telefone(tel):
    apenas_numeros = re.sub(r'\D', '', str(tel))
    if 10 <= len(apenas_numeros) <= 11: apenas_numeros = "55" + apenas_numeros
    return apenas_numeros

# --- GERENCIAMENTO DE SESSÃO ---
def criar_sessao_persistente(usuario_id):
    token = str(uuid.uuid4())
    with conn.session as s:
        s.execute(text("UPDATE usuarios SET token_sessao = :t WHERE id = :id"), {"t": token, "id": usuario_id})
        s.commit()
    st.query_params["sessao"] = token

def verificar_sessao_automatica():
    if st.session_state.get('logado', False): return
    token_url = st.query_params.get("sessao")
    if token_url:
        df = run_query("SELECT * FROM usuarios WHERE token_sessao = :t", {"t": token_url})
        if not df.empty:
            row = df.iloc[0]
            st.session_state.update({
                'logado': True,
                'usuario_cod': row['usuario'],
                'usuario_nome': row['nome'],
                'tipo_usuario': str(row['tipo']).lower().strip(),
                'saldo_atual': float(row['saldo']),
                'valor_ponto_usuario': float(row.get('valor_ponto', 0.50) or 0.50)
            })
            st.rerun()

def realizar_logout():
    if st.session_state.get('usuario_cod'):
        with conn.session as s:
            s.execute(text("UPDATE usuarios SET token_sessao = NULL WHERE usuario = :u"), {"u": st.session_state.usuario_cod})
            s.commit()
    st.query_params.clear()
    st.session_state.clear()
    st.rerun()

# --- FUNÇÕES DE ENVIO ---
def enviar_sms(telefone, mensagem_texto):
    try:
        base_url = st.secrets["INFOBIP_BASE_URL"].rstrip('/')
        api_key = st.secrets["INFOBIP_API_KEY"]
        url = f"{base_url}/sms/2/text/advanced"
        tel_final = formatar_telefone(telefone)
        if len(tel_final) < 12: return False, f"Num Inválido: {tel_final}", "CLIENT_ERROR"
        payload = { "messages": [ { "from": "InfoSMS", "destinations": [{"to": tel_final}], "text": mensagem_texto } ] }
        headers = { "Authorization": f"App {api_key}", "Content-Type": "application/json", "Accept": "application/json" }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code not in [200, 201]: return False, f"Erro SMS {response.status_code}: {response.text}", str(response.status_code)
        return True, "SMS Enviado", str(response.status_code)
    except Exception as e: return False, f"Erro SMS Exception: {str(e)}", "EXCEPTION"

def enviar_whatsapp_template(telefone, parametros, nome_template="atualizar_envio_pedidos"):
    try:
        base_url = st.secrets["INFOBIP_BASE_URL"].rstrip('/')
        api_key = st.secrets["INFOBIP_API_KEY"]
        sender = st.secrets["INFOBIP_SENDER"]
        url = f"{base_url}/whatsapp/1/message/template"
        tel_final = formatar_telefone(telefone)
        if len(tel_final) < 12: return False, f"Número inválido: {tel_final}", "CLIENT_ERROR"
        payload = { "messages": [ { "from": sender, "to": tel_final, "content": { "templateName": nome_template, "templateData": { "body": { "placeholders": parametros } }, "language": "pt_BR" } } ] }
        headers = { "Authorization": f"App {api_key}", "Content-Type": "application/json", "Accept": "application/json" }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code not in [200, 201]: return False, f"Erro API {response.status_code}: {response.text}", str(response.status_code)
        return True, "Enviado com Sucesso", str(response.status_code)
    except Exception as e: return False, f"Erro Conexão: {str(e)}", "EXCEPTION"

# --- BANCO DE DADOS ---
def run_query(query_str, params=None): return conn.query(query_str, params=params, ttl=0)
def run_transaction(query_str, params=None):
    with conn.session as s: s.execute(text(query_str), params if params else {}); s.commit()

def registrar_log(acao, detalhes):
    try:
        resp = st.session_state.get('usuario_nome', 'Sistema')
        run_transaction("INSERT INTO logs (data, responsavel, acao, detalhes) VALUES (NOW(), :resp, :acao, :det)", {"resp": resp, "acao": acao, "det": detalhes})
    except Exception as e: print(f"Erro log: {e}")

# --- LÓGICA DE NEGÓCIO ---
def validar_login(user_input, pass_input):
    df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": user_input.strip()})
    if df.empty: return False, None, None, 0, None, None, 0.50
    linha = df.iloc[0]
    if verificar_senha_hash(pass_input.strip(), linha['senha']):
        v_ponto = float(linha.get('valor_ponto', 0.50) or 0.50)
        return True, linha['nome'], str(linha['tipo']).lower().strip(), float(linha['saldo']), str(linha['telefone']), int(linha['id']), v_ponto
    return False, None, None, 0, None, None, 0.50

def salvar_venda(usuario_cod, item_nome, custo, email_contato, telefone_resgate):
    try:
        user_df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario_cod})
        if user_df.empty: return False
        if float(user_df.iloc[0]['saldo']) < custo: st.error("Saldo insuficiente."); return False
        with conn.session as s:
            s.execute(text("UPDATE usuarios SET saldo = saldo - :custo WHERE LOWER(usuario) = LOWER(:u)"), {"custo": custo, "u": usuario_cod})
            s.execute(text("INSERT INTO vendas (data, usuario, item, valor, status, email, nome_real, telefone) VALUES (NOW(), :u, :item, :valor, 'Pendente', :email, :nome, :tel)"),
                {"u": usuario_cod, "item": item_nome, "valor": custo, "email": email_contato, "nome": user_df.iloc[0]['nome'], "tel": telefone_resgate})
            s.commit()
        registrar_log("Resgate", f"Usuário: {user_df.iloc[0]['nome']} | Item: {item_nome}")
        st.session_state['saldo_atual'] -= custo
        return True
    except Exception as e: st.error(f"Erro: {e}"); return False

def comprar_ticket_rifa(rifa_id, custo, usuario_cod):
    try:
        user_df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario_cod})
        if user_df.empty: return False, "Usuário não encontrado"
        custo_real = float(custo)
        if float(user_df.iloc[0]['saldo']) < custo_real: return False, "Saldo insuficiente"
        with conn.session as s:
            s.execute(text("UPDATE usuarios SET saldo = saldo - :custo WHERE LOWER(usuario) = LOWER(:u)"), 
                      {"custo": custo_real, "u": usuario_cod})
            s.execute(text("INSERT INTO rifa_tickets (rifa_id, usuario) VALUES (:rid, :u)"), 
                      {"rid": int(rifa_id), "u": usuario_cod})
            s.commit()
        st.session_state['saldo_atual'] -= custo_real
        registrar_log("Rifa", f"Comprou ticket rifa {rifa_id}")
        return True, "Ticket comprado com sucesso!"
    except Exception as e: return False, f"Erro: {str(e)}"

def cadastrar_novo_usuario(usuario, senha, nome, saldo, tipo, telefone, valor_ponto=0.50):
    try:
        df = run_query("SELECT id FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario})
        if not df.empty: return False, "Usuário já existe!"
        run_transaction("INSERT INTO usuarios (usuario, senha, nome, saldo, pontos_historico, tipo, telefone, valor_ponto) VALUES (:u, :s, :n, :bal, :bal, :t, :tel, :vp)",
            {"u": usuario, "s": gerar_hash(senha), "n": nome, "bal": saldo, "t": tipo, "tel": formatar_telefone(telefone), "vp": valor_ponto})
        registrar_log("Novo Cadastro", f"Criou usuário: {usuario}")
        return True, "Cadastrado com sucesso!"
    except Exception as e: return False, f"Erro: {str(e)}"

def distribuir_pontos_multiplos(lista_usuarios, quantidade):
    try:
        if "Todos" in lista_usuarios:
            run_transaction("UPDATE usuarios SET saldo = saldo + :q, pontos_historico = COALESCE(pontos_historico, 0) + :q WHERE tipo NOT IN ('admin', 'staff')", {"q": quantidade})
            msg = f"Adicionou {quantidade} pts para TODOS."
        else:
            with conn.session as s:
                s.execute(
                    text("UPDATE usuarios SET saldo = saldo + :q, pontos_historico = COALESCE(pontos_historico, 0) + :q WHERE usuario IN :users"),
                    {"q": quantidade, "users": tuple(lista_usuarios)}
                )
                s.commit()
            msg = f"Adicionou {quantidade} pts para {len(lista_usuarios)} usuários."
        registrar_log("Distribuição Pontos", msg)
        return True
    except Exception as e: return False

# --- MODAIS ---
@st.dialog("🔐 Alterar Senha")
def abrir_modal_senha(usuario_cod):
    n = st.text_input("Nova Senha", type="password"); c = st.text_input("Confirmar", type="password")
    if st.button("Salvar Senha", type="primary"):
        if n == c and n:
            run_transaction("UPDATE usuarios SET senha = :s WHERE LOWER(usuario) = LOWER(:u)", {"s": gerar_hash(n), "u": usuario_cod})
            registrar_log("Senha Alterada", f"Usuário: {usuario_cod}")
            st.success("Sucesso!"); time.sleep(1); st.session_state['logado'] = False; st.rerun()

@st.dialog("🔑 Gerar Senha Provisória")
def abrir_modal_resete_senha(titulo_janela="Recuperar Senha"):
    st.write(f"**{titulo_janela}**")
    st.write("Digite o nome de usuário (login). Se ele existir, enviaremos uma senha provisória via SMS para o telefone cadastrado.")
    user_input = st.text_input("Usuário (Login)")
    
    if st.button("Gerar e Enviar SMS", type="primary"):
        df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": user_input.strip()})
        if df.empty:
            st.error("Usuário não encontrado.")
        else:
            row = df.iloc[0]
            tel = str(row['telefone'])
            if len(formatar_telefone(tel)) < 12:
                st.error("O telefone cadastrado para este usuário parece inválido. Contate o suporte.")
                return
            nova_senha = gerar_senha_aleatoria()
            nova_senha_hash = gerar_hash(nova_senha)
            user_id = int(row['id']) 
            with conn.session as s:
                s.execute(text("UPDATE usuarios SET senha = :s WHERE id = :id"), {"s": nova_senha_hash, "id": user_id})
                s.commit()
            msg = f"Sua senha provisoria e: {nova_senha}. Acesse e troque."
            ok, det, cod = enviar_sms(tel, msg)
            if ok:
                st.success(f"Sucesso! Senha enviada para o final ...{tel[-4:]}.")
                registrar_log(titulo_janela, f"Usuário: {row['usuario']}")
                time.sleep(4); st.rerun()
            else:
                st.error(f"Erro ao enviar SMS: {det}")

@st.dialog("🎁 Confirmar Resgate")
def confirmar_resgate_dialog(item_nome, custo, usuario_cod):
    st.write(f"Resgatando: **{item_nome}** por **{custo} pts**.")
    with st.form("form_resgate"):
        email = st.text_input("E-mail:", placeholder="exemplo@email.com")
        tel = st.text_input("WhatsApp (DDD+Num):", placeholder="Ex: 34999998888")
        if st.form_submit_button("CONFIRMAR", type="primary", use_container_width=True):
            if "@" not in email: st.error("E-mail inválido."); return
            if len(formatar_telefone(tel)) < 12: st.error("Telefone inválido!"); return
            if salvar_venda(usuario_cod, item_nome, custo, email, formatar_telefone(tel)):
                st.balloons(); st.success("Sucesso!"); time.sleep(2); st.rerun()

@st.dialog("🎟️ Comprar Ticket Rifa")
def confirmar_compra_ticket(rifa_id, item_nome, custo, usuario_cod):
    st.write(f"Você está comprando um ticket para sortear: **{item_nome}**")
    st.write(f"Custo: **{custo} pts**")
    st.info("Quanto mais tickets comprar, maior a chance de ganhar!")
    if st.button("CONFIRMAR COMPRA", type="primary", use_container_width=True):
        ok, msg = comprar_ticket_rifa(rifa_id, custo, usuario_cod)
        if ok:
            st.balloons(); st.success(msg); time.sleep(2); st.rerun()
        else:
            st.error(msg)

@st.dialog("🎉 TEMOS UM VENCEDOR!")
def mostrar_vencedor_dialog(nome_vencedor, usuario_vencedor, nome_premio, imagem_premio):
    st.balloons()
    if imagem_premio: st.image(processar_link_imagem(imagem_premio), width=300)
    st.markdown(f"<h2 style='text-align:center; color:#28a745;'>{nome_vencedor}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center;'>({usuario_vencedor})</p>", unsafe_allow_html=True)
    st.success(f"Parabéns! Você ganhou: {nome_premio}")
    st.info("O prêmio já foi adicionado aos seus pedidos.")

@st.dialog("🔍 Detalhes do Produto")
def ver_detalhes_produto(item, imagem, custo, descricao):
    st.image(processar_link_imagem(imagem), use_container_width=True)
    st.markdown(f"## {item}")
    st.markdown(f"#### 💎 Valor: **{custo} pts**")
    st.divider()
    st.write("### 📝 Descrição")
    if descricao and str(descricao).lower() != "none" and len(str(descricao)) > 3: st.write(descricao)
    else: st.caption("Sem descrição adicional para este item.")
    st.divider()
    st.info("ℹ️ **Informações de Entrega:**\nEste item será enviado para o endereço ou contato cadastrado. O prazo de processamento é de até 5 dias úteis.")

@st.dialog("🚀 Confirmar e Processar Envios", width="large")
def processar_envios_dialog(df_selecionados, usar_zap, usar_sms, tipo_envio="vendas"):
    st.write(f"Você selecionou **{len(df_selecionados)} destinatários**.")
    st.markdown(f"""
        <div style='background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-bottom: 10px;'>
            <b>Canais Selecionados:</b> {'✅ WhatsApp' if usar_zap else '❌ WhatsApp'} | {'✅ SMS' if usar_sms else '❌ SMS'}
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("CONFIRMAR E DISPARAR", type="primary", use_container_width=True):
        logs_envio = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        total = len(df_selecionados)
        for i, (index, row) in enumerate(df_selecionados.iterrows()):
            status_text.text(f"Processando {i+1}/{total}: {row.get('nome', '')}...")
            tel = str(row['telefone'])
            if tipo_envio == "vendas":
                nome = str(row['nome_real'] or row['usuario'])
                var1 = str(row['item'])
                var2 = str(row['codigo_vale'])
            else: 
                nome = str(row['nome'])
                try: var1 = f"{float(row['saldo']):,.0f}"
                except: var1 = "0"
                var2 = ""

            if usar_zap:
                if len(formatar_telefone(tel)) >= 12:
                    if tipo_envio == "vendas":
                        ok, det, cod = enviar_whatsapp_template(tel, [nome, var1, var2], "atualizar_envio_pedidos")
                    else:
                        ok, det, cod = enviar_whatsapp_template(tel, [nome, var1], "atualizar_saldo_pedidos")
                    logs_envio.append({"Nome": nome, "Tel": tel, "Canal": "WhatsApp", "Status": "✅ OK" if ok else "❌ Erro", "Detalhe API": det})
                else:
                    logs_envio.append({"Nome": nome, "Tel": tel, "Canal": "WhatsApp", "Status": "⚠️ Ignorado", "Detalhe API": "Número Inválido"})

            if usar_sms:
                if len(formatar_telefone(tel)) >= 12:
                    if tipo_envio == "vendas": texto = f"Ola {nome}, seu resgate de {var1} foi liberado! Cod: {var2}."
                    else: texto = f"Lojinha Culli: Ola {nome}, sua pontuacao foi atualizada e seu saldo atual e de {var1}. Acesse o site e realize a troca dos pontos: https://lojinha-culligan.streamlit.app/"
                    ok, det, cod = enviar_sms(tel, texto)
                    logs_envio.append({"Nome": nome, "Tel": tel, "Canal": "SMS", "Status": "✅ OK" if ok else "❌ Erro", "Detalhe API": det})
                else:
                    logs_envio.append({"Nome": nome, "Tel": tel, "Canal": "SMS", "Status": "⚠️ Ignorado", "Detalhe API": "Número Inválido"})
            progress_bar.progress((i + 1) / total)

        progress_bar.empty()
        status_text.success("Processamento Finalizado!")
        sucessos = len([x for x in logs_envio if "OK" in x['Status']])
        erros = len(logs_envio) - sucessos
        c1, c2 = st.columns(2)
        c1.metric("✅ Sucessos", sucessos)
        c2.metric("❌ Falhas/Ignorados", erros)
        registrar_log("Disparo em Massa", f"Tipo: {tipo_envio} | Qtd: {total}")
        with st.expander("📄 Ver Detalhes (Log Completo)"): st.dataframe(pd.DataFrame(logs_envio), use_container_width=True)
        st.download_button(label="📥 Baixar Extrato (CSV)", data=pd.DataFrame(logs_envio).to_csv(index=False).encode('utf-8'), file_name=f'log_{datetime.now().strftime("%Y%m%d_%H%M")}.csv', mime='text/csv')
        if st.button("Fechar Janela"): st.rerun()

# --- TELAS ---
def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.write("") 
        
        if st.session_state.get('em_verificacao_2fa', False):
            with st.form("f_2fa"):
                st.markdown("""<div style="text-align: center; margin-bottom: 20px;"><h2 style="color: #003366;">🔒 Segurança</h2><p>Enviamos um código SMS para o final <b>...{}</b></p></div>""".format(str(st.session_state.dados_usuario_temp.get('telefone', ''))[-4:]), unsafe_allow_html=True)
                codigo_digitado = st.text_input("Digite o Código de 6 dígitos", max_chars=6, help="Verifique seu SMS")
                if st.form_submit_button("VALIDAR ACESSO", type="primary", use_container_width=True):
                    if codigo_digitado == st.session_state.codigo_2fa_esperado:
                        dados = st.session_state.dados_usuario_temp
                        st.session_state.update({
                            'logado': True, 'usuario_cod': dados['usuario'], 'usuario_nome': dados['nome'],
                            'tipo_usuario': dados['tipo'], 'saldo_atual': dados['saldo'],
                            'valor_ponto_usuario': dados.get('valor_ponto', 0.50), 'em_verificacao_2fa': False, 'dados_usuario_temp': {}
                        })
                        criar_sessao_persistente(dados['id'])
                        st.rerun()
                    else: st.error("Código incorreto. Tente novamente.")
            if st.button("⬅️ Voltar", type="secondary", use_container_width=True):
                st.session_state.em_verificacao_2fa = False
                st.session_state.dados_usuario_temp = {}
                st.rerun()
        else:
            with st.form("f_login"):
                st.markdown("""<div style="text-align: center; margin-bottom: 20px;"><h1 style="color: #003366; font-weight: 900; font-size: 2.8rem; margin: 0; margin-bottom: -15px; line-height: 1;">Lojinha Culli's</h1><p style="color: #555555; font-size: 0.9rem; line-height: 1.2; font-weight: 400; margin: 0; margin-top: 0px;">Realize seu login para resgatar seus pontos<br>e acompanhar seus pedidos.</p></div>""", unsafe_allow_html=True)
                u = st.text_input("Usuário"); s = st.text_input("Senha", type="password")
                st.write("") 
                if st.form_submit_button("ENTRAR", type="primary", use_container_width=True):
                    ok, n, t, sld, tel_completo, uid, v_ponto = validar_login(u, s)
                    if ok:
                        codigo = str(random.randint(100000, 999999))
                        msg_2fa = f"Seu codigo de acesso Culli: {codigo}"
                        enviou, info, _ = enviar_sms(tel_completo, msg_2fa)
                        if enviou:
                            st.session_state.em_verificacao_2fa = True
                            st.session_state.codigo_2fa_esperado = codigo
                            st.session_state.dados_usuario_temp = {'usuario': u, 'nome': n, 'tipo': t, 'saldo': sld, 'telefone': tel_completo, 'id': uid, 'valor_ponto': v_ponto}
                            st.rerun()
                        else: st.error(f"Erro no envio do SMS: {info}. Verifique se o telefone está correto no cadastro.")
                    else: st.toast("Usuário ou senha incorretos", icon="❌")
            st.write("")
            c_esqueceu, c_primeiro = st.columns(2)
            with c_esqueceu:
                if st.button("Esqueci a senha", type="secondary", use_container_width=True): abrir_modal_resete_senha("Recuperar Senha")
            with c_primeiro:
                if st.button("Primeiro Acesso?", type="secondary", use_container_width=True): abrir_modal_resete_senha("Primeiro Acesso")

def tela_admin():
    st.subheader("🛠️ Painel Admin")
    t1, t2, t3, t4, t5 = st.tabs(["📊 Entregas", "👥 Usuários", "🎁 Prêmios", "🛠️ Logs", "🎟️ Sorteio"])
    
    with t1:
        df_v = run_query("SELECT * FROM vendas ORDER BY id DESC")
        if not df_v.empty:
            lista_status = df_v['status'].dropna().unique().tolist()
            filtro_status = st.multiselect("🔍 Filtrar por Status:", options=lista_status, placeholder="Selecione para filtrar (Vazio = Todos)")
            if filtro_status: df_v = df_v[df_v['status'].isin(filtro_status)]
            if "Enviar" not in df_v.columns: df_v.insert(0, "Enviar", False)
            edit_v = st.data_editor(df_v, use_container_width=True, hide_index=True, key="ed_vendas", column_config={"Enviar": st.column_config.CheckboxColumn("Enviar?", default=False), "recebido_user": st.column_config.CheckboxColumn("Recebido pelo Usuário?", disabled=True)})
            st.markdown("<br>", unsafe_allow_html=True)
            c_check_zap_1, c_check_sms_1, c_btn_save_1, c_btn_send_1 = st.columns([0.8, 0.8, 1.2, 1.5])
            with c_check_zap_1: usar_zap = st.checkbox("WhatsApp", value=True, key="chk_zap_vendas_tab1") 
            with c_check_sms_1: usar_sms = st.checkbox("SMS", value=False, key="chk_sms_vendas_tab1") 
            with c_btn_save_1:
                if st.button("💾 Salvar Tabela", use_container_width=True, key="btn_save_vendas"):
                    st.cache_data.clear() 
                    try:
                        with conn.session as s:
                            for i, row in edit_v.iterrows():
                                s.execute(text("UPDATE vendas SET item=:item, valor=:valor, codigo_vale=:c, status=:st, nome_real=:n, telefone=:t, email=:e WHERE id=:id"), {"item": str(row['item']), "valor": float(row['valor']), "c": str(row['codigo_vale']), "st": str(row['status']), "n": str(row['nome_real']), "t": str(row['telefone']), "e": str(row.get('email', '')), "id": int(row['id'])})
                            s.commit()
                        registrar_log("Admin", "Editou vendas"); st.success("Salvo com sucesso!"); time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Erro ao salvar: {e}")
            with c_btn_send_1:
                if st.button("📤 Enviar Selecionados", type="primary", use_container_width=True):
                    sel = edit_v[edit_v['Enviar'] == True]
                    if sel.empty: st.warning("Ninguém selecionado.")
                    else: processar_envios_dialog(sel, usar_zap, usar_sms, tipo_envio="vendas")

    with t2:
        with st.expander("💎 Configurar Valor do Ponto Individualizado"):
            st.info("Utilize esta ferramenta para definir quanto vale 1 ponto para um usuário específico.")
            df_users_list = run_query("SELECT id, usuario, nome, valor_ponto FROM usuarios ORDER BY nome")
            
            if not df_users_list.empty:
                opcoes_user = {f"{row['nome']} ({row['usuario']})": row['id'] for i, row in df_users_list.iterrows()}
                user_selecionado_chave = st.selectbox("Selecione o Usuário:", list(opcoes_user.keys()))
                user_id_sel = opcoes_user[user_selecionado_chave]
                valor_atual = df_users_list[df_users_list['id'] == user_id_sel]['valor_ponto'].iloc[0]
                if pd.isna(valor_atual): valor_atual = 0.50
                novo_valor_ponto = st.number_input(f"Valor do Ponto para {user_selecionado_chave} (R$)", value=float(valor_atual), step=0.01, format="%.2f")
                if st.button("💾 Salvar Valor Personalizado", type="primary"):
                    try:
                        run_transaction("UPDATE usuarios SET valor_ponto = :vp WHERE id = :id", {"vp": novo_valor_ponto, "id": user_id_sel})
                        st.cache_data.clear(); st.success(f"Atualizado! Para este usuário, 1 Ponto agora vale R$ {novo_valor_ponto:.2f}"); time.sleep(2); st.rerun()
                    except Exception as e: st.error(f"Erro: {e}")

        with st.expander("➕ Cadastrar Novo Usuário"):
            with st.form("form_novo"):
                c_n1, c_n2 = st.columns(2)
                u = c_n1.text_input("Usuário"); s = c_n2.text_input("Senha")
                n = c_n1.text_input("Nome"); t = c_n2.text_input("Telefone")
                bal = c_n1.number_input("Saldo", step=100.0); tp = c_n2.selectbox("Tipo", ["comum", "admin", "staff"])
                vp = c_n1.number_input("Valor do Ponto (R$)", value=0.50, step=0.01)
                if st.form_submit_button("Cadastrar"):
                    ok, msg = cadastrar_novo_usuario(u, s, n, bal, tp, t, vp)
                    if ok: st.cache_data.clear(); st.success(msg); time.sleep(1.5); st.rerun()
                    else: st.error(msg)
        
        with st.expander("💰 Distribuir Pontos (Soma no Ranking)", expanded=False):
            c_d1, c_d2, c_d3 = st.columns([2, 1, 1])
            df_users_list_dist = run_query("SELECT usuario FROM usuarios WHERE tipo NOT IN ('admin', 'staff') ORDER BY usuario")
            lista_users = df_users_list_dist['usuario'].tolist() if not df_users_list_dist.empty else []
            target_users = c_d1.multiselect("Selecione os Usuários", ["Todos"] + lista_users)
            qtd_pontos = c_d2.number_input("Pontos", step=50, value=0)
            if c_d3.button("➕ Creditar", type="primary", use_container_width=True):
                if qtd_pontos > 0 and target_users:
                    if distribuir_pontos_multiplos(target_users, qtd_pontos): st.cache_data.clear(); st.success("Creditado com sucesso!"); time.sleep(2); st.rerun()
                else: st.warning("Selecione alguém e um valor maior que 0.")

        st.divider()
        df_u = run_query("SELECT * FROM usuarios ORDER BY id") 
        if not df_u.empty:
            if "Notificar" not in df_u.columns: df_u.insert(0, "Notificar", False)
            edit_u = st.data_editor(df_u, use_container_width=True, key="ed_u", column_config={
                "Notificar": st.column_config.CheckboxColumn("Avisar?", default=False),
                "saldo": st.column_config.NumberColumn("Saldo (Gastar)", help="Dinheiro na carteira agora"),
                "pontos_historico": st.column_config.NumberColumn("Ranking (Total)", help="Total acumulado na vida (não zera)"),
                "tipo": st.column_config.SelectboxColumn("Tipo de Conta", options=["comum", "admin", "staff"], required=True),
                "valor_ponto": st.column_config.NumberColumn("Valor Ponto (R$)", format="%.2f")
            })
            st.markdown("<br>", unsafe_allow_html=True)
            c_check_zap_2, c_check_sms_2, c_btn_save_2, c_btn_send_2 = st.columns([0.8, 0.8, 1.2, 1.5])
            with c_check_zap_2: aviso_zap = st.checkbox("WhatsApp", value=True, key="chk_zap_saldos_tab2") 
            with c_check_sms_2: aviso_sms = st.checkbox("SMS", value=False, key="chk_sms_saldos_tab2") 
            with c_btn_save_2:
                if st.button("💾 Salvar Tabela", use_container_width=True, key="btn_save_users"):
                    st.cache_data.clear()
                    try:
                        with conn.session as s:
                            for i, row in edit_u.iterrows():
                                v_ponto_salvar = float(row.get('valor_ponto', 0.50) or 0.50)
                                s.execute(text("UPDATE usuarios SET saldo=:s, pontos_historico=:ph, telefone=:t, nome=:n, tipo=:tp, valor_ponto=:vp WHERE id=:id"), 
                                         {"s": float(row['saldo']), "ph": float(row['pontos_historico']), "t": str(row['telefone']), "n": str(row['nome']), "tp": str(row['tipo']), "vp": v_ponto_salvar, "id": int(row['id'])})
                            s.commit()
                        registrar_log("Admin", "Editou usuários na tabela"); st.success("Dados atualizados!"); time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Erro ao salvar: {e}")
            with c_btn_send_2:
                if st.button("📤 Enviar Avisos", type="primary", use_container_width=True):
                    sel = edit_u[edit_u['Notificar'] == True]
                    if sel.empty: st.warning("Ninguém selecionado.")
                    else: processar_envios_dialog(sel, aviso_zap, aviso_sms, tipo_envio="usuarios")

    with t3:
        with st.expander("⚙️ Reprecificação em Massa (Valor do Ponto)"):
            st.info("ℹ️ Utilize esta ferramenta para ajustar o preço de **TODOS** os produtos de uma só vez com base no valor do ponto em Reais.")
            c_base1, c_base2 = st.columns(2)
            valor_ponto_atual = c_base1.number_input("Valor ATUAL do Ponto (R$)", value=0.50, step=0.01, min_value=0.01, format="%.2f")
            valor_ponto_novo = c_base2.number_input("NOVO Valor do Ponto (R$)", value=0.50, step=0.01, min_value=0.01, format="%.2f")
            if valor_ponto_atual != valor_ponto_novo:
                st.write("---"); st.markdown("### 🔎 Simulação de Novos Preços")
                fator = valor_ponto_atual / valor_ponto_novo
                df_preview = run_query("SELECT id, item, custo FROM premios")
                if not df_preview.empty:
                    df_preview['custo_novo'] = (df_preview['custo'] * fator).astype(int)
                    df_preview['diferenca'] = df_preview['custo_novo'] - df_preview['custo']
                    st.dataframe(df_preview[['item', 'custo', 'custo_novo', 'diferenca']], use_container_width=True, hide_index=True)
                    st.warning(f"⚠️ **Atenção:** Esta ação irá alterar o preço de **{len(df_preview)} produtos**.")
                    if st.button("✅ CONFIRMAR REPRECIFICAÇÃO", type="primary"):
                        try:
                            with conn.session as sess:
                                for i, row in df_preview.iterrows():
                                    sess.execute(text("UPDATE premios SET custo = :c WHERE id = :id"), {"c": int(row['custo_novo']), "id": int(row['id'])})
                                sess.commit()
                            st.cache_data.clear(); st.balloons(); st.success("Preços atualizados com sucesso!"); time.sleep(2); st.rerun()
                        except Exception as e: st.error(f"Erro ao atualizar: {e}")

        st.divider()
        df_p = run_query("SELECT * FROM premios ORDER BY id")
        edit_p = st.data_editor(df_p, use_container_width=True, num_rows="dynamic", key="ed_p", column_config={"descricao": st.column_config.TextColumn("Descrição (Detalhes)", width="large")})
        if st.button("Salvar Prêmios"):
            st.cache_data.clear()
            try:
                with conn.session as sess:
                    for i, row in edit_p.iterrows():
                        if pd.notna(row['id']): 
                            sess.execute(text("UPDATE premios SET item=:i, imagem=:im, custo=:c, descricao=:d WHERE id=:id"), {"i": str(row['item']), "im": str(row['imagem']), "c": float(row['custo']), "d": str(row.get('descricao', '')), "id": int(row['id'])})
                        else:
                            if row['item']: sess.execute(text("INSERT INTO premios (item, imagem, custo, descricao) VALUES (:i, :im, :c, :d)"), {"i": str(row['item']), "im": str(row['imagem']), "c": float(row['custo']), "d": str(row.get('descricao', ''))})
                    sess.commit()
                st.success("Salvo!"); st.rerun()
            except Exception as e: st.error(f"Erro ao salvar prêmios: {e}")

    with t4: st.dataframe(run_query("SELECT * FROM logs ORDER BY id DESC LIMIT 50"), use_container_width=True)

    with t5:
        st.markdown("### 🎟️ Gestão de Sorteios/Rifas")
        rifa_ativa = run_query("SELECT * FROM rifas WHERE status = 'ativa'")
        if not rifa_ativa.empty:
            r = rifa_ativa.iloc[0]
            st.success(f"🔥 Sorteio Ativo: **{r['item_nome']}** (Custo: {r['custo_ticket']} pts)")
            qtd_tickets = run_query("SELECT COUNT(*) as qtd FROM rifa_tickets WHERE rifa_id = :rid", {"rid": int(r['id'])})
            total = qtd_tickets.iloc[0]['qtd']
            st.metric("Tickets Vendidos", total)
            st.divider()
            if st.button("🎲 SORTEAR VENCEDOR", type="primary"):
                if total == 0: st.error("Ninguém comprou ticket ainda!")
                else:
                    tickets = run_query("SELECT usuario FROM rifa_tickets WHERE rifa_id = :rid", {"rid": int(r['id'])})
                    vencedor = random.choice(tickets['usuario'].tolist())
                    user_data = run_query("SELECT * FROM usuarios WHERE usuario = :u", {"u": vencedor})
                    nome_real = user_data.iloc[0]['nome']; telefone = user_data.iloc[0]['telefone']
                    with conn.session as s:
                        s.execute(text("DELETE FROM rifa_tickets WHERE rifa_id = :rid"), {"rid": int(r['id'])})
                        s.execute(text("INSERT INTO vendas (data, usuario, item, valor, status, email, nome_real, telefone) VALUES (NOW(), :u, :item, 0, 'Sorteio', '', :n, :t)"), {"u": vencedor, "item": f"GANHADOR RIFA: {r['item_nome']}", "n": nome_real, "t": telefone})
                        s.execute(text("UPDATE rifas SET status = 'encerrada', ganhador_usuario = :u WHERE id = :id"), {"u": vencedor, "id": int(r['id'])})
                        s.commit()
                    img_premio = ""
                    df_p_img = run_query("SELECT imagem FROM premios WHERE id = :pid", {"pid": int(r['premio_id'])})
                    if not df_p_img.empty: img_premio = df_p_img.iloc[0]['imagem']
                    mostrar_vencedor_dialog(nome_real, vencedor, r['item_nome'], img_premio)
                    registrar_log("Sorteio", f"Vencedor: {vencedor} - Item: {r['item_nome']}"); time.sleep(5); st.rerun()
            if st.button("Cancelar Sorteio (Sem Vencedor)"):
                with conn.session as s:
                    s.execute(text("DELETE FROM rifa_tickets WHERE rifa_id = :rid"), {"rid": int(r['id'])})
                    s.execute(text("UPDATE rifas SET status = 'cancelada' WHERE id = :id"), {"id": int(r['id'])})
                    s.commit()
                st.warning("Cancelado e tickets limpos."); st.rerun()
        else:
            st.info("Nenhum sorteio ativo no momento. Configure um abaixo:")
            df_premios = run_query("SELECT id, item FROM premios")
            opcoes = {f"{row['id']} - {row['item']}": row['id'] for i, row in df_premios.iterrows()}
            escolha = st.selectbox("Escolha o Prêmio para Sortear:", list(opcoes.keys()))
            custo_rifa = st.number_input("Custo do Ticket (Pontos)", min_value=1, value=50)
            if st.button("🚀 INICIAR SORTEIO", type="primary"):
                premio_id = opcoes[escolha]; nome_premio = escolha.split(" - ", 1)[1]
                run_transaction("INSERT INTO rifas (premio_id, item_nome, custo_ticket, status) VALUES (:pid, :nome, :custo, 'ativa')", {"pid": premio_id, "nome": nome_premio, "custo": custo_rifa})
                st.success("Sorteio Criado!"); st.rerun()

def tela_principal():
    u_cod, u_nome, sld, tipo = st.session_state.usuario_cod, st.session_state.usuario_nome, st.session_state.saldo_atual, st.session_state.tipo_usuario
    valor_ponto_usuario = st.session_state.get('valor_ponto_usuario', 0.50)
    valor_padrao_ponto = 0.50 

    if tipo == 'admin':
        cols = st.columns([3, 0.6, 1.2, 0.6, 0.6], gap="small")
        c_banner, c_refresh, c_toggle, c_senha, c_sair = cols
    else:
        cols = st.columns([3, 1, 1], gap="medium")
        c_banner, c_senha, c_sair = cols; c_refresh = c_toggle = None

    with c_banner:
        st.markdown(f'''<div class="header-style"><div style="display:flex; justify-content:space-between; align-items:center;"><div><h2 style="margin:0; color:white;">Olá, {u_nome}! 👋</h2><p style="margin:0; opacity:0.9; color:white;">Agora você pode trocar seus pontos por prêmios incríveis!</p></div><div style="text-align:right; color:white;"><span class="saldo-label">SEU SALDO</span><br><span class="saldo-valor">{sld:,.0f}</span> pts</div></div></div>''', unsafe_allow_html=True)
    
    if c_refresh:
        with c_refresh:
            if st.button("🔄", help="Atualizar", type="secondary", use_container_width=True): st.cache_data.clear(); st.rerun()

    if c_toggle:
        with c_toggle:
            label = "👁️ Ver Loja" if st.session_state.admin_mode else "🛠️ Voltar"
            if st.button(label, type="secondary", use_container_width=True):
                st.session_state.admin_mode = not st.session_state.admin_mode; st.rerun()

    with c_senha:
        if st.button("🔐", help="Senha", type="secondary", use_container_width=True): abrir_modal_senha(u_cod)
    with c_sair:
        if st.button("❌", help="Sair", type="secondary", use_container_width=True): realizar_logout()

    st.divider()
    
    if tipo == 'admin' and st.session_state.admin_mode:
        tela_admin()
    else:
        t1, t2, t3, t4 = st.tabs(["🎁 Catálogo", "🍀 Sorteio", "📜 Meus Resgates", "🏆 Ranking"])
        with t1:
            df_p = run_query("SELECT * FROM premios ORDER BY id")
            if not df_p.empty:
                cols = st.columns(4)
                for i, row in df_p.iterrows():
                    with cols[i % 4]:
                        with st.container(border=True):
                            if row['imagem']: st.image(processar_link_imagem(row['imagem']))
                            custo = int(row['custo'] * (0.50 / valor_ponto_usuario))
                            st.markdown(f"**{row['item']}**")
                            st.markdown(f"<div style='color:#0066cc; font-weight:bold;'>{custo} pts</div>", unsafe_allow_html=True)
                            c_detalhe, c_resgate = st.columns([1, 1])
                            with c_detalhe:
                                if st.button("Detalhes", key=f"det_{row['id']}", help="Ver Detalhes", type="secondary", use_container_width=True): ver_detalhes_produto(row['item'], row['imagem'], custo, row.get('descricao', ''))
                            with c_resgate:
                                if sld >= custo:
                                    if st.button("RESGATAR", key=f"b_{row['id']}", type="primary", use_container_width=True): confirmar_resgate_dialog(row['item'], custo, u_cod)
        with t2:
            rifa_ativa = run_query("SELECT * FROM rifas WHERE status = 'ativa'")
            if not rifa_ativa.empty:
                r = rifa_ativa.iloc[0]; img_premio = ""
                df_p_img = run_query("SELECT imagem, descricao FROM premios WHERE id = :pid", {"pid": int(r['premio_id'])})
                if not df_p_img.empty: img_premio = df_p_img.iloc[0]['imagem']
                st.markdown(f"""<div class="rifa-card"><div class="rifa-tag">🍀 SORTEIO ATIVO</div><h3 style="margin:0; color:#333;">{r['item_nome']}</h3><p style="font-size:14px; color:#666;">Participe do sorteio exclusivo deste prêmio incrível!</p></div>""", unsafe_allow_html=True)
                c_img_rifa, c_info_rifa = st.columns([1, 2])
                with c_img_rifa:
                    if img_premio: st.image(processar_link_imagem(img_premio), use_container_width=True)
                with c_info_rifa:
                    st.markdown(f"#### Custo do Ticket: **{r['custo_ticket']} pts**")
                    my_tickets_count = 0
                    try:
                        df_count = run_query("SELECT COUNT(*) as qtd FROM rifa_tickets WHERE rifa_id = :rid AND usuario = :u", {"rid": int(r['id']), "u": u_cod})
                        if not df_count.empty: my_tickets_count = df_count.iloc[0]['qtd']
                    except: pass
                    if my_tickets_count > 0: st.success(f"🎟️ Você já tem: **{my_tickets_count} tickets**")
                    else: st.info("Você ainda não tem tickets.")
                    if st.button(f"🎟️ COMPRAR TICKET ({r['custo_ticket']} pts)", type="primary", use_container_width=True): confirmar_compra_ticket(int(r['id']), r['item_nome'], r['custo_ticket'], u_cod)
            else:
                rifa_encerrada = run_query("SELECT * FROM rifas WHERE status = 'encerrada' ORDER BY id DESC LIMIT 1")
                if not rifa_encerrada.empty:
                    r_fim = rifa_encerrada.iloc[0]; img_premio_fim = ""
                    df_p_img_fim = run_query("SELECT imagem FROM premios WHERE id = :pid", {"pid": int(r_fim['premio_id'])})
                    if not df_p_img_fim.empty: img_premio_fim = df_p_img_fim.iloc[0]['imagem']
                    nome_ganhador = r_fim['ganhador_usuario']
                    df_ganhador = run_query("SELECT nome FROM usuarios WHERE usuario = :u", {"u": nome_ganhador})
                    if not df_ganhador.empty: nome_ganhador = df_ganhador.iloc[0]['nome']
                    st.markdown(f"""<div class="winner-card"><div class="winner-tag">🏆 HALL DA FAMA</div><h3 style="margin:0; color:#333;">Parabéns, {nome_ganhador}!</h3><p style="font-size:14px; color:#666;">Foi o ganhador do último sorteio: <b>{r_fim['item_nome']}</b></p></div>""", unsafe_allow_html=True)
                    if img_premio_fim: st.image(processar_link_imagem(img_premio_fim), width=300)
                else: st.info("Nenhum sorteio ativo no momento.")
        with t3:
            st.info("### 📜 Acompanhamento\nPedido recebido! Prazo: **5 dias úteis** no seu Whatsapp informado no momento do resgate!.")
            meus_pedidos = run_query("SELECT id, data, item, valor, status, codigo_vale, recebido_user FROM vendas WHERE usuario = :u ORDER BY data DESC", {"u": u_cod})
            if not meus_pedidos.empty:
                editor_pedidos = st.data_editor(meus_pedidos, use_container_width=True, hide_index=True, key="editor_meus_pedidos", column_config={"id": st.column_config.TextColumn("ID", disabled=True), "data": st.column_config.DatetimeColumn("Data", disabled=True, format="DD/MM/YYYY"), "item": st.column_config.TextColumn("Item", disabled=True), "valor": st.column_config.NumberColumn("Valor", disabled=True), "status": st.column_config.TextColumn("Status", disabled=True), "codigo_vale": st.column_config.TextColumn("Código/Vale", disabled=True), "recebido_user": st.column_config.CheckboxColumn("Já Recebeu?", help="Marque se você já recebeu seu prêmio")}, disabled=["id", "data", "item", "valor", "status", "codigo_vale"])
                if st.button("💾 Confirmar Recebimento"):
                    with conn.session as s:
                        for i, row in editor_pedidos.iterrows():
                            if row['recebido_user']: s.execute(text("UPDATE vendas SET recebido_user = TRUE WHERE id = :id"), {"id": row['id']})
                            else: s.execute(text("UPDATE vendas SET recebido_user = FALSE WHERE id = :id"), {"id": row['id']})
                        s.commit()
                    st.toast("Status de recebimento atualizado!", icon="✅"); time.sleep(1); st.rerun()
            else: st.write("Nenhum pedido encontrado.")
        with t4:
            st.markdown("### 🏆 Top Users (Histórico)")
            st.caption("Este ranking considera todos os pontos já ganhos, independente se já foram gastos ou zerados.")
            df_rank = run_query("SELECT usuario, pontos_historico FROM usuarios WHERE tipo NOT IN ('admin', 'staff') ORDER BY pontos_historico DESC LIMIT 10")
            if not df_rank.empty:
                df_rank['pontos_historico'] = df_rank['pontos_historico'].fillna(0).astype(int)
                df_rank = df_rank.rename(columns={"usuario": "Usuário", "pontos_historico": "Pontos Acumulados"})
                st.dataframe(df_rank, use_container_width=True, hide_index=True)
            else: st.info("Ranking ainda vazio.")

if __name__ == "__main__":
    if st.session_state.get('logado', False): tela_principal()
    else: tela_login()
