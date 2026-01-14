import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import base64
import bcrypt
import requests
import re

# --- CONFIGURAÇÕES GERAIS ---
st.set_page_config(page_title="Loja Culligan", layout="wide", page_icon="🎁")

ARQUIVO_LOGO = "logo.png"

# --- FUNÇÕES DE SUPORTE ---

def carregar_logo_base64(caminho_arquivo):
    try:
        with open(caminho_arquivo, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        return f"data:image/png;base64,{encoded_string}"
    except Exception:
        return "https://cdn-icons-png.flaticon.com/512/6213/6213388.png"

def verificar_senha_hash(senha_digitada, hash_armazenado):
    try:
        return bcrypt.checkpw(senha_digitada.encode('utf-8'), hash_armazenado.encode('utf-8'))
    except ValueError:
        return senha_digitada == hash_armazenado

def gerar_hash(senha):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha.encode('utf-8'), salt).decode('utf-8')

def converter_link_drive(url):
    url = str(url).strip()
    if "drive.google.com" in url:
        if "id=" in url: return url
        try:
            file_id = url.split("/")[-2]
            return f"https://drive.google.com/uc?export=view&id={file_id}"
        except: return url
    return url

def formatar_telefone(tel_bruto):
    apenas_numeros = re.sub(r'\D', '', str(tel_bruto))
    if 10 <= len(apenas_numeros) <= 11:
        apenas_numeros = "55" + apenas_numeros
    return apenas_numeros

def enviar_whatsapp_template(telefone, parametros):
    """Envia usando Template e pega erro detalhado"""
    try:
        base_url = st.secrets["INFOBIP_BASE_URL"].rstrip('/')
        api_key = st.secrets["INFOBIP_API_KEY"]
        sender = st.secrets["INFOBIP_SENDER"]
        
        url = f"{base_url}/whatsapp/1/message/template"
        
        payload = {
            "messages": [
                {
                    "from": sender,
                    "to": formatar_telefone(telefone),
                    "content": {
                        "templateName": "premios_campanhas_envio", 
                        "templateData": {
                            "body": {
                                "placeholders": parametros # Lista [Nome, Item, Codigo]
                            }
                        },
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
        
        if response.status_code not in [200, 201]:
            # Retorna o erro exato para mostrar na tela
            return False, f"Erro {response.status_code}: {response.text}"
            
        return True, "Sucesso"
    except Exception as e:
        return False, f"Erro de Conexão: {str(e)}"

# --- SESSÃO ---
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
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Roboto', sans-serif; }}
    header {{ visibility: hidden; }}
    .stDeployButton {{ display: none; }}
    @keyframes gradient {{ 0% {{ background-position: 0% 50%; }} 50% {{ background-position: 100% 50%; }} 100% {{ background-position: 0% 50%; }} }}
    {bg_style}
    .block-container {{ padding-top: 2rem !important; padding-bottom: 2rem !important; }}
    [data-testid="stForm"] {{ background-color: #ffffff; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); border: none; }}
    .header-style {{ background: linear-gradient(-45deg, #000428, #004e92, #2F80ED, #56CCF2); background-size: 400% 400%; animation: gradient 10s ease infinite; padding: 20px 25px; border-radius: 15px; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.1); display: flex; flex-direction: column; justify-content: center; height: 100%; }}
    [data-testid="stImage"] img {{ height: 150px !important; object-fit: contain !important; border-radius: 10px; }}
    div.stButton > button[kind="secondary"] {{ background-color: #0066cc; color: white; border-radius: 8px; border: none; height: 40px; font-weight: bold; width: 100%; }}
    div.stButton > button[kind="primary"] {{ background-color: #ff4b4b !important; color: white !important; border-radius: 8px; border: none; height: 40px; font-weight: bold; width: 100%; }}
    .btn-container-alinhado {{ margin-top: -10px; }}
    </style>
""", unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_dados(aba):
    try: return conn.read(worksheet=aba, ttl=0)
    except: return pd.DataFrame()

def limpar_dado(dado): 
    texto = str(dado).strip()
    return texto.replace('.0', '') if texto.endswith('.0') else texto

def validar_login(user_input, pass_input):
    df = carregar_dados("usuarios")
    if df.empty: return False, None, None, 0
    u_in = limpar_dado(user_input).lower()
    df_temp = df.copy()
    df_temp['u_busca'] = df_temp['usuario'].astype(str).apply(lambda x: limpar_dado(x).lower())
    user_row = df_temp[df_temp['u_busca'] == u_in]
    if not user_row.empty:
        linha = user_row.iloc[0]
        if verificar_senha_hash(limpar_dado(pass_input), limpar_dado(linha['senha'])):
            return True, linha['nome'], str(linha['tipo']).lower().strip(), float(linha['saldo'])
    return False, None, None, 0

def salvar_venda(usuario_cod, item_nome, custo, email_contato):
    try:
        # 1. Debita saldo
        df_u = carregar_dados("usuarios")
        # Procura o usuário para pegar dados completos (telefone e nome)
        usuario_row = df_u[df_u['usuario'].astype(str).str.lower() == usuario_cod.lower()]
        
        if usuario_row.empty: return False
        
        idx = usuario_row.index[0]
        telefone_user = str(usuario_row.at[idx, 'telefone']) # Pega o telefone do cadastro
        nome_user = str(usuario_row.at[idx, 'nome'])         # Pega o nome do cadastro
        
        df_u.at[idx, 'saldo'] = float(df_u.at[idx, 'saldo']) - custo
        conn.update(worksheet="usuarios", data=df_u)
        
        # 2. Registra Venda (AGORA COM NOME E TELEFONE)
        df_v = carregar_dados("vendas")
        nova = pd.DataFrame([{
            "Data": datetime.now().strftime("%d/%m/%Y %H:%M"), 
            "Usuario": usuario_cod, 
            "Item": item_nome, 
            "Valor": custo, 
            "Status": "Pendente", 
            "Email": email_contato,
            "NomeReal": nome_user,    # Nova Coluna
            "Telefone": telefone_user # Nova Coluna
        }])
        
        # Concatena garantindo que as colunas existam
        conn.update(worksheet="vendas", data=pd.concat([df_v, nova], ignore_index=True))
        st.session_state['saldo_atual'] -= custo
        return True
    except Exception as e:
        print(e)
        return False

# --- MODAIS ---
@st.dialog("🔐 Alterar Senha")
def abrir_modal_senha(usuario_cod):
    n = st.text_input("Nova Senha", type="password")
    c = st.text_input("Confirmar", type="password")
    if st.button("Salvar Senha"):
        if n == c and n:
            df = carregar_dados("usuarios")
            df.loc[df['usuario'].astype(str).str.lower() == usuario_cod.lower(), 'senha'] = gerar_hash(n)
            conn.update(worksheet="usuarios", data=df)
            st.success("Senha alterada!"); time.sleep(1); st.session_state['logado'] = False; st.rerun()

@st.dialog("🎁 Confirmar Resgate")
def confirmar_resgate_dialog(item_nome, custo, usuario_cod):
    st.write(f"Resgatando: **{item_nome}** por **{custo} pts**.")
    email_contato = st.text_input("E-mail para envio do vale:", placeholder="exemplo@email.com")
    if st.button("CONFIRMAR", type="primary", use_container_width=True):
        if "@" in email_contato and "." in email_contato:
            if salvar_venda(usuario_cod, item_nome, custo, email_contato):
                st.success("Sucesso! Compra registrada."); st.balloons(); time.sleep(2); st.rerun()
        else: st.warning("E-mail inválido.")

# --- TELAS ---
def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        with st.form("f_login"):
            img_b64 = carregar_logo_base64(ARQUIVO_LOGO)
            st.markdown(f'<center><img src="{img_b64}" width="220"></center><br>', unsafe_allow_html=True)
            u = st.text_input("Usuário"); s = st.text_input("Senha", type="password")
            if st.form_submit_button("ENTRAR", type="primary", use_container_width=True):
                ok, n, t, sld = validar_login(u, s)
                if ok:
                    st.session_state.update({'logado':True, 'usuario_cod':u, 'usuario_nome':n, 'tipo_usuario':t, 'saldo_atual':sld})
                    st.rerun()
                else: st.toast("Erro!", icon="❌")

def tela_admin():
    st.subheader("🛠️ Painel Admin")
    t1, t2, t3, t4 = st.tabs(["📊 Entregas & WhatsApp", "👥 Usuários", "🎁 Prêmios", "🛠️ Ferramentas"])
    
    with t1:
        df_v = carregar_dados("vendas")
        
        if not df_v.empty:
            if "Enviar" not in df_v.columns: df_v.insert(0, "Enviar", False)
            
            # Garante que as novas colunas existem no dataframe para visualização
            if "Telefone" not in df_v.columns: df_v["Telefone"] = ""
            if "NomeReal" not in df_v.columns: df_v["NomeReal"] = ""
            
            st.info("💡 As colunas 'Telefone' e 'NomeReal' devem estar preenchidas na planilha. Se estiverem vazias, preencha manualmente antes de enviar.")
            
            # Configuração das Colunas
            col_config = {
                "Enviar": st.column_config.CheckboxColumn("Enviar?", default=False),
                "CodigoVale": st.column_config.TextColumn("Código do Vale (Obrigatório)"),
                "Telefone": st.column_config.TextColumn("Telefone (Obrigatório)", help="Formato: 11999999999"),
                "NomeReal": st.column_config.TextColumn("Nome na Mensagem")
            }
            
            edit_v = st.data_editor(
                df_v, use_container_width=True, hide_index=True, key="ed_vendas_final_v4", column_config=col_config
            )
            
            if st.button("📤 Processar Envios", type="primary"):
                selecionados = edit_v[edit_v['Enviar'] == True]
                
                if selecionados.empty:
                    st.warning("Nenhuma linha selecionada.")
                else:
                    enviados = 0
                    erros = []
                    
                    barra = st.progress(0)
                    total = len(selecionados)
                    
                    st.write("--- Iniciando Envios ---")
                    
                    for i, (index, row) in enumerate(selecionados.iterrows()):
                        barra.progress((i + 1) / total)
                        
                        # 1. PEGA DADOS DIRETO DA LINHA (Sem PROCV)
                        tel_destino = str(row.get('Telefone', '')).strip()
                        nome_destino = str(row.get('NomeReal', '')).strip()
                        # Se NomeReal estiver vazio, usa o Usuario como quebra-galho
                        if not nome_destino or nome_destino == 'nan': nome_destino = str(row.get('Usuario', ''))
                        
                        item_venda = str(row.get('Item', ''))
                        cod_vale = str(row.get('CodigoVale', ''))
                        
                        # 2. VALIDAÇÕES BÁSICAS
                        if len(tel_destino) < 8 or tel_destino == 'nan':
                            msg = f"❌ Erro: Telefone vazio na venda de {nome_destino}."
                            st.write(msg); erros.append(msg)
                            continue
                            
                        if cod_vale == '' or cod_vale == 'nan':
                            msg = f"❌ Erro: Código do vale vazio na venda de {nome_destino}."
                            st.write(msg); erros.append(msg)
                            continue

                        # 3. ENVIA
                        # Parametros: {{1}}=Nome, {{2}}=Item, {{3}}=Codigo
                        sucesso, resposta = enviar_whatsapp_template(tel_destino, [nome_destino, item_venda, cod_vale])
                        
                        if sucesso:
                            st.write(f"✅ Enviado para {nome_destino} ({tel_destino})")
                            enviados += 1
                        else:
                            msg = f"⚠️ Erro API ({nome_destino}): {resposta}"
                            st.write(msg); erros.append(msg)
                            
                    if enviados > 0:
                        st.success(f"Concluído! {enviados} mensagens enviadas.")
                        edit_v_limpo = edit_v.drop(columns=["Enviar"])
                        conn.update(worksheet="vendas", data=edit_v_limpo)
                        time.sleep(3); st.rerun()

    with t2:
        df_u = carregar_dados("usuarios")
        edit_u = st.data_editor(df_u, use_container_width=True, num_rows="dynamic", key="ed_u")
        if st.button("Salvar Usuários"): conn.update(worksheet="usuarios", data=edit_u); st.rerun()
    with t3:
        df_p = carregar_dados("premios")
        edit_p = st.data_editor(df_p, use_container_width=True, num_rows="dynamic", key="ed_p")
        if st.button("Salvar Prêmios"): conn.update(worksheet="premios", data=edit_p); st.rerun()
    
    with t4:
        st.markdown(f"### 🧪 Teste de Envio")
        c1, c2 = st.columns([2, 1])
        tel_teste = c1.text_input("Número (com DDD)", placeholder="11999999999")
        if c1.button("Testar Template Agora"):
            if tel_teste:
                ok, resp = enviar_whatsapp_template(tel_teste, ["Teste", "Prêmio X", "COD-123"])
                if ok: st.success("✅ Sucesso!")
                else: st.error(f"❌ {resp}")

def tela_principal():
    u_cod, u_nome, sld, tipo = st.session_state.usuario_cod, st.session_state.usuario_nome, st.session_state.saldo_atual, st.session_state.tipo_usuario
    c_info, c_acoes = st.columns([3, 1.1])
    with c_info:
        st.markdown(f'<div class="header-style"><div style="display:flex; justify-content:space-between; align-items:center;"><div><h2 style="margin:0; color:white;">Olá, {u_nome}! 👋</h2><p style="margin:0; opacity:0.9; color:white;">Bem Vindo (a) a Loja Culligan.</p></div><div style="text-align:right; color:white;"><span style="font-size:12px; opacity:0.8;">SEU SALDO</span><br><span style="font-size:32px; font-weight:bold;">{sld:,.0f}</span> pts</div></div></div>', unsafe_allow_html=True)
    with c_acoes:
        img_b64 = carregar_logo_base64(ARQUIVO_LOGO)
        st.markdown(f'<center><img src="{img_b64}" style="max-height: 80px;"></center>', unsafe_allow_html=True)
        st.markdown('<div class="btn-container-alinhado">', unsafe_allow_html=True)
        cs, cl = st.columns([1.1, 1])
        if cs.button("Alterar Senha", use_container_width=True): abrir_modal_senha(u_cod)
        if cl.button("Sair", type="primary", use_container_width=True): st.session_state.logado=False; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    st.divider()
    if tipo == 'admin': tela_admin()
    else:
        t1, t2 = st.tabs(["🎁 Catálogo", "📜 Meus Resgates"])
        with t1:
            df_p = carregar_dados("premios")
            if not df_p.empty:
                cols = st.columns(4, gap="small")
                for i, row in df_p.iterrows():
                    with cols[i % 4]:
                        with st.container(border=True):
                            img = str(row.get('imagem', '')).strip()
                            if img and img != "0" and len(img) > 10: st.image(converter_link_drive(img))
                            else: st.image("https://via.placeholder.com/200")
                            st.markdown(f"**{row['item']}**")
                            cor = "#0066cc" if sld >= row['custo'] else "#999"
                            st.markdown(f"<div style='color:{cor}; font-weight:bold;'>{row['custo']} pts</div>", unsafe_allow_html=True)
                            if sld >= row['custo'] and st.button("RESGATAR", key=f"b_{row['id']}", use_container_width=True):
                                confirmar_resgate_dialog(row['item'], row['custo'], u_cod)
        with t2:
            st.info("### 📜 Acompanhamento\nPedido recebido! Prazo: **5 dias úteis** via e-mail.")
            df_v = carregar_dados("vendas")
            if not df_v.empty:
                meus = df_v[df_v['Usuario'].astype(str)==str(u_cod)]
                if 'Status' in meus.columns:
                    st.dataframe(meus[['Data','Item','Valor','Status','Email']], use_container_width=True, hide_index=True)
                else:
                    st.dataframe(meus, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    if st.session_state.logado: tela_principal()
    else: tela_login()
