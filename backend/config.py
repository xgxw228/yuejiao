import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "yuejiao.db")
SQL_PATH = os.path.join(BASE_DIR, "sql", "schema.sql")

# 内部服务令牌：Dify 的 HTTP 工具节点写操作时带这个头，
# 页面侧写操作则用登录用户的 token（见 agent_tool_api.require_service）。
INTERNAL_TOKEN = os.environ.get("YJ_INTERNAL_TOKEN", "yj-internal-demo-2026")