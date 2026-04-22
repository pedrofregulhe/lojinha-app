import streamlit as st
from sqlalchemy import text
import pandas as pd
from datetime import datetime, timedelta
import time
import base64
import bcrypt
import requests
import re
import random
import string
import uuid

# --- CONFIGURAÇÕES GERAIS ---
st.set_page_config(
    page_title="Loja Culligan", 
    layout="wide", 
    page_icon="🎁",
    menu_items={} 
)

# --- CONEXÃO SQL (NEON) ---
# CORREÇÃO 1: Adicionado pool_pre_ping e pool_recycle para evitar quedas de conexão inativa
conn = st.connection("postgresql", type="sql", pool_pre_ping=True, pool_recycle=300)

# --- ROBÔ DE ATUALIZAÇÃO DO BANCO (MIGRAÇÕES) ---
@st.cache_resource
def iniciar_banco_dados():
    with conn.session as s:
        try:
            # Colunas originais
            s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS valor_ponto FLOAT DEFAULT 0.50;"))
            # Novas colunas de Segurança e LGPD
            s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS consentimento_lgpd BOOLEAN DEFAULT FALSE;"))
            s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS data_consentimento TIMESTAMP;"))
            s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS token_expira_em TIMESTAMP;"))
            s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS reset_token TEXT;"))
            s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS reset_token_expira TIMESTAMP;"))
            s.commit()
        except Exception:
            pass 

iniciar_banco_dados()

# --- INICIALIZAÇÃO DA SESSÃO ---
if 'logado' not in st.session_state: st.session_state['logado'] = False
if 'usuario_cod' not in st.session_state: st.session_state['usuario_cod'] = ""
if 'usuario_nome' not in st.session_state: st.session_state['usuario_nome'] = ""
if 'tipo_usuario' not in st.session_state: st.session_state['tipo_usuario'] = "comum"
if 'saldo_atual' not in st.session_state: st.session_state['saldo_atual'] = 0.0
if 'valor_ponto_usuario' not in st.session_state: st.session_state['valor_ponto_usuario'] = 0.50 
if 'admin_mode' not in st.session_state: st.session_state['admin_mode'] = True 
if 'supervisor_mode' not in st.session_state: st.session_state['supervisor_mode'] = True 
if 'lgpd_pendente' not in st.session_state: st.session_state['lgpd_pendente'] = False
if 'em_verificacao_2fa' not in st.session_state: st.session_state['em_verificacao_2fa'] = False
if 'codigo_2fa_esperado' not in st.session_state: st.session_state['codigo_2fa_esperado'] = ""
if 'dados_usuario_temp' not in st.session_state: st.session_state['dados_usuario_temp'] = {}

# --- CSS DINÂMICO ---
css_comum = """
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;800;900&display=swap');
    
    #MainMenu {visibility: hidden;}
    [data-testid="stHeader"] {display: none;}
    footer {visibility: hidden;}

    @keyframes gradient { 
        0% { background-position: 0% 50%; } 
        50% { background-position: 100% 50%; } 
        100% { background-position: 0% 50%; } 
    }

    h1, h2, h3, h4, h5, h6, p, a, li, button, input, select, textarea, label, .stMarkdown, .stText {
        font-family: 'Poppins', sans-serif !important;
        color: #31333F; 
    }
    
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }

    .header-style { 
        background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); 
        background-size: 400% 400% !important; 
        animation: gradient 10s ease infinite !important; 
        padding: 0 25px; 
        border-radius: 12px; 
        color: white !important; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.1); 
        display: flex; 
        flex-direction: column; 
        justify-content: center; 
        height: 110px !important; 
        margin: 0 !important;
    }
    .header-style h2, .header-style p, .header-style span, .header-style div { color: white !important; }
    .header-style h2 { font-size: 20px !important; font-weight: 700 !important; margin: 0 !important; }
    .header-style p { font-size: 12px !important; line-height: 1.3 !important; opacity: 0.9 !important; margin: 2px 0 0 0 !important; }
    .header-style .saldo-label { font-size: 10px !important; font-weight: 600 !important; }
    .header-style .saldo-valor { font-size: 30px !important; font-weight: 900 !important; text-shadow: 0 2px 4px rgba(0,0,0,0.15); }

    div.stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        width: 100%;
        border: none !important;
    }

    [data-testid="stTabs"] div.stButton > button {
        height: 45px !important;      
        min-height: 45px !important;
        max-height: 45px !important;
        margin-top: auto !important;
    }

    [data-testid="stTabs"] button[kind="primary"] { background-color: #0066cc !important; color: white !important; }
    [data-testid="stTabs"] button[kind="primary"]:hover { background-color: #0052a3 !important; }
    [data-testid="stTabs"] button[kind="primary"] p { color: white !important; }

    [data-testid="stTabs"] button[kind="secondary"] { background-color: #ffffff !important; color: #003366 !important; border: 1px solid #e0e0e0 !important; }
    [data-testid="stTabs"] button[kind="secondary"]:hover { background-color: #f5f5f5 !important; }

    div[data-testid="column"] div.stButton > button[kind="secondary"] {
        background-color: #ffffff !important;
        color: #003366 !important;
        border: 2px solid #eef2f6 !important;
        height: 50px !important;
        min-height: 50px !important;
    }

    [data-testid="stImage"] img { height: 110px !important; object-fit: contain !important; border-radius: 10px; }
    [data-testid="stMetricValue"] { font-size: 2.2rem !important; }
    [data-testid="stMetricLabel"] { font-size: 1rem !important; }

    .rifa-card { border: 2px solid #FFD700; background: linear-gradient(to bottom right, #fffdf0, #ffffff); padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .rifa-tag { background-color: #FFD700; color: #000; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 12px; margin-bottom: 10px; display: inline-block; }
    .winner-card { border: 2px solid #28a745; background: linear-gradient(to bottom right, #f0fff4, #ffffff); padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .winner-tag { background-color: #28a745; color: #fff; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 12px; margin-bottom: 10px; display: inline-block; }

    @media only screen and (max-width: 600px) {
        .header-style { height: auto !important; padding: 15px !important; text-align: center !important; }
        div.stButton > button { height: 50px !important; }
    }
"""

if not st.session_state.get('logado', False):
    estilo_especifico = """
    .stApp { 
        background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); 
        background-size: 400% 400% !important; 
        animation: gradient 15s ease infinite !important; 
    }
    [data-testid="stForm"] { background-color: #ffffff; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
    """
else:
    estilo_especifico = ".stApp { background-color: #f4f8fb; }"

st.markdown(f"<style>{css_comum} {estilo_especifico}</style>", unsafe_allow_html=True)

# --- FUNÇÕES BÁSICAS ---
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
    expira_em = datetime.now() + timedelta(hours=24)
    with conn.session as s:
        s.execute(text("UPDATE usuarios SET token_sessao = :t, token_expira_em = :exp WHERE id = :id"), 
                  {"t": token, "exp": expira_em, "id": usuario_id})
        s.commit()
    st.query_params["sessao"] = token

def verificar_sessao_automatica():
    if st.session_state.get('logado', False): return
    token_url = st.query_params.get("sessao")
    if token_url:
        try:
            df = run_query("SELECT * FROM usuarios WHERE token_sessao = :t AND token_expira_em > NOW()", {"t": token_url}, ttl=0)
            if not df.empty:
                row = df.iloc[0]
                tem_lgpd = bool(row.get('consentimento_lgpd', False))
                st.session_state.update({
                    'logado': True,
                    'usuario_cod': row['usuario'],
                    'usuario_nome': row['nome'],
                    'tipo_usuario': str(row['tipo']).lower().strip(),
                    'saldo_atual': float(row['saldo']),
                    'valor_ponto_usuario': float(row.get('valor_ponto', 0.50) or 0.50),
                    'lgpd_pendente': not tem_lgpd
                })
                st.rerun()
            else:
                if st.query_params.get("sessao"):
                    st.query_params.clear()
        except Exception:
            pass

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
# CORREÇÃO 2: Função run_query robusta com tratamento de erros de conexão e reset
def run_query(query_str, params=None, ttl="5m"):
    try:
        return conn.query(query_str, params=params, ttl=ttl)
    except Exception:
        # Se falhar (ex: conexão perdida com o Neon), limpamos o cache e tentamos resetar a conexão
        st.cache_data.clear()
        try:
            conn.reset() # Força uma nova conexão
            return conn.query(query_str, params=params, ttl=ttl)
        except Exception:
            # Caso falhe novamente, retorna um dataframe vazio para evitar a tela de erro vermelha
            st.warning("⚠️ O sistema está a restabelecer a ligação. Por favor, atualize a página.")
            return pd.DataFrame()

def run_transaction(query_str, params=None):
    with conn.session as s: s.execute(text(query_str), params if params else {}); s.commit()

def registrar_log(acao, detalhes):
    try:
        resp = st.session_state.get('usuario_nome', 'Sistema')
        run_transaction("INSERT INTO logs (data, responsavel, acao, detalhes) VALUES (NOW(), :resp, :acao, :det)", {"resp": resp, "acao": acao, "det": detalhes})
    except Exception as e: print(f"Erro log: {e}")

# --- LÓGICA DE NEGÓCIO ---
def validar_login(user_input, pass_input):
    df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": user_input.strip()}, ttl=0)
    if df.empty: return False, None, None, 0, None, None, 0.50, False
    linha = df.iloc[0]
    if verificar_senha_hash(pass_input.strip(), linha['senha']):
        v_ponto = float(linha.get('valor_ponto', 0.50) or 0.50)
        tem_lgpd = bool(linha.get('consentimento_lgpd', False))
        return True, linha['nome'], str(linha['tipo']).lower().strip(), float(linha['saldo']), str(linha['telefone']), int(linha['id']), v_ponto, tem_lgpd
    return False, None, None, 0, None, None, 0.50, False

def salvar_venda(usuario_cod, item_nome, custo, email_contato, telefone_resgate):
    try:
        user_df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario_cod}, ttl=0)
        if user_df.empty: 
            st.error("Erro interno: Cadastro não localizado para o resgate.")
            return False
        if float(user_df.iloc[0]['saldo']) < custo: st.error("Saldo insuficiente."); return False
        with conn.session as s:
            s.execute(text("UPDATE usuarios SET saldo = saldo - :custo WHERE LOWER(usuario) = LOWER(:u)"), {"custo": custo, "u": usuario_cod})
            s.execute(text("INSERT INTO vendas (data, usuario, item, valor, status, email, nome_real, telefone) VALUES (NOW(), :u, :item, :valor, 'Pendente', :email, :nome, :tel)"),
                {"u": usuario_cod, "item": item_nome, "valor": custo, "email": email_contato, "nome": user_df.iloc[0]['nome'], "tel": telefone_resgate})
            s.commit()
        registrar_log("Resgate", f"Usuário: {user_df.iloc[0]['nome']} | Item: {item_nome}")
        st.session_state['saldo_atual'] -= custo
        st.cache_data.clear() 
        return True
    except Exception as e: st.error(f"Erro: {e}"); return False

def comprar_ticket_rifa(rifa_id, custo, usuario_cod):
    try:
        user_df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario_cod}, ttl=0)
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
        st.cache_data.clear() 
        return True, "Ticket comprado com sucesso!"
    except Exception as e: return False, f"Erro: {str(e)}"

def cadastrar_novo_usuario(usuario, senha, nome, saldo, tipo, telefone, valor_ponto=0.50, consentimento_lgpd=False):
    usuario = usuario.strip()
    try:
        df = run_query("SELECT id FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario}, ttl=0)
        if not df.empty: return False, "Usuário já existe!"
        data_cons = datetime.now() if consentimento_lgpd else None
        run_transaction(
            "INSERT INTO usuarios (usuario, senha, nome, saldo, pontos_historico, tipo, telefone, valor_ponto, consentimento_lgpd, data_consentimento) VALUES (:u, :s, :n, :bal, :bal, :t, :tel, :vp, :lgpd, :dt_lgpd)",
            {"u": usuario, "s": gerar_hash(senha), "n": nome, "bal": saldo, "t": tipo, "tel": formatar_telefone(telefone), "vp": valor_ponto, "lgpd": consentimento_lgpd, "dt_lgpd": data_cons}
        )
        registrar_log("Novo Cadastro", f"Criou usuário: {usuario} (LGPD Inicial: {consentimento_lgpd})")
        return True, "Cadastrado com sucesso!"
    except Exception as e: return False, f"Erro: {str(e)}"

def distribuir_pontos_multiplos(lista_usuarios, quantidade):
    try:
        if "Todos" in lista_usuarios:
            run_transaction("UPDATE usuarios SET saldo = saldo + :q, pontos_historico = COALESCE(pontos_historico, 0) + :q WHERE tipo NOT IN ('admin', 'staff', 'supervisor')", {"q": quantidade})
            msg = f"Adicionou {quantidade} pts para TODOS (exceto staff/admin/supervisor)."
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

# --- MODAIS E DIÁLOGOS ---
@st.dialog("🔒 Termos de Uso e Privacidade (LGPD)")
def modal_consentimento_lgpd():
    st.markdown("""
    ### Política de Privacidade e Proteção de Dados
    Para continuar utilizando a **Lojinha Culli's**, precisamos do seu consentimento para o tratamento dos seus dados pessoais, em conformidade com a Lei Geral de Proteção de Dados (LGPD - Lei nº 13.709/2018).
    **1. Dados Coletados:** Nome, Login e Telefone. Histórico de transações. Logs de acesso.
    **2. Finalidade:** Gestão de recompensas, comunicação de status via WhatsApp/SMS e auditoria.
    **3. Direitos:** Pode solicitar correção ou exclusão de dados, implicando no cancelamento da conta.
    **4. Segurança:** Dados protegidos e compartilhados apenas com operadores técnicos necessários.
    ---
    Ao clicar em **"Li e Aceito"**, declara estar de acordo.
    """)
    if st.button("✅ LI E ACEITO OS TERMOS", type="primary", use_container_width=True):
        try:
            u_cod = st.session_state.get('usuario_cod')
            if u_cod:
                with conn.session as s:
                    s.execute(text("UPDATE usuarios SET consentimento_lgpd = TRUE, data_consentimento = NOW() WHERE usuario = :u"), {"u": u_cod})
                    s.commit()
                st.session_state['lgpd_pendente'] = False
                st.cache_data.clear()
                st.success("Consentimento registrado com sucesso!")
                time.sleep(1)
                st.rerun()
        except Exception as e:
            st.error(f"Erro ao registrar: {e}")

@st.dialog("💾 Confirmação de Sistema")
def modal_sucesso_salvamento(detalhes):
    st.success("As alterações foram gravadas no banco de dados!")
    st.code(f"LOG: {detalhes}\nTIMESTAMP: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", language="sql")
    if st.button("Fechar Janela", type="primary"):
        st.rerun()

@st.dialog("👤 Meu Perfil")
def abrir_modal_perfil(usuario_cod):
    df_user = run_query("SELECT nome, telefone FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario_cod}, ttl=0)
    if df_user.empty: st.error("Erro ao carregar dados."); return
    nome_atual = df_user.iloc[0]['nome']; tel_atual = str(df_user.iloc[0]['telefone'])
    with st.form("form_perfil"):
        novo_nome = st.text_input("Nome Completo", value=nome_atual)
        novo_telefone = st.text_input("Telefone / WhatsApp", value=tel_atual)
        st.divider(); st.write("🔐 **Alterar Senha**")
        n = st.text_input("Nova Senha", type="password"); c = st.text_input("Confirmar", type="password")
        if st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True):
            tel_f = formatar_telefone(novo_telefone)
            if len(tel_f) < 12: st.error("Telefone inválido!"); return
            query = "UPDATE usuarios SET nome = :n, telefone = :t"; params = {"n": novo_nome, "t": tel_f, "u": usuario_cod}
            if n or c:
                if n != c: st.error("Senhas não coincidem!"); return
                query += ", senha = :s"; params["s"] = gerar_hash(n)
            query += " WHERE LOWER(usuario) = LOWER(:u)"
            try:
                run_transaction(query, params); registrar_log("Perfil Atualizado", f"Usuário: {usuario_cod}")
                st.session_state['usuario_nome'] = novo_nome; st.success("Atualizado!"); time.sleep(1.5); st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

@st.dialog("🔑 Recuperar Acesso")
def enviar_link_recuperacao():
    st.write("Digite o seu login para redefinir a senha.")
    user_input = st.text_input("Login")
    if st.button("Enviar Link", type="primary"):
        df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": user_input.strip()}, ttl=0)
        if df.empty: st.error("Usuário não encontrado."); return
        row = df.iloc[0]; tel = str(row['telefone']); reset_token = str(uuid.uuid4()); exp = datetime.now() + timedelta(minutes=15)
        try:
            with conn.session as s:
                s.execute(text("UPDATE usuarios SET reset_token = :rt, reset_token_expira = :exp WHERE id = :id"), {"rt": reset_token, "exp": exp, "id": int(row['id'])})
                s.commit()
            link = f"https://lojinha-culligan.streamlit.app/?rt={reset_token}"
            ok, det, _ = enviar_sms(tel, f"Culli: Redefina a sua senha aqui (15min): {link}")
            if ok: st.success("Enviado via SMS!"); registrar_log("Solicitação Reset", user_input); time.sleep(2); st.rerun()
            else: st.error(det)
        except Exception as e: st.error(f"Erro: {e}")

def tela_nova_senha_token(token_url):
    st.markdown("## 🔐 Nova Senha")
    try:
        df = run_query("SELECT * FROM usuarios WHERE reset_token = :rt AND reset_token_expira > NOW()", {"rt": token_url}, ttl=0)
        if df.empty: 
            st.error("Link inválido ou expirado."); 
            if st.button("Voltar"): st.query_params.clear(); st.rerun()
            return
        with st.form("f_reset"):
            n1 = st.text_input("Nova Senha", type="password"); n2 = st.text_input("Confirme", type="password")
            if st.form_submit_button("REDEFINIR"):
                if n1 == n2 and len(n1) >= 4:
                    with conn.session as s:
                        s.execute(text("UPDATE usuarios SET senha=:s, reset_token=NULL, reset_token_expira=NULL WHERE id=:id"), {"s": gerar_hash(n1), "id": int(df.iloc[0]['id'])})
                        s.commit()
                    st.success("Sucesso!"); st.query_params.clear(); time.sleep(2); st.rerun()
                else: st.error("Senhas inválidas.")
    except Exception as e: st.error(f"Erro: {e}")

@st.dialog("🎁 Confirmar Resgate")
def confirmar_resgate_dialog(item_nome, custo, usuario_cod):
    st.write(f"Resgatar **{item_nome}** por **{custo} pts**.")
    with st.form("form_resgate"):
        email = st.text_input("E-mail:"); tel = st.text_input("WhatsApp:")
        if st.form_submit_button("CONFIRMAR", type="primary", use_container_width=True):
            if "@" not in email: st.error("E-mail inválido."); return
            if len(formatar_telefone(tel)) < 12: st.error("Telefone inválido!"); return
            if salvar_venda(usuario_cod, item_nome, custo, email, formatar_telefone(tel)):
                st.balloons(); st.success("Sucesso!"); time.sleep(2); st.rerun()

@st.dialog("🎟️ Comprar Ticket Rifa")
def confirmar_compra_ticket(rifa_id, item_nome, custo, usuario_cod):
    st.write(f"Comprar ticket para **{item_nome}** por **{custo} pts**.")
    if st.button("CONFIRMAR", type="primary", use_container_width=True):
        ok, msg = comprar_ticket_rifa(rifa_id, custo, usuario_cod)
        if ok: st.balloons(); st.success(msg); time.sleep(2); st.rerun()
        else: st.error(msg)

@st.dialog("🎉 TEMOS UM VENCEDOR!")
def mostrar_vencedor_dialog(nome_vencedor, usuario_vencedor, nome_premio, imagem_premio):
    st.balloons()
    if imagem_premio: st.image(processar_link_imagem(imagem_premio), width=300)
    st.markdown(f"<h2 style='text-align:center; color:#28a745;'>{nome_vencedor}</h2>", unsafe_allow_html=True)
    st.success(f"Parabéns! Ganhou: {nome_premio}")

@st.dialog("🔍 Detalhes do Produto")
def ver_detalhes_produto(item, imagem, custo, descricao):
    st.image(processar_link_imagem(imagem), use_container_width=True)
    st.markdown(f"## {item}\n#### 💎 Valor: **{custo} pts**\n---\n### 📝 Descrição")
    st.write(descricao if (descricao and str(descricao).lower() != "none") else "Sem descrição.")
    st.info("ℹ️ Prazo de processamento: 5 dias úteis.")

@st.dialog("🚀 Confirmar e Processar Envios")
def processar_envios_dialog(df_selecionados, tipo_envio="vendas"):
    st.write(f"Selecionados: **{len(df_selecionados)}**")
    usar_zap = st.toggle("WhatsApp", value=True); usar_sms = st.toggle("SMS", value=True)
    if st.button("DISPARAR", type="primary", use_container_width=True):
        logs = []
        p = st.progress(0); total = len(df_selecionados)
        for i, (idx, row) in enumerate(df_selecionados.iterrows()):
            tel = str(row['telefone'])
            if tipo_envio == "vendas": nome = str(row['nome_real'] or row['usuario']); v1 = str(row['item']); v2 = str(row['codigo_vale'])
            else: nome = str(row['nome']); v1 = f"{float(row['saldo']):,.0f}"; v2 = ""
            if usar_zap and len(formatar_telefone(tel)) >= 12:
                ok, det, _ = enviar_whatsapp_template(tel, [nome, v1, v2], "atualizar_envio_pedidos") if tipo_envio == "vendas" else enviar_whatsapp_template(tel, [nome, v1], "atualizar_saldo_pedidos")
                logs.append({"Nome": nome, "Canal": "Zap", "Status": ok})
            if usar_sms and len(formatar_telefone(tel)) >= 12:
                txt = f"Seu resgate de {v1} liberado! Cod: {v2}" if tipo_envio == "vendas" else f"Seu saldo atual é {v1}. Acesse: https://lojinha-culligan.streamlit.app/"
                ok, det, _ = enviar_sms(tel, txt)
                logs.append({"Nome": nome, "Canal": "SMS", "Status": ok})
            p.progress((i + 1) / total)
        st.success("Finalizado!"); registrar_log("Disparo Massa", f"{tipo_envio} - {total}")
        st.dataframe(pd.DataFrame(logs), use_container_width=True)

# --- TELAS ---
def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        if st.session_state.get('em_verificacao_2fa', False):
            with st.form("f_2fa"):
                st.markdown(f"## 🔒 Segurança\nCódigo enviado para **...{str(st.session_state.dados_usuario_temp.get('telefone', ''))[-4:]}**")
                cod = st.text_input("Código de 6 dígitos", max_chars=6)
                if st.form_submit_button("VALIDAR"):
                    if cod == st.session_state.codigo_2fa_esperado:
                        d = st.session_state.dados_usuario_temp
                        st.session_state.update({'logado': True, 'usuario_cod': d['usuario'], 'usuario_nome': d['nome'], 'tipo_usuario': d['tipo'], 'saldo_atual': d['saldo'], 'valor_ponto_usuario': d.get('valor_ponto', 0.50), 'em_verificacao_2fa': False, 'lgpd_pendente': not st.session_state.get('temp_lgpd_status', False)})
                        criar_sessao_persistente(d['id']); st.rerun()
                    else: st.error("Código incorreto.")
            if st.button("⬅️ Voltar"): st.session_state.em_verificacao_2fa = False; st.rerun()
        else:
            with st.form("f_login"):
                st.markdown("<h1 style='text-align:center;'>Lojinha Culli's</h1>", unsafe_allow_html=True)
                u = st.text_input("Usuário"); s = st.text_input("Senha", type="password")
                if st.form_submit_button("ENTRAR", type="primary", use_container_width=True):
                    ok, n, t, sld, tel, uid, vp, lgpd = validar_login(u, s)
                    if ok:
                        cod = str(random.randint(100000, 999999))
                        env, info, _ = enviar_sms(tel, f"Codigo Culli: {cod}")
                        if env:
                            st.session_state.update({'em_verificacao_2fa': True, 'codigo_2fa_esperado': cod, 'dados_usuario_temp': {'usuario': u.strip(), 'nome': n, 'tipo': t, 'saldo': sld, 'telefone': tel, 'id': uid, 'valor_ponto': vp}, 'temp_lgpd_status': lgpd})
                            st.rerun()
                        else: st.error(f"Erro SMS: {info}")
                    else: st.toast("Erro!", icon="❌")
            c_e, c_p = st.columns(2)
            if c_e.button("Esqueci a senha", use_container_width=True): enviar_link_recuperacao()
            if c_p.button("Primeiro Acesso?", use_container_width=True): enviar_link_recuperacao()

def tela_admin():
    st.subheader("🛠️ Painel Admin")
    t1, t2, t3, t4, t5 = st.tabs(["📊 Vendas", "👥 Usuários", "🎁 Prêmios", "🛠️ Logs", "🎟️ Sorteio"])
    with t1:
        df_v = run_query("SELECT * FROM vendas ORDER BY id DESC")
        if not df_v.empty:
            if "Enviar" not in df_v.columns: df_v.insert(0, "Enviar", False)
            edit_v = st.data_editor(df_v, use_container_width=True, hide_index=True, key="ed_v")
            if st.button("💾 Salvar Vendas"):
                try:
                    with conn.session as s:
                        for _, r in edit_v.iterrows():
                            s.execute(text("UPDATE vendas SET item=:item, valor=:valor, codigo_vale=:c, status=:st, nome_real=:n, telefone=:t, email=:e WHERE id=:id"), {"item": str(r['item']), "valor": float(r['valor']), "c": str(r['codigo_vale']), "st": str(r['status']), "n": str(r['nome_real']), "t": str(r['telefone']), "e": str(r.get('email', '')), "id": int(r['id'])})
                        s.commit()
                    modal_sucesso_salvamento("Vendas atualizadas."); st.cache_data.clear()
                except Exception as e: st.error(e)
            if st.button("📤 Enviar Selecionados"):
                sel = edit_v[edit_v['Enviar'] == True]
                if sel.empty: st.warning("Vazio.")
                else: processar_envios_dialog(sel, "vendas")
    with t2:
        with st.expander("➕ Novo"):
            with st.form("fn"):
                u = st.text_input("User"); s = st.text_input("Senha"); n = st.text_input("Nome"); tel = st.text_input("Tel")
                b = st.number_input("Saldo"); tp = st.selectbox("Tipo", ["comum", "admin", "staff", "supervisor"]); vp = st.number_input("V. Ponto", 0.50)
                if st.form_submit_button("Criar"):
                    ok, m = cadastrar_novo_usuario(u, s, n, b, tp, tel, vp); st.cache_data.clear()
                    if ok: st.success(m)
                    else: st.error(m)
        df_u = run_query("SELECT * FROM usuarios ORDER BY id")
        if not df_u.empty:
            if "Notificar" not in df_u.columns: df_u.insert(0, "Notificar", False)
            ed_u = st.data_editor(df_u, use_container_width=True, key="ed_uu")
            if st.button("💾 Salvar Usuários"):
                try:
                    with conn.session as s:
                        for _, r in ed_u.iterrows():
                            s.execute(text("UPDATE usuarios SET saldo=:s, pontos_historico=:ph, telefone=:t, nome=:n, tipo=:tp, valor_ponto=:vp WHERE id=:id"), {"s": float(r['saldo']), "ph": float(r['pontos_historico']), "t": str(r['telefone']), "n": str(r['nome']), "tp": str(r['tipo']), "vp": float(r.get('valor_ponto', 0.5)), "id": int(r['id'])})
                        s.commit()
                    modal_sucesso_salvamento("Users atualizados."); st.cache_data.clear()
                except Exception as e: st.error(e)
    with t3:
        df_p = run_query("SELECT * FROM premios ORDER BY id")
        ed_p = st.data_editor(df_p, use_container_width=True, num_rows="dynamic", key="ed_pp")
        if st.button("Salvar Catálogo"):
            try:
                with conn.session as s:
                    for _, r in ed_p.iterrows():
                        if pd.notna(r['id']): s.execute(text("UPDATE premios SET item=:i, imagem=:im, custo=:c, descricao=:d WHERE id=:id"), {"i": str(r['item']), "im": str(r['imagem']), "c": float(r['custo']), "d": str(r.get('descricao', '')), "id": int(r['id'])})
                        elif r['item']: s.execute(text("INSERT INTO premios (item, imagem, custo, descricao) VALUES (:i, :im, :c, :d)"), {"i": str(r['item']), "im": str(r['imagem']), "c": float(r['custo']), "d": str(r.get('descricao', ''))})
                    s.commit()
                st.cache_data.clear(); modal_sucesso_salvamento("Catálogo salvo.")
            except Exception as e: st.error(e)
    with t4: st.dataframe(run_query("SELECT * FROM logs ORDER BY id DESC LIMIT 50"))
    with t5:
        r_ativa = run_query("SELECT * FROM rifas WHERE status = 'ativa'")
        if not r_ativa.empty:
            r = r_ativa.iloc[0]; st.success(f"Ativa: {r['item_nome']}")
            if st.button("🎲 SORTEAR"):
                tkts = run_query("SELECT usuario FROM rifa_tickets WHERE rifa_id = :rid", {"rid": int(r['id'])}, ttl=0)
                if tkts.empty: st.error("Sem tickets.")
                else:
                    venc = random.choice(tkts['usuario'].tolist())
                    u_v = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": venc})
                    if not u_v.empty:
                        with conn.session as s:
                            s.execute(text("DELETE FROM rifa_tickets WHERE rifa_id=:rid"), {"rid": int(r['id'])})
                            s.execute(text("UPDATE rifas SET status='encerrada', ganhador_usuario=:u WHERE id=:id"), {"u": venc, "id": int(r['id'])})
                            s.execute(text("INSERT INTO vendas (data, usuario, item, valor, status, nome_real, telefone) VALUES (NOW(), :u, :i, 0, 'Sorteio', :n, :t)"), {"u": venc, "i": f"RIFA: {r['item_nome']}", "n": u_v.iloc[0]['nome'], "t": u_v.iloc[0]['telefone']})
                            s.commit()
                        st.cache_data.clear(); mostrar_vencedor_dialog(u_v.iloc[0]['nome'], venc, r['item_nome'], ""); time.sleep(5); st.rerun()
        else:
            df_pr = run_query("SELECT id, item FROM premios")
            ops = {f"{row['id']} - {row['item']}": row['id'] for _, row in df_pr.iterrows()}
            escolha = st.selectbox("Prêmio:", list(ops.keys()))
            custo = st.number_input("Custo Ticket", 50)
            if st.button("INICIAR"):
                run_transaction("INSERT INTO rifas (premio_id, item_nome, custo_ticket, status) VALUES (:p, :n, :c, 'ativa')", {"p": ops[escolha], "n": escolha.split(" - ")[1], "c": custo})
                st.cache_data.clear(); st.rerun()

def tela_supervisor():
    st.subheader("📦 Visão Supervisor")
    df_v = run_query("SELECT * FROM vendas ORDER BY id DESC")
    if not df_v.empty:
        st.dataframe(df_v, use_container_width=True, hide_index=True)
    else: st.info("Vazio.")

def tela_principal():
    u_cod, u_nome, sld, tipo = st.session_state.usuario_cod, st.session_state.usuario_nome, st.session_state.saldo_atual, st.session_state.tipo_usuario
    vp_u = st.session_state.get('valor_ponto_usuario', 0.50)

    if st.session_state.get('lgpd_pendente', False):
        modal_consentimento_lgpd()
    else:
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f'''<div class="header-style"><div style="display:flex; justify-content:space-between; align-items:center;"><div><h2>Olá, {u_nome}! 👋</h2><p>Troque pontos por prêmios!</p></div><div style="text-align:right;">Saldo: <span class="saldo-valor">{sld:,.0f}</span> pts</div></div></div>''', unsafe_allow_html=True)
        with c2:
            if st.button("👤 Perfil"): abrir_modal_perfil(u_cod)
            if st.button("❌ Sair"): realizar_logout()
            if tipo == 'admin':
                if st.button("Admin Mode"): st.session_state.admin_mode = not st.session_state.admin_mode; st.rerun()
            elif tipo == 'supervisor':
                if st.button("Supervisor Mode"): st.session_state.supervisor_mode = not st.session_state.supervisor_mode; st.rerun()

        st.divider()
        if tipo == 'admin' and st.session_state.admin_mode: tela_admin()
        elif tipo == 'supervisor' and st.session_state.supervisor_mode: tela_supervisor()
        else:
            t1, t2, t3, t4 = st.tabs(["🎁 Loja", "🍀 Rifa", "📜 Pedidos", "🏆 Ranking"])
            with t1:
                df_p = run_query("SELECT * FROM premios ORDER BY id")
                if not df_p.empty:
                    cols = st.columns(4)
                    for i, (idx, row) in enumerate(df_p.iterrows()):
                        with cols[i % 4]:
                            with st.container(border=True):
                                if row['imagem']: st.image(processar_link_imagem(row['imagem']))
                                c_final = int(row['custo'] * (0.50 / vp_u))
                                st.write(f"**{row['item']}**")
                                st.write(f"{c_final} pts")
                                if st.button("Ver", key=f"v_{row['id']}"): ver_detalhes_produto(row['item'], row['imagem'], c_final, row['descricao'])
                                if sld >= c_final:
                                    if st.button("RESGATAR", key=f"r_{row['id']}", type="primary"): confirmar_resgate_dialog(row['item'], c_final, u_cod)
            with t2:
                r_ativa = run_query("SELECT * FROM rifas WHERE status = 'ativa'")
                if not r_ativa.empty:
                    r = r_ativa.iloc[0]
                    st.success(f"🍀 {r['item_nome']} - {r['custo_ticket']} pts")
                    if st.button("Comprar Ticket"): confirmar_compra_ticket(int(r['id']), r['item_nome'], r['custo_ticket'], u_cod)
                else: st.info("Sem sorteios ativos.")
            with t3:
                meus = run_query("SELECT * FROM vendas WHERE LOWER(usuario) = LOWER(:u) ORDER BY data DESC", {"u": u_cod})
                if not meus.empty: st.dataframe(meus, use_container_width=True, hide_index=True)
                else: st.write("Vazio.")
            with t4:
                rk = run_query("SELECT usuario, pontos_historico FROM usuarios WHERE tipo='comum' ORDER BY pontos_historico DESC LIMIT 10")
                st.dataframe(rk, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    qp = st.query_params
    if "rt" in qp: tela_nova_senha_token(qp["rt"])
    else:
        verificar_sessao_automatica()
        if st.session_state.get('logado', False): tela_principal()
        else: tela_login()
