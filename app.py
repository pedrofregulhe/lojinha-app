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
if 'valor_ponto_user' not in st.session_state: st.session_state['valor_ponto_user'] = 0.50
if 'em_verificacao_2fa' not in st.session_state: st.session_state['em_verificacao_2fa'] = False
if 'codigo_2fa_esperado' not in st.session_state: st.session_state['codigo_2fa_esperado'] = ""
if 'dados_usuario_temp' not in st.session_state: st.session_state['dados_usuario_temp'] = {}

# --- CSS DINÂMICO (Preservado do original) ---
css_comum = """
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;800;900&display=swap');
    html, body, [class*="css"], .stMarkdown, .stText, p, h1, h2, h3, h4, span, div { font-family: 'Poppins', sans-serif; color: #31333F !important; }
    input, textarea, select { color: #31333F !important; background-color: #ffffff !important; }
    .header-style h2, .header-style p, .header-style span, .header-style div { color: white !important; }
    button[kind="primary"] p, button[kind="primary"] div { color: white !important; }
    header { visibility: hidden; }
    .stDeployButton { display: none; }
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
    [data-testid="stImage"] { display: flex; justify-content: center; }
    [data-testid="stImage"] img { height: 180px !important; width: auto !important; max-width: 100%; object-fit: contain !important; border-radius: 10px; }
    .header-style h2 { font-size: 20px !important; font-weight: 700 !important; margin-bottom: 2px !important; }
    .header-style p { font-size: 12px !important; line-height: 1.3 !important; opacity: 0.9 !important; }
    .header-style .saldo-valor { font-size: 30px !important; font-weight: 900 !important; text-shadow: 0 2px 4px rgba(0,0,0,0.15); }
    div.stButton > button[kind="primary"] { background-color: #0066cc !important; color: white !important; border-radius: 12px; border: none; height: 55px; font-weight: 600; width: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    div.stButton > button[kind="secondary"] { background-color: #ffffff !important; color: #003366 !important; border-radius: 12px !important; border: 2px solid #eef2f6 !important; height: 110px !important; font-weight: 600; width: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .rifa-card { border: 2px solid #FFD700; background: linear-gradient(to bottom right, #fffdf0, #ffffff); padding: 20px; border-radius: 15px; box-shadow: 0 4px 15px rgba(255, 215, 0, 0.2); margin-bottom: 20px; text-align: center; }
    .rifa-tag { background-color: #FFD700; color: #000; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 12px; margin-bottom: 10px; display: inline-block; }
    .winner-card { border: 2px solid #28a745; background: linear-gradient(to bottom right, #f0fff4, #ffffff); padding: 20px; border-radius: 15px; text-align: center; }
"""

if not st.session_state.get('logado', False):
    estilo_especifico = ".stApp { background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); background-size: 400% 400%; animation: gradient 15s ease infinite; } [data-testid='stForm'] { background-color: #ffffff; padding: 40px; border-radius: 20px; }"
else:
    estilo_especifico = ".stApp { background-color: #f4f8fb; } .header-style { background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); padding: 20px 30px; border-radius: 15px; color: white; display: flex; flex-direction: column; justify-content: center; }"

st.markdown(f"<style>{css_comum} {estilo_especifico}</style>", unsafe_allow_html=True)

# --- FUNÇÕES DE UTILITÁRIO (Preservadas) ---
def verificar_senha_hash(senha, hash_armazenado):
    try:
        if not hash_armazenado.startswith("$2b$"): return senha == hash_armazenado
        return bcrypt.checkpw(senha.encode('utf-8'), hash_armazenado.encode('utf-8'))
    except: return False

def gerar_hash(senha): return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
def gerar_senha_aleatoria(tamanho=6): return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(tamanho))
def formatar_telefone(tel):
    t = re.sub(r'\D', '', str(tel))
    return "55" + t if 10 <= len(t) <= 11 else t
def processar_link_imagem(url):
    url = str(url).strip()
    if "github.com" in url and "/blob/" in url: return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url

# --- COMUNICAÇÃO (Infobip) ---
def enviar_sms(tel, msg):
    try:
        url = f"{st.secrets['INFOBIP_BASE_URL'].rstrip('/')}/sms/2/text/advanced"
        headers = {"Authorization": f"App {st.secrets['INFOBIP_API_KEY']}", "Content-Type": "application/json"}
        payload = {"messages": [{"from": "InfoSMS", "destinations": [{"to": formatar_telefone(tel)}], "text": msg}]}
        r = requests.post(url, json=payload, headers=headers)
        return r.status_code in [200, 201], r.text, str(r.status_code)
    except Exception as e: return False, str(e), "ERR"

def enviar_whatsapp_template(tel, params, template="atualizar_envio_pedidos"):
    try:
        url = f"{st.secrets['INFOBIP_BASE_URL'].rstrip('/')}/whatsapp/1/message/template"
        headers = {"Authorization": f"App {st.secrets['INFOBIP_API_KEY']}", "Content-Type": "application/json"}
        payload = {"messages": [{"from": st.secrets["INFOBIP_SENDER"], "to": formatar_telefone(tel), "content": {"templateName": template, "templateData": {"body": {"placeholders": params}}, "language": "pt_BR"}}]}
        r = requests.post(url, json=payload, headers=headers)
        return r.status_code in [200, 201], r.text, str(r.status_code)
    except Exception as e: return False, str(e), "ERR"

# --- BANCO DE DADOS ---
def run_query(query, params=None): return conn.query(query, params=params, ttl=0)
def run_transaction(query, params=None):
    with conn.session as s: s.execute(text(query), params if params else {}); s.commit()
def registrar_log(acao, detalhes):
    run_transaction("INSERT INTO logs (data, responsavel, acao, detalhes) VALUES (NOW(), :r, :a, :d)", {"r": st.session_state.get('usuario_nome', 'Sistema'), "a": acao, "d": detalhes})

# --- GESTÃO DE USUÁRIO E SESSÃO ---
def validar_login(u, p):
    df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": u.strip()})
    if df.empty: return False, None, None, 0, None, 0, 0.50
    r = df.iloc[0]
    if verificar_senha_hash(p.strip(), r['senha']):
        return True, r['nome'], str(r['tipo']).lower().strip(), float(r['saldo']), str(r['telefone']), int(r['id']), float(r.get('valor_ponto_individual', 0.50))
    return False, None, None, 0, None, 0, 0.50

def verificar_sessao_automatica():
    if st.session_state.get('logado', False): return
    token = st.query_params.get("sessao")
    if token:
        df = run_query("SELECT * FROM usuarios WHERE token_sessao = :t", {"t": token})
        if not df.empty:
            r = df.iloc[0]
            st.session_state.update({'logado': True, 'usuario_cod': r['usuario'], 'usuario_nome': r['nome'], 'tipo_usuario': str(r['tipo']).lower().strip(), 'saldo_atual': float(r['saldo']), 'valor_ponto_user': float(r.get('valor_ponto_individual', 0.50))})
            st.rerun()

def realizar_logout():
    run_transaction("UPDATE usuarios SET token_sessao = NULL WHERE usuario = :u", {"u": st.session_state.get('usuario_cod', '')})
    st.query_params.clear(); st.session_state.clear(); st.rerun()

# --- LÓGICA DE NEGÓCIO ---
def salvar_venda(u_cod, item, custo, email, tel):
    if st.session_state['saldo_atual'] < custo: return False
    with conn.session as s:
        s.execute(text("UPDATE usuarios SET saldo = saldo - :c WHERE LOWER(usuario) = LOWER(:u)"), {"c": custo, "u": u_cod})
        s.execute(text("INSERT INTO vendas (data, usuario, item, valor, status, email, nome_real, telefone) VALUES (NOW(), :u, :i, :v, 'Pendente', :e, :n, :t)"), {"u": u_cod, "i": item, "v": custo, "e": email, "n": st.session_state.usuario_nome, "t": tel})
        s.commit()
    st.session_state['saldo_atual'] -= custo
    registrar_log("Resgate", f"Item: {item}")
    return True

def comprar_ticket_rifa(rifa_id, custo, u_cod):
    if st.session_state['saldo_atual'] < custo: return False, "Saldo insuficiente"
    with conn.session as s:
        s.execute(text("UPDATE usuarios SET saldo = saldo - :c WHERE LOWER(usuario) = LOWER(:u)"), {"c": custo, "u": u_cod})
        s.execute(text("INSERT INTO rifa_tickets (rifa_id, usuario) VALUES (:rid, :u)"), {"rid": rifa_id, "u": u_cod})
        s.commit()
    st.session_state['saldo_atual'] -= custo
    return True, "Ticket comprado!"

# --- DIALOGS (Preservados e Atualizados) ---
@st.dialog("🎁 Confirmar Resgate")
def confirmar_resgate_dialog(item, custo, u_cod):
    st.write(f"Resgatando: **{item}** por **{custo:,.0f} pts**.")
    with st.form("f_res"):
        e = st.text_input("E-mail"); t = st.text_input("WhatsApp")
        if st.form_submit_button("CONFIRMAR", type="primary"):
            if salvar_venda(u_cod, item, custo, e, formatar_telefone(t)):
                st.balloons(); st.success("Sucesso!"); time.sleep(2); st.rerun()

@st.dialog("🎟️ Comprar Ticket")
def confirmar_compra_ticket(rid, item, custo, u_cod):
    st.write(f"Sorteio: **{item}** | Custo: **{custo:,.0f} pts**")
    if st.button("CONFIRMAR COMPRA", type="primary", use_container_width=True):
        ok, msg = comprar_ticket_rifa(rid, custo, u_cod)
        if ok: st.balloons(); st.success(msg); time.sleep(2); st.rerun()
        else: st.error(msg)

@st.dialog("🚀 Processar Envios", width="large")
def processar_envios_dialog(df, usar_zap, usar_sms, tipo="vendas"):
    st.write(f"Destinatários: {len(df)}")
    if st.button("CONFIRMAR DISPARO", type="primary"):
        pb = st.progress(0)
        for i, (idx, row) in enumerate(df.iterrows()):
            tel = str(row['telefone'])
            nome = str(row.get('nome_real') or row.get('nome'))
            if tipo == "vendas":
                v1, v2 = str(row['item']), str(row['codigo_vale'])
                if usar_zap: enviar_whatsapp_template(tel, [nome, v1, v2], "atualizar_envio_pedidos")
                if usar_sms: enviar_sms(tel, f"Ola {nome}, seu resgate de {v1} foi liberado! Cod: {v2}")
            else:
                v1 = f"{float(row['saldo']):,.0f}"
                if usar_zap: enviar_whatsapp_template(tel, [nome, v1], "atualizar_saldo_pedidos")
                if usar_sms: enviar_sms(tel, f"Lojinha Culli: Ola {nome}, seu saldo atual e de {v1} pts.")
            pb.progress((i+1)/len(df))
        st.success("Disparo finalizado!"); time.sleep(2); st.rerun()

# --- TELAS ---
def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        if st.session_state.get('em_verificacao_2fa', False):
            with st.form("f_2fa"):
                st.write("### 🔒 2FA"); cod = st.text_input("Código SMS")
                if st.form_submit_button("VALIDAR"):
                    if cod == st.session_state.codigo_2fa_esperado:
                        d = st.session_state.dados_usuario_temp
                        st.session_state.update({'logado':True,'usuario_cod':d['u'],'usuario_nome':d['n'],'tipo_usuario':d['t'],'saldo_atual':d['s'],'valor_ponto_user':d['v']})
                        run_transaction("UPDATE usuarios SET token_sessao = :t WHERE id = :id", {"t":str(uuid.uuid4()), "id":d['id']})
                        st.rerun()
        else:
            with st.form("f_log"):
                st.markdown("<h1 style='text-align:center;'>Lojinha Culli's</h1>", unsafe_allow_html=True)
                u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
                if st.form_submit_button("ENTRAR", type="primary"):
                    ok, n, t, sld, tel, uid, v_ponto = validar_login(u, p)
                    if ok:
                        codigo = str(random.randint(100000, 999999))
                        enviar_sms(tel, f"Codigo Culli: {codigo}")
                        st.session_state.update({'em_verificacao_2fa':True,'codigo_2fa_esperado':codigo,'dados_usuario_temp':{'u':u,'n':n,'t':t,'s':sld,'v':v_ponto,'id':uid}})
                        st.rerun()
                    else: st.error("Incorreto")

def tela_admin():
    st.subheader("🛠️ Admin")
    t1, t2, t3, t4, t5 = st.tabs(["📊 Entregas", "👥 Usuários", "🎁 Prêmios", "🛠️ Logs", "🎟️ Sorteio"])
    
    with t1:
        df_v = run_query("SELECT * FROM vendas ORDER BY id DESC")
        if not df_v.empty:
            if "Enviar" not in df_v.columns: df_v.insert(0, "Enviar", False)
            edit_v = st.data_editor(df_v, use_container_width=True, hide_index=True)
            c1, c2, c3 = st.columns(3)
            with c1: zap = st.checkbox("WhatsApp", value=True, key="z1")
            with c2: sms = st.checkbox("SMS", key="s1")
            with c3:
                if st.button("📤 Disparar Selecionados"):
                    sel = edit_v[edit_v['Enviar'] == True]
                    processar_envios_dialog(sel, zap, sms, "vendas")

    with t2:
        df_u = run_query("SELECT * FROM usuarios ORDER BY id")
        edit_u = st.data_editor(df_u, use_container_width=True, key="ed_u", column_config={
            "valor_ponto_individual": st.column_config.NumberColumn("Valor Ponto (R$)", format="%.2f", help="0.50 padrão. Menos encarece a loja.")
        })
        if st.button("💾 Salvar Usuários"):
            for _, row in edit_u.iterrows():
                run_transaction("UPDATE usuarios SET saldo=:s, pontos_historico=:ph, valor_ponto_individual=:v, tipo=:tp WHERE id=:id", {"s":row['saldo'], "ph":row['pontos_historico'], "v":row['valor_ponto_individual'], "tp":row['tipo'], "id":row['id']})
            st.success("Salvo!"); st.rerun()

    with t3:
        df_p = run_query("SELECT * FROM premios ORDER BY id")
        edit_p = st.data_editor(df_p, use_container_width=True, num_rows="dynamic")
        if st.button("Salvar Prêmios"):
            for _, row in edit_p.iterrows():
                if pd.notna(row['id']): run_transaction("UPDATE premios SET item=:i, custo=:c, imagem=:im WHERE id=:id", {"i":row['item'],"c":row['custo'],"im":row['imagem'],"id":row['id']})
                else: run_transaction("INSERT INTO premios (item, custo, imagem) VALUES (:i, :c, :im)", {"i":row['item'],"c":row['custo'],"im":row['imagem']})
            st.rerun()

    with t4: st.dataframe(run_query("SELECT * FROM logs ORDER BY id DESC LIMIT 50"))
    
    with t5:
        st.write("### Gestão de Rifas")
        rifa = run_query("SELECT * FROM rifas WHERE status = 'ativa'")
        if not rifa.empty:
            r = rifa.iloc[0]
            st.info(f"Rifa Ativa: {r['item_nome']}")
            if st.button("🎲 SORTEAR AGORA", type="primary"):
                tickets = run_query("SELECT usuario FROM rifa_tickets WHERE rifa_id = :rid", {"rid": int(r['id'])})
                if not tickets.empty:
                    vencedor = random.choice(tickets['usuario'].tolist())
                    run_transaction("UPDATE rifas SET status='encerrada', ganhador_usuario=:u WHERE id=:id", {"u":vencedor, "id":r['id']})
                    st.success(f"Vencedor: {vencedor}!"); time.sleep(3); st.rerun()
        else:
            if st.button("Iniciar Nova Rifa (Exemplo)"):
                run_transaction("INSERT INTO rifas (item_nome, custo_ticket, status) VALUES ('Prêmio Teste', 100, 'ativa')")
                st.rerun()

def tela_principal():
    u_nome, sld = st.session_state.usuario_nome, st.session_state.saldo_atual
    v_ponto = st.session_state.get('valor_ponto_user', 0.50)
    
    # CÁLCULO DO FATOR (Lógica de Reprecificação)
    fator = 0.50 / v_ponto if v_ponto > 0 else 1.0
    
    c_head, c_btn = st.columns([4, 1])
    with c_head: st.markdown(f'<div class="header-style"><h2>Olá, {u_nome}! 👋</h2><p>Saldo: <b>{sld:,.0f} pts</b> | <i>Cotação: R$ {v_ponto:.2f}/pt</i></p></div>', unsafe_allow_html=True)
    with c_btn:
        if st.button("🔄"): st.rerun()
        if st.button("❌ Sair"): realizar_logout()

    if st.session_state.tipo_usuario == 'admin': tela_admin()
    else:
        t1, t2, t3, t4 = st.tabs(["🎁 Catálogo", "🍀 Sorteio", "📜 Meus Pedidos", "🏆 Ranking"])
        
        with t1:
            df_p = run_query("SELECT * FROM premios ORDER BY id")
            cols = st.columns(4)
            for i, row in df_p.iterrows():
                custo_ajustado = int(row['custo'] * fator)
                with cols[i % 4]:
                    with st.container(border=True):
                        if row['imagem']: st.image(processar_link_imagem(row['imagem']))
                        st.markdown(f"**{row['item']}**")
                        st.markdown(f"💎 {custo_ajustado:,.0f} pts")
                        if sld >= custo_ajustado:
                            if st.button("RESGATAR", key=f"r_{row['id']}", type="primary"):
                                confirmar_resgate_dialog(row['item'], custo_ajustado, st.session_state.usuario_cod)

        with t2:
            st.write("### Sorteios Ativos")
            r_ativa = run_query("SELECT * FROM rifas WHERE status = 'ativa'")
            if not r_ativa.empty:
                r = r_ativa.iloc[0]
                custo_rifa = int(r['custo_ticket'] * fator)
                st.markdown(f'<div class="rifa-card"><div class="rifa-tag">ATIVO</div><h3>{r["item_nome"]}</h3><p>Custo por ticket: {custo_rifa} pts</p></div>', unsafe_allow_html=True)
                if st.button(f"🎟️ Comprar Ticket ({custo_rifa} pts)", type="primary"):
                    confirmar_compra_ticket(r['id'], r['item_nome'], custo_rifa, st.session_state.usuario_cod)
            else: st.info("Sem sorteios no momento.")

        with t3: st.dataframe(run_query("SELECT * FROM vendas WHERE usuario = :u ORDER BY data DESC", {"u": st.session_state.usuario_cod}), use_container_width=True)
        with t4: st.dataframe(run_query("SELECT usuario, pontos_historico FROM usuarios ORDER BY pontos_historico DESC LIMIT 10"), use_container_width=True)

if __name__ == "__main__":
    verificar_sessao_automatica()
    if st.session_state.logado: tela_principal()
    else: tela_login()
