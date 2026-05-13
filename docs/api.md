# API Reference

al-script 全部公开 API 参考。顶层可通过 `from module import ...` 或 `import al`（打包后） 导入。

## 任务系统 (`module.task`)

### TaskBase

所有自动化任务的基类，提供截图、点击、找图、OCR 等核心方法。

```python
from module.task.base_task import TaskBase
```

**构造函数**

```python
TaskBase(
    config=None,            # dict: 任务配置
    device_manager=None,    # DeviceManager: 设备管理器
    exit_event=None,        # ExitEvent: 退出信号
    handler=None,           # Handler: 处理器
)
```

**属性**

| 属性 | 类型 | 说明 |
|------|------|------|
| `device_manager` | DeviceManager | 设备管理器（可读写） |
| `feature_set` | FeatureSet | 素材集（可读写） |
| `frame` | np.ndarray | 当前截图帧（只读） |

**截图方法**

| 方法 | 返回 | 说明 |
|------|------|------|
| `screenshot()` | np.ndarray | 截图并存储至 `_last_screenshot` |
| `get_resolution()` | (int, int) | 返回目标分辨率 `(1280, 720)` |
| `crop_screenshot(area)` | np.ndarray | 裁剪截图至指定区域 |

**按钮检测**

| 方法 | 返回 | 说明 |
|------|------|------|
| `appear(button, offset=0, interval=0)` | bool | 按钮是否出现在当前截图中 |
| `appear_then_click(button, offset=0, interval=0)` | bool | 检测到按钮后点击 |
| `click(target)` | None | 点击 Button / Box / (x,y) 坐标 |

**模板匹配**

| 方法 | 返回 | 说明 |
|------|------|------|
| `find_one(feature_name, threshold=0.85)` | Box or None | 查找单个特征 |
| `find_all(feature_name, threshold=0.85)` | list[Box] | 查找全部匹配 |
| `find_one_and_click(feature_name, threshold=0.85)` | bool | 找到并点击 |
| `wait_feature(feature_name, timeout=10, interval=0.5, threshold=0.85)` | Box or None | 等待特征出现 |
| `wait_and_click_feature(feature_name, timeout=10, threshold=0.85)` | bool | 等待并点击 |

**OCR 方法**

| 方法 | 返回 | 说明 |
|------|------|------|
| `ocr(area, letter, threshold, alphabet)` | str | 区域文字识别 |
| `ocr_digit(area)` | int | 识别数字 |
| `ocr_counter(area)` | (int, int, int) | 识别 `current/total` 格式 |

**控制方法**

| 方法 | 说明 |
|------|------|
| `swipe(x1, y1, x2, y2, duration=0.5)` | 滑动操作 |
| `click_box(box, offset_x=0, offset_y=0)` | 点击 Box 中心 |
| `sleep(seconds)` | 可中断的 sleep |
| `wait_until(condition, timeout=10, interval=0.5)` | 等待条件成立 |
| `get_color(area)` | 获取区域平均颜色 |
| `is_running()` | 检查任务是否应继续运行 |

---

### ScriptTask

```python
from module.task.base_task import ScriptTask
```

线性脚本任务，继承 `TaskBase`。

**执行流程**

```
before_run() → run() → after_run()
```

**可重写方法**

| 方法 | 说明 |
|------|------|
| `run()` | **必须实现**，主逻辑 |
| `before_run()` | 可选，run 之前调用 |
| `after_run()` | 可选，run 之后调用 |
| `execute()` | 完整生命周期，一般不需要重写 |

**示例**

```python
class MyTask(ScriptTask):
    def before_run(self):
        self.screenshot()

    def run(self):
        box = self.find_one('START')
        if box:
            self.click_box(box)

    def after_run(self):
        logger.info('完成')
```

---

### StateTask

```python
from module.task.base_task import StateTask
```

状态循环任务，继承 `TaskBase`。自动执行截图→状态判断→动作的循环。

**执行流程**

```
while is_running():
    screenshot()
    if handle_exit(): break
    handle_states()
```

**可重写方法**

| 方法 | 说明 |
|------|------|
| `handle_states()` | **必须实现**，处理各状态 |
| `handle_exit()` | 可选，返回 True 退出循环 |
| `execute()` | 完整循环，一般不需要重写 |

**示例**

```python
class LoopTask(StateTask):
    def handle_states(self):
        if self.appear_then_click(BTN_A): return
        if self.appear_then_click(BTN_B): return

    def handle_exit(self):
        return self.appear(EXIT_FLAG)
```

---

### TaskExecutor

```python
from module.task.executor import TaskExecutor
```

任务执行引擎，管理任务生命周期。线程安全。

**构造函数**

```python
TaskExecutor(
    device_manager=None,
    config=None,
    exit_event=None,
    feature_set=None,
    global_config=None,
    debug=False,
)
```

**方法**

| 方法 | 说明 |
|------|------|
| `start()` | 启动执行器线程 |
| `stop()` | 停止执行器 |
| `pause()` | 暂停 |
| `resume()` | 恢复 |
| `add_task(task)` | 添加一次性任务 |
| `add_trigger_task(task)` | 添加触发型任务（条件满足时执行） |
| `add_scheduled_task(task, interval_minutes)` | 添加定时任务 |

**属性**

| 属性 | 说明 |
|------|------|
| `is_running` | 是否运行中 |
| `is_paused` | 是否暂停中 |
| `current_task` | 当前正在执行的任务实例 |

---

### TaskScheduler

```python
from module.task.scheduler import TaskScheduler
```

独立的定时任务调度器。

| 方法 | 说明 |
|------|------|
| `add_scheduled_task(task, interval_minutes)` | 添加定时任务 |
| `start()` | 启动调度 |
| `stop()` | 停止调度 |

---

### 异常 (`module.task.exceptions`)

```python
from module.task.exceptions import (
    TaskError, WaitTimeoutError, CaptureError,
    FeatureNotFoundError, TaskDisabledError, FinishedError
)
```

| 异常 | 说明 |
|------|------|
| `TaskError` | 所有任务异常的基类 |
| `WaitTimeoutError` | 等待超时 |
| `CaptureError` | 截图失败 |
| `FeatureNotFoundError` | 模板未找到 |
| `TaskDisabledError` | 任务被禁用 |
| `FinishedError` | 任务正常结束（控制流用途） |

---

## 按钮与模板匹配 (`module.base`)

### Button

```python
from module.base.button import Button
```

基于区域颜色的 UI 按钮检测。

**构造函数**

```python
Button(
    area,      # (ul_x, ul_y, br_x, br_y) 颜色检测区域
    color,     # (r, g, b) 期望的平均颜色
    button=None,  # (ul_x, ul_y, br_x, br_y) 点击区域，默认等于 area
    file=None,    # 素材文件路径
    name=None,    # 按钮名称
)
```

**方法**

| 方法 | 返回 | 说明 |
|------|------|------|
| `appear_on(image, threshold=10)` | bool | 颜色相似度检查（Photoshop 魔棒算法） |
| `match(image, offset=30, threshold=0.85)` | Button or None | 模板匹配 |
| `match_any(image, offset=30, threshold=0.85)` | list[Button] | 多点模板匹配 |
| `load_color(image)` | None | 从截图重新取样颜色 |
| `set_server(server)` | self | 切换多服配置 |

**属性**

| 属性 | 类型 | 说明 |
|------|------|------|
| `area` | tuple | 当前服的 area |
| `color` | tuple | 当前服的 color |
| `button` | tuple | 当前服的点击区域 |
| `name` | str | 按钮名称 |
| `file` | str | 素材文件路径 |

---

### ButtonGrid

```python
from module.base.button import ButtonGrid
```

生成二维 Button 阵列，用于网格化 UI 元素。

```python
ButtonGrid(
    origin,         # (x, y) 左上角坐标
    delta,          # (dx, dy) 按钮间距
    button_shape,   # (w, h) 按钮大小
    grid_shape,     # (cols, rows) 网格尺寸
    name=None,      # 命名模板
)
```

支持 `grid[0, 1]`、`grid[3]` 索引和 `for btn in grid` 迭代。

---

### Template

```python
from module.base.template import Template
```

基于 OpenCV 的模板匹配。支持 PNG 和 GIF（GIF 每帧都会匹配并取最佳结果）。

```python
Template(file)    # file: 模板图片路径
```

**方法**

| 方法 | 返回 | 说明 |
|------|------|------|
| `match(image, similarity=0.85)` | Button or None | 模板匹配 |
| `match_result(image)` | (sim, (x,y)) or None | 返回相似度和位置 |
| `match_multi(image, similarity=0.85)` | list[Button] | 多点匹配，自动合并邻近点 |
| `set_server(server)` | self | 切换多服配置 |

**属性**

| 属性 | 说明 |
|------|------|
| `file` | 当前服的文件路径 |
| `name` | 模板名称（文件名大写） |
| `image` | 预处理后的图片矩阵 |
| `image_binary` | 二值化图片 |
| `image_luma` | 亮度通道 |
| `size` | (width, height) |

**预处理**

子类可重写 `pre_process(image)` 实现自定义预处理。

---

### 装饰器 (`module.base.decorator`)

```python
from module.base.decorator import Config, cached_property, timer
```

**`@Config.when(**kwargs)`**

基于配置值分发不同实现（类似 Alas 的 `@Config.when()`）：

```python
@Config.when(PLATFORM='pc')
def click(self):
    # PC 点击实现

@Config.when(PLATFORM='adb')
def click(self):
    # ADB 点击实现
```

**`@cached_property`**

方法结果缓存为属性，删除 `self.__dict__['attr']` 重新计算。

**`@timer`**

打印函数执行耗时。

---

### 工具函数 (`module.base.utils`)

```python
from module.base.utils import (
    crop, get_color, color_similar, color_similarity,
    load_image, save_image, image_size,
    area_offset, area_pad, area_size, area_limit,
    point_in_area, area_in_area, area_cross_area,
    random_rectangle_point, random_rectangle_vector,
    random_line_segments, random_normal_distribution_int,
    ensure_time, node2location, location2node,
    rgb2luma, color_similarity_2d,
    extract_letters, extract_white_letters,
    color_bar_percentage, get_bbox
)
```

| 函数 | 说明 |
|------|------|
| `crop(image, area)` | 裁剪图片 |
| `get_color(image, area)` | 获取区域平均色 |
| `color_similar(c1, c2, threshold=10)` | Photoshop 魔棒算法判断颜色相似 |
| `color_similarity(c1, c2)` | 计算颜色差异值 |
| `color_similarity_2d(image, color)` | 生成 2D 颜色相似度图（OpenCV 实现） |
| `load_image(file)` | 加载图片返回 RGB ndarray |
| `save_image(image, file)` | 保存图片 |
| `image_size(image)` | 返回 (width, height) |
| `area_offset(area, offset)` | 平移区域 |
| `area_pad(area, pad=10)` | 内缩区域 |
| `area_size(area)` | 区域宽高 |
| `area_limit(area1, area2)` | 限制 area1 在 area2 内 |
| `point_in_area(point, area, threshold=0)` | 点是否在区域内 |
| `area_in_area(area1, area2)` | area1 是否完全在 area2 内 |
| `area_cross_area(area1, area2)` | 两区域是否相交 |
| `random_rectangle_point(area, n=3)` | 区域内随机点（正态分布） |
| `random_rectangle_vector(vector, box, ...)` | 在 box 中随机放置向量 |
| `random_line_segments(p1, p2, n, ...)` | 将线段随机分段 |
| `random_normal_distribution_int(a, b, n=3)` | 正态分布整数 |
| `ensure_time(second, n=3, precision=3)` | 解析时间值（支持 int/tuple/str '10,30'） |
| `node2location('E3')` | 节点名 → (x, y) |
| `location2node((4, 2))` | (x, y) → 节点名 |
| `rgb2luma(image)` | RGB 转灰度 |
| `extract_letters(image, letter, threshold)` | 提取指定颜色文字的二值图 |
| `extract_white_letters(image, threshold)` | 提取白色文字 |
| `color_bar_percentage(image, area, prev_color)` | 颜色进度条百分比 |
| `get_bbox(image)` | 获取非零像素包围盒 |

---

### Timer (`module.base.timer`)

```python
from module.base.timer import Timer
```

| 方法 | 说明 |
|------|------|
| `start()` | 开始计时 |
| `reached()` | 是否超过 limit |
| `reset()` | 重新计时 |
| `wait()` | 等待直到到达 limit |
| `elapsed` (属性) | 已过秒数 |

支持 `with Timer(limit=5) as t:` 上下文管理器。

---

### 其他工具

```python
from module.base.retry import retry           # @retry(tries=3, delay=1)
from module.base.filter import function_drop  # @function_drop(rate=0.5)
from module.base.mask import mask_area, mask_keep_area, overlay_mask
from module.base.resource import Resource
```

---

## 特征检测 (`module.feature`)

### Box

```python
from module.feature.box import Box
```

检测到的特征的包围盒。

**构造函数**

```python
Box(x=0, y=0, width=0, height=0, confidence=0, name='')
```

**属性**

| 属性 | 类型 | 说明 |
|------|------|------|
| `x, y` | int | 左上角坐标 |
| `width, height` | int | 宽高 |
| `confidence` | float | 置信度 (0-1) |
| `name` | str | 特征名称 |
| `center` | (int, int) | 中心点坐标 |
| `area` | (ul_x, ul_y, br_x, br_y) | 区域四元组 |
| `left, top, right, bottom` | int | 四边坐标 |

**方法**

| 方法 | 返回 | 说明 |
|------|------|------|
| `scale(factor_x, factor_y=None)` | Box | 缩放 |
| `offset(dx, dy)` | Box | 偏移 |
| `intersects(other)` | bool | 是否相交 |
| `intersection_area(other)` | int | 相交面积 |
| `contains_point(x, y)` | bool | 是否包含点 |

**Box 工具函数**

```python
from module.feature.box import (
    find_box_by_name, find_boxes_by_name,
    find_highest_confidence_box, sort_boxes,
    relative_box, crop_image,
    average_width, average_height,
    find_boxes_within_boundary, get_bounding_box
)
```

| 函数 | 说明 |
|------|------|
| `find_box_by_name(boxes, name)` | 按名称查找第一个 Box |
| `find_highest_confidence_box(boxes)` | 最高置信度 Box |
| `sort_boxes(boxes, key='x')` | 按 x/y/confidence 排序 |
| `relative_box(x, y, to_x, to_y, sw, sh)` | 比例坐标创建 Box |
| `crop_image(image, box)` | 用 Box 裁剪图片 |
| `average_width(boxes) / average_height(boxes)` | 平均宽高 |
| `find_boxes_within_boundary(boxes, boundary_box)` | 在边界内的 Box |
| `get_bounding_box(boxes)` | 包含所有 Box 的最小 Box |

---

### Feature

```python
from module.feature.feature import Feature
```

图片特征封装。

```python
Feature(mat, name='', x=0, y=0)
# mat:  numpy 图片数组
# name: 特征名称
# x, y: 在屏幕上的偏移
```

| 属性 | 说明 |
|------|------|
| `mat` | numpy 图片数组 |
| `width` | 宽度 |
| `height` | 高度 |

---

### FeatureSet

```python
from module.feature.feature_set import FeatureSet
```

素材管理系统。加载模板图片并提供匹配能力。

**构造函数**

```python
FeatureSet(
    assets_dir='./assets',
    debug=False,
    default_threshold=0.85,
    feature_processor=None,
)
```

**方法**

| 方法 | 返回 | 说明 |
|------|------|------|
| `load_from_directory(directory, recursive=True, pattern='*.png')` | None | 从目录加载 PNG 素材 |
| `load_from_assets_py(module_name, assets_module)` | None | 从 assets.py 模块加载 Button/Template |
| `add_feature(name, image, x=0, y=0)` | None | 手动添加特征 |
| `get_feature(name)` | Feature or None | 按名称获取特征 |
| `find_feature(image, feature_name, threshold=None)` | list[Box] | 查找全部匹配 |
| `find_one(image, feature_name, threshold=None)` | Box or None | 查找最佳匹配 |
| `find_all_features(image, threshold=None)` | dict | 查找全部已注册特征 |
| `count_feature(image, feature_name, threshold=None)` | int | 计数 |
| `has_feature(image, feature_name, threshold=None)` | bool | 是否存在 |
| `clear_cache()` | None | 清空缓存 |

---

## 设备系统 (`module.device`)

### DeviceManager

```python
from module.device.device_manager import DeviceManager
```

统一的设备管理器，管理截图和输入方式。

**构造函数**

```python
DeviceManager(config=None, exit_event=None, global_config=None)
```

**常量**

```python
TARGET_WIDTH = 1280
TARGET_HEIGHT = 720
TARGET_RESOLUTION = (1280, 720)
```

所有截图自动缩放到 1280x720。

**方法**

| 方法 | 返回 | 说明 |
|------|------|------|
| `screenshot()` | np.ndarray | 截图并缩放至 1280x720 |
| `click(x, y)` | bool | 点击 |
| `swipe(x1, y1, x2, y2, duration=0.5)` | bool | 滑动 |
| `send_key(key)` | bool | 发送按键 |

**属性**

| 属性 | 说明 |
|------|------|
| `hwnd_window` | 游戏窗口句柄 |
| `is_pc` | 是否为 PC 模式 |
| `is_adb` | 是否为 ADB 模式 |
| `capture` | 当前截图方法实例 |
| `interaction` | 当前输入方法实例 |

---

### 截图方法

```python
from module.device.screenshot import (
    ScreenshotMethod,        # 基类
    ADBScreenshot,           # ADB screencap
    WindowsGraphicsScreenshot,  # DXGI
    BitBltScreenshot,        # BitBlt
)
```

| 类 | 说明 |
|------|------|
| `ADBScreenshot(serial)` | 通过 ADB exec-out screencap 截图 |
| `WindowsGraphicsScreenshot(hwnd)` | Windows Graphics Capture (DXGI) |
| `BitBltScreenshot(hwnd)` | GDI BitBlt 截图 |

所有截图方法都有 `grab() -> np.ndarray` 方法。

---

### 输入方法

```python
from module.device.control import (
    InteractionMethod,       # 基类
    ADBInteraction,          # ADB input tap
    PostMessageInteraction,  # Win32 PostMessage
    PyDirectInteraction,     # pydirectinput
)
```

| 类 | 说明 |
|------|------|
| `ADBInteraction(serial)` | 通过 ADB shell input 发送点击/滑动 |
| `PostMessageInteraction(hwnd)` | 向窗口发送 WM_LBUTTONDOWN/UP 消息 |
| `PyDirectInteraction()` | 使用 pydirectinput 模拟真实鼠标/键盘 |

所有输入方法都有 `click(x,y)`, `swipe(x1,y1,x2,y2,duration)`, `send_key(key)` 方法。

---

### AppControl

```python
from module.device.app_control import AppControl
```

ADB 应用生命周期控制。

| 方法 | 说明 |
|------|------|
| `launch(package=None, activity=None)` | 启动 App |
| `kill(package)` | 强杀 App |
| `is_running(package)` | 检查 App 是否在运行 |

---

## OCR (`module.ocr`)

### Ocr

```python
from module.ocr.ocr import Ocr
```

核心 OCR 类，支持多引擎。

**构造函数**

```python
Ocr(
    buttons,              # 识别区域 (x1,y1,x2,y2) 或 [area, area, ...]
    name=None,            # 名称
    letter=(255,255,255), # 文字颜色
    threshold=128,        # 二值化阈值
    alphabet=None,        # 限定字符集，如 '0123456789'
    engine='default',     # 引擎: default/cnocr/paddle/rapid
    lang=None,            # 语言
)
```

**方法**

| 方法 | 返回 | 说明 |
|------|------|------|
| `ocr(image)` | list[str] | 执行 OCR，返回每个区域的识别文本 |

**预处理**

自动对每个区域：裁剪 → 灰度化 → 二值化 → 转回 RGB，然后送入引擎。

---

### 专用 OCR 类

```python
from module.ocr.ocr import Digit, DigitCounter, Duration
```

| 类 | 返回 | 说明 |
|------|------|------|
| `Digit` | int | 数字识别，失败返回 0 |
| `DigitCounter` | (int, int, int) | 识别 `14/15`，返回 `(current, remaining, total)` |
| `Duration` | timedelta or None | 识别 `08:00:00` 格式时间 |

---

### OCR 引擎

```python
from module.ocr.engine import OcrEngine
```

| 类方法 | 说明 |
|------|------|
| `OcrEngine.register(name, engine_class)` | 注册引擎 |
| `OcrEngine.create(name='default', lang=None)` | 创建引擎实例 |
| `OcrEngine.available_engines()` | 已注册的引擎列表 |
| `OcrEngine.auto_register()` | 自动检测并注册可用引擎 |

**引擎实现**

```python
from module.ocr.engine.cnocr_engine import CnOcrEngine      # cnocr
from module.ocr.engine.paddle_ocr_engine import PaddleOcrEngine  # PaddleOCR
from module.ocr.engine.rapid_ocr_engine import RapidOcrEngine    # RapidOCR
```

---

### OcrResult / OcrBase

```python
from module.ocr.ocr_result import OcrResult
from module.ocr.ocr_base import OcrBase
```

`OcrResult(text, confidence, box)` — OCR 识别结果
`OcrBase(lang)` — OCR 引擎基类，子类需实现 `ocr(image) -> list[OcrResult]`

---

## 配置系统 (`module.config`)

### AlConfig

```python
from module.config.config import AlConfig
```

JSON 配置文件读取器，支持属性访问和自动保存。

```python
config = AlConfig('my_config')  # 加载 config/my_config.json
print(config.DefaultTask_Device_Platform)  # -> 'auto'
config.DefaultTask_Device_Platform = 'pc'  # 自动标记为已修改
config.save()  # 保存回文件
```

| 方法 | 说明 |
|------|------|
| `load()` | 重新加载 JSON |
| `save()` | 保存修改回 JSON |
| `get_function(name)` | 获取 Function 对象（调度器信息） |
| `get_task_list()` | 获取可用任务名称列表 |

### 配置深层工具

```python
from module.config.deep import deep_get, deep_set, deep_pop, deep_iter, deep_default
```

| 函数 | 说明 |
|------|------|
| `deep_get(d, 'a.b.c', default=None)` | 深层获取 |
| `deep_set(d, 'a.b.c', value)` | 深层设置（自动创建中间节点） |
| `deep_pop(d, 'a.b.c', default=None)` | 深层弹出 |
| `deep_default(d, 'a.b.c', value)` | 不存在时设置默认值 |
| `deep_iter(d, depth=3)` | 深层迭代，返回 (path, value) |

---

## GUI (`module.gui`)

### 启动方式

```bash
# CLI 入口
al-script-gui my_config

# Python 入口
python -m module.gui.launcher my_config
```

### MainWindow

```python
from module.gui.main_window import MainWindow
```

PySide6 主窗口，提供：

- **左侧栏**: 任务列表、Start/Stop/Pause 按钮
- **Task Config 标签**: 可视化配置编辑器
- **Templates 标签**: 模板文件浏览、导入 PNG
- **Debug 标签**: 截图预览 + Box 标注
- **Log 标签**: 实时日志查看
- **Settings 标签**: 主题/语言/路径设置
- **About 标签**: 版本信息

**方法**

| 方法 | 说明 |
|------|------|
| `set_executor(executor)` | 注入 TaskExecutor |

### Communicate（信号总线）

```python
from module.gui.communicate import communicate
```

GUI 组件间通信的中央信号总线。

| 信号 | 参数 | 说明 |
|------|------|------|
| `task_started` | str(config_name) | 任务启动 |
| `task_stopped` | - | 任务停止 |
| `task_paused` | - | 暂停 |
| `task_resumed` | - | 恢复 |
| `new_frame` | np.ndarray | 新截图帧 |
| `new_boxes` | list[Box] | 检测到的 Box |
| `new_log` | str | 日志行 |
| `new_status` | str | 状态变更 |
| `config_changed` | - | 配置被修改 |
| `config_saved` | - | 配置已保存 |
| `quit` | - | 退出应用 |

### OverlayWindow

```python
from module.gui.overlay import OverlayWindow
```

半透明调试叠加层，在游戏窗口上实时渲染 Box 和文字。

### ScreenshotViewer

```python
from module.gui.overlay import ScreenshotViewer
```

截图查看器控件，支持缩放显示和 Box 标注。

---

## 国际化 (`module.i18n`)

```python
from module.i18n import translator, tr, set_language
```

| 函数 | 说明 |
|------|------|
| `tr(key, default=None)` | 翻译 key（全局翻译器） |
| `set_language(lang)` | 切换语言 |
| `translator.available_languages()` | 获取可用语言列表 |

基于 JSON 文件（`module/i18n/{lang}.json`）：

```json
{
    "Start": "开始",
    "Stop": "停止"
}
```

---

## 工具函数 (`module.util`)

### 日志

```python
from module.util.logger import logger, Logger, config_logger
```

| 函数/对象 | 说明 |
|------|------|
| `logger` | 全局 logger（name='al'） |
| `config_logger(logger=None, level=INFO)` | 配置日志（控制台+文件） |
| `Logger.hr(title, level=0)` | 打印分隔线 |
| `Logger.attr(name, text)` | 打印属性行 |
| `Logger.attr_align(name, text, align=20)` | 对齐属性行 |

### 文件路径

```python
from module.util.file import (
    get_root_path, get_toolkit_path, get_python_exe,
    get_git_exe, get_adb_exe, get_path_relative_to_exe,
    delete_if_exists, install_path_isascii
)
```

| 函数 | 说明 |
|------|------|
| `get_root_path()` | al-script 根目录 |
| `get_toolkit_path(subpath='')` | toolkit 目录 |
| `get_python_exe()` | Python 可执行文件路径 |
| `get_git_exe()` | Git 可执行文件路径 |
| `get_adb_exe()` | ADB 可执行文件路径 |
| `get_path_relative_to_exe(path)` | 相对于 exe/cwd 的路径 |
| `install_path_isascii(path)` | 路径是否纯 ASCII |

### Handler / ExitEvent

```python
from module.util.handler import Handler, ExitEvent
```

| 类 | 说明 |
|------|------|
| `ExitEvent` | 线程安全的退出事件，`sleep(seconds)` 在 set 时提前唤醒 |
| `Handler(exit_event, name)` | 退出处理器，支持 `on_stop(callback)` 和 `sleep(seconds)` |

### 进程/窗口

```python
from module.util.process import (
    check_mutex, get_first_gpu_free_memory_mib,
    windows_graphics_available, get_focused_window,
    set_focus_window, get_window_title,
    find_window_by_title, find_window_by_class,
    print_all_windows, get_window_rect, get_client_rect
)
```

| 函数 | 说明 |
|------|------|
| `check_mutex(name)` | 单实例互斥锁 |
| `get_first_gpu_free_memory_mib()` | GPU 空闲显存 (MiB) |
| `windows_graphics_available()` | DXGI 是否可用 |
| `get_focused_window()` | 前台窗口句柄 |
| `find_window_by_title(title, partial=True)` | 按标题找窗口 |
| `find_window_by_class(class_name)` | 按类名找窗口 |
| `print_all_windows()` | 打印所有可见窗口（调试用） |
| `get_window_rect(hwnd)` | 窗口矩形 |
| `get_client_rect(hwnd)` | 客户区矩形 |

### 颜色工具

```python
from module.util.color import (
    mask_white, is_pure_black,
    find_color_rectangles, get_mask_in_color_range,
    color_range_to_bound, calculate_color_percentage,
    count_pixels_in_color_range, average_color, is_color_similar
)
```

| 函数 | 说明 |
|------|------|
| `mask_white(image)` | 白色像素掩膜 |
| `is_pure_black(image, threshold=5)` | 是否几乎全黑 |
| `find_color_rectangles(image, lower, upper)` | 在颜色范围内找矩形 |
| `get_mask_in_color_range(image, lower, upper)` | 获取颜色范围掩膜 |
| `color_range_to_bound(color, range=10)` | 颜色 → (lower, upper) |
| `calculate_color_percentage(image, lower, upper)` | 颜色范围占比 |
| `count_pixels_in_color_range(image, lower, upper)` | 颜色范围像素数 |
| `average_color(image, area=None)` | 平均颜色 |
| `is_color_similar(c1, c2, tolerance=10)` | 两颜色是否相似 |

---

## 开发工具 (`module.dev_tools`)

### button_extract

```python
python -m module.dev_tools.button_extract [--module <name>]
```

从 `assets/default/<module>/` 下的 PNG 自动生成 `assets.py`：

- 普通 PNG → Button（自动提取 area 和 color）
- `TEMPLATE_*.png` → Template
- `*.AREA.png` / `*.COLOR.png` / `*.BUTTON.png` → 覆盖对应属性

---

## App 类 (`module.app`)

```python
from module.app import App
```

应用主类，初始化所有子系统。

```python
app = App(config={
    'config_name': 'template',
    'use_gui': True,
    'debug': False,
    'assets_dir': './assets',
    'check_mutex': True,
})
app.start()    # 启动 GUI 或 CLI 循环
app.stop()     # 停止
app.quit()     # 退出（同 stop）
```

**主要属性**

| 属性 | 类型 | 说明 |
|------|------|------|
| `device_manager` | DeviceManager | 设备管理器 |
| `feature_set` | FeatureSet | 素材集 |
| `task_executor` | TaskExecutor | 任务执行器 |
| `exit_event` | ExitEvent | 退出事件 |
| `handler` | Handler | 处理器 |
| `frame` | np.ndarray | 最新截图 |
