from ProcessAgent.constant import Constants
from metagpt.actions import Action
from metagpt.logs import logger
import subprocess
import json
import os
import re
import shutil
import copy

class VampireRun(Action):
    
    name: str = "VampireRun"

    async def run(self, path: str):
        tptp_dict = Constants.read_json(path)
        if len(tptp_dict)==0:
            return
        
        # Used to store the results of the vampire execution
        vampire_run_res_dir = os.path.join(Constants.OUTPUT_DIR,Constants.VAMPIRE_RUN_RES_DIR)
        if os.path.exists(vampire_run_res_dir):
            shutil.rmtree(vampire_run_res_dir)
        os.mkdir(vampire_run_res_dir)

        # get task info
        task = Constants.read_json(os.path.join(Constants.OUTPUT_DIR,Constants.TASK_INFO_FILE_NAME))
        c_gt_label = task["label"]
        llm_answer = task["reasoning_answer"]
        
        c_gt_res = None
        if c_gt_label == 1:
            c_gt_res = Constants.VAMPIRE_ANSWER_TRUE
        elif c_gt_label == -1:
            c_gt_res = Constants.VAMPIRE_ANSWER_FALSE
        else:
            c_gt_res = Constants.VAMPIRE_ANSWER_UNCERTAIN
        
        AnswerCorrect = None
        if c_gt_label==llm_answer:
            AnswerCorrect = True
        else:
            AnswerCorrect = False
        
        premise_list = task[Constants.FOL_PREMISE_FLAG+"_fol"]
        step_list = task[Constants.FOL_STEP_FLAG+"_fol"]
        conclusion = task[Constants.FOL_CONCLUSION_FLAG+"_fol"]

        cate = None

        # check extraction and gt_label
        p_infer_c_res = self.verify_single_step(premise_list,conclusion,Constants.P_INFER_C)
        if p_infer_c_res == Constants.VAMPIRE_ANSWER_ERROR:
            cate = Constants.VAMPIRE_ANSWER_ERROR
            logger.warning("Error in p_infer_c")
            # return "Error in p_infer_c"
        elif p_infer_c_res!=c_gt_res:
            cate = Constants.SEMANTIC_ERROR
            logger.warning(f"gt_label({c_gt_res}) != p_infer_c_res({p_infer_c_res})")
        
        # check p=>s_i get `p_infer_s_label`
        p_infer_s_label = []
        step_num = len(step_list)
        for i in range(step_num):
            step = step_list[i]
            step_res = self.verify_single_step(premise_list,step,f"{Constants.P_INFER_S}_{i+1}")
            if step_res == Constants.VAMPIRE_ANSWER_ERROR:
                cate = Constants.VAMPIRE_ANSWER_ERROR
                logger.warning(f"Error in p_infer_s_{i+1}")
                # return f"Error in p_infer_s_{i}"
            p_infer_s_label.append(step_res)

        # # check has_valid_proof_path_label # TODO
        # s_temp = []
        # for i in range(len(step_list)):
        #     if p_infer_s_label[i]==Constants.VAMPIRE_ANSWER_TRUE:
        #         s_temp.append(step_list[i])

        # check has_valid_proof_path_label
        s_valid = [None for i in range(step_num)]
        s_temp = []
        for i in range(len(step_list)):
            if p_infer_s_label[i]==Constants.VAMPIRE_ANSWER_TRUE:
                res = self.verify_single_step(s_temp,step_list[i],f"{Constants.S_INFER_C}_{i+1}")
                if res==Constants.VAMPIRE_ANSWER_UNCERTAIN:
                    s_temp.append(step_list[i])
                    s_valid[i] = Constants.STEP_VALID
                    continue
            s_valid[i] = Constants.STEP_UNVALID
            s_temp.append(None)
        
        has_valid_proof_path_res = self.verify_single_step(s_temp,conclusion,f"has_proof_path_check")
        has_valid_proof_path_label = False
        if has_valid_proof_path_res==c_gt_res:
            has_valid_proof_path_label = True

        # get cate
        if not cate:
            cate = self.get_cate(AnswerCorrect,p_infer_s_label,has_valid_proof_path_label)
        
        # save check results
        res_dict = dict(AnswerCorrect=AnswerCorrect,step_correctness_label=p_infer_s_label,has_valid_proof_path_label=has_valid_proof_path_label,cate=cate)
        for key in task.keys():
            res_dict[key] = task[key]
        res_path = os.path.join(Constants.OUTPUT_DIR,Constants.CHECK_RES_FILE_NAME)
        Constants.write_json(res_path,res_dict)
        logger.info(str(res_dict))

        return res_path

    def get_cate(self,AnswerCorrect,step_correctness_label,has_proof_path_label):
        has_false_step = False
        if Constants.VAMPIRE_ANSWER_FALSE in step_correctness_label or Constants.VAMPIRE_ANSWER_UNCERTAIN in step_correctness_label:
            has_false_step = True

        if AnswerCorrect:
            # Has a valid proof path
            if has_proof_path_label:
                if not has_false_step:
                    return "T1"
                else:
                    return "T2"
            # Has a invalid proof path
            else:
                if not has_false_step:
                    return "T3"
                else:
                    return "T4"
        else:
            # predicted answer is wrong
            if not has_false_step:
                return "F1"
            else:
                return "F2"


    def verify_single_step(self,premise_list,conclusion,type_name):
        vampire_run_res_dir = os.path.join(Constants.OUTPUT_DIR,Constants.VAMPIRE_RUN_RES_DIR)

        tptp_list = []
        premise_id=0
        for premise in premise_list:
            if premise==None:
                continue
            reference = premise["ref"]
            statement = premise["fol"]
            new_statement = premise["tptp"]
            premise_id+=1
            fof = f"% {reference}\n% {statement}\nfof(premise_{premise_id}, axiom, {new_statement}).\n"
            tptp_list.append(fof)
        
        reference = conclusion["ref"]
        statement = conclusion["fol"]
        new_statement = conclusion["tptp"]

        fof = f"% {reference}\n% {statement}\nfof(conclusion_{type_name}, conjecture, {new_statement}).\n"
        tptp_list.append(fof)
        tptp_path = os.path.join(vampire_run_res_dir,f"{type_name}.p")
        tptp_res_path = os.path.join(vampire_run_res_dir,f"{type_name}.txt")
        with open(tptp_path,'w') as f:
            f.write('\n'.join(tptp_list))
        
        neg_fof = f"% {reference}\n% {statement}\nfof(conclusion_{type_name}, conjecture, ~({new_statement})).\n"
        tptp_list[-1]=neg_fof
        negative_tptp_path = os.path.join(vampire_run_res_dir,f"negative_{type_name}.p")
        negative_tptp_res_path = os.path.join(vampire_run_res_dir,f"negative_{type_name}.txt")
        with open(negative_tptp_path,'w') as f:
            f.write('\n'.join(tptp_list))
        
        return VampireRun.process(Constants.VAMPIRE_BIN_PATH,tptp_path,tptp_res_path,negative_tptp_path,negative_tptp_res_path)
    

    @staticmethod
    def process(vampire_bin_path: str, tptp_path: str, tptp_res_path:str, negative_tptp_path:str, negative_tptp_res_path:str):

        # tptp_path
        result = VampireRun.run_vampire(vampire_bin_path, tptp_path, tptp_res_path)
        # negative_tptp_path
        negative_result = VampireRun.run_vampire(vampire_bin_path, negative_tptp_path, negative_tptp_res_path)

        if result == "" or negative_result == "":
            return Constants.VAMPIRE_ANSWER_ERROR
        
        if result == "refutation" and negative_result == "refutation":
            return Constants.VAMPIRE_ANSWER_ERROR

        if result == "refutation":
            return Constants.VAMPIRE_ANSWER_TRUE

        if negative_result == "refutation":
            return Constants.VAMPIRE_ANSWER_FALSE

        return Constants.VAMPIRE_ANSWER_UNCERTAIN


    @staticmethod
    def run_vampire(vampire_bin_path: str, tptp_path: str, output_path: str="") -> str:
        command = [vampire_bin_path,"-t","5", tptp_path]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=10)

            if output_path!="":
                with open(output_path,"w") as f:
                    f.write(result.stdout)
        
            termination_reason = re.search(r"Termination reason: (\w+)", result.stdout)

            if termination_reason is not None:
                return termination_reason.group(1).lower().strip()
            
            logger.warning(f"{command}: could not find termination reason")
            return ""

        except subprocess.TimeoutExpired:
            logger.warning(f"{command}: timed out")
            return ""
        except subprocess.CalledProcessError as e:
            logger.warning(f"{command} failed with error output: \n{e.stdout}")
            if output_path!="":
                with open(output_path,"w") as f:
                    f.write(e.stdout)
            # logger.warning(f"{command} failed with error code: {e.returncode}")
            return ""