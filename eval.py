import json
import re
from pathlib import Path
from collections import deque

from main import ask_agent

# 执行 JSON 题库，统计回答不符与运行失败的题号。
def run_eval(cases_path=Path(__file__).with_name("eval_cases.json")):
    with open(cases_path, encoding="utf-8") as f:
        cases = json.load(f)

    passed=0
    failed_cases=[]
    runtime_errors=[]
    sessions={}
    for case in cases:
                # 相同 session 共享对话；普通单轮题使用独立的空历史。
        session = case.get("session")
        history = sessions.setdefault(session, deque(maxlen=5)) if session else deque(maxlen=5)
        recent_messages = [message for turn in history for message in turn]
        print(f"\n[{case['id']}] {case['question']}")
                # 每道题独立收集本轮 SQL 结果，避免混入上一题的数据。
        query_results = []
        try:
            answer = ask_agent(
                    case["question"], recent_messages, query_results=query_results
            )
        except Exception as e:
            print(f"  运行失败：{type(e).__name__}")
            runtime_errors.append(case["id"])
            continue

                # 空回答或轮次耗尽归入运行失败，不写入评测对话历史。
        if not isinstance(answer, str) or not answer.strip() or answer.strip() == "达到最大轮次，任务未完成。":
            runtime_errors.append(case["id"])
            print("  运行失败：没有获得有效回答")
            continue

                # 多轮评测传递模型的实际回答，包括回答有误的情况。
        history.append((
            {"role": "user", "content": case["question"]},
            {"role": "assistant", "content": answer},
        ))

        # 检查必含关键词
        missing = [kw for kw in case["expect_keywords"] if kw not in answer]
        # 检查禁止词
        forbidden = [kw for kw in case.get("expect_absent", []) if kw in answer]

                # 关键词和正则都针对最终回答；正则仅在用例配置时启用。
        pattern = case.get("expect_pattern")
        pattern_ok = pattern is None or re.search(pattern, answer) is not None
                # 部分题目额外核对 SQLite 返回值，独立于中文回答判分。
        sql_error = None
        if "expected_sql_value" in case:
            expected = case["expected_sql_value"]
            column = case["expected_sql_column"]
            sql_error = "本轮没有成功的 SQL 查询结果"

                        # 从后往前找成功的查询结果，跳过工具返回的纯文本错误。
            for result in reversed(query_results):
                try:
                    data = json.loads(result)
                except json.JSONDecodeError:
                    continue  # run_sql 的错误消息是纯文本

                                # 单列直接取值；多列优先按用例指定的字段识别金额。
                rows = data["rows"]
                if data["truncated"] or len(rows) != 1:
                    sql_error = "预期 SQL 返回一行，且结果未截断"
                    break

                row = rows[0]
                if len(row) == 1:
                    actual = next(iter(row.values()))
                elif column in row:
                    actual = row[column]
                elif "total_amount" in row:
                    actual = row["total_amount"]
                else:
                    sql_error = f"找不到金额列，实际列：{list(row)}"
                    break

                if actual == expected:
                    sql_error = None
                else:
                    sql_error = f"SQL 结果不符：预期 {expected}，实际 {actual}"
                break

                # 所有启用的检查都通过才计为通过，并输出失败原因。
        ok = not missing and not forbidden and pattern_ok and sql_error is None
        if ok:
            passed += 1
            print(f"  ✅ 通过")
        else:
            failed_cases.append(case["id"])
            print(f"  ❌ 失败")
            if sql_error is not None:
                print(f"     {sql_error}")
            if missing:
                print(f"     缺少关键词：{missing}")
            if forbidden:
                print(f"     出现禁止词：{forbidden}")
            if not pattern_ok:
                print(f"     数值、单位或月份不匹配：{pattern}")
        print(f"  回答：{answer[:120]}...")

        # 汇总整体通过率、运行失败题号和答案判分失败题号。
    total = len(cases)
    print(f"\n{'=' * 40}")
    rate = passed / total if total else 0
    print(f"通过率：{passed}/{total} = {rate:.1%}")
    if runtime_errors:
        print(f"运行失败题号：{runtime_errors}")
    if failed_cases:
        print(f"失败题号：{failed_cases}")
    return passed, total


if __name__ == "__main__":
    run_eval()