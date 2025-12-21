import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd

# MATP Result
matp_data = {
    "T1": [50, 0, 0, 0],
    "T2": [0, 50, 0, 0],
    "T3": [0, 0, 50, 2],
    "T4": [0, 0, 0, 48]
}
matp_df = pd.DataFrame(matp_data, index=["T1", "T2", "T3", "T4"])

# Baseline Result GPT4o
gpt4_data = {
    "T1": [39, 1, 5, 0],
    "T2": [4, 36, 1, 5],
    "T3": [0, 0, 42, 0],
    "T4": [7, 13, 2, 45]
}
gpt4_df = pd.DataFrame(gpt4_data, index=["T1", "T2", "T3", "T4"])

# Baseline Result DeepSeek-R1
deepseekr1_data = {
    "T1": [48, 0, 4, 0],
    "T2": [1, 45, 0, 9],
    "T3": [0, 0, 46, 0],
    "T4": [1, 5, 0, 41]
}
deepseekr1_df = pd.DataFrame(deepseekr1_data, index=["T1", "T2", "T3", "T4"])


# Setting the subgraph
fig, axes = plt.subplots(1, 3, figsize=(7, 2))

# Set the color range so that the two heatmaps have the same color
vmin = min(matp_df.min().min(), deepseekr1_df.min().min(), gpt4_df.min().min())
vmax = max(matp_df.max().max(), deepseekr1_df.max().max(), gpt4_df.min().min())

# Plot the MATP heat map
sns.heatmap(matp_df, annot=True, fmt="d", cmap="Greens", cbar=False, linewidths=0.5, 
            vmin=vmin, vmax=vmax, annot_kws={"weight": "bold"}, ax=axes[0])
axes[0].set_title("MATP Predicted Label", fontweight="bold",fontsize=8)
axes[0].set_ylabel("Ground Truth Label", fontweight="bold",fontsize=8)

# Plot the GPT-4 heat map
sns.heatmap(gpt4_df, annot=True, fmt="d", cmap="Greens", cbar=False, linewidths=0.5, 
            vmin=vmin, vmax=vmax, annot_kws={"weight": "bold"}, ax=axes[1])
axes[1].set_title("GPT-4o Predicted Label", fontweight="bold",fontsize=8)

# Plot the DeepSeek heat map
sns.heatmap(deepseekr1_df, annot=True, fmt="d", cmap="Greens", cbar=False, linewidths=0.5, 
            vmin=vmin, vmax=vmax, annot_kws={"weight": "bold"}, ax=axes[2])
axes[2].set_title("DeepSeek-R1 Predicted Label", fontweight="bold",fontsize=8)


axes[1].tick_params(labelsize=6)
axes[0].tick_params(labelsize=6)
axes[2].tick_params(labelsize=6)


plt.subplots_adjust(wspace=0.25)
plt.savefig("rq2.pdf", format="pdf")
