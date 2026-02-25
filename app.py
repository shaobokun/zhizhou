from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
import sqlite3
import os
port = int(os.environ.get('PORT', 5000))
app = Flask(__name__)
app.secret_key = 'duty-management-secret-key'

# 邀请码
INVITE_CODE = '123456'

# 数据库配置
DATABASE = 'duty_system.db'

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # 以字典方式访问
    return conn

def init_db():
    """初始化数据库表"""
    if not os.path.exists(DATABASE):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE deductions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name TEXT NOT NULL,
                student_name TEXT NOT NULL,
                reason TEXT NOT NULL,
                score INTEGER NOT NULL,
                week TEXT NOT NULL,
                time TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

# 应用启动时初始化数据库
init_db()

def get_week_key():
    """获取当前周的标识键"""
    today = datetime.now()
    return f"{today.year}-W{today.isocalendar()[1]}"

def get_class_score(class_name):
    """计算班级当前周的总分"""
    week_key = get_week_key()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT SUM(score) FROM deductions 
        WHERE class_name = ? AND week = ?
    ''', (class_name, week_key))
    result = cursor.fetchone()[0]
    conn.close()
    total_deduction = result if result else 0
    return max(0, 100 - total_deduction)

def get_all_records():
    """获取所有记录，按班级分组"""
    week_key = get_week_key()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM deductions WHERE week = ? ORDER BY class_name, time
    ''', (week_key,))
    rows = cursor.fetchall()
    conn.close()
    
    class_data = {}
    for row in rows:
        cn = row['class_name']
        if cn not in class_data:
            class_data[cn] = {'records': [], 'total_score': 100}
        class_data[cn]['records'].append(dict(row))
        class_data[cn]['total_score'] = get_class_score(cn)
    return class_data

# 主页 - 邀请码输入
@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    if request.method == 'POST':
        code = request.form.get('invite_code', '').strip()
        if code == INVITE_CODE:
            session['verified'] = True
            return redirect(url_for('role'))
        error = '邀请码错误，请重新输入'
    return render_template('index.html', error=error)

# 身份选择页面
@app.route('/role')
def role():
    if not session.get('verified'):
        return redirect(url_for('index'))
    return render_template('role.html')

# 值周生 - 扣分填写
@app.route('/student', methods=['GET', 'POST'])
def student():
    if not session.get('verified'):
        return redirect(url_for('index'))
    
    success = False
    if request.method == 'POST':
        class_name = request.form.get('class_name', '').strip()
        student_name = request.form.get('student_name', '').strip()
        reason = request.form.get('reason', '').strip()
        score = request.form.get('score', '0').strip()
        
        if class_name and student_name and reason and score:
            try:
                score_val = int(score)
                if score_val > 0:
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO deductions (class_name, student_name, reason, score, week, time)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (class_name, student_name, reason, score_val, 
                          get_week_key(), datetime.now().strftime('%Y-%m-%d %H:%M')))
                    conn.commit()
                    conn.close()
                    success = True
            except ValueError:
                pass
    
    return render_template('student.html', success=success)

# 老师 - 班级查询
@app.route('/teacher', methods=['GET', 'POST'])
def teacher():
    if not session.get('verified'):
        return redirect(url_for('index'))
    
    query_class = None
    class_records = []
    class_score = 100
    
    if request.method == 'POST':
        query_class = request.form.get('query_class', '').strip()
        if query_class:
            week_key = get_week_key()
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM deductions 
                WHERE class_name = ? AND week = ?
                ORDER BY time
            ''', (query_class, week_key))
            rows = cursor.fetchall()
            conn.close()
            
            class_records = [dict(row) for row in rows]
            class_score = get_class_score(query_class)
    
    return render_template('teacher.html', 
                          query_class=query_class,
                          records=class_records, 
                          score=class_score)

# 总表查看
@app.route('/summary')
def summary():
    if not session.get('verified'):
        return redirect(url_for('index'))
    
    all_data = get_all_records()
    sorted_classes = sorted(all_data.keys())
    
    return render_template('summary.html', 
                          all_data=all_data, 
                          sorted_classes=sorted_classes)

# 退出
@app.route('/logout')
def logout():
    session.pop('verified', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
