import os
from datetime import datetime
from metagpt.logs import logger
import json
import spacy
import re

nlp = spacy.load("en_core_web_sm")

class Constants:

    FOLIO = "folio"
    PROOFWRITER = "proofwriter"
    PRONTOQA_OOD = "prontoqa_ood"

    NL2FOL = "nl2fol"
    BASELINE = "baseline"

    P_INFER_C = "p_infer_c"
    P_INFER_S = "p_infer_s"
    S_INFER_C = "s_infer_c"

    STEP_VALID = "Valid"
    STEP_UNVALID = "Unvalid"

    VAMPIRE_ANSWER_TRUE="True"
    VAMPIRE_ANSWER_FALSE="False"
    VAMPIRE_ANSWER_UNCERTAIN="Unknown"
    VAMPIRE_ANSWER_ERROR="Error"
    SEMANTIC_ERROR = "Semantic_Error"
    VAMPIRE_RUN_RES_DIR="vampire_run_res"
    VAMPIRE_BIN_PATH = "/mnt/c/Users/udaya/vampire/build/vampire"

    DELIMITER = " &xxx& "
    INPUT_TOKEN = "[instruction]"
    PREMISES_TOKEN = "Premises:"
    CONCLUSIONS_TOKEN = "Conclusions:"

    # The separator used to extract the fol
    FOL_PREDICATE_FLAG = "predicate:"
    FOL_PREMISE_FLAG = "premise:"
    FOL_CONCLUSION_FLAG ="conclusion:"
    FOL_PREDICATES_FLAG = "predicates:"
    FOL_PREMISES_FLAG = "premises:"
    FOL_CONCLUSIONS_FLAG ="conclusions:"
    FOL_STEP_FLAG ="steps:"
    GENERATION_TIMES = 3

    # Some output filenames
    TASK_INFO_FILE_NAME = "task_info.json"
    NL2FOL_FILE_NAME = "nl2fol.txt"
    FOL2TPTP_FILE_NAME = "fol2tptp.json"
    CHECK_RES_FILE_NAME = "check_res.json"
    EVALUATE_RES_FILE_NAME = "evaluate_res.txt"
    EVALUATE_RES_JSON_FILE_NAME = "evaluate_res.json"

    OUTPUT_DIR = None
    DATE=None
    TIME=None
    TASK_NAME=None
    PROJECT_NAME=None

    WITH_FEEDBACK=False

    @staticmethod
    def create_output_dir():
        """Create the output folder and update to OUTPUT_DIR"""

        # Get the current directory
        current_directory = os.getcwd()

        # Construct the workspace folder path
        output_directory = os.path.join(current_directory, "workspace")
        # workspace folder is created if it does not exist
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
        # Construct the workspace/output folder path
        output_directory = os.path.join(output_directory, "output")
        # workspace/output folder is created if it does not exist
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
        
        # Gets the current date and time
        now = datetime.now()
        
        # update DATE and TIME
        Constants.DATE = now.strftime("%y%m%d")  # yymmdd
        Constants.TIME = now.strftime("%H%M%S")  # hhmmss

        # If project name is not defined, the workshop/output/date is used as the project path
        if Constants.PROJECT_NAME!=None:
            output_directory = os.path.join(output_directory, Constants.PROJECT_NAME)
        else:
            output_directory = os.path.join(output_directory, Constants.DATE)
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

        # If task name is not defined, the workshop/output/project_name/time is used as the task path
        if Constants.TASK_NAME!=None:
            output_directory = os.path.join(output_directory, Constants.TASK_NAME)
        else:
            output_directory = os.path.join(output_directory, Constants.TIME)
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

        # update output_dir
        Constants.OUTPUT_DIR = output_directory

        logger.info(f"Constants.OUTPUT_DIR: {Constants.OUTPUT_DIR}, Constants.DATE: {Constants.DATE}, Constants.TIME: {Constants.TIME}")


    @staticmethod
    def update_task_name(name:str):
        Constants.TASK_NAME = name
    

    @staticmethod
    def update_project_name(name:str):
        Constants.PROJECT_NAME = name
    

    @staticmethod
    def get_prompt(dataset_name:str,type_name:str,with_feedback:bool=False):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # The prompts for nl2fol and baseline are in the prompt directory on the same level as the file
        # prompt file name is [proofwriter, prontoqa_ood, folio]_[nl2fol, baseline].txt
        if with_feedback:
            file_path = os.path.join(base_dir, "prompt", f"{dataset_name}_{type_name}_with_feedback.txt")
        else:
            file_path = os.path.join(base_dir, "prompt", f"{dataset_name}_{type_name}.txt")
        prompt = ""
        if os.path.exists(file_path):
            with open(file_path,'r') as f:
                prompt = f.read()
        return prompt


    @staticmethod
    def read_json(path:str):
        ddict = dict()
        if os.path.exists(path):
            with open(path,'r',encoding="utf8") as f:
                ddict = json.load(f)
        else:
            logger.warning(f"file {path} doesn't exist")
        return ddict
    
    @staticmethod
    def read(path:str):
        text = ""
        if os.path.exists(path):
            with open(path,'r') as f:
                text = f.read()
        else:
            logger.warning(f"file {path} doesn't exist")
        return text
    
    @staticmethod
    def write(path:str,text:str):
        with open(path,'w') as f:
            f.write(text)

    @staticmethod
    def write_json(path:str,ddict):
        with open(path,'w',encoding="utf8") as f:
            json.dump(ddict,f,indent=4,ensure_ascii=False)


    @staticmethod 
    def filter_str(string:str):
        """ Filter inference steps that are not clearly stated (to be improved) """
        ss = string.lower()
        if len(ss)==0 or " " not in ss:
            return False

        # TODO: Optimization is needed.
        # key_word = ["there is", "conclusion", "contradict", "information", "conclude", " rule ", " know ", "this ", " we ", "necessarily", "confirm", "however", " rule"," imply ","evidence"]
        key_word = ["premises:","there is", "contradict", "no information", "necessarily", "confirm", "evidence","necessity","therefore","false","however","conclusion"]
        for key in key_word:
            if key in ss:
                return False

        return True


    @staticmethod
    def filter_step(steps:list,conclusion:str):
        # Cut out useless reasoning steps
        filter_steps = []
        # last_idx = 0
        for i in range(len(steps)):
            item = steps[i]
            item = item.replace('\n','').strip()
            # Completely repeated steps are excluded
            if len(item)==0 or item in filter_steps:
                steps[i] = None
            # Eliminate some ambiguous statements
            elif Constants.filter_str(item):
                filter_steps.append(item)
                # last_idx = i
            else:
                steps[i] = None

        filter_steps.append(conclusion)

        return steps, filter_steps
    

    @staticmethod
    def add_index_to_list(ll:list):
        for i in range(len(ll)):
            ll[i] = f"({i+1}) " + ll[i]
        return ll


    @staticmethod
    def campare_list(old_reasoning_steps:list, now_reasoning_steps:list):
        old_reasoning_steps_1 =[item for item in old_reasoning_steps if item]
        now_reasoning_steps_1 =[item for item in now_reasoning_steps if item] 

        if len(old_reasoning_steps_1)!=len(now_reasoning_steps_1):
            return False
        else:
            for i in range(len(now_reasoning_steps_1)):
                if old_reasoning_steps_1[i]!=now_reasoning_steps_1[i]:
                    return False
        return True


    @staticmethod
    def remove_numbered_prefixes(text):
        cleaned_text = re.sub(r'\s*[\(\[]?\d+[\)\.\]]\s*', '\n', text.strip())
        return cleaned_text.strip()

    
    @staticmethod
    def extract_logical_sentences(text):
        print(f"context: {text}\n")
        if len(text)==0:
            return 0,[]

        # get reasoning answer and steps
        if re.search(r'Answer:.*?\bTrue\b', text, re.IGNORECASE | re.DOTALL):
            answer = 1
        elif re.search(r'Answer:.*?\bFalse\b', text, re.IGNORECASE | re.DOTALL):
            answer = -1
        else:
            answer = 0
        
        cleaned_text = re.sub(r'Answer:.*?\b(True|False)\b', '', text, flags=re.IGNORECASE | re.DOTALL)
        thought_text = cleaned_text.replace("Thoughts:","").strip()

        thought_list = [t.replace("*","").replace("-", "").strip() for t in thought_text.split('\n') if len(t.strip())>0]
        reasoning_steps = []
        for t in thought_list:
            t = t.replace(", so ",". ")
            t= t.replace(" because ",". ")
            t= t.replace(" therefore ",". therefore ")
            t= t.replace("; ",". ")
            doc = nlp(t)
            for sent in doc.sents:
                clean_sent = Constants.remove_numbered_prefixes(sent.text.strip())
                if len(clean_sent)<3 or clean_sent in reasoning_steps:
                    continue
                reasoning_steps.append(clean_sent)
                # if sent.text not in reasoning_steps:
                #     reasoning_steps.append(sent.text.strip())
        reasoning_steps_str = '\n'.join(reasoning_steps)
        print(f"answer: {answer}\nreasoning_steps: {reasoning_steps_str}\n\n")
        return answer, reasoning_steps