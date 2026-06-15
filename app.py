import streamlit as st
import pdfplumber
import pandas as pd
import re
import plotly.express as px
import os

st.set_page_config(page_title="陸上部 記録管理アプリ", layout="wide")

# ==========================================
# 🔒 セキュリティ設定（パスワード機能）
# ==========================================
# 【ここを好きなパスワードに変えてください！】
# 半角の英数字や記号で、推測されにくいものを設定してください。
CORRECT_PASSWORD = "genyo2018" 

# パスワード認証のチェック
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 ログインが必要です")
    user_password = st.text_input("パスワードを入力してください", type="password")
    if st.button("ログイン"):
        if user_password == CORRECT_PASSWORD:
            st.session_state.authenticated = True
            st.success("ログインに成功しました！")
            st.rerun()
        else:
            st.error("パスワードが違います。")
    st.stop() # パスワードが違う場合は、ここでプログラムを強制ストップ（下の画面を見せない）
# ==========================================

# --- ここから下はログイン成功時のみ実行される ---
st.title("🏃‍♂️ 陸上競技部 記録管理・推移アプリ")
st.write("大会の結果PDFを読み込ませて、自校の生徒の記録を自動で抽出し、個人ページを作成します。")

# --- サイドバーで学校名を設定 ---
target_school = st.sidebar.text_input("抽出する学校名を入力してください", value="玄洋中")

# --- データの保存・読み込みの仕組み ---
DB_FILE = "rikujo_saved_database.csv"

if os.path.exists(DB_FILE):
    try:
        st.session_state.all_data = pd.read_csv(DB_FILE)
    except:
        st.session_state.all_data = pd.DataFrame(columns=["日付", "大会名", "種目", "氏名", "学年/年齢", "所属", "記録"])
else:
    if "all_data" not in st.session_state:
        st.session_state.all_data = pd.DataFrame(columns=["日付", "大会名", "種目", "氏名", "学年/年齢", "所属", "記録"])

# --- PDFアップロードエリア ---
st.header("1. 大会リザルトPDFの読込")
col1, col2 = st.columns(2)

with col1:
    uploaded_file = st.file_uploader("大会の結果PDFファイルをアップロードしてください", type=["pdf"])
with col2:
    meet_name = st.text_input("大会名を入力してください", value="春季記録会")
    meet_date = st.date_input("大会の日付を選択してください")

if uploaded_file is not None and st.button("PDFからデータを抽出して蓄積する"):
    with st.spinner("PDFを解析中..."):
        extracted_rows = []
        current_event = "不明な種目"
        
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                lines = text.split("\n")
                for line in lines:
                    line_str = line.strip()
                    
                    if "中学" in line_str and ("m" in line_str or "跳" in line_str or "投" in line_str or "リレー" in line_str or "H" in line_str or "競技" in line_str):
                        current_event = line_str
                        continue
                    
                    if target_school in line_str:
                        pattern = r'([^\d\s\(\)]+\s*[^\d\s\(\)]*)\s*[（\(](\d+)[）\)]\s*([\w・]*' + target_school + r'[\w・]*)\s+([\d\:\.\-\s]*\d+m?\d*)'
                        matches = re.findall(pattern, line_str)
                        
                        for match in matches:
                            name = match[0].strip()
                            name = re.sub(r'^[A-Za-z\d\s]+', '', name).strip()
                            grade = match[1].strip()
                            school = match[2].strip()
                            score = match[3].strip()
                            
                            score = re.sub(r'\(.*?\)', '', score).strip()
                            score_match = re.search(r'^(\d+[\:\.]\d+|\d+m\d+|\d+\.\d+|\d+)', score)
                            if score_match:
                                score = score_match.group(1)
                            
                            extracted_rows.append({
                                "日付": str(meet_date),
                                "大会名": meet_name,
                                "種目": current_event,
                                "氏名": name,
                                "学年/年齢": grade,
                                "所属",: school,
                                "記録": score
                            })
        
        if extracted_rows:
            new_df = pd.DataFrame(extracted_rows)
            st.session_state.all_data = pd.concat([st.session_state.all_data, new_df], ignore_index=True).drop_duplicates()
            st.session_state.all_data.to_csv(DB_FILE, index=False, encoding="utf-8-sig")
            st.success(f"成功！{target_school}の生徒を {len(new_df)} 件抽出してデータベースに保存しました！")
            st.rerun()
        else:
            st.warning(f"指定された学校（{target_school}）の生徒が見つかりませんでした。")

# --- データが集まった後の処理 ---
df_saved = st.session_state.all_data

if not df_saved.empty:
    st.header("2. 選手ごとの個人ページ・記録推移")
    
    students = df_saved["氏名"].unique()
    selected_student = st.selectbox("選手を選択してください", students)
    
    st.subheader(f"📊 {selected_student} 選手の専用ダッシュボード")
    
    student_df = df_saved[df_saved["氏名"] == selected_student]
    
    events = student_df["種目"].unique()
    tabs = st.tabs(list(events))
    
    for i, event in enumerate(events):
        with tabs[i]:
            event_df = student_df[student_df["種目"] == event].sort_values(by="日付")
            is_field = "跳" in event or "投" in event
            
            def to_num(val):
                try:
                    if ":" in str(val):
                        parts = str(val).split(":")
                        return float(parts[0]) * 60 + float(parts[1])
                    return float(str(val).replace("m", ""))
                except:
                    return 999999 if not is_field else -1

            event_df["_num_score"] = event_df["記録"].apply(to_num)
            
            if is_field:
                pb_row = event_df.loc[event_df["_num_score"].idxmax()]
                current_year = event_df["日付"].str[:4].max()
                year_df = event_df[event_df["日付"].str.startswith(current_year)]
                sb_row = year_df.loc[year_df["_num_score"].idxmax()]
            else:
                pb_row = event_df.loc[event_df["_num_score"].idxmin()]
                current_year = event_df["日付"].str[:4].max()
                year_df = event_df[event_df["日付"].str.startswith(current_year)]
                sb_row = year_df.loc[year_df["_num_score"].idxmin()]
            
            b_col1, b_col2 = st.columns(2)
            with b_col1:
                st.metric(label="🏆 自己ベスト (PB)", value=pb_row["記録"], delta=f"({pb_row['大会名']})", delta_color="off")
            with b_col2:
                st.metric(label="✨ シーズンベスト (SB)", value=sb_row["記録"], delta=f"({sb_row['大会名']})", delta_color="off")
            
            st.write("---")
            st.write(f"**【出場履歴と記録一覧】**")
            st.dataframe(event_df[["日付", "大会名", "記録"]], use_container_width=True)
            
            fig = px.line(event_df, x="日付", y="記録", hover_data=["大会名"], title=f"{event} 記録推移", markers=True)
            if not is_field:
                fig.update_yaxes(autorange="reversed")
                
            st.plotly_chart(fig, use_container_width=True)
            
    st.write("---")
    with st.expander("🛠️ 蓄積された全データベースの確認・削除"):
        st.dataframe(df_saved)
        col_dl, col_del = st.columns(2)
        with col_dl:
            csv = df_saved.to_csv(index=False).encode('utf-8-sig')
            st.download_button("Excel用CSVとしてダウンロード", data=csv, file_name="rikujo_database.csv", mime="text/csv")
        with col_del:
            if st.button("🚨 データベースを完全に初期化（全消去）する"):
                if os.path.exists(DB_FILE):
                    os.remove(DB_FILE)
                st.session_state.all_data = pd.DataFrame(columns=["日付", "大会名", "種目", "氏名", "学年/年齢", "所属", "記録"])
                st.success("データをすべて消去しました。")
                st.rerun()
