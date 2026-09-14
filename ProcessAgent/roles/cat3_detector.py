# ProcessAgent/roles/cat3_detector.py
from ProcessAgent.actions import VampireRun
from ProcessAgent.detectors.detect_cat3 import DetectCat3
from metagpt.roles import Role
from metagpt.logs import logger
from metagpt.schema import Message

class Cat3Detector(Role):
    name: str = "Cat3Detector"
    profile: str = "Cat3ErrorDetector"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([DetectCat3])
        self._watch([VampireRun])

    async def _act(self) -> Message:
        logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo
        msg = self.get_memories(k=1)[0]
        result = await todo.run(msg.content)
        return Message(content=result, role=self.profile, cause_by=type(todo))