import json
import os
import sqlite3
from openai import OpenAI
from collections import deque
from contextlib import closing
from pathlib import Path
from openai import APIConnectionError,APIStatusError,OpenAI

# 数据库路径相对源码解析；每次查询最多展示 MAX_ROWS 条记录。
DB_PATH = Path(__file__).resolve().with_name("demo.db")
MAX_ROWS =50

# 通过 OpenAI 兼容接口调用 DeepSeek，密钥从环境变量读取。
client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],  # 或者从环境变量读取
    base_url="https://api.deepseek.com"
)  # 如果用其他服务，加 base_url="..."


# 告诉模型有哪些工具可用
# 1. 定义真正的执行函数（你原来就有，不用动）
def run_sql(sql: str) -> str:
    """执行只读 SQL，返回结果字符串。"""
        # 先检查 SQL 类型，再以 SQLite 只读模式打开数据库。
    if not sql.strip().lower().startswith("select"):
        return "错误：只允许执行 SELECT 查询。"
    try:
        with closing(sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)) as conn:
            cursor = conn.execute(sql)
            columns = [column[0] for column in cursor.description]
                        # 多读一行来判断结果是否截断，返回时按列名组织数据。
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
    # 里面是你原来的 sqlite 查询逻辑，保持不变

# 2. 把函数和它的说明书打包在一起
run_sql_tool = {
    "schema": {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": "在 sales(id, product, amount, quantity, sale_date) 表上执行 SELECT 查询。",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "一条合法的 SQLite SELECT 语句"}
                },
                "required": ["sql"]
            }
        }
    },
    "func": run_sql  # 关键点：把上面那个函数塞进来
}

# 3. 建立一个工具箱列表
AVAILABLE_TOOLS = [run_sql_tool]

# 4. 提取出说明书，待会儿要发给大模型（注意，这行放在你的 ask_agent 里面，替换掉原来的 tools）
tools_schema = [tool["schema"] for tool in AVAILABLE_TOOLS]

# ---------- Agent 循环 ----------
def ask_agent(question: str,history=(),*,query_results=None) -> str|None:
        # 每轮组合系统提示、本轮之前的对话和当前用户问题。
    messages = [
        {"role": "system", "content": (
            "你是一个数据分析助手。你可以使用 run_sql 工具查询 sales 表"
            "（字段：id, product, amount,quantity, sale_date）。"
            "先想清楚需要什么数据，再调用工具；拿到数据后用中文写一段简洁的报告。"
            "拿到空结果就直接回答“没有查到相关数据”"
            "不要编造数据。"
            "回答销售额、总金额等货币数值时，统一在数字后标明单位“元”，例如“总销售额为 2780 元"
            "当工具返回 truncated=true 时，说明结果只展示了部分记录，并询问用户是否继续查看下一页。"
            "用户请求明细时，按 id 排序分页；避免用 GROUP_CONCAT 等聚合函数拼接整表明细。"
            "回答问题时，精准回答用户所提的问题，不要列举那些没用的信息，比如问卖了什么商品时不需要给出金额，如此类比"
        )},
        *history,
        {"role": "user", "content": question}
    ]

    for _ in range(5):  # 防止死循环，最多 5 轮
        try:
                        # 让模型决定继续调用查数工具，还是直接给出中文回答。
            resp = client.chat.completions.create(
            model="deepseek-flash",  # 换成你可用的模型
            messages=messages,
            tools=tools_schema,
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
                # 逐个解析工具参数，并用调用 ID 把执行结果交回模型。
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
                                # 评测调用可收集完整结果，终端继续显示简短预览。
                if query_results is not None:
                    query_results.append(result)

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
                # 将最近的完整问答展开成 API 所需的消息列表。
        recent_messages = [
            message
            for turn in history
            for message in turn
        ]
        answer = ask_agent(q, recent_messages)
        print(f"\nAgent：{answer}")

        if answer and answer != "达到最大轮次，任务未完成。":
            history.append((
                {"role": "user", "content": q},
                {"role": "assistant", "content": answer},
            ))

            while True:
                feedback = input("\n[系统] 回答满意吗？(直接回车跳过，输入 n 记录为错题): ").strip().lower()
                if feedback == "":
                    print("[系统] 已跳过。")  # 加上这句，让你明确知道已经跳过了
                    break
                                # 记录本轮实际收到的历史，方便复现依赖前文的错例。
                elif feedback == "n":
                    record = {
                        "question": q,
                        "bad_answer": answer,
                        "history": recent_messages,
                    }
                    with open("bad_cases.log", "a", encoding="utf-8") as f:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    print("[系统] 已记录到 bad_cases.log，感谢反馈！")
                    break
                else:
                    print("[系统] 输入无效，请直接回车，或输入 n 记录。")