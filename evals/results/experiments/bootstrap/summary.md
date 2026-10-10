# Bootstrap 95% CIs (44 questions, 10000 resamples of questions, seed 0, percentile)

| mode | recall@1 | recall@5 | recall@10 | mrr@20 |
|---|---|---|---|---|
| dense | 0.750 [0.614, 0.864] | 0.920 [0.841, 0.989] | 0.955 [0.886, 1.000] | 0.830 [0.733, 0.914] |
| lexical | 0.409 [0.273, 0.545] | 0.648 [0.511, 0.784] | 0.716 [0.580, 0.841] | 0.513 [0.387, 0.635] |
| hybrid | 0.659 [0.523, 0.795] | 0.920 [0.841, 0.989] | 0.955 [0.886, 1.000] | 0.781 [0.682, 0.870] |
| rerank | 0.716 [0.591, 0.841] | 0.920 [0.841, 0.989] | 0.966 [0.909, 1.000] | 0.823 [0.732, 0.907] |

Paired differences (same resampled questions):

| difference | point | 95% CI | excludes 0? |
|---|---|---|---|
| hybrid-dense recall@5 | +0.000 | [-0.091, +0.091] | no |
| hybrid-dense mrr@20 | -0.049 | [-0.150, +0.052] | no |
| rerank-hybrid recall@5 | +0.000 | [-0.068, +0.068] | no |
| rerank-hybrid mrr@20 | +0.043 | [-0.051, +0.137] | no |
| rerank-dense recall@5 | +0.000 | [-0.068, +0.068] | no |
| rerank-dense mrr@20 | -0.007 | [-0.111, +0.098] | no |
