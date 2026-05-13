# Quick Start

本指南将带你从零开始使用 al-script 构建游戏自动化脚本。

## 1. 安装

```bash
pip install al-script
```

可选依赖：

```bash
# OCR 支持
pip install cno cr>=2.2 paddleocr>=2.7

# Git 增量更新
pip install gitpython>=3.1
```

## 2. 核心概念

al-script 将游戏自动化抽象为几个核心操作：

| 概念 | 说明 |
|------|------|
| **截图 (Screenshot)** | 通过 ADB/Windows DXGI/BitBlt 捕获游戏画面，统一缩放至 1280x720 |
| **找图 (Template Match)** | 用 OpenCV 模板匹配在截图中定位 PNG 素材 |
| **找色 (Color Match)** | 基于区域平均色判断 UI 元素是否出现 |
| **点击 (Click)** | 通过 ADB/PostMessage/PyDirectInput 模拟点击 |
| **OCR** | 多引擎文字识别（cnocr / PaddleOCR / RapidOCR） |
| **任务 (Task)** | 线性脚本模式 (ScriptTask) 或状态循环模式 (StateTask) |

## 3. 第一个 ScriptTask

`ScriptTask` 是传统的线性脚本模式，适合简单、一次性执行的自动化流程。

```python
from module.task.base_task import ScriptTask
from module.base.button import Button
from module.util.logger import logger


class MyFirstTask(ScriptTask):
    def run(self):
        # 1. 截图
        self.screenshot()

        # 2. 定义一个按钮 (区域 + 颜色)
        start_btn = Button(
            area=(500, 300, 600, 350),   # 颜色检测区域
            color=(255, 200, 100),        # 期望的平均颜色
            button=(500, 300, 600, 350),  # 点击区域
            name='START'
        )

        # 3. 检测并点击
        if self.appear(start_btn):
            self.click(start_btn)
            self.sleep(1)

    def before_run(self):
        logger.info('准备开始任务...')

    def after_run(self):
        logger.info('任务执行完毕')
```

生命周期：`before_run()` → `run()` → `after_run()`

## 4. 状态循环模式 StateTask

`StateTask` 适合持续运行的自动化（如循环收菜、反复刷图）。它使用状态机模式：

```python
from module.task.base_task import StateTask


class MyLoopTask(StateTask):
    def handle_states(self):
        """每个截图帧依次检查各状态，命中后 return 等待下一帧"""
        # 状态 1: 主界面 → 点击"出击"
        if self.appear_then_click(BATTLE_ENTRY_BUTTON):
            return

        # 状态 2: 战斗中 → 什么都不做，等待
        if self.appear(IN_BATTLE_INDICATOR):
            return

        # 状态 3: 结算界面 → 点击确认
        if self.appear_then_click(CONFIRM_BUTTON):
            return

    def handle_exit(self):
        """返回 True 退出循环"""
        return self.appear(EXIT_CONDITION)

    def execute(self):
        # StateTask 内置循环：截图 → handle_exit → handle_states → 重复
        super().execute()
```

## 5. 准备素材（模板匹配）

### 5.1 存放 PNG 素材

将游戏截图中的按钮/图标裁剪为 PNG 文件，放入 `assets/default/<模块名>/`：

```
assets/
  default/
    my_game/
      START_BUTTON.png
      CONFIRM_BUTTON.png
      TEMPLATE_LOGO.png
```

### 5.2 加载素材

在 `App` 初始化时会自动创建 `FeatureSet` 并加载素材目录：

```python
from module.app import App

app = App(config={
    'config_name': 'my_config',
    'assets_dir': './assets',
    'debug': True,
})

# 加载素材目录
app.feature_set.load_from_directory('assets/default/my_game')
```

### 5.3 在 Task 中使用模板匹配

```python
class MyTask(ScriptTask):
    def run(self):
        self.screenshot()

        # 找单个特征，返回 Box 或 None
        box = self.find_one('START_BUTTON', threshold=0.85)
        if box:
            self.click_box(box)  # 点击 Box 中心

        # 找所有匹配
        all_boxes = self.find_all('GOLD_ICON', threshold=0.80)
        logger.info(f'找到 {len(all_boxes)} 个金币图标')

        # 等待某个特征出现（超时 10 秒）
        result = self.wait_feature('LOADING_DONE', timeout=10, interval=0.5)
        if result:
            logger.info('加载完成')

        # 等待并点击
        self.wait_and_click_feature('CONFIRM', timeout=5)
```

### 5.4 自动生成 Button 定义

使用 `button_extract` 工具从 PNG 截图自动提取 Button 坐标和颜色：

```bash
python -m module.dev_tools.button_extract
```

这会扫描 `assets/default/*/` 下的 PNG 文件，自动生成各模块的 `assets.py`，包含 Button 定义。

素材命名约定：

| 文件名 | 含义 |
|--------|------|
| `MY_BUTTON.png` | 基础截图，自动提取 area 和 color |
| `MY_BUTTON.AREA.png` | 覆盖颜色检测区域 |
| `MY_BUTTON.COLOR.png` | 覆盖颜色值 |
| `MY_BUTTON.BUTTON.png` | 覆盖点击区域 |
| `TEMPLATE_XXX.png` | 模板匹配对象（非 Button） |

## 6. OCR 文字识别

```python
class MyTask(ScriptTask):
    def run(self):
        self.screenshot()

        # 通用文字识别
        text = self.ocr(
            area=(100, 200, 400, 250),
            letter=(255, 255, 255),  # 文字颜色
            threshold=128,            # 二值化阈值
        )
        logger.info(f'识别结果: {text}')

        # 识别数字
        count = self.ocr_digit((300, 100, 400, 150))
        logger.info(f'数字: {count}')

        # 识别计数器 "14/15"
        current, remaining, total = self.ocr_counter((300, 100, 400, 150))
        logger.info(f'进度: {current}/{total}, 剩余: {remaining}')

        # 自定义 OCR 引擎
        from module.ocr.ocr import Ocr
        my_ocr = Ocr(
            buttons=[(100, 200, 400, 250)],
            engine='paddle',          # 指定引擎: cnocr / paddle / rapid
            alphabet='0123456789',    # 限定字符集
            lang='ch',
        )
        results = my_ocr.ocr(self._last_screenshot)
```

可用的 OCR 引擎：

| 引擎 | 引擎名 | 安装包 |
|------|--------|--------|
| cnocr | `cnocr` | `cno cr` |
| PaddleOCR | `paddle` | `paddleocr` |
| RapidOCR | `rapid` | `rapidocr-onnxruntime` |

引擎会自动检测并注册。默认按 `cnocr → paddle` 的优先级选择。

## 7. 设备配置

### 7.1 ADB 模式（模拟器）

```json
{
  "DefaultTask": {
    "Device": {
      "Platform": "adb",
      "Serial": "127.0.0.1:5555",
      "ScreenshotMethod": "auto",
      "ControlMethod": "auto"
    }
  }
}
```

支持的截图方式：ADB screencap
支持的输入方式：ADB tap / swipe / minitouch / maatouch

### 7.2 PC 模式（Windows 窗口）

```json
{
  "DefaultTask": {
    "Device": {
      "Platform": "pc",
      "ScreenshotMethod": "auto",
      "ControlMethod": "auto"
    },
    "Window": {
      "Title": "My Game",
      "Class": ""
    }
  }
}
```

支持的截图方式：

| 方式 | 配置文件值 | 说明 |
|------|-----------|------|
| Windows Graphics (DXGI) | `WindowsGraphics` | 最快，需要 Win10 17763+ |
| BitBlt | `BitBlt` | 较慢，兼容性好 |
| ADB | `ADB` | 通过 ADB 连接 |

支持的输入方式：

| 方式 | 配置文件值 | 说明 |
|------|-----------|------|
| PostMessage | `PostMessage` | 后台消息，不影响前台操作 |
| PyDirectInput | `PyDirectInput` | 模拟真实输入 |
| ADB | `ADB` | 通过 ADB |

不同截图和输入方式可以**自由组合**，例如 WindowsGraphics 截图 + ADB 点击。

### 7.3 自动检测

设置 `"Platform": "auto"`（默认）时，DeviceManager 会按以下优先级自动选择：

1. 配置了 `Window.Title` → 尝试 PC 模式
2. 配置了 `Device.Serial` → 尝试 ADB 模式
3. 兜底 → PC 桌面模式

## 8. 配置文件

配置文件存放在 `config/` 目录，JSON 格式。默认使用 `template.json`。

```json
{
  "DefaultTask": {
    "Scheduler": {
      "Enable": true,
      "Command": "DefaultTask"
    },
    "Device": {
      "Platform": "auto",
      "Serial": "auto"
    },
    "Ocr": {
      "Engine": "default"
    }
  }
}
```

通过配置生成器创建完整的配置框架：

```bash
python -m module.config.config_generator
```

## 9. 运行方式

### 9.1 命令行

```bash
# CLI 模式
python main.py my_config

# 或通过模块入口
python -m module.launcher my_config

# 环境变量指定配置
AL_CONFIG=my_config python main.py
```

### 9.2 GUI 模式

```bash
# 启动 GUI
python -m module.gui.launcher my_config

# 或
al-script-gui my_config
```

GUI 提供完整的功能界面：任务管理、配置编辑、模板浏览、截图调试、日志查看。

### 9.3 编程方式

```python
from module.app import App

app = App(config={
    'config_name': 'my_config',
    'use_gui': False,
    'debug': True,
})

# 注册并运行任务
from my_tasks import MyTask
task = MyTask(
    config=app.config,
    device_manager=app.device_manager,
    exit_event=app.exit_event,
)
task.feature_set = app.feature_set
app.task_executor.add_task(task)
app.start()
```

## 10. 完整示例

一个完整的自动化示例，演示截图→找图→点击→OCR 的组合使用：

```python
from module.task.base_task import ScriptTask
from module.base.button import Button
from module.util.logger import logger


class DailyQuest(ScriptTask):
    def before_run(self):
        logger.info('开始每日任务...')

    def run(self):
        # 步骤 1: 等待主界面加载
        self.wait_feature('HOME_INDICATOR', timeout=30)
        logger.info('主界面已加载')

        # 步骤 2: 点击"任务"按钮
        if self.find_one_and_click('QUEST_BUTTON'):
            self.sleep(1.5)

        # 步骤 3: 检查任务是否完成
        self.screenshot()
        progress = self.ocr_counter((600, 400, 700, 430))
        current, remaining, total = progress
        logger.info(f'任务进度: {current}/{total}')

        # 步骤 4: 如果有剩余，继续执行
        if remaining > 0:
            self.find_one_and_click('START_QUEST')
            self.sleep(3)

        # 步骤 5: 领取奖励
        self.screenshot()
        if self.find_one_and_click('CLAIM_REWARD'):
            logger.info('奖励已领取')
            self.sleep(1)

        logger.info('每日任务完成!')

    def after_run(self):
        logger.info('任务结束')
```

## 下一步

- [API 文档](api.md) — 全部类和函数的详细参考
- [GitHub 仓库](https://github.com/LmeSzinc/AzurLaneAutoScript) — 原始 Alas 项目
- `examples/basic_automation.py` — 更多示例代码
