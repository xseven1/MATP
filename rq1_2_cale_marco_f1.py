from ProcessAgent.constant import Constants
import random
from sklearn.metrics import f1_score

def cale_marco_f1_score():

    dataset = Constants.read_json(res_path)
    baseline_deepseekr1_dataset = Constants.read_json(baseline_deepseekr1_path)
    baseline_gpt4o_dataset = Constants.read_json(baseline_gpt4o_path)


    label = dict()
    label["True"]=0
    label["False"]=1
    label["Unknown"]=2

    our = []
    baseline_deepseekr1 = []
    baseline_gpt4o = []
    gt = []

    for i in range(len(dataset)):
        task = dataset[i]
        baseline_deepseekr1_task = baseline_deepseekr1_dataset[i]
        baseline_gpt4o_task = baseline_gpt4o_dataset[i]

        if "idx" not in task.keys():
            continue
        if baseline_deepseekr1_task["idx"]!=task["idx"] or baseline_gpt4o_task["idx"]!=task["idx"]:
            print("Error!")
            print(task["idx"])
            print(baseline_deepseekr1_task["idx"])
            print(baseline_gpt4o_task["idx"])
            return
        # print()

        for ll in task["step_correctness_label"]:
            our.append(label[ll])
        for ll in task["step_correctness_label_manual_annotation"]:
            gt.append(label[ll])
        for ll in baseline_deepseekr1_task["step_correctness_label"]:
            baseline_deepseekr1.append(label[ll])
        for ll in baseline_gpt4o_task["step_correctness_label"]:
            baseline_gpt4o.append(label[ll])
        
        if len(our) == len(gt) and len(gt)==len(baseline_deepseekr1) and len(gt)==len(baseline_gpt4o):
            continue
        else:
            print(model_name)
            print(task["idx"])
            print(f"our_len: {len(our)}")
            print(f"basline_deepseekr1_len: {len(baseline_deepseekr1)}")
            print(f"basline_gpt4o_len: {len(baseline_gpt4o)}")
            print(f"gt_len: {len(gt)}")
            print("Len Error")
            return None
    # print(gt[:10])
    # print(our[:10])
    # print(baseline[:10])

    our_f1 = f1_score(gt, our, average='macro')
    baseline_gpt4o_f1 = f1_score(gt, baseline_gpt4o, average='macro')
    baseline_deepseekr1_f1 = f1_score(gt, baseline_deepseekr1, average='macro')
    print(f"{dataset_name}_{model_name}")
    print(f"our marco F1 Score: {our_f1}")
    print(f"baseline_gpt4o marco F1 Score: {baseline_gpt4o_f1}")
    print(f"baseline_deepseekr1 marco F1 Score: {baseline_deepseekr1_f1}")


    # return dict(dataset_name=dataset_name,model_name=model_name,our_f1=our_f1,baseline_f1=baseline_f1)
    return [dataset_name,model_name,our_f1,baseline_gpt4o_f1,baseline_deepseekr1_f1]
    
    

# (Constants.FOLIO,"folio/folio_train")
# (Constants.PRONTOQA_OOD,"prontoqa_ood/prontoqa_ood_4hop")
# (Constants.PROOFWRITER, "proofwriter/proofwriter_dev")
datasets = [(Constants.PRONTOQA_OOD,"prontoqa_ood/prontoqa_ood_4hop"),
(Constants.PROOFWRITER, "proofwriter/proofwriter_dev"),
(Constants.FOLIO,"folio/folio_train")]

# "gpt3.5","gpt4o","llama318b","llama3170b","deepseekr1",
# "DeepseekR1Qwen32b","qwen32b","qwen257b" "DeepseekR1Qwen7b" "gpto4mini"
models = ["gpt3.5","gpt4o","llama318b","llama3170b","qwen257b",
"qwen32b","DeepseekR1Qwen7b","DeepseekR1Qwen32b","deepseekr1","gpto4mini"]

results = []
folio_all = [0,0,0]
proofwriter_all = [0,0,0]
prontoqa_all = [0,0,0]

for model_name in models:
    for dataset in datasets:
        dataset_name = dataset[1]
        res_path = f"workspace/dataset_v_last/RQ1_2/{dataset_name}_{model_name}_manual_annotation.json"
        baseline_gpt4o_path = f"workspace/dataset_v_last/RQ1_2/{dataset_name}_{model_name}_baseline_gpt4o.json"
        baseline_deepseekr1_path = f"workspace/dataset_v_last/RQ1_2/{dataset_name}_{model_name}_baseline_deepseekr1.json"
        res = cale_marco_f1_score()
        results.append(res)

for item in results:
    print(item)
    if item:
        if item[0]=="folio/folio_train":
            folio_all[0]+=item[2]
            folio_all[1]+=item[3]
            folio_all[2]+=item[4]

        elif item[0]=="proofwriter/proofwriter_dev":
            proofwriter_all[0]+=item[2]
            proofwriter_all[1]+=item[3]
            proofwriter_all[2]+=item[4]

        elif item[0]=="prontoqa_ood/prontoqa_ood_4hop":
            prontoqa_all[0]+=item[2]
            prontoqa_all[1]+=item[3]
            prontoqa_all[2]+=item[4]

print(prontoqa_all)
print(proofwriter_all)
print(folio_all)