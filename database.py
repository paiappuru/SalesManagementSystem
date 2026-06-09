# ============================================================
# database.py — データベース管理モジュール
# ============================================================
# SQLite（Pythonに最初から入っているDB）を使って
# 顧客と案件のデータを保存・取得・更新・削除します
# ============================================================

import sqlite3  # データベース操作ライブラリ（インストール不要）
import os       # ファイルパス操作ライブラリ

# データベースファイルの保存場所
# このスクリプトと同じフォルダに "sales.db" を作成します
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sales.db")


def get_connection():
    """
    データベースへの接続を取得する関数
    ---
    戻り値の conn.row_factory = sqlite3.Row を設定することで、
    取得したデータを「辞書のように」column名でアクセスできるようになります
    例: row['company_name']  ← 列名でアクセス可能
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    """
    テーブルを作成する関数
    ---
    アプリ起動時に一度だけ呼び出します
    「IF NOT EXISTS」を使うので、すでにテーブルがあっても安全です
    """
    conn = get_connection()
    cursor = conn.cursor()  # SQLを実行するためのカーソル（ペンのようなもの）

    # 顧客テーブルを作成
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id           INTEGER PRIMARY KEY AUTOINCREMENT, -- 自動で採番されるID
            company_name TEXT    NOT NULL,                  -- 会社名（必須）
            industry     TEXT,                              -- 業界
            department   TEXT,                              -- 担当部署
            contact_name TEXT,                              -- 担当者名
            email        TEXT,                              -- メールアドレス
            phone        TEXT,                              -- 電話番号
            challenges   TEXT,                              -- 顧客課題
            notes        TEXT,                              -- 備考
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- 登録日時（自動）
        )
    """)

    # 案件テーブルを作成
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            case_name   TEXT    NOT NULL,                   -- 案件名（必須）
            customer_id INTEGER,                            -- 紐づく顧客のID
            summary     TEXT,                               -- 案件概要
            amount      INTEGER DEFAULT 0,                  -- 案件金額（万円）
            products    TEXT,                               -- 提案製品
            start_date  TEXT,                               -- 開始日
            status      TEXT    DEFAULT '未接触',            -- ステータス
            memo        TEXT,                               -- 営業メモ
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) -- 顧客IDと紐づける
        )
    """)

    conn.commit()  # 変更を確定（保存）
    conn.close()   # 接続を閉じる


# ============================================================
# 顧客(Customer)のCRUD操作
# CRUD = Create（作成）Read（読取）Update（更新）Delete（削除）
# ============================================================

class CustomerDB:

    @staticmethod
    def get_all():
        """全顧客を取得して返す"""
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM customers ORDER BY company_name"
        ).fetchall()
        conn.close()
        return rows

    @staticmethod
    def get_by_id(customer_id):
        """IDで顧客を1件取得"""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        conn.close()
        return row

    @staticmethod
    def search(keyword):
        """会社名・担当者名・業界でキーワード検索"""
        conn = get_connection()
        like = f"%{keyword}%"  # LIKE検索用：前後にワイルドカードをつける
        rows = conn.execute("""
            SELECT * FROM customers
            WHERE company_name LIKE ?
               OR contact_name  LIKE ?
               OR industry      LIKE ?
            ORDER BY company_name
        """, (like, like, like)).fetchall()
        conn.close()
        return rows

    @staticmethod
    def add(data: dict) -> int:
        """
        顧客を新規登録する
        引数: dataは辞書型 {'company_name': '...' , ...}
        戻り値: 新しく作成されたレコードのID
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO customers
                (company_name, industry, department, contact_name, email, phone, challenges, notes)
            VALUES
                (:company_name, :industry, :department, :contact_name, :email, :phone, :challenges, :notes)
        """, data)
        conn.commit()
        new_id = cursor.lastrowid  # 登録されたIDを取得
        conn.close()
        return new_id

    @staticmethod
    def update(customer_id: int, data: dict):
        """既存の顧客情報を更新する"""
        data['id'] = customer_id
        conn = get_connection()
        conn.execute("""
            UPDATE customers SET
                company_name = :company_name,
                industry     = :industry,
                department   = :department,
                contact_name = :contact_name,
                email        = :email,
                phone        = :phone,
                challenges   = :challenges,
                notes        = :notes
            WHERE id = :id
        """, data)
        conn.commit()
        conn.close()

    @staticmethod
    def delete(customer_id: int):
        """顧客を削除する（関連する案件は残ります）"""
        conn = get_connection()
        conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_name_map() -> dict:
        """
        {会社名: ID} の辞書を返す
        Streamlitのセレクトボックスに使います
        """
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, company_name FROM customers ORDER BY company_name"
        ).fetchall()
        conn.close()
        return {row['company_name']: row['id'] for row in rows}


# ============================================================
# 案件(Case)のCRUD操作
# ============================================================

# 案件のステータス一覧（リストで管理）
STATUS_LIST = [
    "未接触", "初回商談", "課題ヒアリング", "提案中",
    "PoC実施中", "見積提出", "契約交渉中", "受注", "失注"
]


class CaseDB:

    @staticmethod
    def get_all(status_filter: str = "全件"):
        """
        案件を取得する（ステータスで絞り込み可能）
        JOINで顧客名も一緒に取得しています
        """
        conn = get_connection()
        if status_filter == "全件":
            rows = conn.execute("""
                SELECT c.*, cu.company_name AS customer_name
                FROM   cases     c
                LEFT JOIN customers cu ON c.customer_id = cu.id
                ORDER BY c.updated_at DESC
            """).fetchall()
        else:
            rows = conn.execute("""
                SELECT c.*, cu.company_name AS customer_name
                FROM   cases     c
                LEFT JOIN customers cu ON c.customer_id = cu.id
                WHERE  c.status = ?
                ORDER BY c.updated_at DESC
            """, (status_filter,)).fetchall()
        conn.close()
        return rows

    @staticmethod
    def get_by_id(case_id: int):
        """IDで案件を1件取得"""
        conn = get_connection()
        row = conn.execute("""
            SELECT c.*, cu.company_name AS customer_name
            FROM   cases c
            LEFT JOIN customers cu ON c.customer_id = cu.id
            WHERE  c.id = ?
        """, (case_id,)).fetchone()
        conn.close()
        return row

    @staticmethod
    def add(data: dict) -> int:
        """案件を新規登録する"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cases
                (case_name, customer_id, summary, amount, products, start_date, status, memo)
            VALUES
                (:case_name, :customer_id, :summary, :amount, :products, :start_date, :status, :memo)
        """, data)
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id

    @staticmethod
    def update(case_id: int, data: dict):
        """案件を更新する"""
        data['id'] = case_id
        conn = get_connection()
        conn.execute("""
            UPDATE cases SET
                case_name   = :case_name,
                customer_id = :customer_id,
                summary     = :summary,
                amount      = :amount,
                products    = :products,
                start_date  = :start_date,
                status      = :status,
                memo        = :memo,
                updated_at  = CURRENT_TIMESTAMP
            WHERE id = :id
        """, data)
        conn.commit()
        conn.close()

    @staticmethod
    def delete(case_id: int):
        """案件を削除する"""
        conn = get_connection()
        conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_statistics() -> dict:
        """
        ダッシュボード用の集計データを返す
        戻り値の例:
        {
          'total': 10,
          'by_status': {'提案中': 3, '受注': 2, ...},
          'win_rate': 40.0
        }
        """
        conn = get_connection()

        # 総案件数
        total = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]

        # ステータス別の件数
        rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM   cases
            GROUP  BY status
        """).fetchall()
        by_status = {row['status']: row['cnt'] for row in rows}

        conn.close()

        # 受注率を計算（受注 ÷ (受注 + 失注)）
        won  = by_status.get("受注", 0)
        lost = by_status.get("失注", 0)
        win_rate = round(won / (won + lost) * 100, 1) if (won + lost) > 0 else 0.0

        return {
            "total":     total,
            "by_status": by_status,
            "win_rate":  win_rate,
        }
