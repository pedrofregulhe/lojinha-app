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
    bg_style = ".stApp { background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); background-size: 400% 400%; animation: gradient 15s ease infinite; }"
else:
    bg_style = ".stApp { background-color: #f4f8fb; }"

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;900&display=swap');
    html, body, [class*="css"] {{ font-family: 'Poppins', sans-serif; }}
    header {{ visibility: hidden; }}
    .stDeployButton {{ display: none; }}
    @keyframes gradient {{ 0% {{ background-position: 0% 50%; }} 50% {{ background-position: 100% 50%; }} 100% {{ background-position: 0% 50%; }} }}
    {bg_style}
    .block-container {{ padding-top: 2rem !important; padding-bottom: 2rem !important; }}
    [data-testid="stForm"] {{ background-color: #ffffff; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); border: none; }}
    .header-style {{ background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); background-size: 400% 400%; animation: gradient 10s ease infinite; padding: 25px 30px; border-radius: 15px; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.1); display: flex; flex-direction: column; justify-content: center; height: 100%; }}
    [data-testid="stImage"] img {{ height: 150px !important; object-fit: contain !important; border-radius: 10px; }}
    div.stButton > button[kind="secondary"] {{ background-color: #0066cc; color: white; border-radius: 8px; border: none; height: 45px; font-weight: 600; width: 100%; }}
    div.stButton > button[kind="primary"] {{ background-color: #ff4b4b !important; color: white !important; border-radius: 8px; border: none; height: 45px; font-weight: 600; width: 100%; }}
    .big-success {{ padding: 20px; background-color: #d4edda; color: #155724; border-radius: 10px; font-weight: bold; text-align: center; border: 1px solid #c3e6cb; margin-bottom: 10px; }}
    [data-testid="column"] {{ display: flex; flex-direction: column; justify-content: center; }}
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES ---
def verificar_senha_hash(senha_digitada, hash_armazenado):
    try:
        if not hash_armazenado.startswith("$2b$"): return senha_digitada == hash_armazenado
        return bcrypt.checkpw(senha_digitada.encode('utf-8'), hash_armazenado.encode('utf-8'))
    except ValueError: return False

def gerar_hash(senha):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha.encode('utf-8'), salt).decode('utf-8')

def processar_link_imagem(url):
    url = str(url).strip()
    if "github.com" in url and "/blob/" in url: return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    if "drive.google.com" in url:
        if "id=" in url: return url
        try: file_id = url.split("/")[-2]; return f"https://drive.google.com/uc?export=view&id={file_id}"
        except: return url
    return url

def formatar_telefone(tel_bruto):
    # Remove espaços, parênteses, traços
    texto = str(tel_bruto).strip()
    if texto.endswith(".0"): texto = texto[:-2]
    apenas_numeros = re.sub(r'\D', '', texto)
    
    # Se tiver entre 10 e 11 dígitos (Ex: 11999998888), adiciona 55
    if 10 <= len(apenas_numeros) <= 11: 
        apenas_numeros = "55" + apenas_numeros
    # Se já tiver 12 ou 13 (Ex: 5511999998888), mantém
    
    return apenas_numeros

# --- FUNÇÃO SMS PADRÃO (Igual para ambas as abas) ---
def enviar_sms(telefone, mensagem_texto):
    try:
        base_url = st.secrets["INFOBIP_BASE_URL"].rstrip('/')
        api_key = st.secrets["INFOBIP_API_KEY"]
        
        url = f"{base_url}/sms/2/text/advanced"
        tel_final = formatar_telefone(telefone)
        
        # Validação simples
        if len(tel_final) < 12: 
            return False, f"Num Inválido: {tel_final}"

        payload = {
            "messages": [
                {
                    # Sem "from" para garantir entrega com rota padrão
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
            return False, f"Erro API {response.status_code}: {response.text}"
            
        return True, tel_final
    except Exception as e: return False, str(e)

def enviar_whatsapp_template(telefone, parametros, nome_template="atualizar_envio_pedidos"):
    try:
        base_url = st.secrets["INFOBIP_BASE_URL"].rstrip('/')
        api_key = st.secrets["INFOBIP_API_KEY"]
        sender = st.secrets["INFOBIP_SENDER"]
        url = f"{base_url}/whatsapp/1/message/template"
        tel_final = formatar_telefone(telefone)
        if len(tel_final) < 12: return False, f"Número inválido: {tel_final}"
        payload = { "messages": [ { "from": sender, "to": tel_final, "content": { "templateName": nome_template, "templateData": { "body": { "placeholders": parametros } }, "language": "pt_BR" } } ] }
        headers = { "Authorization": f"App {api_key}", "Content-Type": "application/json", "Accept": "application/json" }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code not in [200, 201]: return False, f"Erro API {response.status_code}: {response.text}"
        return True, f"Enviado para {tel_final}"
    except Exception as e: return False, f"Erro Conexão: {str(e)}"

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
    if df.empty: return False, None, None, 0
    linha = df.iloc[0]
    if verificar_senha_hash(pass_input.strip(), linha['senha']):
        return True, linha['nome'], str(linha['tipo']).lower().strip(), float(linha['saldo'])
    return False, None, None, 0

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
    if st.button("Salvar Senha"):
        if n == c and n:
            run_transaction("UPDATE usuarios SET senha = :s WHERE LOWER(usuario) = LOWER(:u)", {"s": gerar_hash(n), "u": usuario_cod})
            registrar_log("Senha Alterada", f"Usuário: {usuario_cod}")
            st.success("Sucesso!"); time.sleep(1); st.session_state['logado'] = False; st.rerun()

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

# --- TELAS ---
def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        with st.form("f_login"):
            st.markdown("""
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #003366; font-weight: 900; font-size: 3rem; margin: 0; margin-bottom: 10px;">
                        LOJINHA CULLI
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
            
            c1, c2 = st.columns(2)
            if c1.button("💾 Salvar Alterações"):
                with conn.session as s:
                    for i, row in edit_v.iterrows():
                        s.execute(text("UPDATE vendas SET codigo_vale=:c, status=:st, nome_real=:n, telefone=:t WHERE id=:id"), {"c": row['codigo_vale'], "st": row['status'], "n": row['nome_real'], "t": row['telefone'], "id": row['id']})
                    s.commit()
                registrar_log("Admin", "Editou vendas"); st.success("Salvo!"); time.sleep(1); st.rerun()
            
            st.divider()
            st.markdown("##### 📢 Disparo de Prêmios")
            
            c_chan1, c_chan2 = st.columns(2)
            usar_zap = c_chan1.checkbox("Enviar por WhatsApp", value=True)
            usar_sms = c_chan2.checkbox("Enviar por SMS (Custo Extra)", value=False)
            
            if st.button("📤 Enviar Selecionados", type="primary"):
                sel = edit_v[edit_v['Enviar'] == True]
                env_zap = 0
                env_sms = 0
                
                if sel.empty:
                    st.warning("Ninguém selecionado na coluna 'Enviar'.")
                else:
                    for i, row in sel.iterrows():
                        tel = str(row['telefone']); nome = str(row['nome_real'] or row['usuario'])
                        
                        if len(formatar_telefone(tel)) >= 12 and row['codigo_vale']:
                            if usar_zap:
                                if enviar_whatsapp_template(tel, [nome, str(row['item']), str(row['codigo_vale'])])[0]: 
                                    env_zap += 1
                            if usar_sms:
                                texto_sms = f"Ola {nome}, seu resgate de {row['item']} foi liberado! Cod: {row['codigo_vale']}."
                                ok, info = enviar_sms(tel, texto_sms)
                                if ok: 
                                    env_sms += 1
                                else:
                                    st.error(f"Erro SMS para {nome}: {info}")
                                    
                    if env_zap > 0 or env_sms > 0: 
                        registrar_log("Admin", f"Enviou {env_zap} Zaps e {env_sms} SMS")
                        st.balloons()
                        st.success(f"Enviado! (WhatsApp: {env_zap} | SMS: {env_sms})")
                        time.sleep(3); st.rerun()

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
                    
        with st.expander("💰 Distribuir Pontos (Soma no Ranking)", expanded=True):
            st.info("Selecione uma ou mais pessoas para dar pontos. Soma no Saldo e no Ranking.")
            c_d1, c_d2, c_d3 = st.columns([2, 1, 1])
            df_users_list = run_query("SELECT usuario FROM usuarios WHERE tipo NOT IN ('admin', 'staff') ORDER BY usuario")
            lista_users = df_users_list['usuario'].tolist() if not df_users_list.empty else []
            
            target_users = c_d1.multiselect("Selecione os Usuários", ["Todos"] + lista_users)
            qtd_pontos = c_d2.number_input("Pontos", step=50, value=0)
            
            if c_d3.button("➕ Creditar", type="primary", use_container_width=True):
                if qtd_pontos > 0 and target_users:
                    if distribuir_pontos_multiplos(target_users, qtd_pontos): 
                        st.success("Creditado com sucesso!"); time.sleep(2); st.rerun()
                else: st.warning("Selecione alguém e um valor maior que 0.")

        st.divider()
        st.write("### Gerenciar Usuários (Tabela Completa)")
        
        df_u = run_query("SELECT * FROM usuarios ORDER BY id") 
        if not df_u.empty:
            if "Notificar" not in df_u.columns: df_u.insert(0, "Notificar", False)
            edit_u = st.data_editor(df_u, use_container_width=True, key="ed_u", column_config={
                "Notificar": st.column_config.CheckboxColumn("Avisar?", default=False),
                "saldo": st.column_config.NumberColumn("Saldo (Gastar)", help="Dinheiro na carteira agora"),
                "pontos_historico": st.column_config.NumberColumn("Ranking (Total)", help="Total acumulado na vida (não zera)")
            })
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            c_check_zap, c_check_sms, c_btn_save, c_btn_send = st.columns([0.8, 0.8, 1.2, 1.5])

            with c_check_zap:
                aviso_zap = st.checkbox("WhatsApp", value=True, key="check_bal_zap")
            with c_check_sms:
                aviso_sms = st.checkbox("SMS", value=False, key="check_bal_sms")
            
            with c_btn_save:
                if st.button("💾 Atualizar Banco", use_container_width=True):
                    with conn.session as sess:
                        for i, row in edit_u.iterrows():
                            sess.execute(text("UPDATE usuarios SET saldo=:s, pontos_historico=:ph, telefone=:t, nome=:n, tipo=:tp WHERE id=:id"), 
                                         {"s": row['saldo'], "ph": row['pontos_historico'], "t": row['telefone'], "n": row['nome'], "tp": row['tipo'], "id": row['id']})
                        sess.commit()
                    registrar_log("Admin", "Editou usuários na tabela"); st.toast("Dados atualizados!", icon="✅"); time.sleep(1); st.rerun()

            with c_btn_send:
                if st.button("📤 Enviar Avisos", type="primary", use_container_width=True):
                    sel = edit_u[edit_u['Notificar'] == True]
                    env_zap = 0
                    env_sms = 0
                    erros_lista = []
                    
                    if sel.empty:
                        st.warning("Ninguém selecionado na coluna 'Avisar?'.")
                    else:
                        bar_progresso = st.progress(0)
                        total = len(sel)
                        
                        for i, (index, row) in enumerate(sel.iterrows()):
                            tel = str(row['telefone'])
                            nome = str(row['nome'])
                            try: saldo_fmt = f"{float(row['saldo']):,.0f}"
                            except: saldo_fmt = "0"
                            
                            # Validação e Envio - Lógica IDÊNTICA à aba de Vendas
                            if len(formatar_telefone(tel)) >= 12:
                                if aviso_zap:
                                    ok_zap, info_zap = enviar_whatsapp_template(tel, [nome, saldo_fmt], "atualizar_saldo_pedidos")
                                    if ok_zap: env_zap += 1
                                
                                if aviso_sms:
                                    msg_sms = f"Ola {nome}, seu saldo foi atualizado! Saldo atual: {saldo_fmt} pts. Acesse a loja para conferir."
                                    ok_sms, info_sms = enviar_sms(tel, msg_sms)
                                    if ok_sms: env_sms += 1
                                    else: erros_lista.append(f"{nome}: {info_sms}")
                            else:
                                erros_lista.append(f"{nome}: Telefone inválido/curto")

                            bar_progresso.progress((i + 1) / total)
                        bar_progresso.empty()

                        if env_zap > 0 or env_sms > 0: 
                            st.balloons()
                            st.success(f"Enviado! (WhatsApp: {env_zap} | SMS: {env_sms})")
                        
                        if erros_lista:
                            with st.expander("⚠️ Relatório de Problemas", expanded=True):
                                for err in erros_lista: st.error(err)
                        time.sleep(4); st.rerun()

    with t3:
        df_p = run_query("SELECT * FROM premios ORDER BY id"); edit_p = st.data_editor(df_p, use_container_width=True, num_rows="dynamic", key="ed_p")
        if st.button("Salvar Prêmios"):
            with conn.session as sess:
                for i, row in edit_p.iterrows():
                    if row['id']: sess.execute(text("UPDATE premios SET item=:i, imagem=:im, custo=:c WHERE id=:id"), {"i": row['item'], "im": row['imagem'], "c": row['custo'], "id": row['id']})
                sess.commit()
            st.success("Salvo!"); st.rerun()

    with t4:
        st.dataframe(run_query("SELECT * FROM logs ORDER BY id DESC LIMIT 50"), use_container_width=True)

def tela_principal():
    u_cod, u_nome, sld, tipo = st.session_state.usuario_cod, st.session_state.usuario_nome, st.session_state.saldo_atual, st.session_state.tipo_usuario
    c_info, c_acoes = st.columns([3, 1])
    with c_info: st.markdown(f'<div class="header-style"><div style="display:flex; justify-content:space-between; align-items:center;"><div><h2 style="margin:0; color:white;">Olá, {u_nome}! 👋</h2><p style="margin:0; opacity:0.9; color:white;">Bem Vindo (a) a Loja Culligan. Aqui você pode trocar seus pontos por prêmios incríveis! Aproveite!</p></div><div style="text-align:right; color:white;"><span style="font-size:12px; opacity:0.8;">SEU SALDO</span><br><span style="font-size:32px; font-weight:bold;">{sld:,.0f}</span> pts</div></div></div>', unsafe_allow_html=True)
    with c_acoes:
        cs, cl = st.columns([1, 1], gap="small")
        if cs.button("Alterar Senha", use_container_width=True): abrir_modal_senha(u_cod)
        if cl.button("Sair", type="primary", use_container_width=True): st.session_state.logado=False; st.rerun()
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
                            if sld >= row['custo'] and st.button("RESGATAR", key=f"b_{row['id']}", use_container_width=True): confirmar_resgate_dialog(row['item'], row['custo'], u_cod)
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
    if st.session_state.logado: tela_principal()
    else: tela_login()
