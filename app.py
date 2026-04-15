import streamlit as st
from datetime import date
import pandas as pd
from supabase import create_client, Client
import streamlit.components.v1 as components

# --- 1. Supabase 接続設定 ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- 2. データベース復元関数 ---
def load_and_restore_data(uid):
    try:
        res = supabase.table("user_incomes").select("income_data").eq("user_id", uid).execute()
        if len(res.data) > 0:
            saved_data = res.data[0]["income_data"]
            for i in range(1, 13):
                st.session_state[f"m{i}"] = saved_data.get(f"m{i}", 0)
            if "app_settings" in saved_data:
                settings = saved_data["app_settings"]
                st.session_state.user_category = settings.get("user_category", "一般")
                st.session_state.shaho_limit = settings.get("shaho_limit", 1300000)
                st.session_state.target_key = settings.get("target_key", "136万：親や配偶者の税金を増やさない")
            return True
    except:
        pass
    return False

# --- 3. 認証処理 ---
if "code" in st.query_params:
    try:
        supabase.auth.exchange_code_for_session({"auth_code": st.query_params["code"]})
        st.query_params.clear()
        user_resp = supabase.auth.get_user()
        if user_resp and user_resp.user:
            if load_and_restore_data(user_resp.user.id):
                st.session_state.step = "calculation"
        st.rerun()
    except:
        pass

# --- 4. 基礎データ定義（令和8年最新スケジュール反映） ---
YEAR = 2026
WALL_DETAILS = {
    "106万：社会保険（2026年10月賃金要件撤廃予定）": 1060000,
    "130万：自分の社保を免除（一般）": 1300000,
    "136万：親や配偶者の税金を増やさない": 1360000,
    "178万：自分の所得税を0円にする（令和8年特例）": 1780000
}

# --- 5. セッション状態の初期化 ---
user_resp = None
try:
    user_resp = supabase.auth.get_user()
except:
    pass

if user_resp and user_resp.user and 'step' not in st.session_state:
    if load_and_restore_data(user_resp.user.id):
        st.session_state.step = "calculation"
    else:
        st.session_state.step = "diagnosis"

if 'step' not in st.session_state: st.session_state.step = "diagnosis"
if 'target_key' not in st.session_state: st.session_state.target_key = "136万：親や配偶者の税金を増やさない"
if 'user_category' not in st.session_state: st.session_state.user_category = "一般"
if 'shaho_limit' not in st.session_state: st.session_state.shaho_limit = 1300000

# --- 6. アプリ設定 ---
st.set_page_config(page_title="2026年 年収の壁シミュレーター", layout="centered", initial_sidebar_state="collapsed")

# --- 7. Google Search Console 認証タグ ---
components.html("""<meta name="google-site-verification" content="j6no7A2pU6Xtd7DETM3KgDi7O8H" />""", height=0)

# --- 8. サイドバー ---
st.sidebar.header("⚙️ システム設定")
area_type = st.sidebar.selectbox("お住まいの地域", ["東京・大阪など", "県庁所在地など", "その他の市町村"])
jumin_limit_base = 1220000 if "東京" in area_type else (1185000 if "県庁" in area_type else 1120000)

if st.sidebar.button("最初から診断し直す"):
    st.session_state.step = "diagnosis"
    st.rerun()

st.sidebar.divider()
st.sidebar.header("🔐 アカウント")

if user_resp and user_resp.user:
    user_meta = user_resp.user.user_metadata
    c1, c2 = st.sidebar.columns([1, 3])
    with c1: st.image(user_meta.get("avatar_url", ""), use_container_width=True)
    with c2: st.write(f"**{user_meta.get('full_name', 'ユーザー')}** さん")
    if st.sidebar.button("💾 データをクラウドに保存", type="primary", use_container_width=True):
        uid = user_resp.user.id
        data = {f"m{i}": st.session_state.get(f"m{i}", 0) for i in range(1, 13)}
        data["app_settings"] = {"user_category": st.session_state.user_category, "shaho_limit": st.session_state.shaho_limit, "target_key": st.session_state.target_key}
        supabase.table("user_incomes").upsert({"user_id": uid, "income_data": data}).execute()
        st.sidebar.success("クラウドに保存完了！")
    if st.sidebar.button("🚪 ログアウト", use_container_width=True):
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()
else:
    try:
        auth_res = supabase.auth.sign_in_with_oauth({"provider": "google"})
        st.sidebar.markdown(f'<a href="{auth_res.url}" target="_top" style="text-decoration:none;"><div style="background-color:#FF4B4B;color:white;padding:0.6rem;border-radius:8px;text-align:center;font-weight:600;">🌐 Googleでログイン</div></a>', unsafe_allow_html=True)
    except:
        st.sidebar.error("認証準備中...")

st.sidebar.divider()
st.sidebar.header("💛 開発を応援")
support_url = "https://buymeacoffee.com/isseiotsuka" 
st.sidebar.markdown(f'<a href="{support_url}" target="_blank" style="text-decoration:none;"><div style="background-color:#FFDD00;color:black;padding:0.5rem;border-radius:5px;text-align:center;font-weight:bold;">☕ コーヒーをおごる</div></a>', unsafe_allow_html=True)

# --- 9. A. 診断モード ---
if st.session_state.step == "diagnosis":
    st.title("🛡️ あなたの「壁」を診断")
    with st.form("survey"):
        st.write("生年月日を入力してください")
        col_y, col_m, col_d = st.columns(3)
        with col_y: sel_year = st.selectbox("年", range(1960, YEAR + 1), index=YEAR-1960-21)
        with col_m: sel_month = st.selectbox("月", range(1, 13), index=3)
        with col_d: sel_day = st.selectbox("日", range(1, 32), index=0)
        job = st.radio("現在の状況", ["大学生", "高校生", "主婦・主夫", "その他"])
        supporter = st.radio("誰の扶養ですか？", ["親", "配偶者", "なし"])
        if st.form_submit_button("診断を開始"):
            tax_age = YEAR - sel_year
            # 社会保険（106万の壁）：学生は原則対象外（資料2枚目の注釈反映）
            if job in ["大学生", "高校生"]:
                st.session_state.shaho_limit = 1300000
                if 19 <= tax_age <= 22 and supporter == "親": st.session_state.user_category = "特定学生"
                else: st.session_state.user_category = "一般学生"
            else:
                st.session_state.shaho_limit = 1060000
                st.session_state.user_category = "一般（パート・アルバイト）"
            
            if supporter == "なし": st.session_state.target_key = "178万：自分の所得税を0円にする（令和8年特例）"
            else: st.session_state.target_key = "136万：親や配偶者の税金を増やさない"
            st.session_state.step = "calculation"
            st.rerun()

# --- 10. B. 計算モード ---
else:
    st.title("💰 2026年 年収シミュレーター")
    st.success(f"👤 診断結果： **【 {st.session_state.user_category} 】**")
    tab1, tab2 = st.tabs(["⚡ クイック判定", "📅 月別詳細"])
    with tab1:
        st.header("今年の想定年収を入力")
        est = st.number_input("想定年収", value=1000000, step=10000)
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🏛️ 住民税 (目安)")
            if est > jumin_limit_base: st.error("❌ **均等割:** 発生見込み")
            else: st.success("✅ **均等割:** 非課税目安")
            if est > jumin_limit_base + 50000: st.error("❌ **所得割:** 発生可能性高")
            else: st.warning("⚠️ **所得割:** 自治体により変動")
            st.subheader("⚖️ 所得税 (確定)")
            if est > 1780000: st.error("❌ **所得税:** 発生")
            else: st.success("✅ **所得税:** 0円 (特例)")
        with c2:
            st.subheader("🏥 社会保険")
            if est >= st.session_state.shaho_limit: st.error(f"❌ **社会保険:** 扶養外 ({st.session_state.shaho_limit/10000:.0f}万超)")
            else: st.success("✅ **社会保険:** 扶養内")
            st.caption("※2026年10月に賃金要件(8.8万)撤廃予定。学生は原則対象外。")
            st.subheader("👨‍👩‍👧 扶養の壁 (確定)")
            if est > 1360000: st.error("❌ **サポーター:** 増税リスクあり")
            else: st.success("✅ **サポーター:** 影響なし")
    with tab2:
        # インデント修正済み
        target_options = list(WALL_DETAILS.keys())
        current_target = st.session_state.get('target_key', target_options[2])
        default_index = target_options.index(current_target) if current_target in target_options else 2
        selected_key = st.selectbox("設定した上限額", target_options, index=default_index)
        st.session_state.target_key = selected_key
        final_target = WALL_DETAILS[selected_key]
        avg_limit = final_target / 12
        st.header("📅 毎月の給与を入力")
        st.info(f"💡 **月々の目安上限額:** {avg_limit:,.0f} 円")
        incomes = []
        for row in range(4):
            cols = st.columns(3)
            for col in range(3):
                m_idx = row * 3 + col + 1
                with cols[col]:
                    val = st.session_state.get(f"m{m_idx}", 0)
                    st.number_input(f"{m_idx}月", key=f"m{m_idx}", value=val, min_value=0, step=1000)
                    v_upd = st.session_state.get(f"m{m_idx}", 0)
                    incomes.append(v_upd)
                    if v_upd > avg_limit: st.markdown("<span style='color:#ff4b4b'>● 超過</span>", unsafe_allow_html=True)
                    elif v_upd > 0: st.markdown("<span style='color:#24df3b'>● 安全</span>", unsafe_allow_html=True)
        st.divider()
        st.subheader("📊 分析結果")
        c_m1, c_m2 = st.columns(2)
        c_m1.metric("現在の合計年収", f"{sum(incomes):,} 円")
        c_m2.metric("上限まで残り", f"{final_target - sum(incomes):,} 円", delta=-sum(incomes), delta_color="inverse")
        st.progress(min(sum(incomes)/final_target, 1.0))

# --- 11. SEO・解説セクション ---
st.divider()
st.header("🔍 2026年度版：知っておきたい「年収の壁」徹底解説")
st.markdown("""
### 厚生労働省資料による最新の社会保険改正
1. **社会保険の企業規模要件の撤廃**: 改正法により、これまで従業員51人以上の企業に限られていた社会保険加入義務が拡大されます。
2. **「106万円の壁」の撤廃時期**: 厚労省資料によると、2026年10月に賃金要件(月額8.8万円)が撤廃予定です。
3. **学生の特例**: 通常の学生（昼間学生）は、この社会保険の適用拡大（いわゆる106万円の壁）の対象外となります。
4. **所得税178万円・扶養136万円**: 令和8年度税制改正大綱に基づく大幅な枠拡大を反映。
---
*※本ツールは最新の公的資料（厚労省、首相官邸、財務省大綱）に基づき作成されています。*
""")
