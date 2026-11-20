import json
import re
from pathlib import Path
from collections import deque

from main import ask_agent

def run_eval(cases_path=Path(__file__).with_name("eval_cases.json")):
    with open(cases_path, encoding="utf-8") as f:
        cases = json.load(f)

    passed=0
    failed_cases=[]
    runtime_errors=[]
    sessions={}
    for case in cases:
        session = case.get("session")
        history = sessions.setdefault(session, deque(maxlen=5)) if session else deque(maxlen=5)
        recent_messages = [message for turn in history for message in turn]
        print(f"\n[{case['id']}] {case['question']}")
        try:
            answer = ask_agent(case["question"],recent_messages)
        except Exception as e:
            print(f"  运行失败：{type(e).__name__}")
            runtime_errors.append(case["id"])
            continue

        if not isinstance(answer, str) or not answer.strip() or answer.strip() == "达到最大轮次，任务未完成。":
            runtime_errors.append(case["id"])
            print("  运行失败：没有获得有效回答")
            continue

        history.append((
            {"role": "user", "content": case["question"]},
            {"role": "assistant", "content": answer},
        ))

        # 检查必含关键词
        missing = [kw for kw in case["expect_keywords"] if kw not in answer]
        # 检查禁止词
        forbidden = [kw for kw in case.get("expect_absent", []) if kw in answer]

        pattern = case.get("expect_pattern")
        pattern_ok = pattern is None or re.search(pattern, answer) is not None
        ok = not missing and not forbidden and pattern_ok
        if ok:
            passed += 1
            print(f"  ✅ 通过")
        else:
            failed_cases.append(case["id"])
            print(f"  ❌ 失败")
            if missing:
                print(f"     缺少关键词：{missing}")
            if forbidden:
                print(f"     出现禁止词：{forbidden}")
            if not pattern_ok:
                print(f"     数值、单位或月份不匹配：{pattern}")
        print(f"  回答：{answer[:120]}...")

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