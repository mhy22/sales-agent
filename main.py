import json
import os
import sqlite3
from openai import OpenAI
from collections import deque
from contextlib import closing
from pathlib import Path
from openai import APIConnectionError,APIStatusError,OpenAI

DB_PATH = Path(__file__).resolve().with_name("demo.db")
MAX_ROWS =50

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],  # 或者从环境变量读取
    base_url="https://api.deepseek.com"
)  # 如果用其他服务，加 base_url="..."

# ---------- 工具定义 ----------
def run_sql(sql: str) -> str:
    """执行只读 SQL，返回结果字符串。"""
    if not sql.strip().lower().startswith("select"):
        return "错误：只允许执行 SELECT 查询。"
    try:
        with closing(sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)) as conn:
            cursor = conn.execute(sql)
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchmany(MAX_ROWS + 1)

        return json.dumps(
            {
                "rows": [dict(zip(columns, row)) for row in rows[:MAX_ROWS]],
                "truncated": len(rows) > MAX_ROWS,
            },
            ensure_ascii=False,
        )

    except Exception as e:
        return f"SQL 执行出错：{e}"

# 告诉模型有哪些工具可用
tools = [{
    "type": "function",
    "function": {
        "name": "run_sql",
        "description": "在 sales(id, product, amount, quantity, sale_date) 表上执行 SELECT 查询。amount是金额，quantity是数量",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "一条合法的 SQLite SELECT 语句"}
            },
            "required": ["sql"]
        }
    }
}]

# ---------- Agent 循环 ----------
def ask_agent(question: str,history=()) -> str|None:
    messages = [
        {"role": "system", "content": (
            "你是一个数据分析助手。你可以使用 run_sql 工具查询 sales 表"
            "（字段：id, product, amount,quantity, sale_date）。"
            "先想清楚需要什么数据，再调用工具；拿到数据后用中文写一段简洁的报告。"
            "在日期条件明确且查询成功的情况下，拿到空结果就直接回答"
            "不要编造数据。"
            "当工具返回 truncated=true 时，说明结果只展示了部分记录，并询问用户是否继续查看下一页。"
            "用户请求明细时，按 id 排序分页；避免用 GROUP_CONCAT 等聚合函数拼接整表明细。"
            "回答问题时，精准回答用户所提的问题，不要列举那些没用的信息，比如问卖了什么商品时不需要给出金额，如此类比"
        )},
        *history,
        {"role": "user", "content": question}
    ]

    for _ in range(5):  # 防止死循环，最多 5 轮
        try:
            resp = client.chat.completions.create(
            model="deepseek-flash",  # 换成你可用的模型
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        except APIConnectionError:
            print("连接模型服务失败或请求超时，请检查网络后重试。")
            return None
        except APIStatusError as exc:
            if exc.status_code == 401:
                print("模型服务认证失败，请检查 API Key。")
            elif exc.status_code == 429:
                print("模型服务请求受限，请稍后重试或检查额度。")
            else:
                print(f"模型请求失败（HTTP {exc.status_code}），请检查配置或服务状态。")
            return None

        msg = resp.choices[0].message

        # 模型没有调用工具，说明它准备直接回答
        if not msg.tool_calls:
            return msg.content

        # 模型要求调用工具
        messages.append(msg)
        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments)
            except (json.JSONDecodeError, TypeError):
                args = None

            sql = args.get("sql") if isinstance(args, dict) else None

            if not isinstance(sql, str) or not sql.strip():
                result = '参数错误：请传入包含非空 "sql" 字符串的 JSON 对象。'
            else:
                print(f"  [工具调用] SQL: {sql}")
                result = run_sql(sql)

            print(f"  [工具结果] {result[:200]}")
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result,
            })

    return "达到最大轮次，任务未完成。"

# ---------- 入口 ----------
if __name__ == "__main__":
    print("数据 Agent 已启动，输入问题（输入 q 退出）")
    history = deque(maxlen=5)
    while True:
        q = input("\n你：").strip()
        if q.lower() == "q":
            break
        if not q:
            continue
        recent_messages = [
            message
            for turn in history
            for message in turn
        ]
        answer = ask_agent(q, recent_messages)
        if answer is None:
            continue
        print(f"\nAgent：{answer}")

        if answer and answer != "达到最大轮次，任务未完成。":
            history.append((
                {"role": "user", "content": q},
                {"role": "assistant", "content": answer},
            ))
