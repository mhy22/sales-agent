# 销售查询 Agent

在终端用中文查询 SQLite 销售数据。程序通过 OpenAI Python SDK 调用 DeepSeek，由模型生成 SQL、调用查询工具，再根据结果回答。

## 快速开始

需要 Python 3.10 或更高版本，以及可使用当前模型的 DeepSeek API Key。下面的命令在项目根目录的 PowerShell 中执行。如果已有 `.venv`，可以跳过创建虚拟环境的命令。

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install openai
$env:DEEPSEEK_API_KEY = "替换为你的 DeepSeek API Key"
```

如果项目目录还没有 `demo.db`，在项目根目录生成样例数据库。**已有数据时请跳过这一步，初始化脚本会重建当前目录的 `demo.db`。**

```powershell
& .\.venv\Scripts\python.exe .\seed_db.py
```

在刚设置环境变量的终端启动程序：

```powershell
& .\.venv\Scripts\python.exe .\main.py
```

环境变量只在当前 PowerShell 会话及其子进程中生效。输入 `q` 退出。

## 示例问题

- 2026 年 9 月 3 日卖了什么？
- 那天的销售额是多少？
- 2026 年 9 月 6 日卖了什么？

## 查询与错误处理

- 程序只读打开与 `main.py` 同级的 `demo.db`，接受以 `SELECT` 开头的查询。每次工具调用最多返回 50 行，超过上限时会标记截断。
- 命令行保留最近 5 轮完成的问答，供连续追问使用。
- SQL 工具检查 JSON 参数和非空 `sql` 字符串。参数有误时把错误回传给模型，供它修正。
- 模型请求遇到连接失败、超时、认证失败或限流时，终端会提示并继续接收输入。这类失败不会写入对话历史。

版本改动见 [CHANGELOG.md](CHANGELOG.md)。
