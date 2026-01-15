import streamlit as st
from sqlalchemy import text
import pandas as pd
from datetime import datetime
import time
import base64
import bcrypt
import requests
import re

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

# --- CSS ---
if not st.session_state.get('logado', False):
    # Fundo animado (Login)
    bg_style = ".stApp { background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); background-size: 400% 400%; animation: gradient 15s ease infinite; }"
else:
    # Fundo neutro (App)
    bg_style = ".stApp { background-color: #f4f8fb; }"

st.markdown(f"""
    <style>
    /* Importando a fonte POPPINS */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;900&display=swap');
    
    html, body, [class*="css"] {{ font-family: 'Poppins', sans-serif; }}
    header {{ visibility: hidden; }}
    .stDeployButton {{ display: none; }}
    
    @keyframes gradient {{ 0% {{ background-position: 0% 50%; }} 50% {{ background-position: 100% 50%; }} 100% {{ background-position: 0% 50%; }} }}
    {bg_style}
    
    .block-container {{ padding-top: 2rem !important; padding-bottom: 2rem !important; }}
    
    /* Estilo do Formulário de Login */
    [data-testid="stForm"] {{ background-color: #ffffff; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); border: none; }}
    
    /* Estilo do Cabeçalho Principal (Onde fica o saldo) */
    .header-style {{ background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); background-size: 400% 400%; animation: gradient 10s ease infinite; padding: 25px 30px; border-radius: 15px; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.1); display: flex; flex-direction: column; justify-content: center; height: 100%; }}
    
    /* Imagens dos Prêmios */
    [data-testid="stImage"] img {{ height: 150px !important; object-fit: contain !important; border-radius: 10px; }}
    
    /* Botões */
    div.stButton > button[kind="secondary"] {{ background-color: #0066cc; color: white; border-radius: 8px; border: none; height: 45px; font-weight: 600; width: 100%; }}
    div.stButton > button[kind="primary"] {{ background-color: #ff4b4b !important; color: white !important; border-radius: 8px; border: none; height: 45px; font-weight: 600; width: 100%; }}
    
    /* Classe para mensagens de sucesso grandes */
    .big-success {{ padding: 20px; background-color: #d4edda; color: #155724; border-radius: 10px; font-weight: bold; text-align: center; border: 1px solid #c3e6cb; margin-bottom: 10px; }}
    
    /* Ajuste de alinhamento vertical para os botões do header ficarem no meio */
    [data-testid="column"] {{ display: flex; flex-direction: column; justify-content: center; }}
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE SUPORTE ---

def verificar_senha_hash(senha_digitada, hash_armazenado):
    try:
        if not hash_armazenado.startswith("$2b$"):
            return senha_digitada == hash_armazenado
        return bcrypt.checkpw(senha_digitada.encode('utf-8'), hash_armazenado.encode('utf-8'))
    except ValueError:
        return False

def gerar_hash(senha):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha.encode('utf-8'), salt).decode('utf-8')

# --- NOVA FUNÇÃO INTELIGENTE PARA IMAGENS (GitHub & Drive) ---
def processar_link_imagem(url):
    url = str(url).strip()
    
    # Caso 1: Link do GitHub (Converte 'blob' para 'raw')
    # De: https://github.com/user/repo/blob/main/img.png
    # Para: https://raw.githubusercontent.com/user/repo/main/img.png
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    
    # Caso 2: Google Drive (Mantido para segurança)
    if "drive.google.com" in url:
        if "id=" in url: return url
        try:
            file_id = url.split("/")[-2]
            return f"https://drive.google.com/uc?export=view&id={file_id}"
        except: return url
        
    # Caso 3: Link normal, retorna como está
    return url

def formatar_telefone(tel_bruto):
    texto = str(tel_bruto).strip()
    if texto.endswith(".0"): texto = texto[:-2]
    apenas_numeros = re.sub(r'\D', '', texto)
    if 10 <= len(apenas_numeros) <= 11:
        apenas_numeros = "55" + apenas_numeros
    return apenas_numeros

def enviar_whatsapp_template(telefone, parametros, nome_template="premios_campanhas_envio"):
    try:
        base_url = st.secrets["INFOBIP_BASE_URL"].rstrip('/')
        api_key = st.secrets["INFOBIP_API_KEY"]
        sender = st.secrets["INFOBIP_SENDER"]
        
        url = f"{base_url}/whatsapp/1/message/template"
        tel_final = formatar_telefone(telefone)
        
        if len(tel_final) < 12: return False, f"Número inválido: {tel_final}"

        payload = {
            "messages": [
                {
                    "from": sender,
                    "to": tel_final,
                    "content": {
                        "templateName": nome_template, 
                        "templateData": { "body": { "placeholders": parametros } },
                        "language": "pt_BR"
                    }
                }
            ]
        }
        headers = {
            "Authorization": f"App {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code not in [200, 201]: return False, f"Erro API {response.status_code}: {response.text}"
        return True, f"Enviado para {tel_final}"
    except Exception as e: return False, f"Erro Conexão: {str(e)}"

# --- FUNÇÕES DE BANCO DE DADOS (SQL) ---

def run_query(query_str, params=None):
    return conn.query(query_str, params=params, ttl=0)

def run_transaction(query_str, params=None):
    with conn.session as s:
        s.execute(text(query_str), params if params else {})
        s.commit()

def registrar_log(acao, detalhes):
    try:
        resp = st.session_state.get('usuario_nome', 'Sistema')
        sql = """
            INSERT INTO logs (data, responsavel, acao, detalhes)
            VALUES (NOW(), :resp, :acao, :det)
        """
        run_transaction(sql, {"resp": resp, "acao": acao, "det": detalhes})
    except Exception as e:
        print(f"Erro log: {e}")

# --- LÓGICA DE NEGÓCIO ---

def validar_login(user_input, pass_input):
    df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": user_input.strip()})
    if df.empty: return False, None, None, 0
    linha = df.iloc[0]
    hash_banco = linha['senha']
    if verificar_senha_hash(pass_input.strip(), hash_banco):
        return True, linha['nome'], str(linha['tipo']).lower().strip(), float(linha['saldo'])
    return False, None, None, 0

def salvar_venda(usuario_cod, item_nome, custo, email_contato, telefone_resgate):
    try:
        user_df = run_query("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario_cod})
        if user_df.empty: return False
        
        saldo_atual = float(user_df.iloc[0]['saldo'])
        if saldo_atual < custo: 
            st.error("Saldo insuficiente (mudou durante a operação).")
            return False

        nome_user = user_df.iloc[0]['nome']

        with conn.session as s:
            s.execute(
                text("UPDATE usuarios SET saldo = saldo - :custo WHERE LOWER(usuario) = LOWER(:u)"),
                {"custo": custo, "u": usuario_cod}
            )
            s.execute(
                text("""
                    INSERT INTO vendas (data, usuario, item, valor, status, email, nome_real, telefone)
                    VALUES (NOW(), :u, :item, :valor, 'Pendente', :email, :nome, :tel)
                """),
                {
                    "u": usuario_cod, "item": item_nome, "valor": custo, 
                    "email": email_contato, "nome": nome_user, "tel": telefone_resgate
                }
            )
            s.commit()
            
        registrar_log("Resgate", f"Usuário: {nome_user} | Item: {item_nome}")
        st.session_state['saldo_atual'] -= custo
        return True
    except Exception as e:
        st.error(f"Erro ao processar venda: {e}")
        return False

def cadastrar_novo_usuario(usuario, senha, nome, saldo, tipo, telefone):
    try:
        df = run_query("SELECT id FROM usuarios WHERE LOWER(usuario) = LOWER(:u)", {"u": usuario})
        if not df.empty: return False, "Usuário já existe!"
        
        senha_hash = gerar_hash(senha)
        run_transaction("""
            INSERT INTO usuarios (usuario, senha, nome, saldo, tipo, telefone)
            VALUES (:u, :s, :n, :bal, :t, :tel)
        """, {
            "u": usuario, "s": senha_hash, "n": nome, 
            "bal": saldo, "t": tipo, "tel": formatar_telefone(telefone)
        })
        registrar_log("Novo Cadastro", f"Criou usuário: {usuario}")
        return True, "Cadastrado com sucesso!"
    except Exception as e:
        return False, f"Erro: {str(e)}"

# --- MODAIS ---
@st.dialog("🔐 Alterar Senha")
def abrir_modal_senha(usuario_cod):
    n = st.text_input("Nova Senha", type="password")
    c = st.text_input("Confirmar", type="password")
    if st.button("Salvar Senha"):
        if n == c and n:
            novo_hash = gerar_hash(n)
            run_transaction(
                "UPDATE usuarios SET senha = :s WHERE LOWER(usuario) = LOWER(:u)",
                {"s": novo_hash, "u": usuario_cod}
            )
            registrar_log("Senha Alterada", f"Usuário: {usuario_cod}")
            st.success("Senha alterada!"); time.sleep(1); st.session_state['logado'] = False; st.rerun()

@st.dialog("🎁 Confirmar Resgate")
def confirmar_resgate_dialog(item_nome, custo, usuario_cod):
    st.write(f"Resgatando: **{item_nome}** por **{custo} pts**.")
    with st.form("form_resgate"):
        email = st.text_input("E-mail:", placeholder="exemplo@email.com")
        tel = st.text_input("WhatsApp (DDD+Num):", placeholder="Ex: 34999998888")
        submitted = st.form_submit_button("CONFIRMAR", type="primary", use_container_width=True)
    
    if submitted:
        if "@" not in email: st.error("E-mail inválido."); return
        t_limpo = formatar_telefone(tel)
        if len(t_limpo) < 12: st.error("Telefone inválido! (Ex: 34991727088)."); return
        if salvar_venda(usuario_cod, item_nome, custo, email, t_limpo):
            st.balloons()
            st.success("Sucesso! Compra registrada."); time.sleep(2); st.rerun()

# --- TELAS ---
def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        with st.form("f_login"):
            st.markdown("""
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #003366; font-weight: 900; font-size: 3rem; margin: 0; margin-bottom: 10px;">
                        🎁 LOJINHA CULLI 🎁
                    </h1>
                    <p style="color: #555555; font-size: 0.95rem; line-height: 1.4; font-weight: 400; margin: 0;">
                        Realize seu login para resgatar seus pontos<br>e acompanhar seus pedidos.
                    </p>
                </div>
            """, unsafe_allow_html=True)
            
            u = st.text_input("Usuário"); s = st.text_input("Senha", type="password")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("ENTRAR", type="primary", use_container_width=True):
                ok, n, t, sld = validar_login(u, s)
                if ok: st.session_state.update({'logado':True, 'usuario_cod':u, 'usuario_nome':n, 'tipo_usuario':t, 'saldo_atual':sld}); st.rerun()
                else: st.toast("Login inválido", icon="❌")

def tela_admin():
    c_titulo, c_refresh = st.columns([4, 1])
    c_titulo.subheader("🛠️ Painel Admin")
    
    if c_refresh.button("🔄 Atualizar Dados"):
        st.cache_data.clear()
        st.toast("Dados sincronizados com sucesso!", icon="✅")
        time.sleep(1)
        st.rerun()
        
    t1, t2, t3, t4 = st.tabs(["📊 Entregas & WhatsApp", "👥 Usuários & Saldos", "🎁 Prêmios", "🛠️ Ferramentas"])
    
    with t1:
        df_v = run_query("SELECT * FROM vendas ORDER BY id DESC")
        if not df_v.empty:
            if "Enviar" not in df_v.columns: df_v.insert(0, "Enviar", False)
            edit_v = st.data_editor(
                df_v, use_container_width=True, hide_index=True, key="ed_vendas_sql",
                column_config={"Enviar": st.column_config.CheckboxColumn("Enviar?", default=False)}
            )
            c1, c2 = st.columns(2)
            if c1.button("💾 Salvar Alterações"):
                with conn.session as s:
                    for index, row in edit_v.iterrows():
                        s.execute(text("UPDATE vendas SET codigo_vale=:cod, status=:st, nome_real=:nr, telefone=:tel WHERE id=:id"),
                                  {"cod": row['codigo_vale'], "st": row['status'], "nr": row['nome_real'], "tel": row['telefone'], "id": row['id']})
                    s.commit()
                registrar_log("Admin", "Editou vendas")
                st.success("✅ Alterações salvas com sucesso!"); time.sleep(2); st.rerun()

            if c2.button("📤 Enviar Prêmios", type="primary"):
                selecionados = edit_v[edit_v['Enviar'] == True]
                if selecionados.empty: st.warning("Selecione alguém.")
                else:
                    enviados = 0; barra = st.progress(0); total = len(selecionados)
                    for i, (index, row) in enumerate(selecionados.iterrows()):
                        barra.progress((i+1)/total)
                        tel = str(row['telefone']); nome = str(row['nome_real']); item = str(row['item']); cod = str(row['codigo_vale'])
                        if not nome or nome == 'None': nome = str(row['usuario'])
                        if len(formatar_telefone(tel)) < 12 or not cod: continue
                        ok, msg = enviar_whatsapp_template(tel, [nome, item, cod], nome_template="premios_campanhas_envio")
                        if ok: enviados += 1
                    if enviados > 0: 
                        registrar_log("Admin", f"Enviou {enviados} prêmios")
                        st.balloons()
                        st.markdown(f'<div class="big-success">🚀 {enviados} Prêmios Enviados com Sucesso!</div>', unsafe_allow_html=True)
                        time.sleep(3); st.rerun()

    with t2:
        with st.expander("➕ Cadastrar Novo Usuário"):
            with st.form("form_novo"):
                c_n1, c_n2 = st.columns(2)
                u = c_n1.text_input("Usuário"); s = c_n2.text_input("Senha")
                n = c_n1.text_input("Nome"); t = c_n2.text_input("Telefone")
                bal = c_n1.number_input("Saldo", step=100.0); tp = c_n2.selectbox("Tipo", ["comum", "admin"])
                if st.form_submit_button("Cadastrar"):
                    ok, msg = cadastrar_novo_usuario(u, s, n, bal, tp, t)
                    if ok: st.success(msg); time.sleep(1.5); st.rerun()
                    else: st.error(msg)
        
        st.divider()
        df_u = run_query("SELECT * FROM usuarios ORDER BY id") 
        if not df_u.empty:
            if "Notificar" not in df_u.columns: df_u.insert(0, "Notificar", False)
            edit_u = st.data_editor(
                df_u, use_container_width=True, key="ed_u_sql",
                column_config={"Notificar": st.column_config.CheckboxColumn("Avisar?", default=False)}
            )
            c_u1, c_u2 = st.columns(2)
            if c_u1.button("💾 Salvar Saldos"):
                with conn.session as sess:
                    for i, row in edit_u.iterrows():
                        sess.execute(text("UPDATE usuarios SET saldo = :s, telefone = :t, nome = :n WHERE id = :id"),
                                     {"s": row['saldo'], "t": row['telefone'], "n": row['nome'], "id": row['id']})
                    sess.commit()
                registrar_log("Admin", "Atualizou saldos")
                st.success("✅ Saldos atualizados!"); time.sleep(2); st.rerun()
                
            if c_u2.button("📲 Enviar Aviso Saldo", type="primary"):
                sel = edit_u[edit_u['Notificar'] == True]
                enviados = 0
                for i, row in sel.iterrows():
                    tel = str(row['telefone']); nome = str(row['nome']); saldo = f"{float(row['saldo']):,.0f}"
                    if len(formatar_telefone(tel)) < 12: continue
                    ok, _ = enviar_whatsapp_template(tel, [nome, saldo], "aviso_saldo_atualizado")
                    if ok: enviados += 1
                if enviados > 0: 
                    st.balloons()
                    st.markdown(f'<div class="big-success">📲 {enviados} Avisos Enviados!</div>', unsafe_allow_html=True)
                    time.sleep(3); st.rerun()

    with t3:
        df_p = run_query("SELECT * FROM premios ORDER BY id") 
        edit_p = st.data_editor(df_p, use_container_width=True, num_rows="dynamic", key="ed_p_sql")
        if st.button("Salvar Prêmios"):
            with conn.session as sess:
                for i, row in edit_p.iterrows():
                    if row['id']: 
                        sess.execute(text("UPDATE premios SET item=:i, imagem=:im, custo=:c WHERE id=:id"),
                                     {"i": row['item'], "im": row['imagem'], "c": row['custo'], "id": row['id']})
                sess.commit()
            st.success("✅ Catálogo atualizado!"); time.sleep(2); st.rerun()

    with t4:
        st.write("### Ferramentas & Logs")
        df_logs = run_query("SELECT * FROM logs ORDER BY id DESC LIMIT 50")
        st.dataframe(df_logs, use_container_width=True)

def tela_principal():
    u_cod, u_nome, sld, tipo = st.session_state.usuario_cod, st.session_state.usuario_nome, st.session_state.saldo_atual, st.session_state.tipo_usuario
    
    # Header Principal (Sem Logo, Botões Alinhados)
    c_info, c_acoes = st.columns([3, 1])
    
    with c_info:
        st.markdown(f'''
            <div class="header-style">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <h2 style="margin:0; color:white;">Olá, {u_nome}! 👋</h2>
                        <p style="margin:0; opacity:0.9; color:white;">Bem Vindo (a) a Loja Culligan. Aqui você pode trocar seus pontos por prêmios incríveis, aproveite!</p>
                    </div>
                    <div style="text-align:right; color:white;">
                        <span style="font-size:12px; opacity:0.8;">SEU SALDO</span><br>
                        <span style="font-size:32px; font-weight:bold;">{sld:,.0f}</span> pts
                    </div>
                </div>
            </div>
        ''', unsafe_allow_html=True)
        
    with c_acoes:
        cs, cl = st.columns([1, 1], gap="small")
        if cs.button("Alterar Senha", use_container_width=True): abrir_modal_senha(u_cod)
        if cl.button("Sair", type="primary", use_container_width=True): st.session_state.logado=False; st.rerun()

    st.divider()
    
    if tipo == 'admin': tela_admin()
    else:
        t1, t2 = st.tabs(["🎁 Catálogo", "📜 Meus Resgates"])
        with t1:
            df_p = run_query("SELECT * FROM premios ORDER BY id") 
            if not df_p.empty:
                cols = st.columns(4)
                for i, row in df_p.iterrows():
                    with cols[i % 4]:
                        with st.container(border=True):
                            img = str(row.get('imagem', ''))
                            # USANDO A NOVA FUNÇÃO DE PROCESSAMENTO DE LINKS AQUI:
                            if len(img) > 10: st.image(processar_link_imagem(img))
                            st.markdown(f"**{row['item']}**")
                            cor = "#0066cc" if sld >= row['custo'] else "#999"
                            st.markdown(f"<div style='color:{cor}; font-weight:bold;'>{row['custo']} pts</div>", unsafe_allow_html=True)
                            if sld >= row['custo'] and st.button("RESGATAR", key=f"b_{row['id']}", use_container_width=True):
                                confirmar_resgate_dialog(row['item'], row['custo'], u_cod)
        with t2:
            st.info("### 📜 Acompanhamento\nPedido recebido! Prazo: **5 dias úteis** via e-mail.")
            meus = run_query("SELECT data, item, valor, status, email FROM vendas WHERE usuario = :u ORDER BY data DESC", {"u": u_cod})
            st.dataframe(meus, use_container_width=True)

if __name__ == "__main__":
    if st.session_state.logado: tela_principal()
    else: tela_login()
