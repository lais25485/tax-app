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

# 🔽🔽 ここに移動（if文の前に置くことで常に表示されます） 🔽🔽
st.sidebar.header("🔐 データ保存（ログイン）")
try:
    auth_res = supabase.auth.sign_in_with_oauth({"provider": "google"})
    st.sidebar.link_button("🌐 Googleでログイン", auth_res.url)
    st.sidebar.caption("※次回から入力データを引き継げます")
except Exception as e:
    st.sidebar.error("ログインシステム準備中...")
st.sidebar.divider()
# 🔼🔼 移動ここまで 🔼🔼



# --- A. 診断モード ---
if st.session_state.step == "diagnosis":
    st.title("🛡️ あなたの「壁」を診断しましょう")
    st.write("2026年度（令和8年度）の最新税制に基づき、あなたに最適な基準をセットします。")
    
    with st.form("survey"):
        # カレンダーの範囲を1940年からに拡張
        birth_date = st.date_input(
            "生年月日", 
            value=date(1985, 1, 1),
            min_value=date(1940, 1, 1),
            max_value=date(YEAR, 12, 31)
        )
        job = st.radio("現在の状況", ["主婦・主夫", "大学生", "高校生", "フリーター・その他"])
        supporter = st.radio("誰の扶養に入っていますか？", ["配偶者", "親", "誰の扶養でもない"])
        
        if st.form_submit_button("診断を開始"):
            tax_age = YEAR - birth_date.year
            
            # ユーザー区分の判定
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

            # おすすめの壁を初期セット
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

    # サイドバー：設定
    st.sidebar.header("⚙️ 基本設定")
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

    # --- 新機能：タブで機能を分ける ---
    tab_quick, tab_monthly = st.tabs(["⚡ サクッと年収判定", "📅 じっくり月別シミュレーション"])

    # --- タブ1：クイック判定 ---
    with tab_quick:
        st.header("想定年収でリスク判定")
        est_income = st.number_input("今年の想定年収 (円)", min_value=0, step=10000, value=1000000)
        
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

    # --- タブ2：月別シミュレーション ---
    with tab_monthly:
        st.header("🎯 目標ライン設定")
        selected_key = st.selectbox(
            "目標とする「壁」の選択",
            options=list(WALL_DETAILS.keys()),
            index=list(WALL_DETAILS.keys()).index(st.session_state.target_key)
        )
        final_target = WALL_DETAILS[selected_key]
        avg_limit = final_target / 12

        st.header("📅 毎月の給与を入力")
        st.caption(f"目標維持の目安：月額 {avg_limit:,.0f} 円以内")
        
        # スマホでの並び順修正：3列の行を4回繰り返す
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
        
        # グラフ
        df = pd.DataFrame({"月": [f"{i}月" for i in range(1, 13)], "収入": incomes})
        st.bar_chart(df, x="月", y="収入", color="#4db8ff")
