from ProcessAgent.constant import Constants
from metagpt.actions import Action
from metagpt.logs import logger
import json
import os
import re

class FOL2Tptp(Action):
        
    name: str = "FOL2Tptp"

    async def run(self, path: str)->str:

        # The input path is the fol save file that was initially generated
        txt = Constants.read(path).lower().strip('\n')

        info_list = []

        # Extracting useful fol information # TODO
        ll = txt.split('\n')
        tptp_dict = dict()
        tptp_dict[Constants.FOL_PREMISE_FLAG] = list()
        tptp_dict[Constants.FOL_CONCLUSION_FLAG] = list()
        flag = Constants.FOL_PREMISE_FLAG
        for item in ll:
            item = item.strip()
            if len(item)==0:
                continue
            elif item in [Constants.FOL_PREMISE_FLAG,Constants.FOL_PREMISES_FLAG]:
                flag = Constants.FOL_PREMISE_FLAG
                continue
            # conclusion part
            elif item in [Constants.FOL_CONCLUSION_FLAG,Constants.FOL_CONCLUSIONS_FLAG]:
                flag = Constants.FOL_CONCLUSION_FLAG
                continue
            elif "(" not in item or ")" not in item:
                continue

            # get statement(FOL) and reference(NL)
            if " ::: " in item:
                statement, reference = item.split(" ::: ",1)
                # Filter the case where the sequence number is output first
                statement = re.sub(r"^\(\d+\) ", "", statement)
            else:
                # Filtering outputs cases where there is no reply to the reference statement
                statement = re.sub(r"^\(\d+\) ", "", item)
                reference = ""

            # nl 2 fol
            new_statement = FOL2Tptp.convert_to_tptp(statement)
            tptp_dict[flag].append(dict(ref=reference,fol=statement,tptp=new_statement))

        # save nl-fol-tptp to task infomation
        task_info_path = os.path.join(Constants.OUTPUT_DIR,Constants.TASK_INFO_FILE_NAME)
        task = Constants.read_json(task_info_path)
        # premises
        task[Constants.FOL_PREMISE_FLAG+"_fol"] = tptp_dict[Constants.FOL_PREMISE_FLAG]
        # conclusion
        task[Constants.FOL_CONCLUSION_FLAG+"_fol"] = tptp_dict[Constants.FOL_CONCLUSION_FLAG][-1]
        conclusion_fol = tptp_dict[Constants.FOL_CONCLUSION_FLAG][-1]["fol"].strip()
        # steps: exclude the conclusion repeat
        steps =  tptp_dict[Constants.FOL_CONCLUSION_FLAG][:-1]
        step_key = Constants.FOL_STEP_FLAG+"_fol"
        task[step_key] = []
        filter_reasoning_steps_idx=0
        task["final_filter_reasoning_steps"] = []
        for idx in range(len(steps)):
            step_fol = steps[idx]["fol"].strip()
            if step_fol==conclusion_fol or "¬"+step_fol==conclusion_fol or step_fol=="¬"+conclusion_fol or "(" not in step_fol:
                while not task["filter_reasoning_steps"][filter_reasoning_steps_idx]:
                    filter_reasoning_steps_idx+=1
                # task["filter_reasoning_steps"][filter_reasoning_steps_idx] = None
            else:
                task[step_key].append(steps[idx])
                while not task["filter_reasoning_steps"][filter_reasoning_steps_idx]:
                    filter_reasoning_steps_idx+=1
                task["final_filter_reasoning_steps"].append(task["filter_reasoning_steps"][filter_reasoning_steps_idx])
                filter_reasoning_steps_idx+=1
        Constants.write_json(task_info_path,task)

        path = os.path.join(Constants.OUTPUT_DIR,Constants.FOL2TPTP_FILE_NAME)
        Constants.write_json(path,tptp_dict)

        logger.info(f"The content of converting FOL to TPTP has been saved to path: {path}")

        return path
    
    @staticmethod
    def replace_exist_forall(statement:str)->str:
        """
        Replace quantifiers ∀x with ![X]: and ∃x with ?[X]:, and convert variables to uppercase.
        """
        # Replace ∀x with ![X]:
        statement = re.sub(r'∀([a-z])', lambda m: f"![{m.group(1).upper()}]:", statement)
        # Replace ∃x with ?[X]:
        statement = re.sub(r'∃([a-z])', lambda m: f"?[{m.group(1).upper()}]:", statement)
        # Replace variables (a-z) with uppercase versions
        statement = re.sub(r'\b([a-z])\b', lambda m: m.group(1).upper(), statement)
        return statement

    @staticmethod
    def replace_xor(expr:str)->str:
        """
        Replace ⊕ (xor) in the input expression with (~expr1 & expr2) | (expr1 & ~expr2).
        """
        while '⊕' in expr:
            # Find the ⊕ operator and its operands
            parts = expr.split('⊕', 1)

            # Extract the left operand
            left = parts[0].strip()
            len_left = len(left)
            stack = []
            left_start = 0
            for idx in range(len_left-1,-1,-1):
                if left[idx] == ")":
                    stack.append(")")
                elif left[idx] == "(" and len(stack)!=0 and stack[-1]==")":
                    stack.pop()
                elif left[idx] == "(" and len(stack)==0:
                    left_start = idx+1
                    break
                else:
                    continue
            left = left[left_start:]
            # print(left)

            # Extract the right operand
            right = parts[1].strip()
            len_right = len(right)
            stack = []
            right_end = len_right
            for idx in range(len_right):
                if right[idx] == "(":
                    stack.append("(")
                elif right[idx] == ")" and len(stack)!=0 and stack[-1]=="(":
                    stack.pop()
                elif right[idx] == ")" and len(stack)==0:
                    right_end = idx
                    break
                else:
                    continue
            right = right[:right_end]
            # print(right)

            xor_replacement = f"((~({left}) & ({right})) | (({left}) & ~({right})))"
            # xor_replacement = f"xor({left}, {right})"
            expr = expr.replace(f"{left} ⊕ {right}", xor_replacement, 1)
            # print(expr)
        return expr

    @staticmethod
    def convert_to_tptp(statement:str)->str:

        statement = statement.replace('∧','&')
        statement = statement.replace('∨','|')
        statement = statement.replace('¬','~')
        statement = statement.replace('→','=>')
        statement = statement.replace('↔','<=>')
        statement = statement.replace('↔','<=>')
        statement = statement.replace('≠','!=')
        statement = FOL2Tptp.replace_exist_forall(statement)
        statement = FOL2Tptp.replace_xor(statement)

        return statement     