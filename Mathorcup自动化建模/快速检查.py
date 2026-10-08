"""Check calculation, Chinese plotting and XeLaTeX in the existing environment."""
from pathlib import Path
from datetime import datetime
import argparse
import json
import sys
import uuid

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / ".agents/skills/mathorcup-modeling/scripts"))
import local_check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latex", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, help="A new output directory")
    args = parser.parse_args()
    selected = local_check.parse_features(local_check.DEFAULT)
    target = args.out or ROOT / "验证记录" / ("环境检查-" + datetime.now().strftime("%m%d-%H%M%S-") + uuid.uuid4().hex[:4])
    if target.exists():
        parser.error("输出目录已存在，请选择新目录；已有文件不会被覆盖。")
    print("正在使用的 Python：" + sys.executable, flush=True)
    try:
        report, code = local_check.smoke(selected, target)
    except (OSError, ValueError) as exc:
        print("未完成：" + str(exc))
        return 2
    if code == 0:
        print("全部通过：计算、Matplotlib + Seaborn 绘图、Excel、PDF，以及 LaTeX 中文、公式和交叉引用编译。")
        print("打开图片确认中文正常：" + str(target.resolve() / "synthetic_figure.png"))
        print("打开 LaTeX PDF 确认排版：" + str(target.resolve() / "synthetic_latex.pdf"))
    else:
        print("检查未通过，原因如下：")
        for name, item in report.get("modules", {}).items():
            if not item["available"]:
                print(f"  {name}: {item.get('reason', '无法加载')}")
        for name, item in report.get("checks", {}).items():
            if not item["ok"]:
                print(f"  {name}: {item.get('error', '')}")
        for name, item in report.get("features", {}).items():
            if not item["available"] and not item.get("unavailable_modules"):
                if name == "latex":
                    print("  latex: 未找到 XeLaTeX；请按手册确认 TeX 安装，并重启 VS Code。")
                else:
                    print(f"  {name}: 未找到对应程序或 Python 版本不满足要求")
        print("先核对上面的 Python 路径；DLL / 拒绝访问不等于没有安装。")
    if not target.exists():
        target.mkdir(parents=True)
        (target / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("详细报告：" + str(target.resolve() / "report.json"))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
