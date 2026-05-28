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
                    status VARCHAR(20) DEFAULT 'Aberto',
                    vencedor_usuario VARCHAR(255) DEFAULT NULL
                );
            """))
            s.execute(text("ALTER TABLE bolao_jogos ADD COLUMN IF NOT EXISTS vencedor_usuario VARCHAR(255);"))
            
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
        except Exception as e:
            print(f"Erro BD: {e}") 

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

    @keyframes gradient { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }

    h1, h2, h3, h4, h5, h6, p, a, li, button, input, select, textarea, label, .stMarkdown, .stText { font-family: 'Poppins', sans-serif !important; color: #31333F; }
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }

    .header-style { background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); background-size: 400% 400% !important; animation: gradient 10s ease infinite !important; padding: 0 25px; border-radius: 12px; color: white !important; box-shadow: 0 4px 15px rgba(0,0,0,0.1); display: flex; flex-direction: column; justify-content: center; height: 110px !important; margin: 0 !important; }
    .header-style h2, .header-style p, .header-style span, .header-style div { color: white !important; }
    .header-style h2 { font-size: 20px !important; font-weight: 700 !important; margin: 0 !important; }
    .header-style p { font-size: 12px !important; line-height: 1.3 !important; opacity: 0.9 !important; margin: 2px 0 0 0 !important; }
    .header-style .saldo-label { font-size: 10px !important; font-weight: 600 !important; }
    .header-style .saldo-valor { font-size: 30px !important; font-weight: 900 !important; text-shadow: 0 2px 4px rgba(0,0,0,0.15); }

    div.stButton > button { border-radius: 8px !important; font-weight: 600 !important; width: 100%; border: none !important; }
    [data-testid="stTabs"] div.stButton > button { height: 45px !important; min-height: 45px !important; max-height: 45px !important; margin-top: auto !important; }
    [data-testid="stTabs"] button[kind="primary"] { background-color: #0066cc !important; color: white !important; }
    [data-testid="stTabs"] button[kind="primary"]:hover { background-color: #0052a3 !important; }
    [data-testid="stTabs"] button[kind="primary"] p { color: white !important; }
    [data-testid="stTabs"] button[kind="secondary"] { background-color: #ffffff !important; color: #003366 !important; border: 1px solid #e0e0e0 !important; }
    [data-testid="stTabs"] button[kind="secondary"]:hover { background-color: #f5f5f5 !important; }
    div[data-testid="column"] div.stButton > button[kind="secondary"] { background-color: #ffffff !important; color: #003366 !important; border: 2px solid #eef2f6 !important; height: 50px !important; min-height: 50px !important; }

    [data-testid="stImage"] img { height: 110px !important; object-fit: contain !important; border-radius: 10px; }
    [data-testid="stMetricValue"] { font-size: 2.2rem !important; }
    [data-testid="stMetricLabel"] { font-size: 1rem !important; }

    .rifa-card { border: 2px solid #FFD700; background: linear-gradient(to bottom right, #fffdf0, #ffffff); padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .rifa-tag { background-color: #FFD700; color: #000; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 12px; margin-bottom: 10px; display: inline-block; }
    .winner-card { border: 2px solid #28a745; background: linear-gradient(to bottom right, #f0fff4, #ffffff); padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .winner-tag { background-color: #28a745; color: #fff; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 12px; margin-bottom: 10px; display: inline-block; }

    .bolao-card { border: 2px solid #2F80ED; background: linear-gradient(to bottom right, #f0f6ff, #ffffff); padding: 18px; border-radius: 12px; text-align: center; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .bolao-tag { background-color: #2F80ED; color: white; padding: 3px 12px; border-radius: 15px; font-weight: bold; font-size: 11px; margin-bottom: 8px; display: inline-block; }

    @media only screen and (max-width: 600px) {
        .header-style { height: auto !important; padding: 15px !important; text-align: center !important; }
        div.stButton > button { height: 50px !important; }
    }
"""

if not st.session_state.get('logado', False): estilo_especifico = ".stApp { background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); background-size: 400% 400% !important; animation: gradient 15s ease infinite !important; } [data-testid='stForm'] { background-color: #ffffff; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }"
else: estilo_especifico = ".stApp { background-color: #f4f8fb; }"
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

def gerar_hash(senha): return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
def gerar_senha_aleatoria(tamanho=6): return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(tamanho))

def formatar_telefone(tel):
    apenas_numeros = re.sub(r'\D', '', str(tel))
    if 10 <= len(apenas_numeros) <= 11: apenas_numeros = "55" + apenas_numeros
    return apenas_numeros

# --- GERENCIAMENTO DE SESSÃO ---
def criar_sessao_persistente(usuario_id):
    token = str(uuid.uuid4()); expira_em = datetime.now() + timedelta(hours=24)
    with conn.session as s:
        s.execute(text("UPDATE usuarios SET token_sessao = :t, token_expira_em = :exp WHERE id = :id"), {"t": token, "exp": expira_em, "id": usuario_id})
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
                st.session_state.update({
                    'logado': True, 'usuario_cod': row['usuario'], 'usuario_nome': row['nome'], 'tipo_usuario': str(row['tipo']).lower().strip(), 'saldo_atual': float(row['saldo']),
                    'valor_ponto_usuario': float(row.get('valor_ponto', 0.50) or 0.50), 'lgpd_pendente': not bool(row.get('consentimento_lgpd', False)), 'acesso_bolao': bool(row.get('acesso_bolao', False))
                })
                st.rerun()
            else:
                if st.query_params.get("sessao"): st.query_params.clear()
        except Exception: pass

def realizar_logout():
    if st.session_state.get('usuario_cod'):
        with conn.session as s:
            s.execute(text("UPDATE usuarios SET token_sessao = NULL WHERE usuario = :u"), {"u": st.session_state.usuario_cod})
            s.commit()
    st.query_params.clear(); st.session_state.clear(); st.rerun()

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
def run_query(query_str, params=None, ttl="5m"):
    try: return conn.query(query_str, params=params, ttl=ttl)
    except Exception:
        st.cache_data.clear()
        try: conn.reset(); return conn.query(query_str, params=params, ttl=ttl)
        except Exception: st.error("O banco de dados está se reconectando. Atualize a página."); return pd.DataFrame()

def run_transaction(query_str, params=None):
    with conn.session as s: s.execute(text(query_str), params if params else {}); s.commit()

def registrar_log(acao, detalhes):
    try:
        resp = st.session_state.get('usuario_nome', 'Sistema')
        run_transaction("INSERT INTO logs (data, responsavel, acao, detalhes) VALUES (NOW(), :resp, :acao, :det)", {"resp": resp, "acao": acao, "det": detalhes})
    except Exception: pass

# --- MOTOR DE PONTUAÇÃO DO BOLÃO ---
def calcular_pontos_aposta(gols_a_real, gols_b_real, gols_a_aposta, gols_b_aposta):
    pontos = 0
    saldo_real = gols_a_real - gols_b_real
    vencedor_real = "A" if saldo_real > 0 else "B" if saldo_real < 0 else "Empate"
    
    saldo_aposta = gols_a_aposta - gols_b_aposta
    vencedor_aposta = "A" if saldo_aposta > 0 else "B" if saldo_aposta < 0 else "Empate"
    
    if vencedor_real == vencedor_aposta: pontos += 10
    if saldo_real == saldo_aposta: pontos += 5
    if gols_a_real == gols_a_aposta: pontos += 3
    if gols_b_real == gols_b_aposta: pontos += 3
    if (gols_a_real == gols_a_aposta) and (gols_b_real == gols_b_aposta): pontos += 10
        
    return pontos

# --- LÓGICA DE NEGÓCIO ---
def validar_login(user_input, pass_input):
    df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": user_input.strip()}, ttl=0)
    if df.empty: return False, None, None, 0, None, None, 0.50, False, False
    linha = df.iloc[0]
    if verificar_senha_hash(pass_input.strip(), linha['senha']):
        v_ponto = float(linha.get('valor_ponto', 0.50) or 0.50); tem_lgpd = bool(linha.get('consentimento_lgpd', False)); ac_bolao = bool(linha.get('acesso_bolao', False))
        return True, linha['nome'], str(linha['tipo']).lower().strip(), float(linha['saldo']), str(linha['telefone']), int(linha['id']), v_ponto, tem_lgpd, ac_bolao
    return False, None, None, 0, None, None, 0.50, False, False

def salvar_venda(usuario_cod, item_nome, custo, email_contato, telefone_resgate):
    try:
        user_df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario_cod}, ttl=0)
        if user_df.empty: st.error("Erro: Cadastro não localizado."); return False
        if float(user_df.iloc[0]['saldo']) < custo: st.error("Saldo insuficiente."); return False
        with conn.session as s:
            s.execute(text("UPDATE usuarios SET saldo = saldo - :custo WHERE LOWER(usuario) = LOWER(:u)"), {"custo": custo, "u": usuario_cod})
            s.execute(text("INSERT INTO vendas (data, usuario, item, valor, status, email, nome_real, telefone) VALUES (NOW(), :u, :item, :valor, 'Pendente', :email, :nome, :tel)"),
                {"u": usuario_cod, "item": item_nome, "valor": custo, "email": email_contato, "nome": user_df.iloc[0]['nome'], "tel": telefone_resgate})
            s.commit()
        registrar_log("Resgate", f"Item: {item_nome}"); st.session_state['saldo_atual'] -= custo; st.cache_data.clear(); return True
    except Exception as e: st.error(f"Erro: {e}"); return False

def comprar_ticket_rifa(rifa_id, custo, usuario_cod):
    try:
        user_df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario_cod}, ttl=0)
        if user_df.empty: return False, "Usuário não encontrado"
        if float(user_df.iloc[0]['saldo']) < float(custo): return False, "Saldo insuficiente"
        with conn.session as s:
            s.execute(text("UPDATE usuarios SET saldo = saldo - :custo WHERE LOWER(usuario) = LOWER(:u)"), {"custo": float(custo), "u": usuario_cod})
            s.execute(text("INSERT INTO rifa_tickets (rifa_id, usuario) VALUES (:rid, :u)"), {"rid": int(rifa_id), "u": usuario_cod})
            s.commit()
        st.session_state['saldo_atual'] -= float(custo); st.cache_data.clear(); return True, "Ticket comprado!"
    except Exception as e: return False, f"Erro: {str(e)}"

def cadastrar_novo_usuario(usuario, senha, nome, saldo, tipo, telefone, valor_ponto=0.50, consentimento_lgpd=False, acesso_bolao=False):
    try:
        df = run_query("SELECT id FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario.strip()}, ttl=0)
        if not df.empty: return False, "Usuário já existe!"
        run_transaction("INSERT INTO usuarios (usuario, senha, nome, saldo, pontos_historico, tipo, telefone, valor_ponto, consentimento_lgpd, data_consentimento, acesso_bolao) VALUES (:u, :s, :n, :bal, :bal, :t, :tel, :vp, :lgpd, :dt, :ab)",
            {"u": usuario.strip(), "s": gerar_hash(senha), "n": nome, "bal": saldo, "t": tipo, "tel": formatar_telefone(telefone), "vp": valor_ponto, "lgpd": consentimento_lgpd, "dt": datetime.now() if consentimento_lgpd else None, "ab": acesso_bolao})
        return True, "Cadastrado com sucesso!"
    except Exception as e: return False, f"Erro: {str(e)}"

# --- MODAIS E DIÁLOGOS ---
@st.dialog("🔒 Termos de Uso e Privacidade (LGPD)")
def modal_consentimento_lgpd():
    st.markdown("### Política de Privacidade e Proteção de Dados\nPara continuar utilizando a Lojinha Culli's, precisamos do seu consentimento...")
    if st.button("✅ LI E ACEITO OS TERMOS", type="primary"):
        run_transaction("UPDATE usuarios SET consentimento_lgpd = TRUE, data_consentimento = NOW() WHERE usuario = :u", {"u": st.session_state.get('usuario_cod')})
        st.session_state['lgpd_pendente'] = False; st.cache_data.clear(); st.rerun()

@st.dialog("💾 Confirmação de Sistema")
def modal_sucesso_salvamento(detalhes):
    st.success("Ação concluída!"); st.code(f"LOG: {detalhes}"); 
    if st.button("Fechar", type="primary"): st.rerun()

@st.dialog("👤 Meu Perfil")
def abrir_modal_perfil(usuario_cod):
    df_user = run_query("SELECT nome, telefone FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario_cod}, ttl=0)
    if df_user.empty: return
    nome_atual, tel_atual = df_user.iloc[0]['nome'], str(df_user.iloc[0]['telefone'])
    with st.form("form_perfil"):
        novo_nome = st.text_input("Nome", value=nome_atual); novo_telefone = st.text_input("Telefone", value=tel_atual)
        n = st.text_input("Nova Senha", type="password"); c = st.text_input("Confirmar", type="password")
        if st.form_submit_button("Salvar", type="primary"):
            if len(formatar_telefone(novo_telefone)) < 12: st.error("Telefone inválido!"); return
            query = "UPDATE usuarios SET nome = :n, telefone = :t"; params = {"n": novo_nome, "t": formatar_telefone(novo_telefone), "u": usuario_cod}
            if n or c:
                if n != c: st.error("Senhas não coincidem!"); return
                query += ", senha = :s"; params["s"] = gerar_hash(n)
            query += " WHERE LOWER(usuario) = LOWER(:u)"; run_transaction(query, params)
            st.session_state['usuario_nome'] = novo_nome; st.success("Atualizado!"); time.sleep(1); st.rerun()

@st.dialog("🔑 Recuperar Acesso")
def enviar_link_recuperacao():
    user_input = st.text_input("Login")
    if st.button("Enviar Link", type="primary"):
        df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": user_input.strip()}, ttl=0)
        if df.empty: st.error("Usuário não encontrado."); return
        tk = str(uuid.uuid4()); exp = datetime.now() + timedelta(minutes=15)
        run_transaction("UPDATE usuarios SET reset_token = :rt, reset_token_expira = :exp WHERE id = :id", {"rt": tk, "exp": exp, "id": int(df.iloc[0]['id'])})
        ok, det, cod = enviar_sms(str(df.iloc[0]['telefone']), f"Culli: Link para redefinir senha (15 min): https://lojinha-culligan.streamlit.app/?rt={tk}")
        if ok: st.success("SMS enviado!"); time.sleep(2); st.rerun()
        else: st.error(f"Erro: {det}")

def tela_nova_senha_token(token_url):
    st.markdown("<h2>🔐 Nova Senha</h2>", unsafe_allow_html=True)
    df = run_query("SELECT * FROM usuarios WHERE reset_token = :rt AND reset_token_expira > NOW()", {"rt": token_url}, ttl=0)
    if df.empty:
        st.error("Link inválido/expirado."); 
        if st.button("Voltar"): st.query_params.clear(); st.rerun()
        return
    with st.form("f_reset"):
        n1 = st.text_input("Nova Senha", type="password"); n2 = st.text_input("Confirme", type="password")
        if st.form_submit_button("REDEFINIR", type="primary"):
            if n1 == n2 and len(n1) >= 4:
                run_transaction("UPDATE usuarios SET senha = :s, reset_token = NULL, reset_token_expira = NULL WHERE id = :id", {"s": gerar_hash(n1), "id": int(df.iloc[0]['id'])})
                st.success("Senha alterada!"); st.query_params.clear(); time.sleep(2); st.rerun()

@st.dialog("🎁 Confirmar Resgate")
def confirmar_resgate_dialog(item_nome, custo, usuario_cod):
    with st.form("form_resgate"):
        email = st.text_input("E-mail:"); tel = st.text_input("WhatsApp:")
        if st.form_submit_button("CONFIRMAR", type="primary"):
            if "@" not in email: st.error("E-mail inválido."); return
            if salvar_venda(usuario_cod, item_nome, custo, email, formatar_telefone(tel)): st.success("Sucesso!"); time.sleep(1); st.rerun()

@st.dialog("🎟️ Comprar Ticket Rifa")
def confirmar_compra_ticket(rifa_id, custo, usuario_cod):
    if st.button("CONFIRMAR COMPRA", type="primary"):
        ok, msg = comprar_ticket_rifa(rifa_id, custo, usuario_cod)
        if ok: st.success(msg); time.sleep(1); st.rerun()
        else: st.error(msg)

@st.dialog("⚽ Finalizar e Premiar Bolão")
def finalizar_bolao_dialog(jogo_id, time_a, time_b):
    st.subheader(f"{time_a} x {time_b}")
    
    fase_key = f"bolao_fase_{jogo_id}"
    if fase_key not in st.session_state:
        st.session_state[fase_key] = 1

    # ETAPA 1: Lançar placar e ver quem ganhou
    if st.session_state[fase_key] == 1:
        st.markdown("Insira o placar oficial do jogo para descobrirmos os ganhadores:")
        gols_a = st.number_input(f"Gols {time_a}", min_value=0, step=1, value=0)
        gols_b = st.number_input(f"Gols {time_b}", min_value=0, step=1, value=0)
        
        if st.button("Verificar Resultados Técnicos", type="primary", use_container_width=True):
            apostas_df = run_query("SELECT * FROM bolao_apostas WHERE jogo_id = :jid", {"jid": int(jogo_id)}, ttl=0)
            if apostas_df.empty:
                run_transaction("UPDATE bolao_jogos SET gols_a = :ga, gols_b = :gb, status = 'Encerrada', vencedor_usuario = 'Sem Apostas' WHERE id = :id", {"ga": gols_a, "gb": gols_b, "id": int(jogo_id)})
                st.warning("Nenhuma aposta foi feita neste jogo. A rodada foi encerrada sem ganhadores.")
                st.cache_data.clear(); del st.session_state[fase_key]
                time.sleep(2); st.rerun(); return

            lista_resultados = []
            for _, row in apostas_df.iterrows():
                pts = calcular_pontos_aposta(gols_a, gols_b, int(row['gols_a']), int(row['gols_b']))
                lista_resultados.append({"usuario": row['usuario'], "pontos": pts, "ap_a": row['gols_a'], "ap_b": row['gols_b']})
                
            res_df = pd.DataFrame(lista_resultados)
            maior_pontuacao = res_df['pontos'].max()
            vencedores = res_df[res_df['pontos'] == maior_pontuacao].to_dict('records')
            
            st.session_state[f"bolao_vencedores_{jogo_id}"] = vencedores
            st.session_state[f"bolao_placar_{jogo_id}"] = (gols_a, gols_b)
            st.session_state[f"bolao_maior_pts_{jogo_id}"] = maior_pontuacao
            st.session_state[fase_key] = 2; st.rerun()

    # ETAPA 2: Confirmar o prêmio e distribuir pontos
    elif st.session_state[fase_key] == 2:
        gols_a, gols_b = st.session_state[f"bolao_placar_{jogo_id}"]
        vencedores_list = st.session_state[f"bolao_vencedores_{jogo_id}"]
        maior_pontuacao = st.session_state[f"bolao_maior_pts_{jogo_id}"]
        
        st.success(f"**Resultado Real:** {time_a} {gols_a} x {gols_b} {time_b}")
        st.info(f"🏆 **Maior Pontuação Alcançada:** {maior_pontuacao} pts")
        st.write("👥 **Usuário(s) Vencedor(es):**")
        
        nomes_vencedores = []
        for v in vencedores_list:
            u_info = run_query("SELECT nome FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": v['usuario']}, ttl=0)
            nome_real = u_info.iloc[0]['nome'] if not u_info.empty else v['usuario']
            nomes_vencedores.append(nome_real)
            st.markdown(f"- **{nome_real}** (Apostou: {v['ap_a']} x {v['ap_b']})")
            
        st.divider(); st.markdown("##### 💎 Distribuição de Prêmio")
        pontos_premio = st.number_input("Quantos pontos cada vencedor acima deve receber na Lojinha?", min_value=0, step=50, value=200)
        
        col_voltar, col_premiar = st.columns(2)
        if col_voltar.button("Corrigir Placar"):
            st.session_state[fase_key] = 1; st.rerun()
            
        if col_premiar.button("Confirmar e Premiar", type="primary"):
            string_vencedores = ", ".join(nomes_vencedores)
            
            with conn.session as s:
                s.execute(text("UPDATE bolao_jogos SET gols_a = :ga, gols_b = :gb, status = 'Encerrada', vencedor_usuario = :vu WHERE id = :id"), 
                          {"ga": gols_a, "gb": gols_b, "vu": string_vencedores, "id": int(jogo_id)})
                
                for v in vencedores_list:
                    v_user = v['usuario']
                    s.execute(text("UPDATE usuarios SET saldo = saldo + :p, pontos_historico = COALESCE(pontos_historico, 0) + :p WHERE LOWER(usuario) = LOWER(:u)"), {"p": float(pontos_premio), "u": v_user})
                    s.execute(text("INSERT INTO vendas (data, usuario, item, valor, status, nome_real, telefone) VALUES (NOW(), :u, :item, 0, 'Liberado', :nr, :t)"), {"u": v_user, "item": f"Vencedor Bolão: {time_a} x {time_b}", "nr": v_user, "t": ""})
                
                s.commit()
                
            for v in vencedores_list:
                u_info = run_query("SELECT nome, telefone FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": v['usuario']}, ttl=0)
                if not u_info.empty:
                    nome_v = u_info.iloc[0]['nome']; tel_v = str(u_info.iloc[0]['telefone'])
                    msg_sms = f"Culli Copa: GOLAAACO! {nome_v}, voce venceu o Bolao e faturou {pontos_premio} pts! Confira na Lojinha."
                    enviar_sms(tel_v, msg_sms)
                    enviar_whatsapp_template(tel_v, [nome_v, f"Bolão Copa: {time_a} x {time_b}", f"Parabéns! Você ganhou +{pontos_premio} pts!"], "atualizar_envio_pedidos")
                    
            st.cache_data.clear()
            del st.session_state[fase_key]; del st.session_state[f"bolao_vencedores_{jogo_id}"]
            st.balloons(); st.success("Prêmios distribuídos e partida encerrada com sucesso!"); time.sleep(3); st.rerun()

@st.dialog("🔍 Detalhes do Produto")
def ver_detalhes_produto(item, imagem, custo, descricao):
    st.image(processar_link_imagem(imagem), use_container_width=True)
    st.markdown(f"## {item}\n#### 💎 Valor: **{custo} pts**\n### 📝 Descrição")
    st.write(descricao if descricao and str(descricao).lower() != "none" else "Sem descrição.")

# --- TELAS ---
def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        if st.session_state.get('em_verificacao_2fa', False):
            with st.form("f_2fa"):
                st.markdown("### 🔒 Código de Segurança (SMS)")
                codigo_digitado = st.text_input("Código de 6 dígitos", max_chars=6)
                if st.form_submit_button("VALIDAR", type="primary", use_container_width=True):
                    if codigo_digitado == st.session_state.codigo_2fa_esperado:
                        dados = st.session_state.dados_usuario_temp
                        st.session_state.update({'logado': True, 'usuario_cod': dados['usuario'], 'usuario_nome': dados['nome'], 'tipo_usuario': dados['tipo'], 'saldo_atual': dados['saldo'], 'valor_ponto_usuario': dados['valor_ponto'], 'em_verificacao_2fa': False, 'lgpd_pendente': not st.session_state['temp_lgpd_status'], 'acesso_bolao': dados['acesso_bolao']})
                        criar_sessao_persistente(dados['id']); st.rerun()
                    else: st.error("Código incorreto.")
        else:
            with st.form("f_login"):
                st.markdown("<h1 style='text-align:center;'>Lojinha Culli's</h1>", unsafe_allow_html=True)
                u = st.text_input("Usuário"); s = st.text_input("Senha", type="password")
                if st.form_submit_button("ENTRAR", type="primary", use_container_width=True):
                    ok, n, t, sld, tel_completo, uid, vp, lgpd, acb = validar_login(u, s)
                    if ok:
                        codigo = str(random.randint(100000, 999999))
                        enviou, info, _ = enviar_sms(tel_completo, f"Culli: Seu codigo de acesso eh {codigo}")
                        if enviou:
                            st.session_state.update({'em_verificacao_2fa': True, 'codigo_2fa_esperado': codigo, 'dados_usuario_temp': {'usuario': u.strip(), 'nome': n, 'tipo': t, 'saldo': sld, 'telefone': tel_completo, 'id': uid, 'valor_ponto': vp, 'acesso_bolao': acb}, 'temp_lgpd_status': lgpd}); st.rerun()
                        else: st.error(f"Erro SMS: {info}")
                    else: st.toast("Erro no login", icon="❌")
            c_l1, c_l2 = st.columns(2)
            with c_l1: 
                if st.button("Esqueci a senha", use_container_width=True): enviar_link_recuperacao()
            with c_l2: 
                if st.button("Primeiro Acesso?", use_container_width=True): enviar_link_recuperacao()

def tela_admin():
    st.divider()
    t1, t2, t3, t4, t5, t6 = st.tabs(["📊 Entregas", "👥 Usuários", "🎁 Prêmios", "🛠️ Logs", "🎟️ Sorteio", "⚽ Painel Bolão"])
    
    with t1:
        df_v = run_query("SELECT * FROM vendas ORDER BY id DESC")
        if not df_v.empty:
            edit_v = st.data_editor(df_v, use_container_width=True, hide_index=True)
            if st.button("Salvar Vendas"):
                with conn.session as s:
                    for i, row in edit_v.iterrows():
                        s.execute(text("UPDATE vendas SET status=:st, recebido_user=:ru WHERE id=:id"), {"st": str(row['status']), "ru": bool(row['recebido_user']), "id": int(row['id'])})
                    s.commit()
                st.cache_data.clear(); modal_sucesso_salvamento("Salvo")
    
    with t2:
        with st.expander("➕ Novo Usuário"):
            with st.form("form_novo"):
                u = st.text_input("Usuário"); s = st.text_input("Senha"); n = st.text_input("Nome"); t = st.text_input("Telefone")
                bal = st.number_input("Saldo", step=100.0); tp = st.selectbox("Tipo", ["comum", "admin", "staff", "supervisor"]); vp = st.number_input("Valor Ponto", value=0.50)
                ab = st.checkbox("Liberar Bolão Copa?")
                if st.form_submit_button("Cadastrar"):
                    ok, msg = cadastrar_novo_usuario(u, s, n, bal, tp, t, vp, False, ab)
                    if ok: st.cache_data.clear(); modal_sucesso_salvamento(msg)
                    else: st.error(msg)
        df_u = run_query("SELECT * FROM usuarios ORDER BY id") 
        if not df_u.empty:
            edit_u = st.data_editor(df_u, use_container_width=True, column_config={"acesso_bolao": st.column_config.CheckboxColumn("Bolão?")})
            if st.button("Salvar Usuários"):
                with conn.session as s:
                    for i, row in edit_u.iterrows():
                        s.execute(text("UPDATE usuarios SET saldo=:s, tipo=:tp, valor_ponto=:vp, acesso_bolao=:ab WHERE id=:id"), {"s": float(row['saldo']), "tp": str(row['tipo']), "vp": float(row['valor_ponto']), "ab": bool(row['acesso_bolao']), "id": int(row['id'])})
                    s.commit()
                st.cache_data.clear(); modal_sucesso_salvamento("Salvo")
                
    with t3:
        df_p = run_query("SELECT * FROM premios ORDER BY id")
        edit_p = st.data_editor(df_p, use_container_width=True, num_rows="dynamic")
        if st.button("Salvar Prêmios"):
            with conn.session as s:
                for i, row in edit_p.iterrows():
                    if pd.notna(row['id']): s.execute(text("UPDATE premios SET item=:i, custo=:c WHERE id=:id"), {"i": str(row['item']), "c": float(row['custo']), "id": int(row['id'])})
                    else: s.execute(text("INSERT INTO premios (item, custo) VALUES (:i, :c)"), {"i": str(row['item']), "c": float(row['custo'])})
                s.commit()
            st.cache_data.clear(); modal_sucesso_salvamento("Salvo")
            
    with t4: st.dataframe(run_query("SELECT * FROM logs ORDER BY id DESC LIMIT 50"), use_container_width=True)
    
    with t5:
        rifa_ativa = run_query("SELECT * FROM rifas WHERE status = 'ativa'")
        if not rifa_ativa.empty:
            r = rifa_ativa.iloc[0]; st.success(f"Ativo: {r['item_nome']}")
            if st.button("SORTEAR"):
                tkts = run_query("SELECT usuario FROM rifa_tickets WHERE rifa_id = :rid", {"rid": int(r['id'])}, ttl=0)
                if not tkts.empty: run_transaction("UPDATE rifas SET status = 'encerrada', ganhador_usuario = :u WHERE id = :id", {"u": random.choice(tkts['usuario'].tolist()), "id": int(r['id'])}); st.cache_data.clear(); st.rerun()
        else:
            df_p2 = run_query("SELECT id, item FROM premios")
            ops = {f"{row['id']} - {row['item']}": row['id'] for i, row in df_p2.iterrows()}
            esc = st.selectbox("Prêmio:", list(ops.keys())) if ops else None
            c_r = st.number_input("Custo Ticket", min_value=1, value=50)
            if st.button("INICIAR SORTEIO") and esc:
                run_transaction("INSERT INTO rifas (premio_id, item_nome, custo_ticket, status) VALUES (:pid, :n, :c, 'ativa')", {"pid": ops[esc], "n": esc.split(" - ")[1], "c": c_r}); st.cache_data.clear(); st.rerun()

    with t6:
        st.markdown("### ⚽ Painel de Controle do Bolão Copa")
        cb1, cb2 = st.columns([1, 2])
        with cb1:
            st.markdown("##### ➕ Novo Jogo")
            with st.form("f_nj", clear_on_submit=True):
                ta = st.text_input("Time A"); tb = st.text_input("Time B"); dj = st.date_input("Data"); hj = st.time_input("Horário")
                if st.form_submit_button("Gerar Bolão") and ta and tb:
                    run_transaction("INSERT INTO bolao_jogos (time_a, time_b, data_jogo) VALUES (:ta, :tb, :dt)", {"ta": ta, "tb": tb, "dt": datetime.combine(dj, hj)}); st.cache_data.clear(); st.success("Criado!"); time.sleep(1); st.rerun()
        with cb2:
            st.markdown("##### 🎲 Encerrar e Premiar Jogos")
            ja = run_query("SELECT id, time_a, time_b, data_jogo FROM bolao_jogos WHERE status = 'Aberto' ORDER BY data_jogo ASC", ttl=0)
            if not ja.empty:
                op_j = {f"{row['time_a']} x {row['time_b']}": row['id'] for _, row in ja.iterrows()}
                jsel = st.selectbox("Selecione o jogo para encerrar:", list(op_j.keys()))
                if st.button("Inserir Placar", type="primary"):
                    p_df = ja[ja['id'] == op_j[jsel]].iloc[0]
                    finalizar_bolao_dialog(op_j[jsel], p_df['time_a'], p_df['time_b'])
            else: st.info("Nenhum bolão aguardando encerramento.")
            
            st.divider(); st.markdown("##### 📜 Histórico de Jogos Finalizados")
            jf = run_query("SELECT id, time_a, gols_a, gols_b, time_b, vencedor_usuario as Ganhador FROM bolao_jogos WHERE status = 'Encerrada' ORDER BY id DESC")
            if not jf.empty: st.dataframe(jf, use_container_width=True, hide_index=True)

def tela_supervisor():
    df_v = run_query("SELECT id, data, usuario, item, valor, status, telefone FROM vendas ORDER BY id DESC")
    if not df_v.empty: st.dataframe(df_v, use_container_width=True, hide_index=True)

def tela_principal():
    u_cod, u_nome, sld, tipo = st.session_state.usuario_cod, st.session_state.usuario_nome, st.session_state.saldo_atual, st.session_state.tipo_usuario
    valor_ponto_usuario = st.session_state.get('valor_ponto_usuario', 0.50); valor_padrao_ponto = 0.50 

    # --- VERIFICAÇÃO DE LGPD ---
    if st.session_state.get('lgpd_pendente', False):
        modal_consentimento_lgpd()
    
    # Se já aceitou, segue o fluxo normal
    else:
        # MENU SUPERIOR COM O LAYOUT ORIGINAL RESTAURADO
        if tipo == 'admin':
            cols = st.columns([3, 1.5], gap="medium")
            c_banner = cols[0]
            with cols[1]:
                c_btn_top = st.columns(2, gap="small")
                c_btn_bot = st.columns(2, gap="small")
                with c_btn_top[0]:
                    if st.button("Atualizar", type="secondary", use_container_width=True): st.cache_data.clear(); st.toast("Sincronizado!", icon="✅"); time.sleep(1); st.rerun()
                with c_btn_top[1]:
                    if st.button("Perfil", type="secondary", use_container_width=True): abrir_modal_perfil(u_cod)
                with c_btn_bot[0]:
                    label = "Ver Loja" if st.session_state.admin_mode else "Voltar"
                    if st.button(label, type="secondary", use_container_width=True): st.session_state.admin_mode = not st.session_state.admin_mode; st.rerun()
                with c_btn_bot[1]:
                    if st.button("Sair", type="secondary", use_container_width=True): realizar_logout()
        
        elif tipo == 'supervisor':
            cols = st.columns([3, 1.5], gap="medium")
            c_banner = cols[0]
            with cols[1]:
                c_btn_top = st.columns(2, gap="small")
                c_btn_bot = st.columns(1, gap="small")
                with c_btn_top[0]:
                     if st.button("Perfil", type="secondary", use_container_width=True): abrir_modal_perfil(u_cod)
                with c_btn_top[1]:
                    if st.button("Sair", type="secondary", use_container_width=True): realizar_logout()
                with c_btn_bot[0]:
                    label_sup = "Ver Loja" if st.session_state.supervisor_mode else "Painel Supervisor"
                    if st.button(label_sup, type="primary", use_container_width=True): 
                        st.session_state.supervisor_mode = not st.session_state.supervisor_mode
                        st.rerun()

        else:
            cols = st.columns([3, 1], gap="small")
            c_banner = cols[0]
            c_buttons = cols[1]
            with c_buttons:
                if st.button("👤 Meu Perfil", type="secondary", use_container_width=True): abrir_modal_perfil(u_cod)
                if st.button("❌ Sair", type="secondary", use_container_width=True): realizar_logout()
        
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
                abas_nome.insert(2, "⚽ Bolão Copa")
                
            abas = st.tabs(abas_nome)
            
            with abas[abas_nome.index("🎁 Catálogo")]:
                busca = st.text_input("🔍 Buscar Produtos", placeholder="Digite o nome do prêmio...")
                df_p = run_query("SELECT * FROM premios ORDER BY id")
                if not df_p.empty:
                    if busca: df_p = df_p[df_p['item'].str.contains(busca, case=False, na=False)]
                    if df_p.empty: st.warning("Nenhum produto encontrado.")
                    else:
                        cols_cat = st.columns(4)
                        for i, (_, row) in enumerate(df_p.iterrows()):
                            with cols_cat[i % 4]:
                                with st.container(border=True):
                                    if row['imagem']: st.image(processar_link_imagem(row['imagem']))
                                    cst = int(row['custo'] * (valor_padrao_ponto / valor_ponto_usuario))
                                    st.markdown(f"**{row['item']}**\n<br><div style='color:#0066cc; font-weight:bold;'>{cst} pts</div>", unsafe_allow_html=True)
                                    c_det, c_res = st.columns(2)
                                    with c_det: 
                                        if st.button("Detalhes", key=f"det_{row['id']}", use_container_width=True): ver_detalhes_produto(row['item'], row['imagem'], cst, row.get('descricao', ''))
                                    with c_res: 
                                        if sld >= cst and st.button("RESGATAR", key=f"b_{row['id']}", type="primary", use_container_width=True): confirmar_resgate_dialog(row['item'], cst, u_cod)
                else: st.info("Catálogo vazio.")
            
            with abas[abas_nome.index("🍀 Sorteio")]:
                rifa_ativa = run_query("SELECT * FROM rifas WHERE status = 'ativa'")
                if not rifa_ativa.empty:
                    r = rifa_ativa.iloc[0]; img_premio = ""
                    df_p_img = run_query("SELECT imagem FROM premios WHERE id = :pid", {"pid": int(r['premio_id'])})
                    if not df_p_img.empty: img_premio = df_p_img.iloc[0]['imagem']
                    st.markdown(f"<div class='rifa-card'><div class='rifa-tag'>🍀 SORTEIO ATIVO</div><h3>{r['item_nome']}</h3></div>", unsafe_allow_html=True)
                    if img_premio: st.image(processar_link_imagem(img_premio), width=200)
                    if st.button(f"🎟️ COMPRAR TICKET ({r['custo_ticket']} pts)", type="primary"): confirmar_compra_ticket(int(r['id']), r['custo_ticket'], u_cod)
                else: st.info("Nenhum sorteio ativo no momento.")
                
            if st.session_state.get('acesso_bolao', False):
                with abas[abas_nome.index("⚽ Bolão Copa")]:
                    with st.expander("📖 Entenda as Regras e a Pontuação do Bolão (Clique para expandir)"):
                        st.markdown("""
                        O sistema do Bolão recompensa a sua capacidade de fazer uma **leitura técnica** do jogo. 
                        Quem chegar mais perto da realidade da partida levará os pontos para casa!
                        
                        **A pontuação funciona em camadas:**
                        * **Acertar quem vence o jogo (ou se dá empate):** +10 pontos
                        * **Acertar a diferença de gols (saldo):** +5 pontos
                        * **Acertar os gols do Time A:** +3 pontos
                        * **Acertar os gols do Time B:** +3 pontos
                        * **CRAVAR o placar exato:** +10 pontos bônus
                        
                        *Exemplo de Desempate:* Se o jogo terminar **Time Z 3 x 2 Time Y**.
                        Alguém que apostou 4x2 ganharia pontos por acertar o vencedor, o saldo de +1 e os gols do perdedor (Total: 18 pts).
                        Alguém que apostou 2x0 ganharia apenas por acertar o vencedor e o saldo (Total: 15 pts). 
                        Aquele que somou 18 vence!
                        """)
                    
                    st.markdown("### Seus Palpites")
                    jogos_ativos = run_query("SELECT * FROM bolao_jogos WHERE status = 'Aberto' ORDER BY data_jogo ASC", ttl=0)
                    if not jogos_ativos.empty:
                        col_jogos = st.columns(3)
                        for i, (_, jogo) in enumerate(jogos_ativos.iterrows()):
                            jid = int(jogo['id'])
                            with col_jogos[i % 3]:
                                st.markdown(f"<div class='bolao-card'><div class='bolao-tag'>PARTIDA AGENDADA</div><h4>{jogo['time_a']} x {jogo['time_b']}</h4><p style='font-size:11px;'>📅 {jogo['data_jogo'].strftime('%d/%m/%Y %H:%M')}</p></div>", unsafe_allow_html=True)
                                
                                aposta_ex = run_query("SELECT gols_a, gols_b FROM bolao_apostas WHERE jogo_id = :jid AND usuario = :u", {"jid": jid, "u": u_cod}, ttl=0)
                                if not aposta_ex.empty:
                                    pa, pb = int(aposta_ex.iloc[0]['gols_a']), int(aposta_ex.iloc[0]['gols_b'])
                                    st.info(f"⚽ Seu palpite: **{pa} x {pb}**")
                                    st.caption("🔒 Registrado. Não é possível alterar.")
                                else:
                                    ca, cb = st.columns(2)
                                    ga = ca.number_input(f"{jogo['time_a']}", min_value=0, step=1, key=f"ga_{jid}")
                                    gb = cb.number_input(f"{jogo['time_b']}", min_value=0, step=1, key=f"gb_{jid}")
                                    if st.button("Confirmar Palpite", key=f"bp_{jid}", type="secondary"):
                                        run_transaction("INSERT INTO bolao_apostas (jogo_id, usuario, gols_a, gols_b) VALUES (:jid, :u, :ga, :gb)", {"jid": jid, "u": u_cod, "ga": ga, "gb": gb})
                                        st.cache_data.clear(); st.rerun()
                    else: st.info("Nenhum confronto disponível para apostar.")
            
            with abas[abas_nome.index("📜 Meus Resgates")]:
                st.info("### 📜 Acompanhamento\nPedido recebido! Prazo: **5 dias úteis** no seu Whatsapp informado.")
                meus_pedidos = run_query("SELECT id, data, item, valor, status, codigo_vale, recebido_user FROM vendas WHERE LOWER(usuario) = LOWER(:u) ORDER BY data DESC", {"u": u_cod})
                if not meus_pedidos.empty:
                    editor_pedidos = st.data_editor(meus_pedidos, use_container_width=True, hide_index=True, key="ed_meus_ped", disabled=["id", "data", "item", "valor", "status", "codigo_vale"])
                    if st.button("💾 Confirmar Recebimento"):
                        with conn.session as s:
                            for i, row in editor_pedidos.iterrows():
                                s.execute(text("UPDATE vendas SET recebido_user = :ru WHERE id = :id"), {"ru": bool(row['recebido_user']), "id": row['id']})
                            s.commit()
                        st.cache_data.clear(); st.toast("Atualizado!", icon="✅"); time.sleep(1); st.rerun()
                else: st.write("Nenhum pedido encontrado.")
            
            with abas[abas_nome.index("🏆 Ranking")]:
                st.markdown("### 🏆 Top Users (Histórico)")
                df_rank = run_query("SELECT usuario, pontos_historico FROM usuarios WHERE tipo NOT IN ('admin', 'staff', 'supervisor') ORDER BY pontos_historico DESC LIMIT 10")
                if not df_rank.empty:
                    df_rank['pontos_historico'] = df_rank['pontos_historico'].fillna(0).astype(int)
                    df_rank = df_rank.rename(columns={"usuario": "Usuário", "pontos_historico": "Pontos Acumulados"})
                    st.dataframe(df_rank, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    if "rt" in st.query_params: tela_nova_senha_token(st.query_params["rt"])
    else: verificar_sessao_automatica(); tela_principal() if st.session_state.get('logado', False) else tela_login()
