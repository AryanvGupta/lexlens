# Bootstrap 95% CIs (40 questions, 10000 resamples of questions, seed 0, percentile)

| mode | recall@1 | recall@5 | recall@10 | mrr@20 |
|---|---|---|---|---|
| dense | 0.400 [0.250, 0.550] | 0.650 [0.500, 0.800] | 0.775 [0.650, 0.900] | 0.511 [0.379, 0.645] |
| lexical | 0.250 [0.125, 0.400] | 0.450 [0.300, 0.600] | 0.500 [0.350, 0.650] | 0.330 [0.205, 0.462] |
| hybrid | 0.425 [0.275, 0.575] | 0.600 [0.450, 0.750] | 0.750 [0.600, 0.875] | 0.518 [0.382, 0.654] |
| rerank | 0.500 [0.350, 0.650] | 0.650 [0.500, 0.800] | 0.750 [0.625, 0.875] | 0.595 [0.463, 0.726] |

Paired differences (same resampled questions):

| difference | point | 95% CI | excludes 0? |
|---|---|---|---|
| hybrid-dense recall@5 | -0.050 | [-0.150, +0.050] | no |
| hybrid-dense mrr@20 | +0.007 | [-0.065, +0.080] | no |
| rerank-hybrid recall@5 | +0.050 | [-0.075, +0.200] | no |
| rerank-hybrid mrr@20 | +0.078 | [-0.031, +0.190] | no |
| rerank-dense recall@5 | +0.000 | [-0.150, +0.150] | no |
| rerank-dense mrr@20 | +0.084 | [-0.010, +0.187] | no |
