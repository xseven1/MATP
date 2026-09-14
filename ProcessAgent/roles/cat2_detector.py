# ProcessAgent/roles/cat2_detector.py
from ProcessAgent.actions import FOL2Tptp
from ProcessAgent.detectors.detect_cat2 import DetectCat2
from metagpt.roles import Role
from metagpt.logs import logger
from metagpt.schema import Message

class Cat2Detector(Role):
    name: str = "Cat2Detector"
    profile: str = "Cat2ErrorDetector"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([DetectCat2])
        self._watch([FOL2Tptp])

    async def _act(self) -> Message:
        logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo
        msg = self.get_memories(k=1)[0]
        result = await todo.run(msg.content)
        return Message(content=result, role=self.profile, cause_by=type(todo))