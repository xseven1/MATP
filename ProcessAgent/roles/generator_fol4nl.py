from ProcessAgent.actions import NL2FOL
from metagpt.roles import Role
from metagpt.logs import logger
from metagpt.schema import Message
from metagpt.actions import UserRequirement

class GeneratorFOLFromNL(Role):
    name: str = "GeneratorFOLFromNL"
    profile: str = "GenerateFOLFromNL"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._watch([UserRequirement])
        self.set_actions([NL2FOL])

    async def _act(self) -> Message:
        logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo

        msg = self.get_memories(k=1)[0]
        code_text = await todo.run(msg.content)
        msg = Message(content=code_text, role=self.profile, cause_by=type(todo))

        return msg