import streamlit as st
from datetime import date
import pandas as pd
from supabase import create_client, Client

# --- Supabase 接続設定 ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- 🔄 データ復元用の関数 ---
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
                st.session_state.target_key = settings.get("target_key", "130万：自分の社保を免除（一般）")
            return True
    except:
        pass
    return False

# --- 🌟 ログイン処理と自動リダイレクト ---
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

# --- 1. 基礎データ定義 ---
YEAR = 2026
WALL_DETAILS = {
    "123万：家族の税金を守る": 1230000,
    "130万：自分の社保を免除（一般）": 1300000,
    "150万：自分の社保を免除（特定学生特例）": 1500000,
    "160万：自分の所得税を0円に": 1600000
}

# --- 2. セッション状態の初期化 ---
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
if 'target_key' not in st.session_state: st.session_state.target_key = "130万：自分の社保を免除（一般）"
if 'user_category' not in st.session_state: st.session_state.user_category = "一般"
if 'shaho_limit' not in st.session_state: st.session_state.shaho_limit = 1300000

# --- 3. アプリ設定（SEO強化版） ---
st.set_page_config(
    page_title="2026年 年収の壁シミュレーター | 学生・主婦の扶養内計算",
    page_icon="💰",
    layout="centered",
    initial_sidebar_state="expanded",
    # 🔽 ここにキーワードを詰め込む（隠し設定）
    menu_items={
        'Get Help': 'https://github.com/your-repo',
        'About': """
        ### 2026年度最新版：年収の壁シミュレーター
        103万、106万、130万、150万の壁を自動判定。
        住民税や所得税、社会保険料の負担をグラフで可視化します。
        """
    }
)


# --- 🔐 サイドバー ---
st.sidebar.header("⚙️ システム設定")

area_type = st.sidebar.selectbox(
    "お住まいの地域",
    ["東京・大阪など", "県庁所在地など", "その他の市町村"]
)
jumin_limit = 1100000 if "東京" in area_type else (1065000 if "県庁" in area_type else 1030000)

if st.sidebar.button("最初から診断し直す"):
    st.session_state.step = "diagnosis"
    st.rerun()

st.sidebar.divider()
st.sidebar.header("🔐 アカウント")

if user_resp and user_resp.user:
    user_meta = user_resp.user.user_metadata
    c1, c2 = st.sidebar.columns([1, 3])
    with c1:
        st.image(user_meta.get("avatar_url", ""), use_container_width=True)
    with c2:
        st.write(f"**{user_meta.get('full_name', 'ユーザー')}** さん")
    
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    st.sidebar.caption("⚠️ 終了前に必ず押してください")
    
    if st.sidebar.button("💾 データをクラウドに保存", type="primary", use_container_width=True):
        uid = user_resp.user.id
        data = {f"m{i}": st.session_state.get(f"m{i}", 0) for i in range(1, 13)}
        data["app_settings"] = {
            "user_category": st.session_state.user_category,
            "shaho_limit": st.session_state.shaho_limit,
            "target_key": st.session_state.target_key
        }
        supabase.table("user_incomes").upsert({"user_id": uid, "income_data": data}).execute()
        st.toast("クラウドに保存しました！", icon="☁️")
        st.sidebar.success("保存完了！")
    
    st.sidebar.divider()
    
    if st.sidebar.button("🚪 ログアウト", use_container_width=True):
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()
else:
    try:
        auth_res = supabase.auth.sign_in_with_oauth({"provider": "google"})
        login_url = auth_res.url
        st.sidebar.markdown(
            f'<a href="{login_url}" target="_top" style="text-decoration:none;"><div style="background-color:#FF4B4B;color:white;padding:0.6rem;border-radius:8px;text-align:center;font-weight:600;">🌐 Googleでログイン / 新規登録</div></a>',
            unsafe_allow_html=True
        )
    except:
        st.sidebar.error("準備中...")

# --- ☕ 応援ボタンエリア ---
st.sidebar.divider()
st.sidebar.header("💛 開発を応援")
support_url = "https://buymeacoffee.com/isseiotsuka" # ここを自分のURLに書き換えてね！
st.sidebar.markdown(
    f"""
    <div style="background-color: #f0f2f6; padding: 1rem; border-radius: 10px; border: 1px solid #ddd;">
        <p style="font-size: 0.8rem; color: #555; margin-bottom: 0.8rem;">学生エンジニアが運営しています。応援いただけると励みになります！</p>
        <a href="{support_url}" target="_blank" style="text-decoration: none;">
            <div style="background-color: #FFDD00; color: black; padding: 0.5rem; border-radius: 5px; text-align: center; font-weight: bold;">
                ☕ コーヒーをおごる
            </div>
        </a>
    </div>
    """,
    unsafe_allow_html=True
)

# --- A. 診断モード ---
if st.session_state.step == "diagnosis":
    st.title("🛡️ あなたの「壁」を診断")
    with st.form("survey"):
        birth_date = st.date_input("生年月日", value=date(2005, 4, 1))
        job = st.radio("現在の状況", ["大学生", "高校生", "主婦・主夫", "その他"])
        supporter = st.radio("誰の扶養ですか？", ["親", "配偶者", "なし"])
        if st.form_submit_button("診断を開始"):
            tax_age = YEAR - birth_date.year
            if 19 <= tax_age <= 22 and job == "大学生" and supporter == "親":
                st.session_state.user_category, st.session_state.shaho_limit = "特定学生", 1500000
            elif supporter == "配偶者":
                st.session_state.user_category, st.session_state.shaho_limit = "配偶者控除対象", 1300000
            else:
                st.session_state.user_category, st.session_state.shaho_limit = "一般", 1300000
            
            if supporter == "なし": st.session_state.target_key = "160万：自分の所得税を0円に"
            elif supporter == "配偶者": st.session_state.target_key = "123万：家族の税金を守る"
            else:
                if st.session_state.user_category == "特定学生": st.session_state.target_key = "150万：自分の社保を免除（特定学生特例）"
                else: st.session_state.target_key = "130万：自分の社保を免除（一般）"
            st.session_state.step = "calculation"
            st.rerun()

# --- B. 計算モード ---
else:
    st.title("💰 シミュレーター")
    st.success(f"👤 診断： **【 {st.session_state.user_category} 】**")
    
    tab1, tab2 = st.tabs(["⚡ クイック判定", "📅 月別詳細"])
    
    with tab1:
        st.header("今年の想定年収を入力")
        est = st.number_input("想定年収", value=1000000, step=10000)
        c1, c2 = st.columns(2)
        with c1:
            if est > jumin_limit: st.error(f"❌ **住民税:** 発生見込み\n({jumin_limit/10000:.1f}万超)")
            else: st.success("✅ **住民税:** 非課税")
            if est > 1600000: st.error("❌ **所得税:** 発生見込み")
            else: st.success("✅ **所得税:** 非課税")
        with c2:
            if est >= st.session_state.shaho_limit: st.error(f"❌ **社会保険:** 扶養外\n({st.session_state.shaho_limit/10000:.1f}万以上)")
            else: st.success("✅ **社会保険:** 扶養内")
            if est > 1230000: st.warning("⚠️ **扶養者の税金:** 影響あり")
            else: st.success("✅ **扶養者の税金:** 影響なし")
        
    with tab2:
        selected_key = st.selectbox("目標", list(WALL_DETAILS.keys()), index=list(WALL_DETAILS.keys()).index(st.session_state.target_key))
        st.session_state.target_key = selected_key
        final_target = WALL_DETAILS[selected_key]
        avg_limit = final_target / 12
        st.header("📅 毎月の給与を入力")
        incomes = []
        cols = st.columns(3)
        for i in range(1, 13):
            with cols[(i-1)%3]:
                val = st.session_state.get(f"m{i}", 0)
                st.number_input(f"{i}月", key=f"m{i}", value=val, min_value=0, step=1000)
                val_updated = st.session_state.get(f"m{i}", 0)
                incomes.append(val_updated)
                if val_updated > avg_limit: st.markdown("<span style='color:#ff4b4b'>● 超過</span>", unsafe_allow_html=True)
                elif val_updated > 0: st.markdown("<span style='color:#24df3b'>● 安全</span>", unsafe_allow_html=True)
        st.divider()
        st.subheader("📊 分析結果")
        c_m1, c_m2 = st.columns(2)
        c_m1.metric("現在の合計年収", f"{sum(incomes):,} 円")
        c_m2.metric("目標まであと", f"{final_target - sum(incomes):,} 円", delta=-sum(incomes), delta_color="inverse")
        st.progress(min(sum(incomes)/final_target, 1.0))

# --- 📝 SEO用：解説コンテンツエリア ---
st.divider()
st.header("🔍 2026年度版：知っておきたい「年収の壁」徹底解説")

st.markdown("""
### なぜ2026年の年収チェックが重要なのか？
**2026年**は、物価高に伴う最低賃金の上昇により、多くの方が意図せず**「年収の壁」**に直面する年と言われています。特に**学生の扶養**範囲内でのアルバイトや、主婦・主夫のパートタイム労働において、税金や社会保険料の仕組みを正しく理解しておくことは、手取り額を最大化するために不可欠です。

### 1. 「税金の壁」：所得税と住民税
* **103万円の壁（所得税）**: 自分の所得税が0円になるラインです。
* **住民税 非課税ライン**: 地域によって異なりますが、約100万〜110万円を超えると住民税が発生します。住民税の税率は2007年から一律10%で推移していますが、非課税判定は自治体ごとに異なるため、当ツールの「地域選択」を活用してください。

### 2. 「社会保険の壁」：130万円・150万円
* **130万円の壁**: 原則として、この金額を超えると親や配偶者の社会保険（健康保険・年金）から外れ、自分で保険料を納める必要が出てきます。
* **150万円の壁（特定学生特例）**: 19歳から22歳の大学生（特定扶養親族）で、一定の条件を満たす場合は社会保険の適用猶予が受けられる場合があります。

### 3. 学生が損をしないためのポイント
**学生の扶養**控除には、年齢（19歳〜22歳）による上乗せ措置があります。本人の年収が壁を超えてしまうと、本人だけでなく**親の税金が年間10万円以上増えてしまう**ケースがあるため、世帯全体でのシミュレーションが非常に重要です。

---
*※本ツールは2026年度の現行制度に基づいたシミュレーションを行っていますが、実際の税額は自治体や勤務先の条件により異なる場合があります。*
""")
