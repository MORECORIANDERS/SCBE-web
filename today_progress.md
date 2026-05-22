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