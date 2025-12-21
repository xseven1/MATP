from ProcessAgent.constant import Constants
from metagpt.actions import Action
from metagpt.logs import logger
import re
import json
import os
import time
import copy

class NL2FOL(Action):

    name: str = "NL2FOL"

    async def run(self, dataset_name: str):
        prompt = NL2FOL.build_prompt(dataset_name)

        # If OUTPUT_DIR/nl2fol.txt already exists, it will not be generated again
        path = os.path.join(Constants.OUTPUT_DIR, Constants.NL2FOL_FILE_NAME)
        # if os.path.exists(path):
        #   return path

        logger.info(prompt)

        rsp = None
        for attemp in range(5):
          try:
            rsp = await self._aask(prompt)
            break
            # logger.info(f"usage: {rsp.usage}")
          except Exception as e:
            logger.warning(f"api request error ({attemp+1}/5): {e}")
            time.sleep(3)
        
        Constants.write(path,rsp)
        logger.info(f"The content of converting NL to FOL has been saved to path: {path}")

        return path

    @staticmethod
    def build_prompt(dataset_name:str):

        task_info_path = os.path.join(Constants.OUTPUT_DIR, Constants.TASK_INFO_FILE_NAME)
        task = Constants.read_json(task_info_path)
        premises = [item.strip() for item in task["premises"]]
        conclusion = task["question"][0].strip()
        reasoning_steps = task["reasoning_steps"]
        
        # answer, reasoning_steps = Constants.extract_logical_sentences(task["content"])
        # task["reasoning_steps"] = reasoning_steps
        # task["reasoning_answer"] = answer

        # Filtering irrelevant steps
        # The steps are the same size as the original, and the unrelated steps are set to NULL
        # The filter_steps contains only filtered reasoning steps, and the last step is always conclusion
        steps, filter_steps = Constants.filter_step(copy.deepcopy(reasoning_steps),conclusion)

        if "filter_reasoning_steps" in task.keys():
            flag = Constants.campare_list(task["filter_reasoning_steps"],steps)
            if not flag:
                # regeneration!
                nl2fol_file_path = os.path.join(Constants.OUTPUT_DIR, Constants.NL2FOL_FILE_NAME)
                if os.path.exists(nl2fol_file_path):
                    os.remove(nl2fol_file_path)
        
        task["filter_reasoning_steps"] = steps

        # update task_info for filter_reasoning_steps
        Constants.write_json(task_info_path, task)

        premises = Constants.add_index_to_list(copy.deepcopy(premises))
        filter_steps = Constants.add_index_to_list(copy.deepcopy(filter_steps))
        premises_str = '\n'.join(premises)
        conclusions_str = '\n'.join(filter_steps)

        # last time res is error
        res_path = os.path.join(Constants.OUTPUT_DIR,Constants.CHECK_RES_FILE_NAME)
        res_dict = Constants.read_json(res_path)
        last_time_nl2fol_res = ""
        if len(res_dict)!=0 and "Error" in res_dict["cate"]:
          last_time_nl2fol_res = Constants.read(os.path.join(Constants.OUTPUT_DIR, Constants.NL2FOL_FILE_NAME))

        # with_feedback_or_no_feedback
        if len(last_time_nl2fol_res)>0 and Constants.WITH_FEEDBACK:
          PROMPT_TEMPLATE = Constants.get_prompt(dataset_name,Constants.NL2FOL,True)
          msg = f"{Constants.PREMISES_TOKEN}\n" + premises_str + f"\n{Constants.CONCLUSIONS_TOKEN}\n" + conclusions_str
          prompt = PROMPT_TEMPLATE.replace("[instruction]", msg)
          prompt = prompt.replace("[feedback]",last_time_nl2fol_res)
          return prompt
        else:
          PROMPT_TEMPLATE = Constants.get_prompt(dataset_name,Constants.NL2FOL)
          msg = f"{Constants.PREMISES_TOKEN}\n" + premises_str + f"\n{Constants.CONCLUSIONS_TOKEN}\n" + conclusions_str
          prompt = PROMPT_TEMPLATE.replace("[instruction]", msg)
          return prompt





