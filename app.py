# ============================================================
# app.py — 営業案件管理システム（Streamlit版）
# ============================================================
# 実行方法:
#   streamlit run app.py
#
# 必要ライブラリのインストール:
#   pip install streamlit openpyxl
# ============================================================

import streamlit as st          # WebアプリUIライブラリ
import pandas as pd             # データ加工・表示ライブラリ
import datetime                 # 日付操作（標準ライブラリ）

# 自作モジュール（同じフォルダにあるdatabase.pyを読み込む）
from database import (
    create_tables,
    CustomerDB,
    CaseDB,
    STATUS_LIST,
)

# ============================================================
# 定数定義
# ============================================================

# 業界の選択肢
INDUSTRY_LIST = [
    "製造業", "小売業", "金融業", "医療・ヘルスケア", "IT・通信",
    "建設・不動産", "教育", "物流・運輸", "食品・飲料", "その他",
]

# ステータスに対応する色（絵文字で代用）
STATUS_EMOJI = {
    "未接触":     "⚪",
    "初回商談":   "🔵",
    "課題ヒアリング": "🔷",
    "提案中":     "🟠",
    "PoC実施中":  "🟣",
    "見積提出":   "🟡",
    "契約交渉中": "🔴",
    "受注":       "🟢",
    "失注":       "⚫",
}


# ============================================================
# アプリ全体の設定
# ============================================================

# ページ設定（必ずファイルの先頭で呼び出す）
st.set_page_config(
    page_title="営業案件管理システム",
    page_icon="🏢",
    layout="wide",          # 画面を横広に使う
    initial_sidebar_state="expanded",
)

# アプリ起動時にDBテーブルを作成（なければ作る）
create_tables()


# ============================================================
# ページ別の表示関数
# ============================================================

def page_dashboard():
    """
    ダッシュボードページ
    案件の集計情報をカードとグラフで表示します
    """
    st.title("📊 ダッシュボード")
    st.caption("案件状況のサマリーです")
    st.divider()

    # DBから集計データを取得
    stats = CaseDB.get_statistics()
    total    = stats["total"]
    by_st    = stats["by_status"]
    win_rate = stats["win_rate"]

    # --- KPIカードを横に並べる ---
    # st.columns でページを分割できる
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("📁 総案件数", f"{total} 件")
    with col2:
        st.metric("🟠 提案中", f"{by_st.get('提案中', 0)} 件")
    with col3:
        st.metric("🟣 PoC実施中", f"{by_st.get('PoC実施中', 0)} 件")
    with col4:
        st.metric("🟢 受注", f"{by_st.get('受注', 0)} 件")
    with col5:
        st.metric("📈 受注率", f"{win_rate} %")

    st.divider()

    # --- ステータス別 件数グラフ ---
    st.subheader("ステータス別 案件数")

    if total == 0:
        st.info("まだ案件が登録されていません。")
    else:
        # グラフ用のデータフレームを作成
        # データフレーム = 表形式のデータ（Excelのシートのようなもの）
        chart_data = pd.DataFrame({
            "ステータス": STATUS_LIST,
            "件数": [by_st.get(s, 0) for s in STATUS_LIST],
        })
        # 件数0のステータスは除外して見やすくする
        chart_data = chart_data[chart_data["件数"] > 0]

        # 棒グラフを表示
        st.bar_chart(chart_data.set_index("ステータス"))


# ============================================================

def page_customers():
    """
    顧客管理ページ
    顧客一覧の表示・検索・登録・編集・削除ができます
    """
    st.title("👥 顧客管理")
    st.divider()

    # タブで「一覧」と「登録・編集」を切り替える
    tab_list, tab_form = st.tabs(["📋 顧客一覧", "✏️ 登録・編集"])

    # ==================
    # タブ1: 顧客一覧
    # ==================
    with tab_list:

        # 検索バー
        keyword = st.text_input("🔍 検索（会社名・担当者名・業界）", placeholder="キーワードを入力...")

        # キーワードがあれば検索、なければ全件取得
        if keyword:
            rows = CustomerDB.search(keyword)
        else:
            rows = CustomerDB.get_all()

        if not rows:
            st.info("該当する顧客がいません。")
        else:
            # sqlite3.Rowのリストをpandas DataFrameに変換して表示
            # dict(row) で辞書に変換、それをリストにしてDataFrameを作る
            df = pd.DataFrame([dict(r) for r in rows])

            # 表示する列だけ選んで、ヘッダーを日本語に変更する
            display_df = df[["id", "company_name", "industry", "contact_name", "phone", "email"]].copy()
            display_df.columns = ["ID", "会社名", "業界", "担当者名", "電話番号", "メール"]

            # テーブルとして表示（use_container_width=Trueで横幅いっぱいに広げる）
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            st.caption(f"合計 {len(rows)} 件")

        # 削除セクション（詳細な操作はフォームタブへ誘導）
        st.divider()
        st.subheader("🗑️ 顧客の削除")

        customer_names = [r['company_name'] for r in rows] if rows else []
        if customer_names:
            del_name = st.selectbox("削除する会社を選択", customer_names, key="del_customer")

            if st.button("削除する", type="secondary", key="btn_del_customer"):
                # 選択した会社のIDを取得
                target = next((r for r in rows if r['company_name'] == del_name), None)
                if target:
                    CustomerDB.delete(target['id'])
                    st.success(f"「{del_name}」を削除しました。")
                    st.rerun()  # ページを再読み込みして一覧を更新

    # ==================
    # タブ2: 登録・編集
    # ==================
    with tab_form:

        # 既存顧客の編集 or 新規登録かを選ぶ
        all_customers = CustomerDB.get_all()
        mode = st.radio("モード選択", ["✨ 新規登録", "📝 既存顧客を編集"], horizontal=True)

        # 編集モード：まず顧客を選択してフォームに読み込む
        edit_target = None
        if mode == "📝 既存顧客を編集":
            if not all_customers:
                st.warning("まだ顧客が登録されていません。")
                return
            names = [r['company_name'] for r in all_customers]
            selected_name = st.selectbox("編集する顧客を選択", names)
            edit_target = next((r for r in all_customers if r['company_name'] == selected_name), None)

        st.divider()

        # --- 入力フォーム ---
        # st.form を使うと、「送信ボタンを押したときだけ処理が走る」ようになる
        with st.form("customer_form"):
            st.subheader("顧客情報の入力")

            col_a, col_b = st.columns(2)

            with col_a:
                company_name = st.text_input(
                    "会社名 *（必須）",
                    value=edit_target['company_name'] if edit_target else "",
                )
                industry = st.selectbox(
                    "業界",
                    [""] + INDUSTRY_LIST,
                    index=([""] + INDUSTRY_LIST).index(edit_target['industry'])
                          if edit_target and edit_target['industry'] in INDUSTRY_LIST else 0,
                )
                department = st.text_input(
                    "担当部署",
                    value=edit_target['department'] if edit_target else "",
                )

            with col_b:
                contact_name = st.text_input(
                    "担当者名",
                    value=edit_target['contact_name'] if edit_target else "",
                )
                email = st.text_input(
                    "メールアドレス",
                    value=edit_target['email'] if edit_target else "",
                )
                phone = st.text_input(
                    "電話番号",
                    value=edit_target['phone'] if edit_target else "",
                )

            challenges = st.text_area(
                "顧客課題",
                value=edit_target['challenges'] if edit_target else "",
                height=80,
                placeholder="顧客が抱えている課題を記入...",
            )
            notes = st.text_area(
                "備考",
                value=edit_target['notes'] if edit_target else "",
                height=60,
            )

            # フォームの送信ボタン
            submitted = st.form_submit_button("💾 保存する", type="primary", use_container_width=True)

        # 送信ボタンが押されたときの処理
        if submitted:
            # 会社名が空の場合はエラーを出す
            if not company_name.strip():
                st.error("会社名は必須です。")
            else:
                # フォームの値を辞書にまとめる
                data = {
                    "company_name": company_name.strip(),
                    "industry":     industry,
                    "department":   department.strip(),
                    "contact_name": contact_name.strip(),
                    "email":        email.strip(),
                    "phone":        phone.strip(),
                    "challenges":   challenges.strip(),
                    "notes":        notes.strip(),
                }

                if edit_target:
                    # 更新
                    CustomerDB.update(edit_target['id'], data)
                    st.success(f"「{company_name}」の情報を更新しました！ 🎉")
                else:
                    # 新規登録
                    CustomerDB.add(data)
                    st.success(f"「{company_name}」を登録しました！ 🎉")

                st.rerun()


# ============================================================

def page_cases():
    """
    案件管理ページ
    案件一覧・フィルタリング・登録・編集・削除ができます
    """
    st.title("📋 案件管理")
    st.divider()

    tab_list, tab_form = st.tabs(["📋 案件一覧", "✏️ 登録・編集"])

    # ==================
    # タブ1: 案件一覧
    # ==================
    with tab_list:

        # ステータスでフィルタリング
        filter_status = st.selectbox(
            "ステータスで絞り込み",
            ["全件"] + STATUS_LIST,
            key="case_filter",
        )

        rows = CaseDB.get_all(status_filter=filter_status)

        if not rows:
            st.info("該当する案件がありません。")
        else:
            # 表示用データ作成
            table_data = []
            for r in rows:
                emoji = STATUS_EMOJI.get(r['status'], "")
                table_data.append({
                    "ID":         r['id'],
                    "案件名":     r['case_name'],
                    "顧客名":     r['customer_name'] or "（未設定）",
                    "ステータス": f"{emoji} {r['status']}",
                    "金額(万円)": f"{r['amount']:,}" if r['amount'] else "-",
                    "提案製品":   r['products'] or "-",
                    "開始日":     r['start_date'] or "-",
                })

            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"合計 {len(rows)} 件")

        # 削除セクション
        st.divider()
        st.subheader("🗑️ 案件の削除")

        all_cases = CaseDB.get_all()
        if all_cases:
            case_labels = [f"{r['case_name']} ({r['customer_name'] or '顧客未設定'})" for r in all_cases]
            del_label = st.selectbox("削除する案件", case_labels, key="del_case")

            if st.button("削除する", type="secondary", key="btn_del_case"):
                idx = case_labels.index(del_label)
                CaseDB.delete(all_cases[idx]['id'])
                st.success(f"削除しました。")
                st.rerun()

    # ==================
    # タブ2: 登録・編集
    # ==================
    with tab_form:

        all_cases = CaseDB.get_all()
        mode = st.radio("モード選択", ["✨ 新規登録", "📝 既存案件を編集"], horizontal=True, key="case_mode")

        edit_target = None
        if mode == "📝 既存案件を編集":
            if not all_cases:
                st.warning("まだ案件が登録されていません。")
                return
            labels = [f"{r['case_name']} ({r['customer_name'] or '顧客未設定'})" for r in all_cases]
            selected = st.selectbox("編集する案件を選択", labels, key="edit_case_sel")
            idx = labels.index(selected)
            edit_target = all_cases[idx]

        st.divider()

        # 顧客の一覧を取得（案件に顧客を紐づけるため）
        customer_map = CustomerDB.get_name_map()  # {会社名: ID}
        customer_names = ["（未設定）"] + list(customer_map.keys())

        with st.form("case_form"):
            st.subheader("案件情報の入力")

            col_a, col_b = st.columns(2)

            with col_a:
                case_name = st.text_input(
                    "案件名 *（必須）",
                    value=edit_target['case_name'] if edit_target else "",
                )

                # 顧客名のデフォルト値を設定
                default_customer = "（未設定）"
                if edit_target and edit_target['customer_name']:
                    default_customer = edit_target['customer_name']
                customer_idx = customer_names.index(default_customer) if default_customer in customer_names else 0

                selected_customer = st.selectbox(
                    "顧客名",
                    customer_names,
                    index=customer_idx,
                )

                status = st.selectbox(
                    "ステータス",
                    STATUS_LIST,
                    index=STATUS_LIST.index(edit_target['status']) if edit_target and edit_target['status'] in STATUS_LIST else 0,
                )

            with col_b:
                amount = st.number_input(
                    "案件金額（万円）",
                    min_value=0,
                    value=int(edit_target['amount']) if edit_target and edit_target['amount'] else 0,
                )
                products = st.text_input(
                    "提案製品",
                    value=edit_target['products'] if edit_target else "",
                    placeholder="例: AI図面設計支援システム",
                )
                start_date = st.date_input(
                    "開始日",
                    value=datetime.date.fromisoformat(edit_target['start_date'])
                          if edit_target and edit_target['start_date'] else datetime.date.today(),
                )

            summary = st.text_area(
                "案件概要",
                value=edit_target['summary'] if edit_target else "",
                height=80,
            )
            memo = st.text_area(
                "営業メモ",
                value=edit_target['memo'] if edit_target else "",
                height=80,
                placeholder="商談の内容・気づき・次のアクションなど...",
            )

            submitted = st.form_submit_button("💾 保存する", type="primary", use_container_width=True)

        if submitted:
            if not case_name.strip():
                st.error("案件名は必須です。")
            else:
                # 顧客IDを解決（「未設定」を選んだ場合はNone）
                customer_id = customer_map.get(selected_customer)  # Noneになる場合あり

                data = {
                    "case_name":   case_name.strip(),
                    "customer_id": customer_id,
                    "summary":     summary.strip(),
                    "amount":      int(amount),
                    "products":    products.strip(),
                    "start_date":  start_date.isoformat(),  # "YYYY-MM-DD" 形式の文字列に変換
                    "status":      status,
                    "memo":        memo.strip(),
                }

                if edit_target:
                    CaseDB.update(edit_target['id'], data)
                    st.success(f"「{case_name}」を更新しました！ 🎉")
                else:
                    CaseDB.add(data)
                    st.success(f"「{case_name}」を登録しました！ 🎉")

                st.rerun()


# ============================================================
# サイドバーナビゲーション
# ============================================================

def main():
    """
    アプリのエントリーポイント（最初に呼ばれる関数）
    サイドバーにメニューを作り、選択されたページを表示します
    """

    # サイドバー（左側のメニューエリア）の設定
    with st.sidebar:
        st.title("🏢 営業管理")
        st.caption("営業案件管理システム")
        st.divider()

        # ページ選択ラジオボタン
        page = st.radio(
            "ページを選択",
            [
                "📊 ダッシュボード",
                "👥 顧客管理",
                "📋 案件管理",
            ],
            label_visibility="collapsed",  # ラベルを非表示に
        )

        st.divider()
        st.caption(f"🗓️ {datetime.date.today().strftime('%Y年%m月%d日')}")

    # 選択されたページに対応する関数を呼び出す
    if page == "📊 ダッシュボード":
        page_dashboard()
    elif page == "👥 顧客管理":
        page_customers()
    elif page == "📋 案件管理":
        page_cases()


# ============================================================
# プログラムの起動
# ============================================================

# このファイルが直接実行されたときだけ main() を呼ぶ
# （他のファイルからimportされた場合は実行されない）
if __name__ == "__main__":
    main()
