# 统一竞赛环境：交给 Agent 执行

用户要求按本指南配置环境时，完成检测、必要安装、项目配置与实际验收，给出结果；不要只返回安装建议。仅要求阅读或检查时，不安装。已有安装授权不重复询问；超出用户范围或遇到宿主权限限制时，说明具体阻碍。

本指南面向 Windows 64 位电脑，使用已有 PowerShell。统一工具链和验收标准，保留已经可用的环境；`requirements.txt` 是最低兼容清单，并未锁定所有版本。其他系统先按平台调整命令，不照搬 Windows 安装器。

| 组件 | 统一选择与用途 |
|---|---|
| 编辑器 | VS Code；扩展 `ms-python.python`、`James-Yu.latex-workshop`，分别支持 Python 和 LaTeX |
| 计算 | 新环境用标准版 Python 3.13（64 位）及独立 `.venv`；已有可用的 3.12/3.13 环境继续使用，其他版本以实际兼容验收判断 |
| 基础库 | `requirements.txt` 中的 NumPy、SciPy、Pandas、Matplotlib、Seaborn、openpyxl、PyMuPDF |
| 论文 | 新电脑用 TinyTeX 提供 XeLaTeX，准备 `ctex`、`amsmath`、`fandol`；已有可用 TeX 继续使用，统一交付 `.tex` 与 PDF |

VS Code 本身不包含 Python 或 XeLaTeX。基础配置无需另装 Anaconda、R、MATLAB、Word、独立绘图软件或额外 AI 插件；具体题目确实需要的工具另按任务处理。

## 1. 定位文件夹和已有工具

以**本文件所在目录**为包根目录 `$mmRoot`，确认 `requirements.txt`、`快速检查.py`、`.agents`、`.vscode` 都在。解压完整文件夹后工作，不在 ZIP 内执行，不复制开发者电脑的绝对路径。

先查用户指定环境、项目 `.venv`、VS Code 已选解释器、`py -0p` 和 PATH；找不到命令不等于软件未安装。确认操作系统架构与解释器能运行后，将所选解释器真实完整路径赋给 `$mmPython`，记录 `sys.executable`、`sys.version`、`sys.prefix` 与 `sys.base_prefix`。优先既有项目环境，不向 AI 软件内置运行时装包。

同时定位 VS Code CLI `$mmCode`（Windows 常为 `code.cmd`）和 XeLaTeX `$mmXeLaTex`。只检测已知安装目录，不扫描整个磁盘。以下命令中的变量均由 Agent 根据实际检测结果赋值；后续安装和验收使用同一解释器。

```powershell
$mmChecker = Join-Path $mmRoot '.agents/skills/mathorcup-modeling/scripts/local_check.py'
& $mmPython -B -X utf8 $mmChecker check
```

查看输出 JSON 中的 `executable`、`modules` 和 `features`，列出已具备与缺少的能力。有 Python 但无 XeLaTeX 时分别处理，不反复更换 Python。`启动检查.ps1` 会挑首个满足条件的候选环境；已明确路径时传 `-Python` 或直接调用该路径。

## 2. 仅补缺项

**缺基础程序：**从 [Python 官方 Windows 页面](https://www.python.org/downloads/windows/)取得匹配架构的 3.13 稳定版安装器，采用用户级安装；[Python 官方无人值守参数](https://docs.python.org/3.13/using/windows.html#installing-without-ui)支持 `/quiet InstallAllUsers=0 InstallLauncherAllUsers=0 Include_pip=1 Include_test=0`。安装完成后重新定位解释器，不猜路径。VS Code 缺失时用 [官方 User Setup](https://code.visualstudio.com/docs/setup/windows)，保留默认用户安装目录；无需关闭用户当前窗口。

**缺 Python 项目环境：**已有可用环境则跳过。只有目标 `.venv` 不存在时，用已检测的基础解释器 `$mmBasePython` 创建；目录已存在则检查并复用，不覆盖重建。

```powershell
& $mmBasePython -m venv (Join-Path $mmRoot '.venv')
$mmPython = Join-Path $mmRoot '.venv/Scripts/python.exe'
& $mmPython -m pip install --only-binary=:all: -r (Join-Path $mmRoot 'requirements.txt')
& $mmPython -m pip check
```

这组安装命令用于新环境。已有环境只安装确认缺失或不兼容的依赖，不执行全量升级、强制重装或复制他人的 `.venv`。始终用 `$mmPython -m pip`，不依赖终端激活。没有匹配的二进制包时先核对 Python 版本、架构与源，不为此安装整套编译工具。`pip check` 用于发现依赖冲突，之后仍需实际运行验收。[pip 官方说明](https://pip.pypa.io/en/stable/cli/pip_check/)

**缺 XeLaTeX：**从 [TinyTeX 官方页面](https://yihui.org/tinytex/)取得 Windows 安装脚本，保存到本次临时目录、检查内容与目标路径后执行；不要直接把下载内容管道交给解释器。已有安装目录不得覆盖。安装后定位同一发行版中的 `xelatex.exe` 与 `tlmgr`；仅缺宏包时用其 `tlmgr install ctex amsmath fandol` 补齐。通常在用户 AppData 下；以实际安装结果为准。无需安装 R，不做 `tlmgr update --all` 或另装完整 TeX Live。

**缺编辑器扩展：**先用 `$mmCode --list-extensions --show-versions` 核对用户实际使用的配置文件（Profile），只对缺失项执行 `& $mmCode --install-extension ms-python.python` 或 `& $mmCode --install-extension James-Yu.latex-workshop`。使用非默认 Profile 时指定其已有名称，不新建无用 Profile；不加 `--force` 升级已有扩展。[VS Code 官方 CLI](https://code.visualstudio.com/docs/configure/command-line#_working-with-extensions)

每条安装命令检查退出码。下载只用官方来源；使用有时限的前台进程，保留报错。基础命令不认识时先查看其帮助，连续同类失败后换路，不反复重装或关闭安全功能。

## 3. 连接 VS Code 与真实环境

在当前工作区**合并** `.vscode` 配置，保留原有键和编译方案。沿用包内两遍 XeLaTeX、手动构建与内置 PDF 预览；没有现成配置时直接使用包内设置。有参考文献或额外模板要求时再补相应编译步骤。

项目 `.venv` 可设 `python.defaultInterpreterPath` 为 `${workspaceFolder}/.venv`；复用外部环境时使用本机真实路径，仅保留在本机配置。该设置不能覆盖工作区曾经选过的解释器，需通过 `Python: Select Interpreter` 核对；随后在新终端打印 `sys.executable`。不能只凭设置文件就报告“VS Code 已选对 Python”。[官方设置说明](https://code.visualstudio.com/docs/python/settings-reference)

XeLaTeX 不在 PATH 时，当前检查进程设置 `$env:MATHORCUP_XELATEX = $mmXeLaTex`；LaTeX Workshop 的 `xelatex` 工具也设置为同一个实际路径。该环境变量只服务包内检查器，不会自动配置编辑器。不要为当前任务重写系统 PATH；将来换电脑重新检测本机路径。

## 4. 实际验收

用选定解释器执行以下命令。脚本会创建新的 `验证记录/环境检查-*` 目录，运行合成能力测试，不碰赛题数据，也不安装软件。

```powershell
& $mmPython -B -X utf8 (Join-Path $mmRoot '快速检查.py')
```

检查退出码及报告中的 `ok`、`checks`，确认数值优化（含 LP/MILP）、中文 Matplotlib + Seaborn 绘图、Excel 数值读写、PDF 文本与渲染、中文 LaTeX 公式和交叉引用实际通过。若手工指定 `--out`，必须是不存在的新目录。

打开或渲染检查生成的 `synthetic_figure.png`、`synthetic_latex.pdf`，确认中文、公式和引用显示；再在 VS Code 对生成的 `.tex` 实际编译并预览。Agent 没有界面操作权限时，先完成全部可自动执行的检查，只请用户做一次：打开该 `.tex`，按 `Ctrl+Alt+B` 编译、`Ctrl+Alt+V` 预览。界面未验证就标“待确认”，不要冒充完成。

## 5. 留下结果并结束

在本次检查目录写一份简短 `环境结果.md`：记录操作系统、Python/XeLaTeX/VS Code 实际路径和版本、基础库与扩展版本、安装或改动项、`report.json` 位置，以及自动测试/图像目视/编辑器预览分别是否通过。对用户只报告状态、结果位置与未完成项。

全部必要验收完成才报“环境已就绪”；其余报“自动检查通过，编辑器待确认”或列出具体失败。自检不代表真实模型正确，也未验证 Excel 公式重算或所有论文宏包。精确复现时从已通过验收的环境记录依赖版本，在同一系统与 Python 版本的新环境复验；不要把本清单误当精确锁文件。

| 遇到的问题 | Agent 下一步 |
|---|---|
| DLL 加载失败、拒绝访问 | 核对解释器、位数和执行隔离；必要时按宿主规则申请该命令执行权限，不能直接认定缺包 |
| MiKTeX 被自检拦截 | 这是检查器的自动安装策略限制；保留原环境，核实禁用自动装包后的独立编译结果并说明覆盖范围，不静默换发行版 |
| 缺中文字体、宏包或命令找不到 | 分清字体缺失、宏包缺失和 PATH 未刷新；使用已安装字体或同发行版工具补缺，不全量重装 |

结束前确认本次子任务与安装进程已退出，只清理本次产生且不再使用的下载临时文件；保留环境与验收报告。报告在 `验证记录/`，打包时自动排除，不把本机路径、虚拟环境或合成测试输出发给队友。
