# ProcessAgent/roles/cat1_detector.py
from ProcessAgent.actions import NL2FOL
from ProcessAgent.detectors.detect_cat1 import DetectCat1
from metagpt.roles import Role
from metagpt.logs import logger
from metagpt.schema import Message

class Cat1Detector(Role):
    name: str = "Cat1Detector"
    profile: str = "Cat1ErrorDetector"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([DetectCat1])
        self._watch([NL2FOL])

    async def _act(self) -> Message:
        logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo
        msg = self.get_memories(k=1)[0]
        result = await todo.run(msg.content)
        return Message(content=result, role=self.profile, cause_by=type(todo))