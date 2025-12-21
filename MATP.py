import os
import copy
import argparse
import asyncio

from metagpt.logs import logger
from metagpt.team import Team
from metagpt.context import Context
from metagpt.schema import Message

from ProcessAgent.roles import GrammerChecker, GeneratorFOLFromNL, ConverterFOL2tptp
from ProcessAgent.constant import Constants


async def matp(input_task_json_path, check_res_path, dataset_name):
    
    # input tasks
    task_list = Constants.read_json(input_task_json_path)
    if len(task_list)==0:
        logger.waring("Length of input is 0!")
        return

    # process agent
    investment = 3.0
    n_round = 3
    team = Team()
    team.hire(
        [
            GeneratorFOLFromNL(), # NL2FOL
            ConverterFOL2tptp(), # FOL2TPTP
            GrammerChecker(), # Logical Verification
        ]
    )

    check_res = []
    output_name = input_task_json_path.rstrip(".json")
    Constants.update_project_name(output_name)

    for task in task_list:
    
        premises = task["premises"]
        conclusion = task["conclusion"]

        # Exclude tasks that can be obtained by one-step reasoning
        if conclusion in premises or conclusion.replace(" not","") in premises:
            logger.warning(f"{task_name} can be verified by one step.")
            continue

        # update OUTPUT_DIR
        Constants.update_task_name(task_name)
        Constants.create_output_dir()

        # save task init info file
        task_info_path = os.path.join(Constants.OUTPUT_DIR, Constants.TASK_INFO_FILE_NAME)
        if not os.path.exists(task_info_path):
            Constants.write_json(task_info_path, task)
        else:
            old_task = Constants.read_json(task_info_path)
            for key in task.keys():
                old_task[key] = task[key]
            Constants.write_json(task_info_path, old_task)

        error_flag = True
        generation_idx = 0
        res_path = os.path.join(Constants.OUTPUT_DIR,Constants.CHECK_RES_FILE_NAME)
        while generation_idx < Constants.GENERATION_TIMES and error_flag:
            team.invest(investment=investment)
            team.run_project(dataset_name)
            result = await team.run(n_round=n_round)
            generation_idx += 1
            
            # if execution fail or error happen, need to regeneration
            res_dict = Constants.read_json(res_path)
            if len(res_dict)==0 or (len(res_dict)!=0 and "Error" in res_dict["cate"]):
                nl2fol_file_path = os.path.join(Constants.OUTPUT_DIR, Constants.NL2FOL_FILE_NAME)
                if os.path.exists(nl2fol_file_path):
                    os.remove(nl2fol_file_path)
                    time.sleep(5)
            else:
                error_flag = False

        # get check result
        res_dict = Constants.read_json(res_path)
        logger.info(res_dict)
        for key in res_dict.keys():
            task[key] =res_dict[key]
        check_res.append(task)
    
    Constants.write_json(check_res_path,check_res)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process dataset parameters.")
    
    parser.add_argument("--input_task_json_path", type=str, required=True, help="Path to input JSON")
    parser.add_argument("--check_res_path", type=str, required=True, help="Check results output path")
    parser.add_argument("--dataset_name", choices=[Constants.PRONTOQA_OOD, Constants.PROOFWRITER, Constants.FOLIO], required=True, help="Choose dataset")
    args = parser.parse_args()
    
    asyncio.run(matp(**vars(args)))
