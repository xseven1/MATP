from ProcessAgent.actions import FOL2Tptp,NL2FOL
from metagpt.roles import Role
from metagpt.logs import logger
from metagpt.schema import Message

class ConverterFOL2tptp(Role):
    name: str = "ConverterFOL2tptp"
    profile: str = "ConverterFOL2tptp"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([FOL2Tptp])
        self._watch([NL2FOL])

    async def _act(self) -> Message:
        logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo

        msg = self.get_memories(k=1)[0]
        code_text = await todo.run(msg.content)
        msg = Message(content=code_text, role=self.profile, cause_by=type(todo))

        return msg