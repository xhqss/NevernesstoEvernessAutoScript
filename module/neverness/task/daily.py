"""
DailyTask - Automates daily activities: mail, dailies, activity rewards, battle pass.
"""

from datetime import datetime
from typing import Callable, List, Tuple

from module.task.exceptions import FeatureNotFoundError, TaskDisabledError
from module.feature.box import Box, find_color_rectangles
from module.util.logger import logger

from module.neverness.Labels import Labels
from module.neverness.task.onetime import NTEOneTimeTask
from module.neverness.task.base import BaseNTETask
from module.neverness.util import image as iu

# Default text-white color for reward detection
text_white_color = {
    "r": (210, 255),
    "g": (210, 255),
    "b": (210, 255),
}


class DailyTask(NTEOneTimeTask, BaseNTETask):
    """Daily task executor for Neverness-to-Everness."""

    # Configuration keys
    CONF_CLAIM_MAIL = "claim_mail"
    CONF_COMPLETE_DAILY = "complete_daily_activities"
    CONF_CLAIM_ACTIVITY = "claim_activity_rewards"
    CONF_CLAIM_BP = "claim_battle_pass_rewards"
    CONF_AUTO_CYCLE_SUB_TASK = "auto_cycle_sub_task"
    DAILY_STAMINA_TARGET = "target_stamina"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "daily_task"
        self.support_schedule_task = True
        self.task_status = {"success": [], "failed": [], "skipped": [], "pending": []}
        self.current_task_key = None

        # Register config keys (framework-agnostic)
        self._setup_config()

    def _setup_config(self):
        """Initialize default configuration values."""
        self.config.setdefault(self.CONF_CLAIM_MAIL, True)
        self.config.setdefault(self.CONF_COMPLETE_DAILY, True)
        self.config.setdefault(self.CONF_CLAIM_ACTIVITY, True)
        self.config.setdefault(self.CONF_CLAIM_BP, True)
        self.config.setdefault(self.CONF_AUTO_CYCLE_SUB_TASK, False)
        self.config.setdefault(self.DAILY_STAMINA_TARGET, 180)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self):
        super().run()
        try:
            self._do_run()
        except TaskDisabledError:
            pass
        except Exception as e:
            self._handle_exception(e)

    def _do_run(self):
        """Execute the daily task main flow."""
        self._logged_in = False
        self.ensure_main()
        self.log_info("start daily task")

        tasks: List[Tuple[str, Callable]] = [
            (self.CONF_CLAIM_MAIL, self._claim_mail),
            (self.CONF_COMPLETE_DAILY, self._complete_daily_activities),
            (self.CONF_CLAIM_ACTIVITY, self._claim_activity_rewards),
            (self.CONF_CLAIM_BP, self._claim_battle_pass_rewards),
        ]

        self._reset_task_status(tasks)

        for key, func in tasks:
            self._execute_task(key, func)

        self.ensure_main()
        self._print_result()
        self.log_info("daily task finished", notify=True)

    # ------------------------------------------------------------------
    # Task execution helpers
    # ------------------------------------------------------------------

    def _execute_task(self, key: str, func: Callable):
        """Execute a single sub-task with config gating and status tracking."""
        self.task_status["pending"].remove(key)

        if not self.config.get(key, True):
            self.task_status["skipped"].append(key)
            return

        self.current_task_key = key
        self.log_info(f"start sub-task: {key}")
        self.ensure_main()

        result = func()
        if result is False:
            self.task_status["failed"].append(key)
            self.screenshot()
            self.log_info(f"sub-task failed: {key}")
            return

        self.task_status["success"].append(key)
        self.log_info(f"sub-task done: {key}")
        self.current_task_key = None

    def _reset_task_status(self, tasks):
        self.task_status = {
            "success": [],
            "failed": [],
            "skipped": [],
            "pending": [t[0] for t in tasks],
        }

    def _print_result(self):
        self.info_set("success", str(self.task_status["success"]))
        self.info_set("failed", str(self.task_status["failed"]))
        self.info_set("skipped", str(self.task_status["skipped"]))
        logger.info(
            f"daily result: success={self.task_status['success']}, "
            f"failed={self.task_status['failed']}, "
            f"skipped={self.task_status['skipped']}"
        )

    def _handle_exception(self, e):
        self.screenshot()
        if self.current_task_key:
            self.info_set("last failed task", self.current_task_key)
        self._print_result()
        raise e

    # ------------------------------------------------------------------
    # Sub-task: Claim Mail
    # ------------------------------------------------------------------

    def _claim_mail(self) -> bool:
        """Open mail panel and claim all mail rewards."""
        self.log_info("claiming mail rewards")

        def action():
            self.openESCpanel()
            self.operate_click(0.8707, 0.8736)
            self.sleep(0.5)
            return self._wait_panel(Labels.mail_panel)

        result = _retry_on_action(action, self.ensure_main)
        if not result:
            self.log_error("cannot find mail panel", notify=True)
            raise FeatureNotFoundError("cannot find mail panel")
        self.operate_click(0.1289, 0.9299)
        self.sleep(1)
        return True

    # ------------------------------------------------------------------
    # Sub-task: Complete Daily Activities
    # ------------------------------------------------------------------

    def _complete_daily_activities(self) -> bool:
        """Run anomaly tasks to complete daily activity requirements."""
        self.log_info("completing daily activities via AnomalyTask")
        from module.neverness.task.anomaly import AnomalyTask

        task = AnomalyTask(
            config=self.config,
            device_manager=self._device_manager,
            exit_event=self._exit_event,
        )
        stamina_target = self.config.get(self.DAILY_STAMINA_TARGET, 180)
        ret = task.do_run(self.config, stamina_target=stamina_target)
        if ret and self.config.get(self.CONF_AUTO_CYCLE_SUB_TASK):
            self._shift_idx(task)
        return ret

    def _shift_idx(self, task):
        """Auto-cycle to the next sub-task index."""
        task_type = self.config.get(task.CONF_TASK_TYPE)
        next_idx = task.get_next_sub_idx(self.config)
        if task_type == task.TASK_EXP_COIN:
            self.config[task.CONF_EXP_TARGET] = task.EXP_ALL[next_idx]
        else:
            conf_key = {
                task.TASK_ABILITY: task.CONF_ABILITY_ID,
                task.TASK_ARC: task.CONF_ARC_ID,
                task.TASK_CONSOLE: task.CONF_CONSOLE_ID,
            }.get(task_type)
            if conf_key:
                self.config[conf_key] = int(next_idx + 1)

    # ------------------------------------------------------------------
    # Sub-task: Claim Activity Rewards
    # ------------------------------------------------------------------

    def _claim_activity_rewards(self) -> bool:
        """Claim F1 activity rewards."""
        self.log_info("claiming activity rewards")

        def action():
            self.openF1panel()
            self.operate_click(0.0551, 0.3833)
            self.sleep(0.5)
            return self._wait_panel(Labels.f1_activity_panel)

        result = _retry_on_action(action, self.ensure_main)
        if not result:
            self.log_error("cannot find activity panel")
            return False

        if self.find_one(Labels.f1_activity_mission):
            self.operate_click(0.2348, 0.7653)
            self.sleep(2)

        if target := self._get_activity_reward_box():
            self.operate_click(target)
            self.sleep(1)
        else:
            self.log_error("cannot find activity reward box")
            return False
        return True

    def _get_activity_reward_box(self):
        box = self.get_box_by_name(Labels.box_f1_activity_reward)
        mask = iu.binarize_bgr_by_brightness(self._last_screenshot, threshold=245, to_bgr=False)
        mask = iu.morphology_mask(mask, kernel_size=7, to_bgr=True)
        reward_boxes = find_color_rectangles(
            mask, color_range=text_white_color, min_width=10, min_height=10,
            box=box, threshold=0.6
        )
        if reward_boxes:
            return max(reward_boxes, key=lambda b: b.x)
        return None

    # ------------------------------------------------------------------
    # Sub-task: Claim Battle Pass Rewards
    # ------------------------------------------------------------------

    def _claim_battle_pass_rewards(self) -> bool:
        """Claim F2 battle pass (period) rewards."""
        self.log_info("claiming battle pass rewards")

        def action():
            self.openF2panel()
            self.operate_click(0.0570, 0.3451)
            self.sleep(0.5)
            return self._wait_panel(Labels.f2_mission_panel)

        result = _retry_on_action(action, self.ensure_main)
        if not result:
            self.log_error("cannot find battle pass panel")
            return False

        self.operate_click(0.8777, 0.8187)
        self.sleep(1)
        self.operate_click(0.0570, 0.2333)
        self.sleep(1)
        self.operate_click(0.6934, 0.8229)
        self.sleep(1)
        return True


# ------------------------------------------------------------------
# Helper: retry pattern
# ------------------------------------------------------------------

def _retry_on_action(action: Callable, reset_action: Callable = None, attempts: int = 3):
    """Retry an action up to N attempts, calling reset_action between retries."""
    result = None
    for _ in range(attempts):
        result = action()
        if result:
            return result
        if reset_action is not None:
            reset_action()
    return result
