# jlc2ad

> 从 LCSC / EasyEDA 一键生成 Altium Designer 元件库（`.PcbLib` + `.SchLib` + `.LibPkg`）

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)
![Status](https://img.shields.io/badge/Status-Active-2ea44f)

`jlc2ad` 用于把立创商城（LCSC）器件数据转换为 Altium 可直接打开的库文件，适合快速搭建项目私有库、补齐封装与原理图库。

---

## 功能亮点

- 支持多个 LCSC 料号批量生成
- 自动生成 PCB 封装库：`.PcbLib`
- 自动生成原理图库：`.SchLib`
- 自动生成集成库工程：`.LibPkg`
- 自动建立原理图符号与 PCB 封装的模型关联
- 支持对已有库追加器件（不覆盖已有条目）

---

## 效果预览

输入料号：

```text
C15850 C8291 C9652
```

生成结果：

```text
my_lib.PcbLib
my_lib.SchLib
my_lib.LibPkg
```

在 Altium Designer 中打开 `my_lib.LibPkg`，即可编译为 IntLib 使用。

---

## 快速开始

### 1) 安装依赖

```bash
pip install -r requirements.txt
```

### 2) 生成单个器件

```bash
python jlc2ad.py C15850 -o my_lib
```

### 3) 生成多个器件

```bash
python jlc2ad.py C15850 C8291 C9652 -o my_lib
```

---

## 命令说明

```text
python jlc2ad.py <LCSC料号...> -o <输出名>
```

示例：

```bash
python jlc2ad.py C43314 C43317 C2990 -o power_lib
```

---

## 项目结构

```text
jlc2ad.py                  # 兼容入口（CLI）
jlc2ad_core/
  cli.py                   # 命令行主流程
  parsers.py               # EasyEDA API 与图元解析
  writers.py               # PcbLib/SchLib/LibPkg 写入
  types.py                 # 核心常量与数据结构

pcb_file_header.bin        # PCB 模板头
pcb_library_params.txt     # PCB 参数模板
sch_file_header.bin        # SchLib 模板头
sch_storage.bin            # SchLib Storage 模板
requirements.txt           # Python 依赖
```

---

## 生成后如何使用

1. 在 Altium Designer 打开 `xxx.LibPkg`
2. 执行 `Project -> Compile Integrated Library`
3. 在工程中加载并调用生成的库

---

## 常见问题

### 1) 提示库文件损坏

- 确认项目根目录下模板文件存在：
  - `pcb_file_header.bin`
  - `pcb_library_params.txt`
  - `sch_file_header.bin`
  - `sch_storage.bin`
- 建议换一个新的输出名重新生成（避免历史缓存影响）

### 2) 个别符号图形显示不完整

- 记录具体 LCSC 料号并单独生成复现
- EasyEDA 个别图元格式存在差异，后续可按料号持续增强解析规则

---

## 许可证

本项目采用 MIT 许可证，详见 `LICENSE`。
