from ProcessAgent.constant import Constants
from metagpt.actions import Action
from metagpt.logs import logger
import re
import json
import os

PROMPT = """Question:
[Question_Input]
Conclusion:
[Conclusion_Input]
Student Solution:
[Solution_Input]
"""

class Evaluate(Action):
    
    name: str = "Evaluate" # Baseline action

    # The input to the action is preferably a regular string
    async def run(self, instruction: str):

        path = os.path.join(Constants.OUTPUT_DIR,Constants.EVALUATE_RES_FILE_NAME)
        if os.path.exists(path):
            code_text = Constants.read(path)
            if "Final Judgement" not in code_text:
                os.remove(path)
            else:
                self.savejsonres(code_text)
                return path

        dataset_name, premises_str, conclusion_str, steps_str = instruction.split(Constants.DELIMITER)

        msg = PROMPT.replace("[Question_Input]",premises_str)
        msg = msg.replace("[Conclusion_Input]",conclusion_str)
        msg = msg.replace("[Solution_Input]",steps_str)

        PROMPT_TEMPLATE = Constants.get_prompt(dataset_name,Constants.BASELINE)
        prompt = PROMPT_TEMPLATE.replace("[instruction]", msg)


        logger.info(prompt)
        # TODO
        rsp = await self._aask(prompt) # Call LLM api generation
        code_text = rsp

        Constants.write(path,code_text)
        logger.info(f"Reasoning result is saved to {path}")
        
        self.savejsonres(code_text)
        return path

    def savejsonres(self,code_text):
        try:
            res_dict = self.postprocess(code_text)
            # The extracted detection results are saved in [Constants.OUTPUT_DIR]/evaluate_res.json
            json_path = os.path.join(Constants.OUTPUT_DIR,Constants.EVALUATE_RES_JSON_FILE_NAME)
            Constants.write_json(json_path,res_dict)
            logger.info(f"Reasoning result in JSON is saved to {json_path}")
        except Exception as e:
            logger.warning(f"text2json Error : {e}")

    def postprocess(self,code_text):
        # Extract the True/False labels of Step
        # step_by_step_part
        step_res = code_text.split("Final Judgement")[0].split('\n')
        steps_judge_str = []
        # step_index = 0
        for ss in step_res:
            ss = ss.replace("*","").replace("#","").replace("-","").strip()
            match = re.search(r'Step (\d+): (\w+)', ss)
            if match:
                # step_index = int(match.group(1))
                # max_steps = max(max_steps,step_index)
                first_step_label = match.group(2)
                steps_judge_str.append(ss)
            else:
                if len(steps_judge_str)>0:
                    steps_judge_str[-1] = steps_judge_str[-1] + " " + ss

        task_info = Constants.read_json(os.path.join(Constants.OUTPUT_DIR,Constants.TASK_INFO_FILE_NAME))
        max_steps = len(task_info["reasoning_steps"])
        step_labels = ["Unknown" for i in range(max_steps)]
        for ss in steps_judge_str:
            match = re.search(r'Step (\d+):.*?\b(True|False)\b', ss, re.DOTALL)
            if match:
                step_number = int(match.group(1))
                if step_number>max_steps:
                    continue
                truth_value = match.group(2)
                print(f"Step {step_number}: {truth_value}")
                step_labels[step_number-1] = truth_value
                # step_labels.append(truth_value)
    
        # Extract the result of **Final Judgement**
        final_judgement_match = re.search(r'Final Judgement:.*?\b(Yes|No)\b', code_text.replace("*",""), re.DOTALL)
        final_judgement = final_judgement_match.group(1) if final_judgement_match else None
        has_valid_proof_path_label=None
        if "Yes" in final_judgement:
            has_valid_proof_path_label=True
        elif "No" in final_judgement:
            has_valid_proof_path_label= False
    
        return dict(step_correctness_label=step_labels,has_valid_proof_path_label=has_valid_proof_path_label)
