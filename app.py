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
if 'is_student' not in st.session_state:
    st.session_state.is_student = False
if 'age' not in st.session_state:
    st.session_state.age = 20
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
    st.write("質問に答えて、2026年度の最新基準をセットします。")
    
    with st.form("survey"):
        birth_date = st.date_input("生年月日", value=date(2005, 4, 1))
        job = st.radio("現在の職業", ["大学生", "高校生", "フリーター・主婦・その他"])
        supporter = st.radio("誰の扶養に入っていますか？", ["親", "配偶者", "誰の扶養でもない"])
        
        if st.form_submit_button("診断を開始"):
            tax_age = YEAR - birth_date.year
            st.session_state.age = tax_age
            st.session_state.is_student = (job == "大学生")
            
            # ユーザー区分の決定
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
                st.session_state.user_category = "一般"
                st.session_state.shaho_limit = 1300000

            # おすすめ設定の決定
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
    st.success(f"👤 あなたの診断区分： **【 {st.session_state.user_category} 】**")

  
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
        
    # --- 新機能：タブで機能を分ける ---
    tab_quick, tab_monthly = st.tabs(["⚡ サクッと年収判定", "📅 じっくり月別シミュレーション"])

    # ==========================================
    # タブ1：サクッと年収判定（新機能）
    # ==========================================
    with tab_quick:
        st.header("今年の想定年収を入力するだけ")
        est_income = st.number_input("あなたの想定年収 (円)", min_value=0, step=10000, value=1000000)
        
        st.subheader("📋 支払いの発生状況")
        
        # 4つの基準をカード風に表示
        c1, c2 = st.columns(2)
        
        with c1:
            # 1. 住民税
            if est_income > jumin_limit:
                st.error("❌ **住民税:** 発生します（約5,000円〜）")
            else:
                st.success(f"✅ **住民税:** 0円（{jumin_limit/10000:.1f}万以下）")
            
            # 2. 所得税
            if est_income > 1600000:
                st.error("❌ **所得税:** 発生します")
            else:
                st.success("✅ **所得税:** 0円（160万以下）")
                
        with c2:
            # 3. 社会保険
            if est_income >= st.session_state.shaho_limit:
                st.error(f"❌ **社会保険:** 加入義務あり（手取りが減ります）")
            else:
                st.success(f"✅ **社会保険:** 扶養内（{st.session_state.shaho_limit/10000:.1f}万未満）")
            
            # 4. 扶養者の税金
            if est_income > 1230000:
                st.warning("⚠️ **家族の税金:** 扶養者の税金が上がります")
            else:
                st.success("✅ **家族の税金:** 影響なし（123万以下）")
        
        st.info("💡 さらに詳しく月ごとのペース配分を知りたい場合は、上の「📅 じっくり月別シミュレーション」タブを押してください。")

    # ==========================================
    # タブ2：じっくり月別シミュレーション（既存機能）
    # ==========================================
    with tab_monthly:
        st.header("🎯 目標設定")
        selected_key = st.selectbox(
            "目標とする「壁」を選んでください",
            options=list(WALL_DETAILS.keys()),
            index=list(WALL_DETAILS.keys()).index(st.session_state.target_key)
        )
        final_target = WALL_DETAILS[selected_key]
        avg_limit = final_target / 12

        st.header("📅 毎月の給与を入力")
        st.caption(f"1ヶ月の目安：{avg_limit:,.0f}円以内ならセーフ")
        
        # 月別入力と色判定
        cols = st.columns(3)
        incomes = []
        for i in range(1, 13):
            with cols[(i-1)%3]:
                st.number_input(f"{i}月", min_value=0, step=1000, key=f"m{i}")
                val = st.session_state.get(f"m{i}", 0)
                incomes.append(val)
                if val > avg_limit:
                    st.markdown("<span style='color:#ff4b4b'>● 超過</span>", unsafe_allow_html=True)
                elif val > 0:
                    st.markdown("<span style='color:#24df3b'>● セーフ</span>", unsafe_allow_html=True)

        total = sum(incomes)
        remaining = final_target - total

        st.divider()
        st.subheader("⭕ 進捗メーター")
        c_m1, c_m2 = st.columns(2)
        c_m1.metric("現在の合計年収", f"{total:,} 円")
        c_m2.metric("目標まであと", f"{remaining:,} 円", delta=-total, delta_color="inverse")
        
        progress_pct = min(total / final_target, 1.0)
        st.progress(progress_pct)
        
        st.subheader("📊 月別グラフ")
        df = pd.DataFrame({"月": [f"{i}月" for i in range(1, 13)], "収入": incomes})
        st.bar_chart(df, x="月", y="収入", color="#4db8ff")
