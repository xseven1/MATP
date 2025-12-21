from ProcessAgent.actions import VampireRun,FOL2Tptp
from metagpt.roles import Role
from metagpt.logs import logger
from metagpt.schema import Message

class GrammerChecker(Role):
    name: str = "GrammerChecker"
    profile: str = "GrammerCheckerForTPTP"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([VampireRun])
        self._watch([FOL2Tptp])


    async def _act(self) -> Message:
        logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo

        msg = self.get_memories(k=1)[0]
        code_text = await todo.run(msg.content)
        msg = Message(content=code_text, role=self.profile, cause_by=type(todo))

        return msg