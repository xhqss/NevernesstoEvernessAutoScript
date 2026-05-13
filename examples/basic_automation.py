"""
Basic automation example using al-script framework.
Demonstrates ScriptTask with button detection and clicking.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from module.task.base_task import ScriptTask, StateTask
from module.base.button import Button
from module.feature.box import Box
from module.util.logger import logger


class MyFirstTask(ScriptTask):
    """
    A simple task that demonstrates the ScriptTask pattern.

    In a real game automation scenario:
    1. Take a screenshot
    2. Look for a button
    3. If found, click it
    4. Wait for the next screen
    """

    def run(self):
        logger.hr('MyFirstTask', level=0)

        # Take initial screenshot
        self.screenshot()
        if self._last_screenshot is None:
            logger.error('No screenshot available - check device connection')
            return

        # Define a button (area and expected color)
        my_button = Button(
            area=(500, 300, 600, 350),
            color=(255, 200, 100),
            button=(500, 300, 600, 350),
            name='MY_BUTTON'
        )

        # Check if button appears
        if self.appear(my_button):
            logger.info('Button found! Clicking...')
            self.click(my_button)
            self.sleep(1)
        else:
            logger.info('Button not found')

        # Find a feature using template matching
        if self._feature_set:
            box = self.find_one('TEMPLATE_NAME', threshold=0.85)
            if box:
                logger.info(f'Found template at {box.center}')
                self.click_box(box)
                self.sleep(0.5)

        logger.info('Task completed!')


class MyStateTask(StateTask):
    """
    A state-machine task using the Alas-style state loop pattern.
    This is the preferred pattern for complex automation.
    """

    def handle_states(self):
        """Process each state in order."""

        # State 1: Check for main menu
        if self.appear_then_click(MAIN_MENU_BUTTON):
            logger.info('Main menu -> clicked')
            return

        # State 2: Check for battle button
        if self.appear_then_click(BATTLE_BUTTON):
            logger.info('Battle -> clicked')
            return

        # State 3: Check for confirmation
        if self.appear_then_click(CONFIRM_BUTTON):
            logger.info('Confirmed')
            return

    def handle_exit(self):
        """Return True when the task should end."""
        return self.appear(EXIT_CONDITION_BUTTON)


# Example button definitions (would come from assets.py in a real project)
MAIN_MENU_BUTTON = Button(
    area=(100, 600, 250, 680),
    color=(255, 255, 255),
    button=(100, 600, 250, 680),
    name='MAIN_MENU'
)

BATTLE_BUTTON = Button(
    area=(900, 400, 1100, 500),
    color=(255, 200, 50),
    button=(900, 400, 1100, 500),
    name='BATTLE'
)

CONFIRM_BUTTON = Button(
    area=(500, 500, 700, 550),
    color=(100, 200, 255),
    button=(500, 500, 700, 550),
    name='CONFIRM'
)

EXIT_CONDITION_BUTTON = Button(
    area=(50, 50, 150, 100),
    color=(255, 0, 0),
    name='EXIT'
)


if __name__ == '__main__':
    from module.app import App

    # Create app (CLI mode for testing)
    app = App(config={
        'config_name': 'template',
        'use_gui': False,
        'debug': True,
    })

    # Run a simple task
    task = MyFirstTask(
        config=app.config,
        device_manager=app.device_manager,
        exit_event=app.exit_event,
        handler=app.handler
    )
    task.feature_set = app.feature_set
    task.execute()

    app.stop()
