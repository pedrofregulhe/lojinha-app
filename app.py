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
conn = st.connection("postgresql", type="sql", pool_pre_ping=True, pool_recycle=300)

# --- ROBÔ DE ATUALIZAÇÃO DO BANCO (MIGRAÇÕES) ---
@st.cache_resource
def iniciar_banco_dados():
    with conn.session as s:
        try:
            # Colunas originais
            s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS valor_ponto FLOAT DEFAULT 0.50;"))
            s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS consentimento_lgpd BOOLEAN DEFAULT FALSE;"))
            s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS data_consentimento TIMESTAMP;"))
            s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS token_expira_em TIMESTAMP;"))
            s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS reset_token TEXT;"))
            s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS reset_token_expira TIMESTAMP;"))
            
            # NOVAS COLUNAS E TABELAS DO BOLÃO COPA
            s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS acesso_bolao BOOLEAN DEFAULT FALSE;"))
            
            s.execute(text("""
                CREATE TABLE IF NOT EXISTS bolao_jogos (
                    id SERIAL PRIMARY KEY,
                    time_a VARCHAR(50),
                    time_b VARCHAR(50),
                    data_jogo TIMESTAMP,
                    gols_a INT DEFAULT NULL,
                    gols_b INT DEFAULT NULL,
                    status VARCHAR(20) DEFAULT 'Aberto'
                );
            """))
            
            s.execute(text("""
                CREATE TABLE IF NOT EXISTS bolao_apostas (
                    id SERIAL PRIMARY KEY,
                    jogo_id INT REFERENCES bolao_jogos(id) ON DELETE CASCADE,
                    usuario VARCHAR(50),
                    gols_a INT,
                    gols_b INT,
                    pontos_ganhos INT DEFAULT 0
                );
            """))
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
if 'acesso_bolao' not in st.session_state: st.session_state['acesso_bolao'] = False

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

    /* ESTILOS EXCLUSIVOS DO BOLÃO COPA */
    .bolao-card { border: 2px solid #2F80ED; background: linear-gradient(to bottom right, #f0f6ff, #ffffff); padding: 18px; border-radius: 12px; text-align: center; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .bolao-tag { background-color: #2F80ED; color: white; padding: 3px 12px; border-radius: 15px; font-weight: bold; font-size: 11px; margin-bottom: 8px; display: inline-block; }
    .placar-box { font-size: 24px; font-weight: 800; color: #003366; margin: 10px 0; }

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
                    'lgpd_pendente': not tem_lgpd,
                    'acesso_bolao': bool(row.get('acesso_bolao', False))
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

def enviar_sms(telefone, mensagem_texto):
    try:
        base_url = st.secrets["INFOBIP_BASE_URL"].rstrip('/')
        api_key = st.secrets["INFOBIP_API_KEY"]
        url = f"{base_url}/sms/2/text/advanced"
        tel_final = formatar_telefone(telefone)
        
        if len(tel_final) < 12: 
            return False, f"Num Inválido: {tel_final}", "CLIENT_ERROR"
            
        payload = { 
            "messages": [ 
                { 
                    "from": "InfoSMS", 
                    "destinations": [{"to": tel_final}], 
                    "text": mensagem_texto 
                } 
            ] 
        }
        
        headers = { 
            "Authorization": f"App {api_key}", 
            "Content-Type": "application/json", 
            "Accept": "application/json" 
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code not in [200, 201]: 
            return False, f"Erro SMS {response.status_code}: {response.text}", str(response.status_code)
            
        return True, "SMS Enviado", str(response.status_code)
        
    except Exception as e: 
        return False, f"Erro SMS Exception: {str(e)}", "EXCEPTION"

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
def run_query(query_str, params=None, ttl="5m"):
    try:
        return conn.query(query_str, params=params, ttl=ttl)
    except Exception:
        st.cache_data.clear()
        try:
            conn.reset() 
            return conn.query(query_str, params=params, ttl=ttl)
        except Exception:
            st.error("Desculpe, o banco de dados está se reconectando. Por favor, atualize a página.")
            return pd.DataFrame()

def run_transaction(query_str, params=None):
    with conn.session as s: s.execute(text(query_str), params if params else {}); s.commit()

def registrar_log(acao, detalhes):
    try:
        resp = st.session_state.get('usuario_nome', 'Sistema')
        run_transaction("INSERT INTO logs (data, responsavel, acao, detalhes) VALUES (NOW(), :resp, :acao, :det)", {"resp": resp, "acao": acao, "det": detalhes})
    except Exception as e: print(f"Erro log: {e}")

# --- MOTOR DE PONTUAÇÃO DO BOLÃO ---
def calcular_pontos_aposta(gols_a_real, gols_b_real, gols_a_aposta, gols_b_aposta):
    pontos = 0
    saldo_real = gols_a_real - gols_b_real
    vencedor_real = "A" if saldo_real > 0 else "B" if saldo_real < 0 else "Empate"
    
    saldo_aposta = gols_a_aposta - gols_b_aposta
    vencedor_aposta = "A" if saldo_aposta > 0 else "B" if saldo_aposta < 0 else "Empate"
    
    # 1. Acertar vencedor (10 pontos)
    if vencedor_real == vencedor_aposta:
        pontos += 10
    # 2. Acertar diferença de gols (+5 pontos)
    if saldo_real == saldo_aposta:
        pontos += 5
    # 3. Acertar gols do time A (+3 pontos)
    if gols_a_real == gols_a_aposta:
        pontos += 3
    # 4. Acertar gols do time B (+3 pontos)
    if gols_b_real == gols_b_aposta:
        pontos += 3
    # 5. Acertar placar exato (+10 pontos bônus)
    if (gols_a_real == gols_a_aposta) and (gols_b_real == gols_b_aposta):
        pontos += 10
        
    return pontos

# --- LÓGICA DE NEGÓCIO ---
def validar_login(user_input, pass_input):
    df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": user_input.strip()}, ttl=0)
    if df.empty: return False, None, None, 0, None, None, 0.50, False, False
    linha = df.iloc[0]
    if verificar_senha_hash(pass_input.strip(), linha['senha']):
        v_ponto = float(linha.get('valor_ponto', 0.50) or 0.50)
        tem_lgpd = bool(linha.get('consentimento_lgpd', False))
        ac_bolao = bool(linha.get('acesso_bolao', False))
        return True, linha['nome'], str(linha['tipo']).lower().strip(), float(linha['saldo']), str(linha['telefone']), int(linha['id']), v_ponto, tem_lgpd, ac_bolao
    return False, None, None, 0, None, None, 0.50, False, False

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
            s.execute(text("UPDATE usuarios SET saldo = saldo - :custo WHERE LOWER(usuario) = LOWER(:u)"), {"custo": custo_real, "u": usuario_cod})
            s.execute(text("INSERT INTO rifa_tickets (rifa_id, usuario) VALUES (:rid, :u)"), {"rid": int(rifa_id), "u": usuario_cod})
            s.commit()
        st.session_state['saldo_atual'] -= custo_real
        registrar_log("Rifa", f"Comprou ticket rifa {rifa_id}")
        st.cache_data.clear() 
        return True, "Ticket comprado com sucesso!"
    except Exception as e: return False, f"Erro: {str(e)}"

def cadastrar_novo_usuario(usuario, senha, nome, saldo, tipo, telefone, valor_ponto=0.50, consentimento_lgpd=False, acesso_bolao=False):
    usuario = usuario.strip()
    try:
        df = run_query("SELECT id FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario}, ttl=0)
        if not df.empty: return False, "Usuário já existe!"
        data_cons = datetime.now() if consentimento_lgpd else None
        run_transaction(
            "INSERT INTO usuarios (usuario, senha, nome, saldo, pontos_historico, tipo, telefone, valor_ponto, consentimento_lgpd, data_consentimento, acesso_bolao) VALUES (:u, :s, :n, :bal, :bal, :t, :tel, :vp, :lgpd, :dt_lgpd, :ab)",
            {"u": usuario, "s": gerar_hash(senha), "n": nome, "bal": saldo, "t": tipo, "tel": formatar_telefone(telefone), "vp": valor_ponto, "lgpd": consentimento_lgpd, "dt_lgpd": data_cons, "ab": acesso_bolao}
        )
        registrar_log("Novo Cadastro", f"Criou usuário: {usuario} (Bolão: {acesso_bolao})")
        return True, "Cadastrado com sucesso!"
    except Exception as e: return False, f"Erro: {str(e)}"

def distribuir_pontos_multiplos(lista_usuarios, quantidade):
    try:
        if "Todos" in lista_usuarios:
            run_transaction("UPDATE usuarios SET saldo = saldo + :q, pontos_historico = COALESCE(pontos_historico, 0) + :q WHERE tipo NOT IN ('admin', 'staff', 'supervisor')", {"q": quantidade})
            msg = f"Adicionou {quantidade} pts para TODOS (exceto staff/admin/supervisor)."
        else:
            with conn.session as s:
                s.execute(text("UPDATE usuarios SET saldo = saldo + :q, pontos_historico = COALESCE(pontos_historico, 0) + :q WHERE usuario IN :users"), {"q": quantidade, "users": tuple(lista_usuarios)})
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
    Para continuar utilizando a **Lojinha Culli's**, precisamos do seu consentimento para o tratamento dos seus dados pessoais...
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
        except Exception as e: st.error(f"Erro ao registrar: {e}")

@st.dialog("💾 Confirmação de Sistema")
def modal_sucesso_salvamento(detalhes):
    st.success("As alterações foram gravadas no banco de dados!")
    st.code(f"LOG: {detalhes}\nTIMESTAMP: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", language="sql")
    if st.button("Fechar Janela", type="primary"): st.rerun()

@st.dialog("👤 Meu Perfil")
def abrir_modal_perfil(usuario_cod):
    df_user = run_query("SELECT nome, telefone FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario_cod}, ttl=0)
    if df_user.empty: return
    nome_atual, tel_atual = df_user.iloc[0]['nome'], str(df_user.iloc[0]['telefone'])
    with st.form("form_perfil"):
        novo_nome = st.text_input("Nome Completo", value=nome_atual)
        novo_telefone = st.text_input("Telefone / WhatsApp", value=tel_atual)
        n = st.text_input("Nova Senha", type="password"); c = st.text_input("Confirmar Nova Senha", type="password")
        if st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True):
            tel_formatado = formatar_telefone(novo_telefone)
            if len(tel_formatado) < 12: st.error("Telefone inválido!"); return
            query = "UPDATE usuarios SET nome = :n, telefone = :t"; params = {"n": novo_nome, "t": tel_formatado, "u": usuario_cod}
            if n or c:
                if n != c: st.error("As senhas não coincidem!"); return
                query += ", senha = :s"; params["s"] = gerar_hash(n)
            query += " WHERE LOWER(usuario) = LOWER(:u)"
            run_transaction(query, params)
            st.session_state['usuario_nome'] = novo_nome 
            st.success("Perfil atualizado!"); time.sleep(1); st.rerun()

@st.dialog("🔑 Recuperar Acesso")
def enviar_link_recuperacao():
    user_input = st.text_input("Login (Usuário)")
    if st.button("Enviar Link de Redefinição", type="primary"):
        df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": user_input.strip()}, ttl=0)
        if df.empty: st.error("Usuário não encontrado."); return
        row = df.iloc[0]; reset_token = str(uuid.uuid4()); expiracao = datetime.now() + timedelta(minutes=15)
        with conn.session as s:
            s.execute(text("UPDATE usuarios SET reset_token = :rt, reset_token_expira = :exp WHERE id = :id"), {"rt": reset_token, "exp": expiracao, "id": int(row['id'])})
            s.commit()
        link_completo = f"https://lojinha-culligan.streamlit.app/?rt={reset_token}"
        mensagem = f"Culli: Para redefinir sua senha, acesse o link (valido por 15 min): {link_completo}"
        ok, det, cod = enviar_sms(str(row['telefone']), mensagem)
        if ok: st.success("Link enviado por SMS!"); time.sleep(2); st.rerun()
        else: st.error(f"Erro: {det}")

def tela_nova_senha_token(token_url):
    st.markdown("""<div style='text-align: center;'><h2>🔐 Nova Senha</h2></div>""", unsafe_allow_html=True)
    df = run_query("SELECT * FROM usuarios WHERE reset_token = :rt AND reset_token_expira > NOW()", {"rt": token_url}, ttl=0)
    if df.empty:
        st.error("🚫 Link inválido ou expirado.")
        if st.button("Voltar"): st.query_params.clear(); st.rerun()
        return
    with st.form("form_reset_final"):
        n1 = st.text_input("Nova Senha", type="password"); n2 = st.text_input("Confirme", type="password")
        if st.form_submit_button("REDEFINIR SENHA", type="primary"):
            if n1 == n2 and len(n1) >= 4:
                run_transaction("UPDATE usuarios SET senha = :s, reset_token = NULL, reset_token_expira = NULL WHERE id = :id", {"s": gerar_hash(n1), "id": int(df.iloc[0]['id'])})
                st.success("Senha alterada!"); st.query_params.clear(); time.sleep(2); st.rerun()

@st.dialog("🎁 Confirmar Resgate")
def confirmar_resgate_dialog(item_nome, custo, usuario_cod):
    st.write(f"Resgatando: **{item_nome}** por **{custo} pts**.")
    with st.form("form_resgate"):
        email = st.text_input("E-mail:")
        tel = st.text_input("WhatsApp:")
        if st.form_submit_button("CONFIRMAR", type="primary"):
            if "@" not in email: st.error("E-mail inválido."); return
            if salvar_venda(usuario_cod, item_nome, custo, email, formatar_telefone(tel)):
                st.balloons(); st.success("Sucesso!"); time.sleep(2); st.rerun()

@st.dialog("🎟️ Comprar Ticket Rifa")
def confirmar_compra_ticket(rifa_id, item_nome, custo, usuario_cod):
    if st.button("CONFIRMAR COMPRA", type="primary", use_container_width=True):
        ok, msg = comprar_ticket_rifa(rifa_id, custo, usuario_cod)
        if ok: st.balloons(); st.success(msg); time.sleep(2); st.rerun()
        else: st.error(msg)

@st.dialog("⚽ Finalizar e Premiar Bolão")
def finalizar_bolao_dialog(jogo_id, time_a, time_b):
    st.subheader(f"Encerrar: {time_a} x {time_b}")
    gols_a = st.number_input(f"Gols {time_a}", min_value=0, step=1, value=0)
    gols_b = st.number_input(f"Gols {time_b}", min_value=0, step=1, value=0)
    
    st.divider()
    st.markdown("##### 🏆 Configuração da Premiação:")
    pontos_premio = st.number_input("Pontos de recompensa da Loja para o(s) Vencedor(es):", min_value=0, step=50, value=200)
    
    if st.form_submit_button if False else st.button("VALIDAR PLACAR E PREMIAR", type="primary", use_container_width=True):
        # 1. Buscar todas as apostas deste jogo
        apostas_df = run_query("SELECT * FROM bolao_apostas WHERE jogo_id = :jid", {"jid": int(jogo_id)}, ttl=0)
        
        if apostas_df.empty:
            # Sem apostas, apenas encerra o jogo
            run_transaction("UPDATE bolao_jogos SET gols_a = :ga, gols_b = :gb, status = 'Encerrada' WHERE id = :id", {"ga": gols_a, "gb": gols_b, "id": int(jogo_id)})
            st.warning("Nenhum usuário realizou apostas neste jogo. O jogo foi encerrado.")
            time.sleep(2); st.rerun()
            return
            
        # 2. Calcular pontos de cada aposta e salvar no banco temporariamente
        lista_resultados = []
        with conn.session as s:
            for _, row in apostas_df.iterrows():
                pts_calculados = calcular_pontos_aposta(gols_a, gols_b, int(row['gols_a']), int(row['gols_b']))
                s.execute(text("UPDATE bolao_apostas SET pontos_ganhos = :pts WHERE id = :id"), {"pts": pts_calculados, "id": int(row['id'])})
                lista_resultados.append({"usuario": row['usuario'], "pontos_bolao": pts_calculados})
            s.commit()
            
        res_df = pd.DataFrame(lista_resultados)
        maior_pontuacao = res_df['pontos_bolao'].max()
        vencedores = res_df[res_df['pontos_bolao'] == maior_pontuacao]['usuario'].tolist()
        
        # 3. Creditar pontos aos vencedores e enviar notificações
        with conn.session as s:
            for v_user in vencedores:
                # Da o prêmio configurado no saldo do usuário e histórico
                s.execute(text("UPDATE usuarios SET saldo = saldo + :p, pontos_historico = COALESCE(pontos_historico, 0) + :p WHERE usuario = :u"), {"p": pontos_premio, "u": v_user})
                
                # Registra na tabela de vendas/resgastes como prêmio do bolão
                s.execute(text("INSERT INTO vendas (data, usuario, item, valor, status, nome_real, telefone) VALUES (NOW(), :u, :item, 0, 'Liberado', :nr, :t)"),
                          {"u": v_user, "item": f"Vencedor Bolão: {time_a} x {time_b}", "nr": v_user, "t": ""})
                
                # Buscar telefone e nome real do vencedor para enviar alertas
                u_info = run_query("SELECT nome, telefone FROM usuarios WHERE usuario = :u", {"u": v_user}, ttl=0)
                if not u_info.empty:
                    nome_v = u_info.iloc[0]['nome']
                    tel_v = str(u_info.iloc[0]['telefone'])
                    
                    # Notificação SMS
                    msg_sms = f"Culli Copa: GOLAAACO! {nome_v}, voce venceu o Bolao ({time_a} x {time_b}) e faturou {pontos_premio} pts! Confira na Lojinha."
                    enviar_sms(tel_v, msg_sms)
                    
                    # Notificação WhatsApp (Reutilizando seu template cadastrado 'atualizar_envio_pedidos' que recebe [nome, var1, var2])
                    var1_jogo = f"Bolão Copa: {time_a} x {time_b}"
                    var2_pontos = f"Parabéns! Você venceu e ganhou +{pontos_premio} pontos na sua carteira!"
                    enviar_whatsapp_template(tel_v, [nome_v, var1_jogo, var2_pontos], "atualizar_envio_pedidos")
                    
        # 4. Atualizar o status do jogo para encerrado
        run_transaction("UPDATE bolao_jogos SET gols_a = :ga, gols_b = :gb, status = 'Encerrada' WHERE id = :id", {"ga": gols_a, "gb": gols_b, "id": int(jogo_id)})
        st.cache_data.clear()
        
        # Feedback visual de sucesso
        st.balloons()
        st.success(f"🏆 Bolão Encerrado! Maior pontuação técnica: {maior_pontuacao} pontos.")
        st.info(f"Vencedor(es) premiado(s): {', '.join(vencedores)}. Notificações enviadas com sucesso!")
        time.sleep(4)
        st.rerun()

@st.dialog("🎉 TEMOS UM VENCEDOR!")
def mostrar_vencedor_dialog(nome_vencedor, usuario_vencedor, nome_premio, imagem_premio):
    st.balloons()
    if imagem_premio: st.image(processar_link_imagem(imagem_premio), width=300)
    st.markdown(f"<h2 style='text-align:center; color:#28a745;'>{nome_vencedor}</h2>", unsafe_allow_html=True)
    st.success(f"Parabéns! Ganhou: {nome_premio}")

@st.dialog("🔍 Detalhes do Produto")
def ver_detalhes_produto(item, imagem, custo, descricao):
    st.image(processar_link_imagem(imagem), use_container_width=True)
    st.markdown(f"## {item}\n#### 💎 Valor: **{custo} pts**\n### 📝 Descrição")
    st.write(descricao if descricao and str(descricao).lower() != "none" else "Sem descrição.")

@st.dialog("🚀 Confirmar e Processar Envios")
def processar_envios_dialog(df_selecionados, tipo_envio="vendas"):
    st.write(f"Destinatários selecionados: **{len(df_selecionados)}**")
    usar_zap = st.toggle("WhatsApp", value=True); usar_sms = st.toggle("SMS", value=True)
    if st.button("CONFIRMAR E DISPARAR", type="primary", use_container_width=True):
        for i, (index, row) in enumerate(df_selecionados.iterrows()):
            tel = str(row['telefone'])
            if tipo_envio == "vendas": nome = str(row['nome_real'] or row['usuario']); var1 = str(row['item']); var2 = str(row['codigo_vale'])
            else: nome = str(row['nome']); var1 = f"{float(row['saldo']):,.0f}"; var2 = ""
            if usar_zap and len(formatar_telefone(tel)) >= 12:
                if tipo_envio == "vendas": enviar_whatsapp_template(tel, [nome, var1, var2], "atualizar_envio_pedidos")
                else: enviar_whatsapp_template(tel, [nome, var1], "atualizar_saldo_pedidos")
            if usar_sms and len(formatar_telefone(tel)) >= 12:
                texto = f"Olá {nome}, seu resgate de {var1} foi liberado! Cód: {var2}." if tipo_envio == "vendas" else f"Lojinha Culli: Olá {nome}, saldo atualizado para {var1}."
                enviar_sms(tel, texto)
        st.success("Disparos concluídos!"); st.cache_data.clear(); time.sleep(1.5); st.rerun()

# --- TELAS ---
def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        if st.session_state.get('em_verificacao_2fa', False):
            with st.form("f_2fa"):
                st.markdown("### 🔒 Código de Segurança enviado via SMS")
                codigo_digitado = st.text_input("Digite o Código de 6 dígitos", max_chars=6)
                if st.form_submit_button("VALIDAR ACESSO", type="primary", use_container_width=True):
                    if codigo_digitado == st.session_state.codigo_2fa_esperado:
                        dados = st.session_state.dados_usuario_temp
                        tem_lgpd = st.session_state.get('temp_lgpd_status', False) 
                        st.session_state.update({
                            'logado': True, 'usuario_cod': dados['usuario'], 'usuario_nome': dados['nome'], 'tipo_usuario': dados['tipo'], 'saldo_atual': dados['saldo'], 'valor_ponto_usuario': dados.get('valor_ponto', 0.50), 'em_verificacao_2fa': False, 'dados_usuario_temp': {}, 'lgpd_pendente': not tem_lgpd,
                            'acesso_bolao': dados['acesso_bolao']
                        })
                        criar_sessao_persistente(dados['id']); st.rerun()
                    else: st.error("Código incorreto.")
        else:
            with st.form("f_login"):
                st.markdown("<h1 style='text-align: center; color: #003366;'>Lojinha Culli's</h1>", unsafe_allow_html=True)
                u = st.text_input("Usuário"); s = st.text_input("Senha", type="password")
                if st.form_submit_button("ENTRAR", type="primary", use_container_width=True):
                    ok, n, t, sld, tel_completo, uid, v_ponto, tem_lgpd, ac_bolao = validar_login(u, s)
                    if ok:
                        codigo = str(random.randint(100000, 999999))
                        enviou, info, _ = enviar_sms(tel_completo, f"Seu codigo de acesso Culli: {codigo}")
                        if enviou:
                            st.session_state.update({'em_verificacao_2fa': True, 'codigo_2fa_esperado': codigo, 'dados_usuario_temp': {'usuario': u.strip(), 'nome': n, 'tipo': t, 'saldo': sld, 'telefone': tel_completo, 'id': uid, 'valor_ponto': v_ponto, 'acesso_bolao': ac_bolao}, 'temp_lgpd_status': tem_lgpd})
                            st.rerun()
                        else: st.error(f"Erro SMS: {info}")
                    else: st.toast("Usuário ou senha incorretos", icon="❌")
            st.write(""); col_l1, col_l2 = st.columns(2)
            with col_l1:
                if st.button("Esqueci a senha", type="secondary", use_container_width=True): enviar_link_recuperacao()
            with col_l2:
                if st.button("Primeiro Acesso?", type="secondary", use_container_width=True): enviar_link_recuperacao()

def tela_admin():
    st.workspace_in_progress = True
    st.divider()
    t1, t2, t3, t4, t5, t6 = st.tabs(["📊 Entregas & WhatsApp", "👥 Usuários & Saldos", "🎁 Prêmios", "🛠️ Logs", "🎟️ Sorteio", "⚽ Painel Bolão Copa"])
    
    with t1:
        df_v = run_query("SELECT * FROM vendas ORDER BY id DESC")
        if not df_v.empty:
            edit_v = st.data_editor(df_v, use_container_width=True, hide_index=True, key="ed_vendas")
            if st.button("💾 Salvar Tabela", key="btn_save_vendas"):
                with conn.session as s:
                    for i, row in edit_v.iterrows():
                        s.execute(text("UPDATE vendas SET item=:item, valor=:valor, codigo_vale=:c, status=:st, nome_real=:n, telefone=:t, email=:e WHERE id=:id"), {"item": str(row['item']), "valor": float(row['valor']), "c": str(row['codigo_vale']), "st": str(row['status']), "n": str(row['nome_real']), "t": str(row['telefone']), "e": str(row.get('email', '')), "id": int(row['id'])})
                    s.commit()
                st.cache_data.clear(); modal_sucesso_salvamento("Vendas salvas")
    
    with t2:
        with st.expander("➕ Cadastrar Novo Usuário (Com opção de Bolão)"):
            with st.form("form_novo"):
                u = st.text_input("Usuário"); s = st.text_input("Senha"); n = st.text_input("Nome"); t = st.text_input("Telefone")
                bal = st.number_input("Saldo", step=100.0); tp = st.selectbox("Tipo", ["comum", "admin", "staff", "supervisor"]); vp = st.number_input("Valor do Ponto", value=0.50)
                bolao_check = st.checkbox("Liberar acesso à nova aba Bolão Copa para este usuário?", value=False)
                if st.form_submit_button("Cadastrar"):
                    ok, msg = cadastrar_novo_usuario(u, s, n, bal, tp, t, vp, False, bolao_check)
                    if ok: st.cache_data.clear(); modal_sucesso_salvamento(msg)
                    else: st.error(msg)
                    
        st.divider(); df_u = run_query("SELECT * FROM usuarios ORDER BY id") 
        if not df_u.empty:
            # Incluído a coluna acesso_bolao na edição em massa do Admin para fácil gerenciamento
            edit_u = st.data_editor(df_u, use_container_width=True, key="ed_u", column_config={"acesso_bolao": st.column_config.CheckboxColumn("Acesso Bolão?", default=False)})
            if st.button("💾 Salvar Tabela Usuários", key="btn_save_users"):
                with conn.session as s:
                    for i, row in edit_u.iterrows():
                        s.execute(text("UPDATE usuarios SET saldo=:s, pontos_historico=:ph, telefone=:t, nome=:n, tipo=:tp, valor_ponto=:vp, acesso_bolao=:ab WHERE id=:id"), 
                                  {"s": float(row['saldo']), "ph": float(row['pontos_historico']), "t": str(row['telefone']), "n": str(row['nome']), "tp": str(row['tipo']), "vp": float(row['valor_ponto']), "ab": bool(row['acesso_bolao']), "id": int(row['id'])})
                    s.commit()
                st.cache_data.clear(); modal_sucesso_salvamento("Usuários Atualizados.")
                
    with t3:
        df_p = run_query("SELECT * FROM premios ORDER BY id")
        edit_p = st.data_editor(df_p, use_container_width=True, num_rows="dynamic", key="ed_p")
        if st.button("Salvar Prêmios"):
            with conn.session as sess:
                for i, row in edit_p.iterrows():
                    if pd.notna(row['id']): sess.execute(text("UPDATE premios SET item=:i, imagem=:im, custo=:c, descricao=:d WHERE id=:id"), {"i": str(row['item']), "im": str(row['imagem']), "c": float(row['custo']), "d": str(row.get('descricao', '')), "id": int(row['id'])})
                    else: sess.execute(text("INSERT INTO premios (item, imagem, custo, descricao) VALUES (:i, :im, :c, :d)"), {"i": str(row['item']), "im": str(row['imagem']), "c": float(row['custo']), "d": str(row.get('descricao', ''))})
                sess.commit()
            st.cache_data.clear(); modal_sucesso_salvamento("Catálogo salvo")
            
    with t4: st.dataframe(run_query("SELECT * FROM logs ORDER BY id DESC LIMIT 50"), use_container_width=True)
    
    with t5:
        rifa_ativa = run_query("SELECT * FROM rifas WHERE status = 'ativa'")
        if not rifa_ativa.empty:
            r = rifa_ativa.iloc[0]; st.success(f"Sorteio Ativo: {r['item_nome']}")
            if st.button("🎲 SORTEAR VENCEDOR"):
                tickets = run_query("SELECT usuario FROM rifa_tickets WHERE rifa_id = :rid", {"rid": int(r['id'])}, ttl=0)
                if not tickets.empty:
                    vencedor = random.choice(tickets['usuario'].tolist())
                    run_transaction("UPDATE rifas SET status = 'encerrada', ganhador_usuario = :u WHERE id = :id", {"u": vencedor, "id": int(r['id'])})
                    st.cache_data.clear(); st.success(f"Vencedor: {vencedor}!"); time.sleep(2); st.rerun()
        else:
            df_premios = run_query("SELECT id, item FROM premios")
            opcoes = {f"{row['id']} - {row['item']}": row['id'] for i, row in df_premios.iterrows()}
            escolha = st.selectbox("Escolha o Prêmio para Sortear:", list(opcoes.keys())) if opcoes else None
            custo_rifa = st.number_input("Custo Ticket", min_value=1, value=50)
            if st.button("🚀 INICIAR SORTEIO") and escolha:
                run_transaction("INSERT INTO rifas (premio_id, item_nome, custo_ticket, status) VALUES (:pid, :nome, :custo, 'ativa')", {"pid": opcoes[escolha], "nome": escolha.split(" - ")[1], "custo": custo_rifa})
                st.cache_data.clear(); st.success("Sorteio Criado!"); st.rerun()

    # NOVA ABA: GERENCIADOR E CRIADOR DE BOLÕES PARA O ADM
    with t6:
        st.markdown("### ⚽ Painel de Controle do Bolão Copa")
        c_b1, c_b2 = st.columns([1, 2])
        
        with c_b1:
            st.markdown("##### ➕ Cadastrar Novo Jogo para o Bolão")
            with st.form("f_novo_jogo", clear_on_submit=True):
                t_a = st.text_input("Time A (Ex: Brasil)")
                t_b = st.text_input("Time B (Ex: França)")
                d_j = st.date_input("Data do Confronto")
                h_j = st.time_input("Horário do Jogo")
                
                if st.form_submit_button("Gerar e Ativar Bolão"):
                    if t_a and t_b:
                        data_timestamp = datetime.combine(d_j, h_j)
                        run_transaction("INSERT INTO bolao_jogos (time_a, time_b, data_jogo, status) VALUES (:ta, :tb, :dt, 'Aberto')", {"ta": t_a, "tb": t_b, "dt": data_timestamp})
                        st.cache_data.clear()
                        st.success(f"Bolão para {t_a} x {t_b} criado com sucesso!")
                        time.sleep(1.5); st.rerun()
                        
        with c_b2:
            st.markdown("##### 🎲 Encerrar e Premiar Jogos Ativos")
            jogos_abertos = run_query("SELECT id, time_a, time_b, data_jogo FROM bolao_jogos WHERE status = 'Aberto' ORDER BY data_jogo ASC", ttl=0)
            if not jogos_abertos.empty:
                opcoes_jogos = {f"{row['time_a']} x {row['time_b']} ({row['data_jogo'].strftime('%d/%m %H:%M')})": row['id'] for _, row in jogos_abertos.iterrows()}
                jogo_sel = st.selectbox("Selecione qual partida deseja encerrar:", list(opcoes_jogos.keys()))
                
                if st.button("Inserir Placar e Finalizar Rodada", type="primary"):
                    id_do_jogo = opcoes_jogos[jogo_sel]
                    partida_df = jogos_abertos[jogos_abertos['id'] == id_do_jogo].iloc[0]
                    finalizar_bolao_dialog(id_do_jogo, partida_df['time_a'], partida_df['time_b'])
            else:
                st.info("Nenhum bolão ativo aguardando encerramento no momento.")
                
            st.divider()
            st.markdown("##### 📜 Histórico de Jogos Finalizados")
            jogos_fim = run_query("SELECT id, time_a, gols_a, gols_b, time_b, status FROM bolao_jogos WHERE status = 'Encerrada' ORDER BY id DESC")
            if not jogos_fim.empty:
                st.dataframe(jogos_fim, use_container_width=True, hide_index=True)

def tela_supervisor():
    st.subheader("📦 Visão Geral de Todos os Resgates")
    df_v = run_query("SELECT id, data, usuario, nome_real, item, valor, status, telefone, email, codigo_vale, recebido_user FROM vendas ORDER BY id DESC")
    if not df_v.empty:
        st.dataframe(df_v, use_container_width=True, hide_index=True)

def tela_principal():
    u_cod, u_nome, sld, tipo = st.session_state.usuario_cod, st.session_state.usuario_nome, st.session_state.saldo_atual, st.session_state.tipo_usuario
    valor_ponto_usuario = st.session_state.get('valor_ponto_usuario', 0.50); valor_padrao_ponto = 0.50 

    if st.session_state.get('lgpd_pendente', False):
        modal_consentimento_lgpd()
    else:
        # MENU SUPERIOR E ADM CONTROLS
        if tipo == 'admin':
            cols = st.columns([3, 1.5], gap="medium")
            c_banner = cols[0]
            with cols[1]:
                c_btn_top = st.columns(2); c_btn_bot = st.columns(2)
                with c_btn_top[0]: 
                    if st.button("Atualizar", type="secondary"): st.cache_data.clear(); st.rerun()
                with c_btn_top[1]: 
                    if st.button("Perfil", type="secondary"): abrir_modal_perfil(u_cod)
                with c_btn_bot[0]: 
                    if st.button("Ver Loja" if st.session_state.admin_mode else "Painel", type="secondary"): st.session_state.admin_mode = not st.session_state.admin_mode; st.rerun()
                with c_btn_bot[1]: 
                    if st.button("Sair", type="secondary"): realizar_logout()
        elif tipo == 'supervisor':
            cols = st.columns([3, 1.5], gap="medium")
            c_banner = cols[0]
            with cols[1]:
                c_btn_top = st.columns(2); c_btn_bot = st.columns(1)
                with c_btn_top[0]: 
                    if st.button("Perfil", type="secondary"): abrir_modal_perfil(u_cod)
                with c_btn_top[1]: 
                    if st.button("Sair", type="secondary"): realizar_logout()
                with c_btn_bot[0]: 
                    if st.button("Ver Loja" if st.session_state.supervisor_mode else "Painel", type="primary"): st.session_state.supervisor_mode = not st.session_state.supervisor_mode; st.rerun()
        else:
            cols = st.columns([3, 1], gap="small")
            c_banner = cols[0]
            with cols[1]:
                if st.button("👤 Meu Perfil", type="secondary"): abrir_modal_perfil(u_cod)
                if st.button("❌ Sair", type="secondary"): realizar_logout()
        
        with c_banner:
            titulo_painel = "Painel Supervisor 👁️" if (tipo == 'supervisor' and st.session_state.supervisor_mode) else f"Olá, {u_nome}! 👋"
            subtitulo = "Acompanhamento total de resgates." if (tipo == 'supervisor' and st.session_state.supervisor_mode) else "Agora você pode trocar seus pontos por prêmios incríveis!"
            st.markdown(f'''<div class="header-style"><div style="display:flex; justify-content:space-between; align-items:center;"><div><h2 style="margin:0; color:white;">{titulo_painel}</h2><p style="margin:0; opacity:0.9; color:white;">{subtitulo}</p></div><div style="text-align:right; color:white;"><span class="saldo-label">SEU SALDO</span><br><span class="saldo-valor">{sld:,.0f}</span> pts</div></div></div>''', unsafe_allow_html=True)
        
        st.divider()
        
        if tipo == 'admin' and st.session_state.admin_mode: 
            tela_admin()
        elif tipo == 'supervisor' and st.session_state.supervisor_mode: 
            tela_supervisor()
        else:
            # ORGANIZAÇÃO DINÂMICA DAS ABAS BASEADO NO PERMISSIVO DO BOLÃO DO USUÁRIO
            abas_nome = ["🎁 Catálogo", "🍀 Sorteio", "📜 Meus Resgates", "🏆 Ranking"]
            if st.session_state.get('acesso_bolao', False):
                # Insere a nova aba do bolão na terceira posição se permitido
                abas_nome.insert(2, "⚽ Bolão Copa")
                
            abas = st.tabs(abas_nome)
            
            # Indexadores dinâmicos para mapear as abas perfeitamente
            idx_catalogo = abas_nome.index("🎁 Catálogo")
            idx_sorteio = abas_nome.index("🍀 Sorteio")
            idx_resgates = abas_nome.index("📜 Meus Resgates")
            idx_ranking = abas_nome.index("🏆 Ranking")
            
            with abas[idx_catalogo]:
                busca = st.text_input("🔍 Buscar Produtos")
                df_p = run_query("SELECT * FROM premios ORDER BY id")
                if not df_p.empty:
                    if busca: df_p = df_p[df_p['item'].str.contains(busca, case=False, na=False)]
                    cols = st.columns(4)
                    for i, (index_db, row) in enumerate(df_p.iterrows()):
                        with cols[i % 4]:
                            with st.container(border=True):
                                if row['imagem']: st.image(processar_link_imagem(row['imagem']))
                                custo_final = int(row['custo'] * (valor_padrao_ponto / valor_ponto_usuario))
                                st.markdown(f"**{row['item']}**\n<div style='color:#0066cc; font-weight:bold;'>{custo_final} pts</div>", unsafe_allow_html=True)
                                c_det, c_res = st.columns(2)
                                with c_det: 
                                    if st.button("Detalhes", key=f"det_{row['id']}"): ver_detalhes_produto(row['item'], row['imagem'], custo_final, row.get('descricao', ''))
                                with c_res: 
                                    if sld >= custo_final and st.button("RESGATAR", key=f"b_{row['id']}", type="primary"): confirmar_resgate_dialog(row['item'], custo_final, u_cod)
            
            with abas[idx_sorteio]:
                rifa_ativa = run_query("SELECT * FROM rifas WHERE status = 'ativa'")
                if not rifa_ativa.empty:
                    r = rifa_ativa.iloc[0]; img_p = ""
                    df_p_img = run_query("SELECT imagem FROM premios WHERE id = :pid", {"pid": int(r['premio_id'])})
                    if not df_p_img.empty: img_p = df_p_img.iloc[0]['imagem']
                    st.markdown(f"<div class='rifa-card'><div class='rifa-tag'>🍀 SORTEIO ATIVO</div><h3>{r['item_nome']}</h3></div>", unsafe_allow_html=True)
                    if img_p: st.image(processar_link_imagem(img_p), width=200)
                    if st.button(f"🎟️ COMPRAR TICKET ({r['custo_ticket']} pts)", type="primary"): confirmar_compra_ticket(int(r['id']), r['item_nome'], r['custo_ticket'], u_cod)
                else: st.info("Nenhum sorteio ativo.")
                
            # NOVA INTERFACE DO BOLÃO PARA O USUÁRIO LOGADO COM PERMISSÃO
            if st.session_state.get('acesso_bolao', False):
                idx_bolao = abas_nome.index("⚽ Bolão Copa")
                with abas[idx_bolao]:
                    st.markdown("### ⚽ Seus Palpites - Bolão da Copa")
                    st.caption("Aposte no placar exato dos confrontos. A sua pontuação final dependerá de quão próximo seu palpite ficou do resultado real!")
                    
                    jogos_ativos = run_query("SELECT * FROM bolao_jogos WHERE status = 'Aberto' ORDER BY data_jogo ASC", ttl=0)
                    if not jogos_ativos.empty:
                        col_jogos = st.columns(3)
                        for i, (_, jogo) in enumerate(jogos_ativos.iterrows()):
                            jid = int(jogo['id'])
                            with col_jogos[i % 3]:
                                st.markdown(f"""
                                <div class="bolao-card">
                                    <div class="bolao-tag">PARTIDA AGENDADA</div>
                                    <h4 style="margin:5px 0;"><b>{jogo['time_a']} x {jogo['time_b']}</b></h4>
                                    <p style="font-size:11px; color:#555; margin-bottom:10px;">📅 {jogo['data_jogo'].strftime('%d/%m/%Y às %H:%M')}</p>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Verificar se o usuário logado já tem palpite registrado para este confronto específico
                                aposta_existente = run_query("SELECT gols_a, gols_b FROM bolao_apostas WHERE jogo_id = :jid AND usuario = :u", {"jid": jid, "u": u_cod}, ttl=0)
                                
                                with st.container():
                                    if not aposta_existente.empty:
                                        p_a = int(aposta_existente.iloc[0]['gols_a'])
                                        p_b = int(aposta_existente.iloc[0]['gols_b'])
                                        st.success(f"Palpite Registrado: **{p_a} x {p_b}**")
                                        
                                        # Permitir alterar palpite
                                        with st.expander("✏️ Alterar meu palpite"):
                                            g_a = st.number_input(f"Gols {jogo['time_a']}", min_value=0, max_value=99, step=1, value=p_a, key=f"edit_ga_{jid}")
                                            g_b = st.number_input(f"Gols {jogo['time_b']}", min_value=0, max_value=99, step=1, value=p_b, key=f"edit_gb_{jid}")
                                            if st.button("Salvar Novo Palpite", key=f"btn_edit_{jid}", type="primary"):
                                                run_transaction("UPDATE bolao_apostas SET gols_a = :ga, gols_b = :gb WHERE jogo_id = :jid AND usuario = :u", {"ga": g_a, "gb": g_b, "jid": jid, "u": u_cod})
                                                st.cache_data.clear(); st.toast("Palpite Atualizado!"); time.sleep(1); st.rerun()
                                    else:
                                        # Criar novos inputs de palpite
                                        c_ap1, c_ap2 = st.columns(2)
                                        g_a = c_ap1.number_input(f"{jogo['time_a']}", min_value=0, max_value=99, step=1, value=0, key=f"new_ga_{jid}")
                                        g_b = c_ap2.number_input(f"{jogo['time_b']}", min_value=0, max_value=99, step=1, value=0, key=f"new_gb_{jid}")
                                        
                                        if st.button("Confirmar Palpite", key=f"btn_save_{jid}", type="secondary"):
                                            run_transaction("INSERT INTO bolao_apostas (jogo_id, usuario, gols_a, gols_b) VALUES (:jid, :u, :ga, :gb)", {"jid": jid, "u": u_cod, "ga": g_a, "gb": g_b})
                                            st.cache_data.clear(); st.toast("Palpite Gravado!"); time.sleep(1); st.rerun()
                    else:
                        st.info("Nenhum confronto disponível para apostas no momento. Aguarde o administrador lançar novos jogos!")
            
            with abas[idx_resgates]:
                st.info("### Pedido recebido! Prazo: 5 dias úteis no Whatsapp informado.")
                meus_pedidos = run_query("SELECT id, data, item, valor, status, codigo_vale, recebido_user FROM vendas WHERE LOWER(usuario) = LOWER(:u) ORDER BY data DESC", {"u": u_cod})
                if not meus_pedidos.empty:
                    editor_pedidos = st.data_editor(meus_pedidos, use_container_width=True, hide_index=True, key="ed_meus_ped")
                    if st.button("💾 Confirmar Recebimento"):
                        with conn.session as s:
                            for i, row in editor_pedidos.iterrows():
                                s.execute(text("UPDATE vendas SET recebido_user = :ru WHERE id = :id"), {"ru": bool(row['recebido_user']), "id": row['id']})
                            s.commit()
                        st.cache_data.clear(); st.toast("Atualizado!", icon="✅"); time.sleep(1); st.rerun()
                        
            with abas[idx_ranking]:
                df_rank = run_query("SELECT usuario, pontos_historico FROM usuarios WHERE tipo NOT IN ('admin', 'staff', 'supervisor') ORDER BY pontos_historico DESC LIMIT 10")
                if not df_rank.empty: st.dataframe(df_rank, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    qp = st.query_params
    if "rt" in qp:
        tela_nova_senha_token(qp["rt"])
    else:
        verificar_sessao_automatica()
        if st.session_state.get('logado', False): tela_principal()
        else: tela_login()
