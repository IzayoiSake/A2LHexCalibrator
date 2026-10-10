# A2L HEX Calibrator（A2L/HEX 固件标定工具）

简体中文 | [English](README.en.md)

## 界面语言（v1.2.0）

菜单栏“语言 / Language”可切换简体中文和 English，立即生效；保留已加载文件、搜索、筛选、选中项、未保存修改和撤销历史。文件操作中或弹窗打开时暂不切换，关闭弹窗/完成操作后再选。偏好与快捷键一起保存在原有设置文件，下次启动自动恢复。

按钮、菜单、表头、状态、帮助及界面确认提示由 `src/a2l_hex_calibrator/locales/zh_CN.json`、`en_US.json` 提供，代码通过文本键读取，不再直接嵌入中文界面文案。打包的 EXE 内置语言资源，可单独运行；需要修改文案时，将语言 JSON 放入 EXE 旁的 `locales/`，编辑后重启。缺失/无效项回退到内置资源；不要修改文本键和 `{p0}` 等占位符。

A2L 自带的描述、枚举文字和底层解析器的技术错误原文不做机器翻译；Windows 原生文件选择/确认框的系统按钮可能跟随 Windows 语言。详见[国际化维护说明](docs/I18N.md)。

通用 Windows 离线标定编辑工具。读取 A2L 描述及 Intel HEX 中的实际存储值，编辑后另存为新 HEX。不绑定特定项目、变量前缀、芯片型号或固定地址。

## 启动

双击 `dist/A2LHexCalibrator.exe`，不需要安装 Python。Windows 若提示未知发布者，是因为本工具尚未做商业代码签名，不是设备厂家的官方刷写软件。

1. 点击“加载 A2L”和“加载 HEX”，选择配套文件，加载顺序不限。
2. 列表显示全部已识别的标定对象；数组按内存线性下标展开，从 0 开始。
3. 搜索使用不区分大小写的包含匹配，通配符由 Python 标准库 `fnmatch` 处理：`*` 任意字符、`?` 单字符。例如 `Mon*` 可以找到 `Device1_Mon_...`，`Mon*Cmd` 可以跨过中间字符。方括号是数组下标字面值，不是字符集合或正则表达式。名称和描述均参与搜索。
4. 双击条目编辑，默认输入物理值，也可以切换到存储原始值。枚举支持文字或数值；整数可用十进制、`0x` 十六进制、`true/false`。
5. 确认实际存储值和字节。FLOAT32 具有精度限制，界面会展示量化后的实际值。黄色条目表示相对原 HEX 已修改。
6. 使用“修改预览”核对，支持恢复单项、撤销和“已修改”筛选。
7. “另存为新 HEX”可生成新文件，也可确认覆盖已有输出文件；加载的原 HEX 仍禁止覆盖。输出先写入同目录临时文件并校验，通过后才替换目标，写入或替换失败时不会先清空已有文件。

快捷键：Ctrl+F 搜索；Ctrl+Z 撤销；Ctrl+Shift+S 另存为。

## 保持其他内容不变

- 原 HEX 只读，不原地修改。
- 未修改参数时另存，输出与输入文件逐字节一致。
- 有修改时，仅更改被修改的数据字节对应的十六进制字符，以及涉及记录的 Intel HEX 行校验和。
- 保留其他记录、记录顺序、地址记录、入口地址、行长度、换行格式、空白及 EOF 后的 `0x1A` 填充。
- 支持跨记录的参数；遇到相同地址的重复记录且内容一致时同步修改全部副本；若重复地址内容冲突，拒绝加载。
- 输出前重新解析并验证每条记录及数据差异；写入后再读回检查。源文件自加载后发生变化时拒绝保存。
- HEX 缺失地址不会填 0，不猜测 RAM 对应的 Flash 地址，也不做芯片地址别名映射。
- 多个标定对象地址重叠时禁止编辑，避免静默改变另一个参数。

**重要：Intel HEX 行校验和与厂家固件 CRC / 数字签名不同。工具只更新 HEX 行校验和，不修改其他存储区域中的 CRC、签名或 Bootloader 元数据。若设备要求这些校验，刷写前必须使用对应的厂家流程处理。能成功导出不代表能直接刷写或安全运行。**

## 当前支持范围

| 项目 | 支持内容 |
| --- | --- |
| A2L 对象 | VALUE 标量、VAL_BLK 数组；简单直接存储的 AXIS_PTS；明确 MATRIX_DIM 或完整 FIX_AXIS 的 CURVE / MAP / 多维表数值区 |
| 数据类型 | 有符号/无符号 8、16、32、64 位整数，IEEE Float32、Float64 |
| 字节序 | 从对象或 MOD_COMMON 读取 MSB_LAST / MSB_FIRST；未定义时禁止猜测 |
| 数组 | MATRIX_DIM 或 NUMBER，最多 100000 元素；显示内存线性下标，不提供二维曲面编辑 |
| 换算 | IDENTICAL、LINEAR、RAT_FUNC（物理范围内必须有唯一逆解）、严格单调的 TAB_INTP / TAB_NOINTP、COMPU_VTAB 枚举 |
| 位域 | 无符号整数的连续 BIT_MASK，保留掩码之外的原字节位 |
| HEX | Intel HEX 00/01/02/03/04/05 记录；加载时验证每行长度与校验和 |
| 文本编码 | A2L 尝试 UTF-8、GB18030、CP1252；不支持被外部软件加密后的密文 |

本工具不声称完整实现 ASAP2 所有布局。下列情况明确报错或标记不可编辑，不会猜值后写入：

- 多 MODULE A2L、外部 `/include`、动态实例与厂商专用扩展布局。
- 在数值前存放长度/轴计数、间接地址、复杂 RECORD_LAYOUT，非零 ECU_ADDRESS_EXTENSION。
- ASCII 字符串对象、FORM 公式、区间文本表、非单调数值表及不唯一的换算。
- HEX 中没有数据的 RAM 标定、A2L READ_ONLY 对象、重叠标定地址。

简单 RECORD_LAYOUT 指只有一个位置为 1 的 FNC_VALUES，DIRECT、ROW_DIR/COLUMN_DIR；独立轴为位置 1 的 AXIS_PTS_X，DIRECT、INDEX_INCR。复杂布局不会被当作连续数组处理。

界面列出不可处理条目及原因。“全部可标定参数”以 A2L 声明为准；如果 HEX 未携带对应数据，无法仅凭这两个文件恢复它的数值。A2L 和 HEX 是否版本匹配也无法单凭地址存在自动证明，必须由使用者确认。

A2L 声明的范围用于输入检查，不是硬件安全工作范围。原始值输入也会经过类型、换算和范围检查。未知枚举可显示原始数值，但不会允许写入未定义枚举。

## 独立 Miniforge / mamba 环境

源码和构建环境位于本文件所在文件夹，与工程代码和全局 Python 依赖隔离。

```powershell
# 在本文件所在目录执行
mamba env create -p .conda-env -f environment.yml
conda activate ./.conda-env
python app.py
pwsh -File ./tests/run.ps1
pwsh -File ./build.ps1
```

若 Miniforge 安装目录的包缓存不可写，可仅在当前终端指定用户缓存：

```powershell
$env:CONDA_PKGS_DIRS = "$env:LOCALAPPDATA/mamba/pkgs"
```

构建产物 `dist/A2LHexCalibrator.exe` 是独立单文件 EXE。首次启动需要临时解包，可能稍慢。

## 文件说明

- `src/a2l_hex_calibrator/backend/`：独立于 UI 的格式解析、标定数据及应用服务。
- `src/a2l_hex_calibrator/ui/`：Tk 窗口、布局、快捷键、对话框；不直接读写文件或修改待写字节。
- `app.py`：轻量启动壳，支持源码启动和 EXE 打包。
- `tests/`：核心、GUI、服务、架构回归测试，合成数据工厂和只读样例验证。
- `tests/run.ps1`：自动设置本地环境并运行全部测试。
- `environment.yml`、`pyproject.toml`、`build.ps1`：环境、包元数据与构建入口。
- `docs/ARCHITECTURE.md`：中文架构说明、类职责、调用流程及扩展规则。

## 开发与版本管理

项目采用通用命名。不要直接移动已建立的 Conda 环境；更换目录后应按环境文件重新创建。
`src` 为标准 Python 源码布局；激活环境后可使用 `python -m pip install -e .` 安装，再以 `python -m a2l_hex_calibrator` 启动。

后端不依赖 Tkinter；架构测试禁止后端导入 UI，禁止 UI 直接操作文件和条目的 `pending` 字节。
现有快捷键目录及 JSON 格式标识兼容旧版，用户原来的快捷键配置和修改方案可继续使用。

`.gitignore` 排除虚拟环境、`.conda-env`、`build`、`dist`、缓存、临时报告、固件样本和本地重构备份。
原单文件源码保留于 `.refactor-backup/`，旧 EXE 保留在 `dist/`，均不纳入 Git。

源码通过 GitHub API 以 UTF-8 明文提交，发布时逐文件核验 Git blob 哈希。若本机安装了文件加密软件，请确认构建工具能读取明文，不要将密文提交到 Git。

解析规则参考：[ASAM MCD-2 MC](https://www.asam.net/standards/detail/mcd-2-mc/wiki/)。打包方式参考：[PyInstaller](https://pyinstaller.org/en/stable/operating-mode.html)。
