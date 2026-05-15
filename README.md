# NevernesstoEvernessAutoScript

> 基于图像识别技术的《异环》(Neverness to Everness) 游戏自动化工具。

基于 [al-script](https://github.com/xhqss/NevernesstoEvernessAutoScript) 通用自动化框架，
从 [AzurLaneAutoScript (Alas)](https://github.com/LmeSzinc/AzurLaneAutoScript) 核心架构重构而来。

---

## 项目状态：立项阶段

本项目目前处于 **立项 / 早期开发阶段**，尚未发布可用的正式版本。

如果你需要可用的《异环》自动化脚本，请访问：

- [ok-nte](https://github.com/BnanZ0/ok-nte) — 基于 ok-script 的 NTE 自动化
- [MaaNTE](https://github.com/1bananachicken/MaaNTE) — 基于 MaaFramework 的 NTE 自动化

---

## 特性

- **多截图方式**: ADB / Windows DXGI / BitBlt / scrcpy / NemuIPC
- **多输入方式**: ADB / minitouch / maatouch / PostMessage / PyDirectInput
- **双端支持**: 模拟器 (ADB) + PC 端窗口
- **多引擎 OCR**: cnocr / PaddleOCR / RapidOCR / DGOCR / ONNXOCR
- **模板匹配**: 基于 OpenCV，自适应分辨率，PNG 素材管理
- **双编程模式**: 传统脚本模式 + 状态循环模式 (StateLoop)
- **资产工具**: 从 PNG 截图自动提取 Button 坐标 (button_extract.py)
- **GUI 界面**: PySide6 全功能界面
- **打包部署**: pyappify → setup.exe，Git 增量更新

## 安装

```bash
pip install al-script
```

## 快速开始

```python
from al.task import ScriptTask

class MyTask(ScriptTask):
    def run(self):
        self.screenshot()
        box = self.find_one("START_BUTTON")
        if box:
            self.click_box(box)
            self.sleep(1)
```

## 文档

- [快速开始](docs/quick_start.md)
- [API 文档](docs/api.md)
