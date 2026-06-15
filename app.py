import streamlit as st
import pdfplumber
import pandas as pd
import re
import plotly.express as px

st.set_page_config(page_title="陸上部 記録管理アプリ", layout="wide")

st.title("🏃‍♂️ 陸上競技部 記録管理・推移アプリ")
st.write("大会の結果PDFを読み込ませて、自校の生徒の記録を自動で抽出し、個人ページを作成します。")

# --- サイドバーで学校名を設定 ---
target_school = st.sidebar.text_input("抽出する学校名を入力してください", value="玄洋中")

# データの保存状態を管理（セッション状態の初期化）
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
                    
                    # 1. 種目名の取得
                    if "中学" in line_str and ("m" in line_str or "跳" in line_str or "投" in line_str or "リレー" in line_str or "H" in line_str or "競技" in line_str):
                        current_event = line_str
                        continue
                    
                    # 2. 指定した学校名が含まれている場合の処理（超強力版に改良）
                    if target_school in line_str:
                        # 横一列に並んだ塊を「学校名」を基準に分割して探す
                        # 例: "... 田浦 晴大(13) 玄洋中 13.97 5 5 D366 藤田 一颯(13) ..." 
                        # 学校名の前後にある名前と記録を柔軟に狙い撃ちします
                        pattern = r'([^\d\s\(\)]+\s*[^\d\s\(\)]*)\s*[（\(](\d+)[）\)]\s*([\w・]*' + target_school + r'[\w・]*)\s+([\d\:\.\-\s]*\d+m?\d*)'
                        matches = re.findall(pattern, line_str)
                        
                        for match in matches:
                            name = match[0].strip()
                            # 名字と名前の間にゴミ（数字など）が残っていたら綺麗にする
                            name = re.sub(r'^[A-Za-z\d\s]+', '', name).strip()
                            
                            grade = match[1].strip()
                            school = match[2].strip()
                            score = match[3].strip()
                            
                            # 風向(0.0)やリレー順などのカッコ文字を排除
                            score = re.sub(r'\(.*?\)', '', score).strip()
                            # 後ろに続く他校の順位などの数字の巻き込みを防ぐ（最初のタイムっぽい部分だけ抜く）
                            score_match = re.search(r'^(\d+[\:\.]\d+|\d+m\d+|\d+\.\d+|\d+)', score)
                            if score_match:
                                score = score_match.group(1)
                            
                            extracted_rows.append({
                                "日付": str(meet_date),
                                "大会名": meet_name,
                                "種目": current_event,
                                "氏名": name,
                                "学年/年齢": grade,
                                "所属": school,
                                "記録": score
                            })
        
        if extracted_rows:
            new_df = pd.DataFrame(extracted_rows)
            # 既存のデータと結合
            st.session_state.all_data = pd.concat([st.session_state.all_data, new_df], ignore_index=True).drop_duplicates()
            st.success(f"成功！{target_school}の生徒を {len(new_df)} 件抽出しました！")
        else:
            st.warning(f"指定された学校（{target_school}）の生徒が見つかりませんでした。PDFの形式が特殊な可能性があります。")

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
            st.write(f"**【出場履歴と記録一覧】**")
            st.dataframe(event_df[["日付", "大会名", "記録"]], use_container_width=True)
            
            fig = px.line(event_df, x="日付", y="記録", hover_data=["大会名"], title=f"{event} 記録推移", markers=True)
            st.plotly_chart(fig, use_container_width=True)
            
    with st.expander("蓄積された全データを確認・ダウンロード"):
        st.dataframe(df_saved)
        csv = df_saved.to_csv(index=False).encode('utf-8-sig')
        st.download_button("Excel用CSVとしてダウンロード", data=csv, file_name="rikujo_database.csv", mime="text/csv")
