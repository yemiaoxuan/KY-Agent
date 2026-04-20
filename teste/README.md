# HTTP 接口测试脚本

这些脚本只通过 HTTP 接口测试项目，不直接调用内部 Python 函数。

## 测试前准备

先启动数据库：

```bash
cd /mnt/hdd/cjt/ky
./scripts/pg_start.sh
```

再启动 API：

```bash
cd /mnt/hdd/cjt/ky
./.venv/bin/uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

默认测试地址：

```text
http://127.0.0.1:8000
```

如果你改了地址，可以设置环境变量：

```bash
export KY_API_BASE=http://127.0.0.1:8000
export KY_API_TIMEOUT=180
```

## 单项测试

```bash
cd /mnt/hdd/cjt/ky/teste
../.venv/bin/python test_health.py
../.venv/bin/python test_topics.py
../.venv/bin/python test_reports.py
../.venv/bin/python test_uploads.py
../.venv/bin/python test_search_chat.py
```

## 一键测试

```bash
cd /mnt/hdd/cjt/ky/teste
../.venv/bin/python run_all.py
```
