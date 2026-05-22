# CloudBase SCF 自定义层（Layer）部署指南 — akshare

> 本文档记录了在腾讯云 CloudBase SCF 上部署包含 `akshare` (v1.18.63) 的自定义层的完整流程、关键注意点和常见坑。

## 背景

CloudBase SCF 的 Python 运行时环境预装依赖有限，无法直接 import `akshare`。通过自定义层（Layer）将依赖挂载到 `/opt/python`，云函数即可导入使用。

## 最终方案

| 组件 | 详情 |
|------|------|
| 运行时 | **Python 3.10** |
| 层名称 | `akshare10` |
| 挂载路径 | `/opt/python` |
| 层内容 | akshare 1.18.63 + 所有 cp310 编译扩展 + pytz + py_mini_racer |
| 最终 zip | `akshare-layer-v7.zip`（57.3 MB, 5538 条目） |
| 验证函数 | `test_akshare_py310`（Python 3.10, 256MB, 60s 超时） |

## 层 Zip 结构规范

SCF 自定义层要求 zip 内所有文件以 `python/` 为前缀：

```
akshare-layer-v7.zip
├── python/
│   ├── akshare/
│   ├── numpy/
│   ├── pandas/
│   ├── pytz/
│   ├── py_mini_racer/
│   ├── ... (所有依赖包)
│   └── *.dist-info/
```

**验证方法：**

```python
import zipfile
with zipfile.ZipFile("layer.zip", "r") as zf:
    names = zf.namelist()
    assert all(n.startswith("python/") for n in names), "结构错误！缺少 python/ 前缀"
```

## 构建步骤

### 方案 A（推荐）：基于已有正确 zip 增量添加

如果有现成的结构正确的 zip（如 v5），只需要补充缺失包：

```powershell
# 1. 下载缺失的纯 Python 包
pip download pytz -d . --platform any --no-deps -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 解压到已有 python/ 目录
#（用 7-Zip 或 Python zipfile 将新包添加到原 zip 的 python/ 下）
```

### 方案 B：从零构建

```powershell
# 1. 下载所有依赖的 Linux manylinux wheel
pip download akshare==1.18.63 -d wheels/ `
  --platform manylinux2014_x86_64 `
  --platform manylinux_2_17_x86_64 `
  --platform any `
  --only-binary=:all: `
  --no-deps `
  -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 注意：jsonpath 没有 manylinux wheel，需要特殊处理
# 见下文"常见问题"
```

### 构建工具脚本

`layer_build/` 目录下保留的构建脚本：

| 脚本 | 用途 |
|------|------|
| `prepare_layer.py` | 将本地的 `python/` 目录重新打包为符合层规范的 zip |
| `extract_wheels.py` | 将下载的 wheel 文件解压到 `python/` 目录 |
| `replace_linux_wheels.py` | 用 Linux manylinux wheel 替换 python/ 目录中的 Windows 版本 |
| `check_zip_struct.py` | 批量检查 zip 文件结构是否符合预期 |
| `check_zip.py` | 检查单个 zip 文件结构 |

## 云函数代码关键点

### 必须手动添加 `/opt/python` 到 sys.path

Python 3.10 和 3.11 的 SCF 运行时 **不会自动** 将层的挂载点 `/opt/python` 加入 `sys.path`。每个需要用到层的函数代码开头必须加：

```python
import sys

opt_python = "/opt/python"
if opt_python in sys.path:
    sys.path.remove(opt_python)
sys.path.insert(0, opt_python)
```

将 `/opt/python` 插到最前面，确保优先从层加载依赖。

### 完整入口模板

```python
import json
import sys
import traceback

def main(event, context):
    # 1. 添加层路径
    opt_python = "/opt/python"
    if opt_python in sys.path:
        sys.path.remove(opt_python)
    sys.path.insert(0, opt_python)

    # 2. 导入 akshare
    try:
        import akshare as ak
    except Exception as e:
        return {"code": 1, "error": str(e)}

    # 3. 调用 API
    try:
        df = ak.index_realtime_sw(symbol="一级行业")
        return {"code": 0, "data": df.head().to_json(force_ascii=False)}
    except Exception as e:
        return {"code": 2, "error": str(e)}
```

## 常见问题与注意事项

### 1. 层 zip 必须带 `python/` 前缀

**错误示例**：zip 内直接是 `akshare/`, `numpy/` 等目录（无前缀）
**正确示例**：zip 内是 `python/akshare/`, `python/numpy/` ...

SCF 将层挂载到 `/opt`，所以 `python/` 前缀对应到 `/opt/python/`。

### 2. CompatibleRuntimes 必须正确设置

通过 API `PublishLayerVersion` 发布层时，必须传 `CompatibleRuntimes` 参数。例如 Python 3.10：

```json
{
    "LayerName": "akshare10",
    "CompatibleRuntimes": ["Python3.10"],
    "Content": { ... }
}
```

不传此参数 API 会报错。控制台创建层时会自动提示选择运行时。

### 3. 不要用运行时 pip install

CloudBase SCF 运行时环境的 pip 是残缺的，缺少 `pip._internal.operations.build` 模块，无法在函数内 pip install 任何包。所有依赖必须提前打包进层。

### 4. 部分包没有 manylinux wheel

**例子**：`jsonpath` 包只有源码包（sdist），没有 manylinux 二进制 wheel。
当使用 `pip download --only-binary=:all:` 时会被跳过。

**解决方案**：
- 将 `jsonpath` 从依赖列表中排除，或使用已有正确 zip 为基础增量构建
- 纯 Python 包（无 C 扩展）可以直接从 PyPI 下载 `.tar.gz` 解压

### 5. akshare 1.18.63 新增依赖

此版本的 akshare 新增依赖 `py_mini_racer`（JavaScript 引擎桥接），它有 manylinux1 wheel，但旧版层 zip 中未包含。如果 import akshare 报 `No module named 'py_mini_racer'`，需补装：

```powershell
pip download py_mini_racer -d . --platform manylinux1_x86_64 --no-deps
```

### 6. 国内镜像加速

下载 Python 包时使用清华镜像可大幅加快速度：

```powershell
-i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 7. 函数内存和时间配置

akshare 导入需要加载大量编译模块（numpy, pandas, lxml, curl_cffi 等），建议：

| 配置 | 建议值 |
|------|--------|
| 内存 | ≥ 256 MB |
| 超时 | ≥ 60 秒（首次冷启动约 20s） |

### 8. 层更新后需要重新部署函数代码

更新层版本后，需要在云函数配置中重新绑定新版本的层。函数代码本身不需要修改，但需要触发一次重新部署（或更新函数配置）来刷新层的挂载。

## 测试验证

测试函数 `test_akshare_py310` 已验证：

```python
# 验证步骤
import akshare as ak                      # ✅ 导入成功
ak.index_realtime_sw(symbol="一级行业")   # ✅ 返回 31 行 × 9 列数据
# 样本：农林牧渔(801010), 基础化工(801030), 钢铁(801040) ...
```
