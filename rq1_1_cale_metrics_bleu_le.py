from fol_metrics.eval import eval_pert
from ProcessAgent.constant import Constants
import random

def get_folio_fol_fb_le(res_check_path, test_path):
    fol_list = []
    
    dataset = Constants.read_json(res_check_path)
    for task in dataset:
        if "idx" not in task.keys():
            continue
        cate = task["cate"]
        if "Error" in cate:
            continue
        gt_fol = task["premises_gt_fol"]
        fol = task["premise:_fol"]
        if len(gt_fol)!=len(fol):
            continue
        for i in range(len(gt_fol)):
            fol_list.append(dict(true_fol=gt_fol[i].strip(),pred_fol=fol[i]["fol"].strip()))

    Constants.write_json(test_path,fol_list)
    res = eval_pert(test_path)
    fol_list.append(res)
    Constants.write_json(test_path,fol_list)

    return res

def get_proofwriter_fol_fb_le(res_path, test_path, gt_fol_path):
    gt_fol_dataset = Constants.read_json(gt_fol_path)
    res_dataset = Constants.read_json(res_path)
    fol_list = []
    for task in res_dataset:
        if "idx" not in task.keys():
            continue
        task_name = task["idx"]
        if task_name not in gt_fol_dataset.keys():
            continue
        fol = task["premise:_fol"]
        if len(fol)!=len(gt_fol_dataset[task_name]):
            continue
        for i in range(len(fol)):
            gt = gt_fol_dataset[task_name][i]["gt_fol"].strip()
            pre = fol[i]["fol"].strip()
            if gt=="":
                continue
            fol_list.append(dict(true_fol=gt,pred_fol=pre))
    
    Constants.write_json(test_path,fol_list)
    res = eval_pert(test_path)
    fol_list.append(res)
    Constants.write_json(test_path,fol_list)

    return res

def get_prontoqa_ood_fol_fb_le(res_path, test_path, gt_fol_path):
    gt_fol_dataset = Constants.read_json(gt_fol_path)
    res_dataset = Constants.read_json(res_path)
    fol_list = []
    for task in res_dataset:
        if "idx" not in task.keys():
            continue
        task_name = task["idx"]
        if task_name not in gt_fol_dataset.keys():
            continue
        fol = task["premise:_fol"]
        if len(fol)!=len(gt_fol_dataset[task_name]):
            continue
        for i in range(len(fol)):
            gt = gt_fol_dataset[task_name][i]["gt_fol"].strip()
            pre = fol[i]["fol"].strip()
            if gt=="":
                continue
            fol_list.append(dict(true_fol=gt,pred_fol=pre))
    
    Constants.write_json(test_path,fol_list)
    res = eval_pert(test_path)
    fol_list.append(res)
    Constants.write_json(test_path,fol_list)

    return res


# (Constants.FOLIO,"folio/folio_train")
# (Constants.PRONTOQA_OOD,"prontoqa_ood/prontoqa_ood_4hop")
datasets = [(Constants.PROOFWRITER, "proofwriter/proofwriter_dev"),
(Constants.PRONTOQA_OOD,"prontoqa_ood/prontoqa_ood_4hop"),
(Constants.FOLIO,"folio/folio_train")]

# "gpt3.5","gpt4o","llama318b","llama3170b","deepseekr1",
# "DeepseekR1Qwen32b","qwen32b","qwen257b" "DeepseekR1Qwen7b" "gpto4mini"
models = ["gpt3.5","gpt4o","llama318b","llama3170b","deepseekr1",
"DeepseekR1Qwen32b","qwen32b","qwen257b","DeepseekR1Qwen7b","gpto4mini"]

results = []
for model in models:
    for i in range(len(datasets)):
        dataset_name, dataset1 = datasets[i]
        gt_fol_path = f"workspace/dataset_v_last/RQ1_1/{dataset1}_gt_fol.json"
        res_path = f"workspace/dataset_v_last/RQ1_RQ3/{dataset1}_{model}_check_res.json"
        test_path = f"workspace/dataset_v_last/RQ1_1/{dataset1}_{model}.json"
        if dataset_name==Constants.PROOFWRITER:
            res = get_proofwriter_fol_fb_le(res_path, test_path, gt_fol_path)
        elif dataset_name==Constants.PRONTOQA_OOD:
            res = get_prontoqa_ood_fol_fb_le(res_path, test_path, gt_fol_path)
        else:
            res = get_folio_fol_fb_le(res_path, test_path)
        # print(f"{model}---{dataset_name}\n{res}\n")
        results.append((model,dataset_name,res["Bleu_mean"],res["LE_mean"]))

for item in results:
    print(item)
