import numpy as np
import matplotlib.pyplot as plt
import json
import os
import copy

def read_json(path:str):
    ddict = dict()
    if os.path.exists(path):
        with open(path,'r',encoding="utf8") as f:
            ddict = json.load(f)
    else:
        print(f"file {path} doesn't exist")
    return ddict

FOLIO = "folio"
PROOFWRITER = "proofwriter"
PRONTOQA_OOD = "prontoqa_ood"

# Data categories
categories = ['T1', 'T2', 'T3', 'T4', 'F1', 'F2', 'Error']

models = [('GPT-3.5', 'gpt3.5'), ('GPT-4o','gpt4o'), ('LLaMA3.1-8B','llama318b'), 
('LLaMA3.1-70B','llama3170b'), ('Qwen2.5-7B','qwen257b'),
('Qwen-32B','qwen32b'),('DS-R1-Qwen7B','DeepseekR1Qwen7b'),
('DS-R1-Qwen32B','DeepseekR1Qwen32b'),('DeepSeek-R1','deepseekr1'),('GPT-o4-mini','gpto4mini')]

datasets = [(PRONTOQA_OOD,"prontoqa_ood/prontoqa_ood_4hop"),
(PROOFWRITER, "proofwriter/proofwriter_dev"),
(FOLIO,"folio/folio_train")]

proofwriter_data = {}
folio_data = {}
prontoqa_data = {}

all_results = []

for model in models:
    model_key = model[0]
    model_file_name = model[1]

    for item in datasets:
        dataset_name = item[1]
        res_path = f"RQ1_RQ3/{dataset_name}_{model_file_name}_check_res.json"
        data = read_json(res_path)
        res = [i for i in data if "T1" in i.keys()][0]
        # print(res)

        ll = []
        for cate in categories:
            if cate == "Error":
                ll.append(res[cate]+res["Semantic_Error"])
            else:
                ll.append(res[cate])

        if item[0] == PRONTOQA_OOD:
            prontoqa_data[model_key] = copy.deepcopy(ll)
        elif item[0] == PROOFWRITER:
            proofwriter_data[model_key] = copy.deepcopy(ll)
        else:
            folio_data[model_key] = copy.deepcopy(ll)
        
        all_results.append((model_file_name,dataset_name,res))
    
data_sets = [prontoqa_data, proofwriter_data, folio_data]
titles = ['PrOntoQA-OOD', 'ProofWriter', 'FOLIO']

# Color for each category (green T1-T4, orange F1-F2, red Error)
category_colors = {
    'T1': '#1a9850',
    'T2': '#66bd63',
    'T3': '#a6d96a',
    'T4': '#d9ef8b',
    'F1': '#fdae61',
    'F2': '#f46d43',
    'Error': '#d73027'
}

x_title = [item[0] for item in models]
x = np.arange(len(x_title))
width = 0.1

# Creating a chart
fig, axes = plt.subplots(3, 1, figsize=(17, 7), sharex=True)

for ax, data, title in zip(axes, data_sets, titles):
    max_height = 0
    for j, cat in enumerate(categories):
        values = [data[model][j] for model in x_title]
        bars = ax.bar(x + (j - 3) * width, values, width, label=cat, color=category_colors[cat])
        for bar in bars:
            height = bar.get_height()
            max_height = max(max_height,height)
            ax.text(bar.get_x() + bar.get_width() / 2, height - 1, str(height), ha='center', va='bottom', fontsize=8, fontweight='bold')
    ax.set_ylim(0, max_height+30)

    ax.set_ylabel('Count', fontsize=12, fontweight='bold')
    # ax.set_title(f'{title} Category Distribution', fontsize=14, fontweight='bold', pad=-30)
    ax.grid(axis='y', linestyle='--', color='darkgray', alpha=0.7)
    # ax.set_title(title, fontsize=14, fontweight='bold', y=0.9)

axes[-1].set_xticks(x)
axes[-1].set_xticklabels(x_title, fontsize=12,fontweight='bold')

# Adding grids uniformly
for ax in axes:
    ax.grid(axis='x', linestyle='--', color='darkgray', alpha=0.7)

# Adding legend
handles = [plt.Rectangle((0, 0), 1, 1, color=category_colors[cat]) for cat in categories]
labels = categories
fig.legend(handles, labels, loc='upper center', ncol=7, fontsize=12, frameon=False)

# Adjusting the layout
plt.tight_layout(rect=[0, 0, 1, 0.98])
for ax, data, title in zip(axes, data_sets, titles):
    ax.text(0.005, 0.95, f"{title}", transform=ax.transAxes, fontsize=14, fontweight='bold',ha='left', va='top')
    
plt.savefig("rq3.pdf", format="pdf")


averge = {}

for item in all_results:
    print(item)
    print()

    model_file_name,dataset_name,res = item[0],item[1],item[2]
    if dataset_name not in averge.keys():
        averge[dataset_name] = [0,0]
    averge[dataset_name][0]+=res["Exe_Rate"]
    averge[dataset_name][1]+=res["Exe_Acc"]

print(averge)