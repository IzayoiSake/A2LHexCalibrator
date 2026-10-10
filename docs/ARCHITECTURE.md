# A2L HEX Calibrator 架构说明

简体中文 | [English](ARCHITECTURE.en.md)

## 1. 分层与依赖方向

```text
app.py / main.py                  启动与 DPI 设置
            ↓
ui/                              窗口、控件、用户确认、事件分发
            ↓
backend/services/                文件操作、编辑事务、搜索、修改方案
            ↓
backend/domain/ + formats/       标定数据、换算规则、A2L/HEX 格式
```

后端不导入 Tkinter 或 UI，也不弹窗。错误以异常返回，是否显示提示、询问覆盖由 UI 决定。
纯粹的数值和布局计算保留为函数；有业务职责的数据和服务用 Class，避免为了类而增加无意义实例。

## 2. 目录与职责

| 位置 | 主要对象与职责 |
| --- | --- |
| `backend/domain/parameter.py` | `Parameter`：A2L 元数据、类型、字节序、维度和范围 |
| `backend/domain/conversion.py` | `Conversion`：原始值/物理值换算，枚举与表插值 |
| `backend/domain/entry.py` | `Entry`：展开后的标量/数组元素，原始字节与待写字节 |
| `backend/domain/session.py` | `Session`：配对 A2L/HEX、逐项与批量校验、字节补丁 |
| `backend/formats/a2l_syntax.py` | `A2LBlockParser` / `Block`：词法与块语法树 |
| `backend/formats/a2l.py` | `A2L`：布局与换算语义解析 |
| `backend/formats/intel_hex.py` | `HexImage` / `Record`：无损读写与 HEX 校验 |
| `backend/services/search.py` | `SearchQuery`：复用 fnmatch 的包含通配符搜索 |
| `backend/services/hex_writer.py` | `HexWriter`：源文件检查、临时输出与安全替换 |
| `backend/services/change_plan.py` | `ChangePlanCodec`：无地址 JSON 格式和整批验证 |
| `backend/services/files.py` | `FileService`：文件加载、JSON/CSV、设置的实际磁盘读写 |
| `backend/services/editing.py` | `EditService`：应用、恢复、撤销修改 |
| `ui/editor.py` | `Editor`：拥有唯一的 Tk 主窗口及界面状态 |
| `ui/layout.py` / `table.py` | 响应式布局、居中、筛选、选择、详情展示 |
| `ui/editing.py` / `files.py` | 编辑弹窗、文件对话框和用户确认；不直接写磁盘/修改 pending |
| `ui/shortcuts.py` / `keymap.py` | 快捷键事件、菜单和键位校验 |
| `ui/jobs.py` | 后台工作队列与主线程回调 |
| `backend/services/translation.py` | `TranslationService`：UTF-8 资源、占位符校验与外部资源回退；不依赖 Tk |
| `ui/language.py` / `locales/*.json` | `LanguageMixin`：保存偏好、重建控件并保留会话；中英文文本资源 |
| `tests/` | 合成数据、核心/GUI/服务/架构测试及 EXE 冒烟脚本 |

界面按职责使用 Mixin 协作类，共享 `Editor` 的控件树和会话引用；它们不能独立实例化。
每个 Mixin 不另建 Tk 根窗口，不持有另一份业务会话。选择这种拆分是为了保留现有键盘绑定和布局行为。

## 3. 编辑与保存数据流

1. `FileService.load_pair()` 加载一侧文件，与已存在的另一侧重新生成 `Session`。
2. `Entry.original` 始终保留输入 HEX 的原始数据；修改先进入 `pending`，不即时写文件。
3. UI 把用户输入交给后端校验；批量操作全部验证后才调用 `EditService.apply()`。
4. `Session.patch()` 只输出实际变化字节。`HexImage.render()` 修改对应字符和行校验和。
5. `HexWriter` 确认源文件未外部变化，临时写入并读回验证后才替换目标。
6. 保存不清除 pending，列表继续显示相对最初加载文件的修改。

厂家固件 CRC、签名、Bootloader 校验不属于 Intel HEX 行校验和，本软件不会自动重算。
改名和重构不改变此边界，也不代表生成固件已通过设备运行验证。

## 4. 兼容约定

- 原来的 JSON `format` 标识仍是 `A2LHexEditor.changes`，以便继续加载历史修改方案。
- 快捷键目录仍兼容 `%APPDATA%/A2LHexEditor/shortcuts.json`，避免丢失用户配置。
- 项目目录可自行命名；移动源码后应重新创建环境，避免已有 Conda 环境中的绝对路径失效。
- 老单文件代码保留于被 Git 忽略的 `.refactor-backup/`，不是运行入口。

## 5. 维护规则

- 新格式和标定规则先写后端及测试，再由 UI 调用；不得反向导入 UI。
- UI 禁止直接读写文件或给 `Entry.pending` 赋值，架构测试会检查此约束。
- 后台线程只执行数据工作，Tk 控件只能在主线程操作。
- 新增依赖写入环境/项目配置；构建和测试不得依赖私有真实固件。
- `tests/run.ps1` 跑全套测试，`build.ps1` 先测试再生成新版 EXE。
- 新界面文字必须添加到中英文 JSON，不得直接写进控件代码。语言切换不改变 `Session`、`pending` 或 `history`。详见 [I18N.md](I18N.md)。
