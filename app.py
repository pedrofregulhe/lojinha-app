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

# --- INICIALIZAÇÃO DA SESSÃO ---
if 'logado' not in st.session_state: st.session_state['logado'] = False
if 'usuario_cod' not in st.session_state: st.session_state['usuario_cod'] = ""
if 'usuario_nome' not in st.session_state: st.session_state['usuario_nome'] = ""
if 'tipo_usuario' not in st.session_state: st.session_state['tipo_usuario'] = "comum"
if 'saldo_atual' not in st.session_state: st.session_state['saldo_atual'] = 0.0

if 'em_verificacao_2fa' not in st.session_state: st.session_state['em_verificacao_2fa'] = False
if 'codigo_2fa_esperado' not in st.session_state: st.session_state['codigo_2fa_esperado'] = ""
if 'dados_usuario_temp' not in st.session_state: st.session_state['dados_usuario_temp'] = {}

# --- CSS DINÂMICO ---
css_comum = """
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;900&display=swap');
    html, body, [class*="css"] { font-family: 'Poppins', sans-serif; }
    header { visibility: hidden; }
    .stDeployButton { display: none; }
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
    
    [data-testid="stImage"] img { height: 150px !important; object-fit: contain !important; border-radius: 10px; }
    
    /* ALINHAMENTO VERTICAL DAS COLUNAS */
    [data-testid="column"] {
        display: flex;
        flex-direction: column;
        justify-content: center;
        height: 100%;
    }

    /* --- ESTILO PADRÃO (HEADER) - BOTÕES GRANDES (100px) --- */
    
    /* Botão Primário (Azul) */
    div.stButton > button[kind="primary"] { 
        background-color: #0066cc !important; 
        color: white !important; 
        border-radius: 12px; 
        border: none; 
        height: 100px !important; /* Altura padrão Header */
        font-weight: 600; 
        width: 100%; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: all 0.2s ease;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #0052a3 !important;
        transform: translateY(-2px);
    }
    
    /* Botão Secundário (Branco) */
    div.stButton > button[kind="secondary"] { 
        background-color: #ffffff; 
        color: #003366; 
        border-radius: 12px; 
        border: 2px solid #eef2f6; 
        height: 100px !important; /* Altura padrão Header */
        font-weight: 600; 
        width: 100%; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); 
        transition: all 0.2s ease;
    }
    div.stButton > button[kind="secondary"]:hover { 
        border-color: #003366; 
        color: #003366; 
        background-color: #ffffff;
        transform: translateY(-2px);
    }

    /* --- OVERRIDE: BOTÕES DENTRO DAS ABAS (CARDS) - PEQUENOS (50px) --- */
    /* Essa regra força qualquer botão dentro das abas a ter 50px */
    [data-testid="stTabs"] div.stButton > button {
        height: 50px !important;
        min-height: 50px !important;
        border-radius: 8px !important;
    }

    .big-success { padding: 20px; background-color: #d4edda; color: #155724; border-radius: 10px; font-weight: bold; text-align: center; border: 1px solid #c3e6cb; margin-bottom: 10px; }
"""

if not st.session_state.get('logado', False):
    estilo_especifico = """
    .stApp { 
        background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); 
        background-size: 400% 400%; 
        animation: gradient 15s ease infinite; 
    }
    @keyframes gradient { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
    
    [data-testid="stForm"] { 
        background-color: #ffffff; 
        padding: 40px; 
        border-radius: 20px; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.2); 
        border: none; 
    }
    
    /* Reset do estilo secundário APENAS para a tela de login (links pequenos) */
    div.stButton > button[kind="secondary"] { 
        background-color: transparent !important; 
        color: white !important; 
        border: 1px solid rgba(255,255,255,0.3) !important; 
        border-radius: 20px !important;
        height: auto !important; 
        font-weight: 400; 
        font-size: 0.8rem;
        box-shadow: none !important;
    }
    div.stButton > button[kind="secondary"]:hover { 
        background-color: rgba(255,255,255,0.1) !important;
        border-color: white !important;
        transform: none !important;
    }
    
    /* Corrige o botão ENTRAR para não ficar gigante no login */
    [data-testid="stForm"] div.stButton > button[kind="primary"] {
        height: 50px !important;
    }
    """
else:
    estilo_especifico = """
    .stApp { background-color: #f4f8fb; }
    
    .header-style { 
        background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); 
        background-size: 400% 400%; 
        animation: gradient 10s ease infinite; 
        padding: 15px 25px; 
        border-radius: 15px; 
        color: white; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.1); 
        display: flex; 
        flex-direction: column; 
        justify-content: center; 
        height: 100px; /* Alinhado com os botões */
    }
    """

st.markdown(f"<style>{css_comum} {estilo_especifico}</style>", unsafe_allow_html=True)

# --- FUNÇÕES BÁSICAS ---
def verificar_senha_hash(senha_digitada, hash_armazenado):
    try:
        if not hash_armazenado.startswith("$2b$"): return senha_digitada == hash_armazenado
        return bcrypt.checkpw(senha_digitada.encode('utf-8'), hash_armazenado.encode('utf-8'))
    except ValueError: return False

def gerar_hash(senha):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha.encode('utf-8'), salt).decode('utf-8')

def gerar_senha_aleatoria(tamanho=6):
    caracteres = string.ascii_uppercase + string.digits
    return ''.join(random.choice(caracteres) for _ in range(tamanho))

def processar_link_imagem(url):
    url = str(url).strip()
    if "github.com" in url and "/blob/" in url: return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    if "drive.google.com" in url:
        if "id=" in url: return url
        try: file_id = url.split("/")[-2]; return f"https://drive.google.com/uc?export=view&id={file_id}"
        except: return url
    return url

def formatar_telefone(tel_bruto):
    texto = str(tel_bruto).strip()
    if texto.endswith(".0"): texto = texto[:-2]
    apenas_numeros = re.sub(r'\D', '', texto)
    if 10 <= len(apenas_numeros) <= 11: apenas_numeros = "55" + apenas_numeros
    return apenas_numeros

# --- GERENCIAMENTO DE SESSÃO (AUTO LOGIN) ---
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
                'saldo_atual': float(row['saldo'])
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

# --- LÓGICA ---
def validar_login(user_input, pass_input):
    df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": user_input.strip()})
    if df.empty: return False, None, None, 0, None, None
    linha = df.iloc[0]
    if verificar_senha_hash(pass_input.strip(), linha['senha']):
        return True, linha['nome'], str(linha['tipo']).lower().strip(), float(linha['saldo']), str(linha['telefone']), int(linha['id'])
    return False, None, None, 0, None, None

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

def cadastrar_novo_usuario(usuario, senha, nome, saldo, tipo, telefone):
    try:
        df = run_query("SELECT id FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario})
        if not df.empty: return False, "Usuário já existe!"
        run_transaction("INSERT INTO usuarios (usuario, senha, nome, saldo, pontos_historico, tipo, telefone) VALUES (:u, :s, :n, :bal, :bal, :t, :tel)",
            {"u": usuario, "s": gerar_hash(senha), "n": nome, "bal": saldo, "t": tipo, "tel": formatar_telefone(telefone)})
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
    st.write(f"Canais Ativos: {'✅ WhatsApp' if usar_zap else ''} {'✅ SMS' if usar_sms else ''}")
    
    if not usar_zap and not usar_sms:
        st.error("Nenhum canal de envio selecionado.")
        return

    st.warning("⚠️ **Atenção:** Ao clicar em Confirmar, o sistema iniciará o disparo. Não feche a janela até o fim.")
    
    if st.button("CONFIRMAR E DISPARAR", type="primary", use_container_width=True):
        logs_envio = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        total = len(df_selecionados)
        log_container = st.container(height=300, border=True)
        
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
                    logs_envio.append({"Nome": nome, "Tel": tel, "Canal": "WhatsApp", "Status": "✅ OK" if ok else "❌ Erro", "Detalhe API": det, "Cód": cod})
                else:
                    logs_envio.append({"Nome": nome, "Tel": tel, "Canal": "WhatsApp", "Status": "⚠️ Ignorado", "Detalhe API": "Número Inválido", "Cód": "-"})

            if usar_sms:
                if len(formatar_telefone(tel)) >= 12:
                    if tipo_envio == "vendas":
                        texto = f"Ola {nome}, seu resgate de {var1} foi liberado! Cod: {var2}."
                    else:
                        texto = f"Ola {nome}, saldo atualizado! Voce tem {var1} pts."
                    ok, det, cod = enviar_sms(tel, texto)
                    logs_envio.append({"Nome": nome, "Tel": tel, "Canal": "SMS", "Status": "✅ OK" if ok else "❌ Erro", "Detalhe API": det, "Cód": cod})
                else:
                    logs_envio.append({"Nome": nome, "Tel": tel, "Canal": "SMS", "Status": "⚠️ Ignorado", "Detalhe API": "Número Inválido", "Cód": "-"})

            progress_bar.progress((i + 1) / total)
            log_container.dataframe(pd.DataFrame(logs_envio), use_container_width=True, hide_index=True)

        progress_bar.empty()
        status_text.success("Processamento Finalizado!")
        registrar_log("Disparo em Massa", f"Tipo: {tipo_envio} | Qtd: {total}")
        st.download_button(label="📥 Baixar Extrato (CSV)", data=pd.DataFrame(logs_envio).to_csv(index=False).encode('utf-8'), file_name=f'log_{datetime.now().strftime("%Y%m%d_%H%M")}.csv', mime='text/csv')
        if st.button("Fechar e Atualizar"): st.rerun()

# --- TELAS ---
def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.write("") 
        
        if st.session_state.get('em_verificacao_2fa', False):
            with st.form("f_2fa"):
                st.markdown("""
                    <div style="text-align: center; margin-bottom: 20px;">
                        <h2 style="color: #003366;">🔒 Segurança</h2>
                        <p>Enviamos um código SMS para o final <b>...{}</b></p>
                    </div>
                """.format(str(st.session_state.dados_usuario_temp.get('telefone', ''))[-4:]), unsafe_allow_html=True)
                
                codigo_digitado = st.text_input("Digite o Código de 6 dígitos", max_chars=6, help="Verifique seu SMS")
                
                if st.form_submit_button("VALIDAR ACESSO", type="primary", use_container_width=True):
                    if codigo_digitado == st.session_state.codigo_2fa_esperado:
                        dados = st.session_state.dados_usuario_temp
                        st.session_state.update({
                            'logado': True,
                            'usuario_cod': dados['usuario'],
                            'usuario_nome': dados['nome'],
                            'tipo_usuario': dados['tipo'],
                            'saldo_atual': dados['saldo'],
                            'em_verificacao_2fa': False,
                            'dados_usuario_temp': {}
                        })
                        criar_sessao_persistente(dados['id'])
                        st.rerun()
                    else:
                        st.error("Código incorreto. Tente novamente.")
            
            if st.button("⬅️ Voltar", type="secondary", use_container_width=True):
                st.session_state.em_verificacao_2fa = False
                st.session_state.dados_usuario_temp = {}
                st.rerun()

        else:
            with st.form("f_login"):
                st.markdown("""
                    <div style="text-align: center; margin-bottom: 20px;">
                        <h1 style="color: #003366; font-weight: 900; font-size: 2.8rem; margin: 0; margin-bottom: 10px;">
                            LOJINHA CULLI
                        </h1>
                        <p style="color: #555555; font-size: 0.9rem; line-height: 1.4; font-weight: 400; margin: 0;">
                            Realize seu login para resgatar seus pontos<br>e acompanhar seus pedidos.
                        </p>
                    </div>
                """, unsafe_allow_html=True)
                u = st.text_input("Usuário"); s = st.text_input("Senha", type="password")
                st.write("") 
                
                if st.form_submit_button("ENTRAR", type="primary", use_container_width=True):
                    ok, n, t, sld, tel_completo, uid = validar_login(u, s)
                    if ok:
                        codigo = str(random.randint(100000, 999999))
                        msg_2fa = f"Seu codigo de acesso Culli: {codigo}"
                        enviou, info, _ = enviar_sms(tel_completo, msg_2fa)
                        
                        if enviou:
                            st.session_state.em_verificacao_2fa = True
                            st.session_state.codigo_2fa_esperado = codigo
                            st.session_state.dados_usuario_temp = {'usuario': u, 'nome': n, 'tipo': t, 'saldo': sld, 'telefone': tel_completo, 'id': uid}
                            st.rerun()
                        else:
                            st.error(f"Erro no envio do SMS: {info}. Verifique se o telefone está correto no cadastro.")
                    else:
                        st.toast("Usuário ou senha incorretos", icon="❌")
            
            st.write("")
            c_esqueceu, c_primeiro = st.columns(2)
            with c_esqueceu:
                if st.button("Esqueci a senha", type="secondary", use_container_width=True):
                    abrir_modal_resete_senha("Recuperar Senha")
            with c_primeiro:
                if st.button("Primeiro Acesso?", type="secondary", use_container_width=True):
                    abrir_modal_resete_senha("Primeiro Acesso")

def tela_admin():
    c_titulo, c_refresh = st.columns([4, 1])
    c_titulo.subheader("🛠️ Painel Admin")
    if c_refresh.button("🔄 Atualizar"): st.cache_data.clear(); st.toast("Sincronizado!", icon="✅"); time.sleep(1); st.rerun()
        
    t1, t2, t3, t4 = st.tabs(["📊 Entregas & WhatsApp", "👥 Usuários & Saldos", "🎁 Prêmios", "🛠️ Logs"])
    
    with t1:
        df_v = run_query("SELECT * FROM vendas ORDER BY id DESC")
        if not df_v.empty:
            lista_status = df_v['status'].dropna().unique().tolist()
            filtro_status = st.multiselect("🔍 Filtrar por Status:", options=lista_status, placeholder="Selecione para filtrar (Vazio = Todos)")
            if filtro_status: df_v = df_v[df_v['status'].isin(filtro_status)]

            if "Enviar" not in df_v.columns: df_v.insert(0, "Enviar", False)
            
            edit_v = st.data_editor(
                df_v, use_container_width=True, hide_index=True, key="ed_vendas", 
                column_config={
                    "Enviar": st.column_config.CheckboxColumn("Enviar?", default=False),
                    "recebido_user": st.column_config.CheckboxColumn("Recebido pelo Usuário?", disabled=True) 
                }
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            c_check_zap_1, c_check_sms_1, c_btn_save_1, c_btn_send_1 = st.columns([0.8, 0.8, 1.2, 1.5])
            with c_check_zap_1: usar_zap = st.checkbox("WhatsApp", value=True, key="chk_zap_vendas")
            with c_check_sms_1: usar_sms = st.checkbox("SMS", value=False, key="chk_sms_vendas")
            with c_btn_save_1:
                if st.button("💾 Salvar Tabela", use_container_width=True, key="btn_save_vendas"):
                    with conn.session as s:
                        for i, row in edit_v.iterrows():
                            s.execute(text("UPDATE vendas SET codigo_vale=:c, status=:st, nome_real=:n, telefone=:t WHERE id=:id"), {"c": row['codigo_vale'], "st": row['status'], "n": row['nome_real'], "t": row['telefone'], "id": row['id']})
                        s.commit()
                    registrar_log("Admin", "Editou vendas"); st.success("Salvo!"); time.sleep(1); st.rerun()
            with c_btn_send_1:
                if st.button("📤 Enviar Selecionados", type="primary", use_container_width=True):
                    sel = edit_v[edit_v['Enviar'] == True]
                    if sel.empty: st.warning("Ninguém selecionado.")
                    else: processar_envios_dialog(sel, usar_zap, usar_sms, tipo_envio="vendas")

    with t2:
        with st.expander("➕ Cadastrar Novo Usuário"):
            with st.form("form_novo"):
                c_n1, c_n2 = st.columns(2)
                u = c_n1.text_input("Usuário"); s = c_n2.text_input("Senha")
                n = c_n1.text_input("Nome"); t = c_n2.text_input("Telefone")
                bal = c_n1.number_input("Saldo", step=100.0); tp = c_n2.selectbox("Tipo", ["comum", "admin", "staff"])
                if st.form_submit_button("Cadastrar"):
                    ok, msg = cadastrar_novo_usuario(u, s, n, bal, tp, t)
                    if ok: st.success(msg); time.sleep(1.5); st.rerun()
                    else: st.error(msg)
        
        with st.expander("💰 Distribuir Pontos (Soma no Ranking)", expanded=False):
            st.info("Selecione uma ou mais pessoas para dar pontos. Soma no Saldo e no Ranking.")
            c_d1, c_d2, c_d3 = st.columns([2, 1, 1])
            df_users_list = run_query("SELECT usuario FROM usuarios WHERE tipo NOT IN ('admin', 'staff') ORDER BY usuario")
            lista_users = df_users_list['usuario'].tolist() if not df_users_list.empty else []
            target_users = c_d1.multiselect("Selecione os Usuários", ["Todos"] + lista_users)
            qtd_pontos = c_d2.number_input("Pontos", step=50, value=0)
            if c_d3.button("➕ Creditar", type="primary", use_container_width=True):
                if qtd_pontos > 0 and target_users:
                    if distribuir_pontos_multiplos(target_users, qtd_pontos): st.success("Creditado com sucesso!"); time.sleep(2); st.rerun()
                else: st.warning("Selecione alguém e um valor maior que 0.")

        st.divider()
        df_u = run_query("SELECT * FROM usuarios ORDER BY id") 
        if not df_u.empty:
            if "Notificar" not in df_u.columns: df_u.insert(0, "Notificar", False)
            edit_u = st.data_editor(df_u, use_container_width=True, key="ed_u", column_config={
                "Notificar": st.column_config.CheckboxColumn("Avisar?", default=False),
                "saldo": st.column_config.NumberColumn("Saldo (Gastar)", help="Dinheiro na carteira agora"),
                "pontos_historico": st.column_config.NumberColumn("Ranking (Total)", help="Total acumulado na vida (não zera)")
            })
            
            st.markdown("<br>", unsafe_allow_html=True)
            c_check_zap_2, c_check_sms_2, c_btn_save_2, c_btn_send_2 = st.columns([0.8, 0.8, 1.2, 1.5])
            with c_check_zap_2: aviso_zap = st.checkbox("WhatsApp", value=True, key="check_bal_zap")
            with c_check_sms_2: aviso_sms = st.checkbox("SMS", value=False, key="check_bal_sms")
            with c_btn_save_2:
                if st.button("💾 Salvar Tabela", use_container_width=True, key="btn_save_users"):
                    with conn.session as sess:
                        for i, row in edit_u.iterrows():
                            sess.execute(text("UPDATE usuarios SET saldo=:s, pontos_historico=:ph, telefone=:t, nome=:n, tipo=:tp WHERE id=:id"), 
                                     {"s": row['saldo'], "ph": row['pontos_historico'], "t": row['telefone'], "n": row['nome'], "tp": row['tipo'], "id": row['id']})
                        sess.commit()
                    registrar_log("Admin", "Editou usuários na tabela"); st.toast("Dados atualizados!", icon="✅"); time.sleep(1); st.rerun()
            with c_btn_send_2:
                if st.button("📤 Enviar Avisos", type="primary", use_container_width=True):
                    sel = edit_u[edit_u['Notificar'] == True]
                    if sel.empty: st.warning("Ninguém selecionado.")
                    else: processar_envios_dialog(sel, aviso_zap, aviso_sms, tipo_envio="usuarios")

    with t3:
        df_p = run_query("SELECT * FROM premios ORDER BY id")
        edit_p = st.data_editor(
            df_p, use_container_width=True, num_rows="dynamic", key="ed_p",
            column_config={"descricao": st.column_config.TextColumn("Descrição (Detalhes)", width="large")}
        )
        if st.button("Salvar Prêmios"):
            with conn.session as sess:
                for i, row in edit_p.iterrows():
                    if row['id']: 
                        sess.execute(text("UPDATE premios SET item=:i, imagem=:im, custo=:c, descricao=:d WHERE id=:id"), 
                            {"i": row['item'], "im": row['imagem'], "c": row['custo'], "d": row.get('descricao', ''), "id": row['id']})
                sess.commit()
            st.success("Salvo!"); st.rerun()

    with t4:
        st.dataframe(run_query("SELECT * FROM logs ORDER BY id DESC LIMIT 50"), use_container_width=True)

def tela_principal():
    u_cod, u_nome, sld, tipo = st.session_state.usuario_cod, st.session_state.usuario_nome, st.session_state.saldo_atual, st.session_state.tipo_usuario
    
    # --- LAYOUT NOVO: 3 COLUNAS ALINHADAS ---
    c_banner, c_senha, c_sair = st.columns([3, 1, 1], gap="medium")
    
    with c_banner:
        st.markdown(f'<div class="header-style"><div style="display:flex; justify-content:space-between; align-items:center;"><div><h2 style="margin:0; color:white;">Olá, {u_nome}! 👋</h2><p style="margin:0; opacity:0.9; color:white;">Bem Vindo (a) a Loja Culligan. Aqui você pode trocar seus pontos por prêmios incríveis! Aproveite!</p></div><div style="text-align:right; color:white;"><span style="font-size:12px; opacity:0.8;">SEU SALDO</span><br><span style="font-size:32px; font-weight:bold;">{sld:,.0f}</span> pts</div></div></div>', unsafe_allow_html=True)
    
    with c_senha:
        # Botão "Secundário" com altura forçada de 100px pelo CSS global
        if st.button("🔐 Alterar Senha", type="secondary", use_container_width=True): 
            abrir_modal_senha(u_cod)
            
    with c_sair:
        # Texto alterado para "Encerrar Sessão"
        if st.button("❌ Encerrar Sessão", type="secondary", use_container_width=True): 
            realizar_logout()
            
    st.divider()
    
    if tipo == 'admin': tela_admin()
    else:
        t1, t2, t3 = st.tabs(["🎁 Catálogo", "📜 Meus Resgates", "🏆 Ranking"])
        with t1:
            df_p = run_query("SELECT * FROM premios ORDER BY id") 
            if not df_p.empty:
                cols = st.columns(4)
                for i, row in df_p.iterrows():
                    with cols[i % 4]:
                        with st.container(border=True):
                            img = str(row.get('imagem', ''))
                            if len(img) > 10: st.image(processar_link_imagem(img))
                            st.markdown(f"**{row['item']}**"); cor = "#0066cc" if sld >= row['custo'] else "#999"
                            st.markdown(f"<div style='color:{cor}; font-weight:bold;'>{row['custo']} pts</div>", unsafe_allow_html=True)
                            
                            # --- BOTÕES LADO A LADO ---
                            c_detalhe, c_resgate = st.columns([1, 2])
                            with c_detalhe:
                                # Aqui ele entra na regra de CSS "stTabs" e fica pequeno (50px)
                                if st.button("Detalhes", key=f"det_{row['id']}", help="Ver Detalhes", type="secondary"):
                                    ver_detalhes_produto(row['item'], img, row['custo'], row.get('descricao', ''))
                            with c_resgate:
                                if sld >= row['custo']:
                                    if st.button("RESGATAR", key=f"b_{row['id']}", use_container_width=True, type="primary"):
                                        confirmar_resgate_dialog(row['item'], row['custo'], u_cod)
        with t2:
            st.info("### 📜 Acompanhamento\nPedido recebido! Prazo: **5 dias úteis** no seu Whatsapp informado no momento do resgate!.")
            meus_pedidos = run_query("SELECT id, data, item, valor, status, codigo_vale, recebido_user FROM vendas WHERE usuario = :u ORDER BY data DESC", {"u": u_cod})
            if not meus_pedidos.empty:
                editor_pedidos = st.data_editor(
                    meus_pedidos,
                    use_container_width=True,
                    hide_index=True,
                    key="editor_meus_pedidos",
                    column_config={
                        "id": st.column_config.TextColumn("ID", disabled=True),
                        "data": st.column_config.DatetimeColumn("Data", disabled=True, format="DD/MM/YYYY"),
                        "item": st.column_config.TextColumn("Item", disabled=True),
                        "valor": st.column_config.NumberColumn("Valor", disabled=True),
                        "status": st.column_config.TextColumn("Status", disabled=True),
                        "codigo_vale": st.column_config.TextColumn("Código/Vale", disabled=True),
                        "recebido_user": st.column_config.CheckboxColumn("Já Recebeu?", help="Marque se você já recebeu seu prêmio")
                    },
                    disabled=["id", "data", "item", "valor", "status", "codigo_vale"]
                )
                if st.button("💾 Confirmar Recebimento"):
                    with conn.session as s:
                        for i, row in editor_pedidos.iterrows():
                            if row['recebido_user']: s.execute(text("UPDATE vendas SET recebido_user = TRUE WHERE id = :id"), {"id": row['id']})
                            else: s.execute(text("UPDATE vendas SET recebido_user = FALSE WHERE id = :id"), {"id": row['id']})
                        s.commit()
                    st.toast("Status de recebimento atualizado!", icon="✅"); time.sleep(1); st.rerun()
            else: st.write("Nenhum pedido encontrado.")

        with t3:
            st.markdown("### 🏆 Top Users (Histórico)")
            st.caption("Este ranking considera todos os pontos já ganhos, independente se já foram gastos ou zerados.")
            df_rank = run_query("SELECT usuario, pontos_historico FROM usuarios WHERE tipo NOT IN ('admin', 'staff') ORDER BY pontos_historico DESC LIMIT 10")
            if not df_rank.empty:
                df_rank['pontos_historico'] = df_rank['pontos_historico'].fillna(0).astype(int)
                df_rank = df_rank.rename(columns={"usuario": "Usuário", "pontos_historico": "Pontos Acumulados"})
                st.dataframe(df_rank, use_container_width=True, hide_index=True)
            else: st.info("Ranking ainda vazio.")

if __name__ == "__main__":
    verificar_sessao_automatica()
    if st.session_state.logado: tela_principal()
    else: tela_login()
