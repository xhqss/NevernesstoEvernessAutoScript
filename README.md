# al-script

基于图像识别技术的通用 Python 游戏自动化框架。

从 [AzurLaneAutoScript (Alas)](https://github.com/LmeSzinc/AzurLaneAutoScript) 提取核心框架层，
重构为通用、可扩展的自动化开发工具包。

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
