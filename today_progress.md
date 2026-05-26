# akshare 层部署进度记录 — 2026-05-22

## 今天做了什么

1. 创建了测试云函数 `test_akshare_layer`（Python3.11），代码在 `cloudfunctions/test_akshare_layer/index.py`
2. 构建了 Linux 兼容的 akshare 本地依赖目录 `cloudfunctions/layer_build/python/`（包含 akshare + pandas + numpy + lxml 等全部依赖）
3. 打包并上传到云存储：`akshare-layer-v2.zip`（45MB），存储地址 `7079-python12-9guk780v324f024d-1304734787.tcb.qcloud.la`
4. 已验证 akshare 层 v1 可绑定到函数，但调用时报 `ModuleNotFoundError: No module named 'akshare'`

## 当前状态

| 项目 | 状态 |
|------|------|
| 函数 `test_akshare_layer` | ✅ Python3.11，正常运行 |
| 层 `akshare` v1 | ✅ Active，Python3.11，已绑定到函数但模块找不到 |
| 层 `test-layer` v1 | ✅ 测试用，173 字节 |
| 本地 `layer_build/python/` | ✅ Linux 兼容的完整依赖 |
| 云存储 `akshare-layer-v2.zip` | ✅ 45MB 已上传 |
| 代码 `index.py` | ✅ 测试逻辑完整 |

## 根因找到

**旧 zip（akshare-layer-v2-py.zip）没有 `python/` 根目录**，所有文件散落在 zip 顶层。
SCF 层要求 zip 内必须有 `python/` 目录，解压后才映射到 `/opt/python/` 加入 sys.path。
之前绑定到函数找不到模块就是这个原因。

## 已准备好的正确文件

✅ `cloudfunctions/layer_build/akshare-layer-py311.zip`
- 结构正确：`python/akshare/`, `python/numpy/`, `python/pandas/` ...
- 4907 个文件，47.9 MB
- Linux 兼容（已替换 Windows .dll/.pyd 为 .so）

## 明天操作

打开控制台手工上传：
https://console.cloud.tencent.com/tcb/scf/layer?envId=python12-9guk780v324f024d
→ 选 akshare 层 → 创建新版本 → 上传 `akshare-layer-py311.zip` → 选运行时 Python3.11

上传后在 CLI：
```bash
tcb fn layer unbind test_akshare_layer --layer akshare
tcb fn layer bind test_akshare_layer --layer akshare --layer-version 2
tcb fn invoke test_akshare_layer
```

## 关键文件

---

# 飞书机器人菜单回调集成 — 2026-05-25

## 今天做了什么

1. 创建云函数 `mootdx-test`（Python3.10），绑定 `mootdx310` 层
2. 实现飞书事件回调处理，支持：
   - **URL验证**：识别 `type=url_verification` 并返回 challenge
   - **菜单点击事件**：接收 `application.bot.menu_v6` 事件
   - **mootdx行情查询**：点击 `test` 菜单获取 `113678` 当日行情
3. 配置HTTP触发器路径：`/test`
4. 验证通过：飞书URL验证 ✅，菜单点击回调 ✅，行情数据已成功返回

## 云函数配置

| 项目 | 值 |
|------|-----|
| 函数名 | `mootdx-test` |
| 运行时 | Python3.10 |
| Handler | `index.main` |
| 超时 | 60s |
| 绑定层 | `mootdx310:1` |
| HTTP触发器URL | `https://python12-9guk780v324f024d-1304734787.ap-shanghai.app.tcloudbase.com/test` |

## 飞书配置

1. 飞书开放平台 → 应用 → 事件订阅
2. 订阅方式：**发送回调到开发者服务器**
3. 请求地址：`https://python12-9guk780v324f024d-1304734787.ap-shanghai.app.tcloudbase.com/test`
4. 添加事件：`application.bot.menu_v6`（机器人菜单点击）
5. 机器人菜单配置：`event_key` 设为 `test`

## 代码要点

### URL验证处理（飞书发POST不是GET）

```python
if body.get('type') == 'url_verification':
    challenge = body.get('challenge', '')
    return {'challenge': challenge}
```

### 菜单事件处理

```python
if event_type == 'application.bot.menu_v6':
    return handle_bot_menu(event_data)
```

### 腾讯云函数事件格式

```python
http_method = event.get('httpMethod', 'GET')
body = event.get('body', '{}')
query_string = event.get('queryString', event.get('queryStringParameters', ''))
```

## 注意事项

1. **飞书URL验证是POST不是GET**：飞书发送POST请求带 `{"type":"url_verification","challenge":"..."}`，需要解析body中的type字段
2. **Handler名称必须匹配**：创建云函数时默认Handler可能是 `index.main`，如果代码入口函数名不同需同步修改
3. **腾讯云函数API网关路由**：`/test` 路径是用户手动配置的HTTP触发器，需要将域名和函数关联
4. **层绑定用CLI**：`tcb fn layer bind <function> --layer <name> --layer-version <n>`
5. **冷启动时间**：Python云函数冷启动约2.7s，但飞书要求URL验证在1s内响应，实测1ms即可返回，但总超时要考虑

## 踩过的坑

| 问题 | 原因 | 解决 |
|------|------|------|
| `handler not found` | Handler配置为 `index.main_handler`，但系统默认用 `index.main` | 统一函数名为 `main` |
| Challenge code没有返回 | 以为URL验证是GET请求传query参数，实际是POST传JSON body | 检查 `type=url_verification` 再返回challenge |
| `{"status": "ok", "event_type": ""}` | POST请求走了回调分支，未识别验证请求 | 添加 `url_verification` 判断优先于事件分发 |

## 当前状态

| 项目 | 状态 |
|------|------|
| 云函数 `mootdx-test` | ✅ Python3.10，正常运行 |
| 层 `mootdx310` 绑定 | ✅ 已绑定到函数 |
| HTTP触发器 `/test` | ✅ 公网可访问 |
| 飞书URL验证 | ✅ 通过 |
| 飞书菜单回调 | ✅ `test` 菜单点击 → 获取113678行情数据成功 |
| mootdx行情查询 | ✅ 返回最新价173.96，成交量250651，成交额4.45亿 |

```
cloudfunctions/
├── test_akshare_layer/
│   ├── index.py           # 测试函数
│   ├── requirements.txt   # akshare>=1.16.72
│   └── func.zip
├── layer_build/
│   ├── python/            # Linux 兼容的依赖目录
│   ├── akshare-layer-v2-py.zip   # 压缩包
│   ├── akshare-layer-v2.zip      # 同上
│   └── publish_layer.py  # SCF API 创建层脚本
└── Dockerfile
cloudbaserc.json           # 环境: python12-9guk780v324f024d
```

---

# PyMySQL 层部署实战 — 2026-05-26

## 背景

`cb_volume_filter` 云函数需要 `pymysql` 连接 MySQL 数据库。通过层方式管理依赖，实现依赖复用和代码分离。

## 部署过程

1. **代码适配层路径**：`index.py` 中使用 `sys.path.insert(0, '/opt/python')` 引入层中的模块
2. **构建 zip 包**：用 Python `zipfile` 模块打包，确保内部结构为 `python/pymysql/...`
3. **手动上传到控制台**：CloudBase 控制台 → 云函数 → 层管理 → pymysql → 新建版本
4. **绑定到函数**：`tcb fn layer bind cb_volume_filter --layer pymysql --layer-version 4`
5. **手动触发验证**：`tcb fn invoke cb_volume_filter` → 成功筛选 12 只转债并推送飞书

## zip 包构建（正确做法）

```python
import os, shutil, zipfile, subprocess

base = 'tmp_layer'
python_dir = os.path.join(base, 'python')
out_zip = 'pymysql-layer.zip'

os.makedirs(python_dir)
subprocess.run(['pip', 'install', 'pymysql==1.1.1', '-t', python_dir, '--no-compile', '--no-deps'], check=True)

# 删除无用文件
for root, dirs, files in os.walk(python_dir, topdown=False):
    for d in dirs:
        if d == '__pycache__' or d.endswith('.dist-info'):
            shutil.rmtree(os.path.join(root, d))

# 用 Python zipfile，不要用 PowerShell Compress-Archive
with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(python_dir):
        for f in files:
            full_path = os.path.join(root, f)
            arcname = os.path.relpath(full_path, base)
            zf.write(full_path, arcname)
```

## 部署要点

| 要点 | 说明 |
|------|------|
| zip 根目录必须是 `python/` | SCF 解压后映射到 `/opt/python/`，代码里 `sys.path.insert(0, '/opt/python')` |
| 用 Python `zipfile` 打包 | **不要用** PowerShell `Compress-Archive`，产生的 zip 可能不兼容云平台 |
| `--no-compile` | 不生成 `.pyc` 缓存文件，减少包体积，避免运行时兼容问题 |
| 删除 `.dist-info` | pip 元数据目录可删除，不影响运行 |
| 层绑定后等几秒 | 绑定操作是异步的，等函数状态变为 `Active` 再触发 |
| 先解绑再删除重建 | 如果绑定失败导致 `UpdateFailed`，先 `unbind` 所有层再操作 |

## 踩过的坑

| 问题 | 原因 | 解决 |
|------|------|------|
| `No module named 'pymysql'` | 初始未使用层，云端未安装依赖 | 创建 pymysql 层并绑定 |
| `InternalError` 绑定层失败 | 旧 zip 用 PowerShell `Compress-Archive` 打包，云平台不兼容 | 改用 Python `zipfile` 模块重新打包 |
| 函数反复 `UpdateFailed` | 绑定有问题的层后函数进入错误状态 | 先解绑所有层 → 删除函数 → 重建 → 用正确 zip 重新绑定 |
| mootdx310 层可以绑定、pymysql 不行 | 不是绑定机制问题，而是 pymysql 层的 zip 格式有问题 | 确认是 zip 打包工具导致的不兼容 |
| CLI 返回 `InternalError`，无法定位原因 | 腾讯云内部错误信息不明确 | 对比测试（绑定 mootdx310 成功 → 确认是 pymysql 层 zip 问题） |

## cloudbaserc.json 层配置

```json
{
  "envId": "python12-9guk780v324f024d",
  "functionRoot": "cloudfunctions",
  "functions": [
    {
      "name": "cb_volume_filter",
      "timeout": 300,
      "memorySize": 512,
      "runtime": "Python3.10",
      "layers": [
        { "name": "pymysql", "version": 4 }
      ]
    }
  ]
}
```

## CLI 常用命令

```bash
tcb fn layer list                          # 查看层列表
tcb fn layer bind <fn> --layer <name> --layer-version <n>   # 绑定层
tcb fn layer unbind <fn> --layer <name>    # 解绑层
tcb fn detail <fn>                         # 查看函数详情（含层绑定状态）
tcb fn invoke <fn>                         # 手动触发函数
```