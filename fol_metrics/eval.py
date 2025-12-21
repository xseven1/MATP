import numpy as np
from tqdm import tqdm
from fol_metrics.metrics import UniversalMetrics
import fire
import json


def eval_pert(
    data_path="perturbations.json",
):
    metric = UniversalMetrics()

    with open(data_path, 'r') as f:
        data = json.load(f)

    Bleu_final = []
    Instruct_bleu_final = []
    LE_final = []

    for ind, data_point in enumerate(tqdm(data)):
        # TODO
        if "true_fol" not in data_point.keys():
            continue
        true_fol = data_point['true_fol'] # ground truth fol
        pred_fol = data_point['pred_fol'] # llm-generated fol

        res = metric.evaluate(
            None,
            true_fol,
            None,
            pred_fol
        )

        bleu, LE, instruct_bleu = res.FOL_bleu, res.FOL_LE, res.FOL_instruct_bleu

        Bleu_score = bleu
        LE_score = LE
        Instruct_bleu_score = instruct_bleu


        Bleu_final.append(Bleu_score)
        LE_final.append(LE_score)
        Instruct_bleu_final.append(Instruct_bleu_score)


    print("Bleu Score", np.mean(Bleu_final))
    print("LE score", np.mean(LE_final))
    print("Instruct Bleu Score", np.mean(Instruct_bleu_final))

    return dict(Bleu_mean=np.mean(Bleu_final),LE_mean=np.mean(LE_final),Bleu=Bleu_final,LE=LE_final)


if __name__ == '__main__':
    fire.Fire(eval_pert)