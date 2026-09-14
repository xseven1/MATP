import os
import time
import copy
import argparse
import asyncio

from metagpt.logs import logger
from metagpt.team import Team
from metagpt.context import Context
from metagpt.schema import Message

from ProcessAgent.roles import GrammerChecker, GeneratorFOLFromNL, ConverterFOL2tptp
from ProcessAgent.roles.cat1_detector import Cat1Detector
from ProcessAgent.roles.cat2_detector import Cat2Detector
from ProcessAgent.roles.cat3_detector import Cat3Detector
from ProcessAgent.constant import Constants

# ---------------------------------------------------------------------------
# Bedrock ARN / inference-profile monkeypatch
#
# metagpt.provider.bedrock_api.BedrockLLM.__init__ calls get_provider(),
# which was imported directly into that module's namespace at import time
# ("from metagpt.provider.bedrock.bedrock_provider import get_provider").
# Patching metagpt.provider.bedrock.bedrock_provider.get_provider does NOT
# affect that local binding, so the patch must target
# metagpt.provider.bedrock_api.get_provider directly.
# ---------------------------------------------------------------------------
import metagpt.provider.bedrock_api as bedrock_api

_original_get_provider = bedrock_api.get_provider


def _extract_provider_key(model_id: str) -> str:
    """
    Handles plain model IDs, regional-prefixed IDs, and full inference-profile ARNs.
    e.g. 'arn:aws:bedrock:us-east-1:...:inference-profile/us.anthropic.claude-sonnet-4-6'
         -> 'anthropic.claude-sonnet-4-6'
    """
    # If it's an ARN, take everything after the last '/'
    if model_id.startswith("arn:"):
        model_id = model_id.rsplit("/", 1)[-1]
    # Strip known regional inference-profile prefixes
    for prefix in ("us.", "eu.", "apac."):
        if model_id.startswith(prefix):
            model_id = model_id[len(prefix):]
            break
    return model_id


def _patched_get_provider(model_id: str):
    return _original_get_provider(_extract_provider_key(model_id))


bedrock_api.get_provider = _patched_get_provider


async def matp(input_task_json_path, check_res_path, dataset_name, limit=None):

    # input tasks
    task_list = Constants.read_json(input_task_json_path)
    if len(task_list) == 0:
        logger.warning("Length of input is 0!")
        return

    if limit is not None:
        task_list = task_list[:limit]
        logger.info(f"--limit set: processing only the first {limit} example(s).")

    # process agent
    investment = 3.0
    n_round = 6   # was 3 — bumped for 3 added parallel-watcher roles
    team = Team()
    team.hire(
        [
            GeneratorFOLFromNL(),  # NL2FOL
            ConverterFOL2tptp(),   # FOL2TPTP
            GrammerChecker(),      # Logical Verification
            Cat1Detector(),        # watches NL2FOL — I-A live
            Cat2Detector(),        # watches FOL2Tptp — I-B/II-A/II-B live
            Cat3Detector(),        # watches VampireRun — I-A/III-A-ii live
        ]
    )

    check_res = []
    output_name = input_task_json_path.rstrip(".json")
    Constants.update_project_name(output_name)

    for task in task_list:

        task_name = task["idx"]
        premises = task["premises"]
        conclusion = task["question"][0] if isinstance(task["question"], list) else task["question"]

        # Exclude tasks that can be obtained by one-step reasoning
        if conclusion in premises or conclusion.replace(" not", "") in premises:
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
        res_path = os.path.join(Constants.OUTPUT_DIR, Constants.CHECK_RES_FILE_NAME)
        while generation_idx < Constants.GENERATION_TIMES and error_flag:
            team.invest(investment=investment)
            team.run_project(dataset_name)
            result = await team.run(n_round=n_round)
            generation_idx += 1

            # if execution fail or error happen, need to regeneration
            res_dict = Constants.read_json(res_path)
            if len(res_dict) == 0 or (len(res_dict) != 0 and "Error" in res_dict["cate"]):
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
            task[key] = res_dict[key]
        check_res.append(task)

    Constants.write_json(check_res_path, check_res)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process dataset parameters.")

    parser.add_argument("--input_task_json_path", type=str, required=True, help="Path to input JSON")
    parser.add_argument("--check_res_path", type=str, required=True, help="Check results output path")
    parser.add_argument("--dataset_name", choices=[Constants.PRONTOQA_OOD, Constants.PROOFWRITER, Constants.FOLIO], required=True, help="Choose dataset")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N examples (for a cheap test run).")
    args = parser.parse_args()

    asyncio.run(matp(**vars(args)))