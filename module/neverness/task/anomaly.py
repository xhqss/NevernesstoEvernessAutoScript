"""
AnomalyTask - Automates Anomaly Domain (异象界域) farming.

Inherits NTEOneTimeTask + BaseCombatTask for combat integration.
Supports 4 task types: EXP+Coin, Ability, ARC, Console.
"""

from module.task.exceptions import TaskDisabledError
from module.util.logger import logger

from module.neverness.Labels import Labels
from module.neverness.task.onetime import NTEOneTimeTask
from module.neverness.combat.base import BaseCombatTask, NotInCombatException, CharDeadException


class AnomalyTask(NTEOneTimeTask, BaseCombatTask):
    """Anomaly Domain (异象界域) farming task."""

    # Configuration keys
    CONF_TASK_TYPE = "task_type"
    CONF_EXP_TARGET = "exp_target"
    CONF_ABILITY_ID = "ability_id"
    CONF_ARC_ID = "arc_id"
    CONF_CONSOLE_ID = "console_id"

    # Task type options
    TASK_EXP_COIN = "exp_and_coin"
    TASK_ABILITY = "ability_material"
    TASK_ARC = "arc_material"
    TASK_CONSOLE = "console"

    # EXP sub-types
    EXP_CHAR = "char_exp"
    EXP_ARC = "arc_exp"
    EXP_COIN = "coin"
    EXP_ALL = [EXP_CHAR, EXP_ARC, EXP_COIN]

    # Index ranges
    ABILITY_IDX_RANGE = (1, 5)
    ARC_IDX_RANGE = (1, 5)
    CONSOLE_IDX_RANGE = (1, 6)

    TASK_COST = 40  # stamina per run

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "anomaly_domain"
        self._outer_config = None
        self._setup_defaults()

    def _setup_defaults(self):
        """Initialize default configuration values."""
        self.config.setdefault(self.CONF_TASK_TYPE, self.TASK_EXP_COIN)
        self.config.setdefault(self.CONF_EXP_TARGET, self.EXP_CHAR)
        self.config.setdefault(self.CONF_ABILITY_ID, 1)
        self.config.setdefault(self.CONF_ARC_ID, 1)
        self.config.setdefault(self.CONF_CONSOLE_ID, 1)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self):
        super().run()
        try:
            self.do_run()
        except TaskDisabledError:
            pass
        except Exception as e:
            self.log_error("AnomalyTask error", e)

    def do_run(self, config=None, stamina_target=None):
        """Execute anomaly domain farming.

        Args:
            config: Optional external config dict (used by DailyTask).
            stamina_target: Optional stamina consumption target.
        """
        if config is None:
            config = self.config

        task_type = config.get(self.CONF_TASK_TYPE)
        idx = self._get_sub_idx(config)

        self.info_set("task type", task_type)
        if task_type == self.TASK_EXP_COIN:
            self.info_set("exp target", config.get(self.CONF_EXP_TARGET))
        else:
            self.info_set("item index", f"#{idx + 1}")

        self.log_info(f"start anomaly: type={task_type}, idx={idx + 1}")

        # Phase 1: Open F1 panel and navigate
        self.ensure_main()
        self.log_info("opening F1 panel")
        self.openF1panel()
        self.operate_click(0.0563, 0.4924)
        self.sleep(0.5)

        # Phase 2: Select task type tab
        self.log_info(f"switching to tab: {task_type}")
        tab_positions = {
            self.TASK_EXP_COIN: (0.1703, 0.1528),
            self.TASK_ABILITY: (0.2977, 0.1528),
            self.TASK_ARC: (0.4211, 0.1528),
            self.TASK_CONSOLE: (0.5422, 0.1528),
        }
        pos = tab_positions.get(task_type, (0.1703, 0.1528))
        self.operate_click(pos[0], pos[1])
        self.sleep(0.5)

        # Check stamina
        stamina = self.get_stamina()
        if stamina < self.TASK_COST:
            self.log_warning("not enough stamina, aborting", notify=True)
            return False

        # Phase 3: Teleport to domain
        self.log_info("teleporting to domain")
        self.operate_click(0.9168, 0.2903)
        self.click_traval_button()
        self.wait_in_team_and_world()

        # Phase 4: Walk to interact point
        self.log_info("walking to interact point")
        self.walk_until_interac(raise_if_not_found=True)
        self.wait_until(
            lambda: not self.find_interac(),
            post_action=lambda: self.send_interac(handle_claim=False),
            time_out=10,
        )

        # Wait for stamina icon to confirm scene load
        self.wait_until(
            lambda: self.find_one(Labels.stamina_icon),
            settle_time=0.5,
            time_out=10,
        )

        # Phase 5: Calculate runs
        stamina_units = stamina // self.TASK_COST
        if stamina_target is not None:
            target_units = (stamina_target + self.TASK_COST - 1) // self.TASK_COST
            stamina_units = min(stamina_units, target_units)
            self.info_set("stamina target", stamina_target)

        double_count = stamina_units // 2
        single_count = stamina_units % 2
        self.log_info(f"runs: double={double_count}, single={single_count}")

        # Phase 6: Select sub-index
        self.log_info(f"selecting item #{idx + 1}")
        self._click_sub_idx(idx)
        self.sleep(0.25)

        # Phase 7: Enter domain and combat
        self.log_info("entering domain")
        self.operate_click(0.8008, 0.9042)

        for i in range(double_count + single_count):
            double = i < double_count
            self.wait_in_team()
            self.sleep(1)
            self._do_combat_and_claim(double)
            self.sleep(2)
            if i < double_count + single_count - 1:
                self.operate_click(0.621, 0.864)

        # Exit
        self.operate_click(0.381, 0.861)
        self.log_info("anomaly domain done")
        return True

    # ------------------------------------------------------------------
    # Combat + Claim
    # ------------------------------------------------------------------

    def _do_combat_and_claim(self, double: bool):
        """Execute one combat run and claim rewards."""
        self.log_info("starting combat")
        self.walk_until_combat(run=True, delay=1)
        self.combat_once()

        self.log_info("combat done, walking to treasure")
        self.walk_to_treasure()
        self.send_interac(handle_claim=False)

        claims = self.find_all_claim()
        self.log_info(f"found {len(claims)} claim buttons")
        if not claims:
            self.log_warning("no claim buttons found")
            return

        if double:
            box = max(claims, key=lambda x: x.x)
        else:
            box = min(claims, key=lambda x: x.x)

        btn = box.copy(x_offset=int(box.width * 3))
        self.operate_click(btn)

    # ------------------------------------------------------------------
    # Sub-index selection
    # ------------------------------------------------------------------

    def _click_sub_idx(self, idx: int):
        """Click on the n-th item in the domain list."""
        y = 0.1715 + idx * (0.2806 - 0.1715)
        self.operate_click(0.0852, y)

    def _get_sub_idx(self, config) -> int:
        """Get the 0-based sub-index from config."""
        task_type = config.get(self.CONF_TASK_TYPE)
        if task_type == self.TASK_EXP_COIN:
            target = config.get(self.CONF_EXP_TARGET)
            if target in self.EXP_ALL:
                return self.EXP_ALL.index(target)
            return 0
        elif task_type == self.TASK_ABILITY:
            return self._config_validate(config, self.ABILITY_IDX_RANGE, self.CONF_ABILITY_ID) - 1
        elif task_type == self.TASK_ARC:
            return self._config_validate(config, self.ARC_IDX_RANGE, self.CONF_ARC_ID) - 1
        elif task_type == self.TASK_CONSOLE:
            return self._config_validate(config, self.CONSOLE_IDX_RANGE, self.CONF_CONSOLE_ID) - 1
        return 0

    def get_next_sub_idx(self, config) -> int:
        """Get the next sub-index for auto-cycling."""
        idx = self._get_sub_idx(config)
        task_type = config.get(self.CONF_TASK_TYPE)
        if task_type == self.TASK_EXP_COIN:
            return (idx + 1) % 3
        ranges = {
            self.TASK_ABILITY: self.ABILITY_IDX_RANGE,
            self.TASK_ARC: self.ARC_IDX_RANGE,
            self.TASK_CONSOLE: self.CONSOLE_IDX_RANGE,
        }
        if task_type in ranges:
            r = ranges[task_type]
            return (idx + 1) % (r[1] - r[0] + 1)
        return 0

    def _config_validate(self, config, index_range, key) -> int:
        """Clamp a config value within its valid range."""
        lo, hi = index_range
        val = config.get(key, 1)
        valid = max(lo, min(val, hi))
        if val != valid:
            config[key] = valid
        return valid
