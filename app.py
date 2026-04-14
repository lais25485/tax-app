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

# --- 🌟 ログインから戻ってきた時の「賢い案内処理」 ---
if "code" in st.query_params:
    try:
        supabase.auth.exchange_code_for_session({"auth_code": st.query_params["code"]})
        st.query_params.clear() # URLを綺麗にする
        
        # データベースをチェックして、初めての人かリピーターか判断する！
        user_resp = supabase.auth.get_user()
        if user_resp and user_resp.user:
            uid = user_resp.user.id
            res = supabase.table("user_incomes").select("income_data").eq("user_id", uid).execute()
            
            if len(res.data) > 0:
                # リピーター：過去の給与と「診断結果」をすべて復元してワープ！
                saved_data = res.data[0]["income_data"]
                
                # 給与を復元
                for i in range(1, 13):
                    st.session_state[f"m{i}"] = saved_data.get(f"m{i}", 0)
                
                # 診断結果（設定）を復元
                if "app_settings" in saved_data:
                    st.session_state.user_category = saved_data["app_settings"].get("user_category", "一般")
                    st.session_state.shaho_limit = saved_data["app_settings"].get("shaho_limit", 1300000)
                    st.session_state.target_key = saved_data["app_settings"].get("target_key", "130万：自分の社保を免除（一般）")
                
                st.session_state.step = "calculation" # 計算画面へスキップ
            else:
                # 初回ユーザー：データがないので診断画面からスタート
                st.session_state.step = "diagnosis"
                
        st.rerun()
    except Exception as e:
        pass

# --- 1. 基礎データ定義 (2026年基準) ---
YEAR = 2026
WALL_DETAILS = {
    "123万：家族の税金を守る": 1230000,
    "130万：自分の社保を免除（一般）": 1300000,
    "150万：自分の社保を免除（特定学生特例）": 1500000,
    "160万：自分の所得税を0円に": 1600000
}

# --- 2. セッション状態の初期化 ---
if 'step' not in st.session_state:
    st.session_state.step = "diagnosis"
if 'target_key' not in st.session_state:
    st.session_state.target_key = "130万：自分の社保を免除（一般）"
if 'user_category' not in st.session_state:
    st.session_state.user_category = "一般"
if 'shaho_limit' not in st.session_state:
    st.session_state.shaho_limit = 1300000

# --- 3. アプリ設定 ---
st.set_page_config(page_title="2026年収の壁診断", layout="centered")

# --- 🔐 サイドバー（設定とアカウント） ---
st.sidebar.header("⚙️ システム設定")
area_type = st.sidebar.selectbox(
    "お住まいの地域（住民税の判定）",
    ["東京・大阪・名古屋などの大都市", "県庁所在地などの地方都市", "町村部・小規模な市"]
)
if "大都市" in area_type: jumin_limit = 1100000
elif "地方都市" in area_type: jumin_limit = 1065000
else: jumin_limit = 1030000

if st.sidebar.button("最初から診断し直す"):
    st.session_state.step = "diagnosis"
    st.rerun()

st.sidebar.divider()
st.sidebar.header("🔐 アカウント")

# 現在のログイン状態を確認してサイドバーの表示を切り替え
current_user = None
try:
    user_resp = supabase.auth.get_user()
    if user_resp and user_resp.user:
        current_user = user_resp.user
except:
    pass

if current_user:
    # ✅ ログイン成功時：Googleのアイコンと名前を表示
    user_meta = current_user.user_metadata
    avatar_url = user_meta.get("avatar_url", "https://www.gravatar.com/avatar/?d=mp")
    name = user_meta.get("full_name", "ユーザー")
    
    c1, c2 = st.sidebar.columns([1, 3])
    with c1:
        st.image(avatar_url, use_container_width=True)
    with c2:
        st.write(f"**{name}** さん")
        
    if st.sidebar.button("🚪 ログアウト"):
        supabase.auth.sign_out()
        st.session_state.step = "diagnosis" # ログアウトしたら最初の画面へ戻す
        st.rerun()
else:
    # ❌ 未ログイン時：いつものログインボタンを表示
    try:
        auth_res = supabase.auth.sign_in_with_oauth({"provider": "google"})
        st.sidebar.link_button("🌐 Googleでログイン / 新規登録", auth_res.url)
        st.sidebar.caption("※次回から自動でデータを引き継ぎます")
    except Exception as e:
        st.sidebar.error("ログインシステム準備中...")


# --- A. 診断モード ---
if st.session_state.step == "diagnosis":
    st.title("🛡️ あなたの「壁」を診断しましょう")
    st.write("質問に答えて、2026年度の最新基準をセットします。")
    
    with st.form("survey"):
        birth_date = st.date_input("生年月日", value=date(1990, 1, 1), min_value=date(1940, 1, 1), max_value=date(YEAR, 12, 31))
        job = st.radio("現在の状況", ["主婦・主夫", "大学生", "高校生", "フリーター・その他"])
        supporter = st.radio("誰の扶養に入っていますか？", ["配偶者", "親", "誰の扶養でもない"])
        
        if st.form_submit_button("診断を開始"):
            tax_age = YEAR - birth_date.year
            
            if 19 <= tax_age <= 22 and job == "大学生" and supporter == "親":
                st.session_state.user_category = "特定学生（19〜22歳）"
                st.session_state.shaho_limit = 1500000
            elif supporter == "配偶者":
                st.session_state.user_category = "配偶者控除対象"
                st.session_state.shaho_limit = 1300000
            elif job in ["大学生", "高校生"]:
                st.session_state.user_category = "一般学生"
                st.session_state.shaho_limit = 1300000
            else:
                st.session_state.user_category = "一般（扶養内）"
                st.session_state.shaho_limit = 1300000

            if supporter == "誰の扶養でもない":
                st.session_state.target_key = "160万：自分の所得税を0円に"
            elif supporter == "配偶者":
                st.session_state.target_key = "123万：家族の税金を守る"
            else:
                if st.session_state.user_category == "特定学生（19〜22歳）":
                    st.session_state.target_key = "150万：自分の社保を免除（特定学生特例）"
                else:
                    st.session_state.target_key = "130万：自分の社保を免除（一般）"
            
            st.session_state.step = "calculation"
            st.rerun()

# --- B. 計算・シミュレーションモード ---
else:
    st.title("💰 年収の壁シミュレーター")
    st.success(f"👤 診断区分： **【 {st.session_state.user_category} 】**")

    tab_quick, tab_monthly = st.tabs(["⚡ サクッと年収判定", "📅 じっくり月別シミュレーション"])

    # タブ1：クイック
    with tab_quick:
        st.header("今年の想定年収を入力するだけ")
        est_income = st.number_input("あなたの想定年収 (円)", min_value=0, step=10000, value=1000000)
        
        st.subheader("📋 制度に基づく自動判定レポート")
        c1, c2 = st.columns(2)
        with c1:
            if est_income > jumin_limit:
                st.error(f"❌ **住民税:** 発生見込み\n({jumin_limit/10000:.1f}万超)")
            else:
                st.success(f"✅ **住民税:** 非課税")
            
            if est_income > 1600000:
                st.error("❌ **所得税:** 発生見込み")
            else:
                st.success("✅ **所得税:** 非課税")
        with c2:
            if est_income >= st.session_state.shaho_limit:
                st.error(f"❌ **社会保険:** 扶養外\n({st.session_state.shaho_limit/10000:.1f}万以上)")
            else:
                st.success(f"✅ **社会保険:** 扶養内")
            
            if est_income > 1230000:
                st.warning("⚠️ **扶養者の税金:** 影響あり")
            else:
                st.success("✅ **扶養者の税金:** 影響なし")

    # タブ2：月別
    with tab_monthly:
        st.header("🎯 目標ライン設定")
        selected_key = st.selectbox(
            "目標とする「壁」の選択",
            options=list(WALL_DETAILS.keys()),
            index=list(WALL_DETAILS.keys()).index(st.session_state.target_key)
        )
        final_target = WALL_DETAILS[selected_key]
        avg_limit = final_target / 12

        st.subheader("☁️ クラウド連携")
        col_load, col_save = st.columns(2)
        
        with col_save:
            if st.button("💾 入力データを保存"):
                try:
                    user_resp = supabase.auth.get_user()
                    if user_resp and user_resp.user:
                        uid = user_resp.user.id
                        
                        # 月給データと「診断設定」を1つの大きなJSONにまとめる
                        data_to_save = {f"m{i}": st.session_state.get(f"m{i}", 0) for i in range(1, 13)}
                        data_to_save["app_settings"] = {
                            "user_category": st.session_state.user_category,
                            "shaho_limit": st.session_state.shaho_limit,
                            "target_key": st.session_state.target_key
                        }
                        
                        supabase.table("user_incomes").upsert({"user_id": uid, "income_data": data_to_save}).execute()
                        st.success("クラウドに保存しました！")
                    else:
                        st.error("先にGoogleでログインしてください")
                except Exception as e:
                    st.error("ログインが必要です")

        with col_load:
            if st.button("🔄 保存データを読み込む"):
                try:
                    user_resp = supabase.auth.get_user()
                    if user_resp and user_resp.user:
                        uid = user_resp.user.id
                        res = supabase.table("user_incomes").select("income_data").eq("user_id", uid).execute()
                        if len(res.data) > 0:
                            saved_data = res.data[0]["income_data"]
                            # 給与を復元
                            for i in range(1, 13):
                                st.session_state[f"m{i}"] = saved_data.get(f"m{i}", 0)
                            # 設定を復元
                            if "app_settings" in saved_data:
                                st.session_state.user_category = saved_data["app_settings"].get("user_category", "一般")
                                st.session_state.shaho_limit = saved_data["app_settings"].get("shaho_limit", 1300000)
                                st.session_state.target_key = saved_data["app_settings"].get("target_key", "130万：自分の社保を免除（一般）")
                            st.success("データを読み込みました！画面を更新して反映します。")
                            st.rerun() # 読み込み後に画面を更新して即反映
                        else:
                            st.info("保存されたデータがありません")
                    else:
                        st.error("先にGoogleでログインしてください")
                except Exception as e:
                    st.error("ログインが必要です")

        st.header("📅 毎月の給与を入力")
        st.caption(f"目標維持の目安：月額 {avg_limit:,.0f} 円以内")
        
        incomes = []
        for r in range(4):
            cols = st.columns(3)
            for c in range(3):
                m_index = r * 3 + c + 1
                with cols[c]:
                    st.number_input(f"{m_index}月", min_value=0, step=1000, key=f"m{m_index}")
                    val = st.session_state.get(f"m{m_index}", 0)
                    incomes.append(val)
                    if val > avg_limit:
                        st.markdown("<span style='color:#ff4b4b'>● 超過</span>", unsafe_allow_html=True)
                    elif val > 0:
                        st.markdown("<span style='color:#24df3b'>● 安全</span>", unsafe_allow_html=True)

        total = sum(incomes)
        remaining = final_target - total

        st.divider()
        st.subheader("📊 分析結果")
        c_m1, c_m2 = st.columns(2)
        c_m1.metric("現在の合計年収", f"{total:,} 円")
        c_m2.metric("目標まであと", f"{remaining:,} 円", delta=-total, delta_color="inverse")
        
        st.progress(min(total / final_target, 1.0))
        
        df = pd.DataFrame({"月": [f"{i}月" for i in range(1, 13)], "収入": incomes})
        st.bar_chart(df, x="月", y="収入", color="#4db8ff")
