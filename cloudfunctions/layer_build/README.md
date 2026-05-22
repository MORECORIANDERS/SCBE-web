# CloudBase SCF 自定义层（Layer）部署指南 — mootdx

> 本文档记录了在腾讯云 CloudBase SCF 上部署包含 `mootdx` (v0.11.7) 的自定义层的完整流程、关键注意点和常见坑。

## 背景

CloudBase SCF 的 Python 运行时环境预装依赖有限，无法直接 import `mootdx`。通过自定义层（Layer）将依赖挂载到 `/opt/python`，云函数即可导入使用。

mootdx 依赖 pandas、numpy、httpx 等包，需确保所有依赖均为 Linux x86_64 兼容版本。

## 最终方案

| 组件 | 详情 |
|------|------|
| 运行时 | **Python 3.10** |
| 层名称 | `mootdx310` |
| 挂载路径 | `/opt/python` |
| 层内容 | mootdx 0.11.7 + pandas + numpy + httpx + 所有 cp310 编译扩展 |
| 最终 zip | `mootdx-layer-python310.zip`（~50.7 MB） |
| 验证函数 | `mootdx-test`（Python 3.10, 256MB, 30s 超时） |

## 层 Zip 结构规范

SCF 自定义层要求 zip 内所有文件以 `python/` 为前缀：

```
mootdx-layer-python310.zip
├── python/
│   ├── mootdx/
│   ├── pandas/
│   ├── numpy/
│   ├── httpx/
│   ├── ... (所有依赖包)
│   └── *.dist-info/
```

**验证方法：**

```python
import zipfile
with zipfile.ZipFile("mootdx-layer-python310.zip", "r") as zf:
    names = zf.namelist()
    assert all(n.startswith("python/") for n in names), "结构错误！缺少 python/ 前缀"
```

## 构建步骤（Windows 环境）

### 1. 创建目录结构

```powershell
mkdir -p cloudfunctions/mootdx-layer/python
mkdir -p cloudfunctions/mootdx-layer/wheels
```

### 2. 下载 Linux 兼容的 wheel 包

在 Windows 上直接 `pip install` 会下载 Windows 版本的包，云函数运行时无法使用。必须使用 `pip download` 指定 Linux 平台：

```powershell
pip download mootdx -d cloudfunctions/mootdx-layer/wheels `
  --platform manylinux2014_x86_64 `
  --platform manylinux_2_17_x86_64 `
  --platform any `
  --python-version 310 `
  --only-binary=:all: `
  -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> **注意**：mootdx 本身是纯 Python 包（`py3-none-any`），但其依赖如 pandas、numpy 有 C 扩展，必须下载 manylinux 版本。

### 3. 解压 wheel 到 python/ 目录

```powershell
# 进入 wheels 目录，逐个解压
cd cloudfunctions/mootdx-layer/wheels
Get-ChildItem *.whl | ForEach-Object {
    python -c "import zipfile; zipfile.ZipFile('$_').extractall('../python')"
}
```

### 4. 打包为层 zip

```powershell
cd cloudfunctions/mootdx-layer
Compress-Archive -Path python -DestinationPath mootdx-layer-python310.zip -Force
```

## 云函数代码关键点

### 1. Path.home() 只读文件系统问题

mootdx 在导入时会自动执行 `config.py` 中的代码：

```python
# mootdx/config.py
CONF = get_config_path('config.json')

# mootdx/utils/__init__.py
def get_config_path(config='config.json'):
    filename = Path.home() / '.mootdx' / config
    Path(pathname).parent.mkdir(parents=True)  # 尝试创建目录
    return str(filename)
```

云函数环境中 `Path.home()` 返回 `/home/qcloud`，该目录是 **只读文件系统**，创建目录会报 `OSError: [Errno 30] Read-only file system`。

**解决方案**：在导入 mootdx 之前 monkey-patch `Path.home()` 指向 `/tmp`：

```python
import pathlib
pathlib.Path.home = classmethod(lambda cls: pathlib.Path('/tmp'))

from mootdx import quotes
```

### 2. 正确的 API 调用方式

mootdx 使用工厂模式创建行情客户端：

```python
from mootdx import quotes

# 正确方式
client = quotes.Quotes.factory(market='std')  # 沪深股票市场
# 或
client = quotes.Quotes.factory(market='ext')  # 扩展市场

# 错误方式（不存在该属性）
# client = quotes.Quotation()  # ❌
```

### 3. 资源释放

每次调用后需要关闭连接：

```python
client.client.close()
```

### 4. 完整入口模板

```python
import json
import pathlib

# 修复只读文件系统问题
pathlib.Path.home = classmethod(lambda cls: pathlib.Path('/tmp'))

from mootdx import quotes


def main_handler(event, context):
    client = None
    try:
        stock_code = '000001'
        if event and isinstance(event, dict):
            if event.get('queryStringParameters') and event['queryStringParameters'].get('code'):
                stock_code = event['queryStringParameters']['code']

        client = quotes.Quotes.factory(market='std')
        data = client.quotes(symbol=[stock_code])

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': True,
                'code': stock_code,
                'data': data.to_dict('records') if data is not None and not data.empty else None
            }, ensure_ascii=False, default=str)
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': False,
                'error': str(e)
            }, ensure_ascii=False, default=str)
        }
    finally:
        if client:
            client.client.close()
```

## 常见问题与注意事项

### 1. 层 zip 必须带 `python/` 前缀

**错误示例**：zip 内直接是 `mootdx/`, `pandas/` 等目录（无前缀）
**正确示例**：zip 内是 `python/mootdx/`, `python/pandas/` ...

SCF 将层挂载到 `/opt`，所以 `python/` 前缀对应到 `/opt/python/`。如果压缩时直接选 python 目录下的内容（而不是 python 目录本身），会导致结构错误。

### 2. CompatibleRuntimes 必须正确设置

通过 API `PublishLayerVersion` 发布层时，必须传 `CompatibleRuntimes` 参数：

```json
{
    "LayerName": "mootdx310",
    "CompatibleRuntimes": ["Python3.10", "Python3.11"],
    "Content": { ... }
}
```

不传此参数 API 会报错。控制台创建层时会自动提示选择运行时。

### 3. 不要用运行时 pip install

CloudBase SCF 运行时环境的 pip 是残缺的，缺少 `pip._internal.operations.build` 模块，无法在函数内 pip install 任何包。所有依赖必须提前打包进层。

### 4. updateFunctionCode 会重置 Handler

通过 API `UpdateFunctionCode` 更新云函数代码后，Handler 会被重置为 `index.main`，即使代码中的函数名是 `main_handler`。

**解决方法**：
- 首次创建时使用 `createFunction` 并正确设置 handler
- 避免使用 `updateFunctionCode`，改用删除重建（`deleteFunction` → `createFunction`）
- 如果必须更新，记得重新设置 handler

### 5. 同名层版本覆盖

发布同名层的新版本时旧版本不会自动删除。如果层内容有变化，记得在云函数配置中重新绑定新版本的层。

### 6. 国内镜像加速

下载 Python 包时使用清华镜像可大幅加快速度：

```powershell
-i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 7. 函数内存和时间配置

mootdx 首次调用需要连接通达信服务器并选择最快节点，建议：

| 配置 | 建议值 |
|------|--------|
| 内存 | ≥ 256 MB |
| 超时 | ≥ 30 秒（首次冷启动约 15s） |

### 8. Windows 打包与 Linux 运行时的差异

由于 Windows 和 Linux 的二进制包不兼容，不能直接在 Windows 上 `pip install` 后将 `Lib/site-packages` 打包。必须使用 `pip download --platform manylinux*` 下载 Linux 专用 wheel 包。

## 测试验证

测试函数 `mootdx-test` 已验证（通过 `InvokeFunction` API 触发）：

```python
# 验证步骤
from mootdx import quotes                      # ✅ 导入成功

client = quotes.Quotes.factory(market='std')    # ✅ 连接成功
data = client.quotes(symbol=['000001'])         # ✅ 返回实时行情
# 返回字段：code, price, open, high, low, vol, amount, bid/ask 五档

data = client.quotes(symbol=['113678'])         # ✅ 可转债行情也支持
# 113 前缀自动识别为 SH 市场
```