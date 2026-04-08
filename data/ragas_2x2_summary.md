# RAGAS 2x2 Summary

- Dataset size: 50
- Dataset target: 50
- Formal dataset ready: True
- Docling effective: True
- Docling chunk ratio: 1.0477
- Docling page ratio: 0.9972
- Docling char ratio: 1.0396

## Executive Versions

| Version | Group | Faithfulness | Precision | Recall |
|---|---|---:|---:|---:|
| V1 | pypdf_no_rerank | 0.5454 | 0.4367 | 0.5000 |
| V2 | pypdf_with_rerank | 0.6203 | 0.5400 | 0.5700 |
| V3 | docling_with_rerank | 0.7389 | 0.4650 | 0.5100 |

## 2x2 Group Means

| Group | Faithfulness | Relevancy | Precision | Recall |
|---|---:|---:|---:|---:|
| pypdf_no_rerank | 0.5454 | 0.6014 | 0.4367 | 0.5000 |
| pypdf_with_rerank | 0.6203 | 0.6063 | 0.5400 | 0.5700 |
| docling_no_rerank | 0.5594 | 0.6051 | 0.4267 | 0.5200 |
| docling_with_rerank | 0.7389 | 0.6038 | 0.4650 | 0.5100 |

## Key Deltas (abs / rel%)

### rerank_gain_on_pypdf
| Metric | Abs | Rel% |
|---|---:|---:|
| faithfulness | 0.0749 | 13.73% |
| answer_relevancy | 0.0049 | 0.81% |
| context_precision | 0.1033 | 23.65% |
| context_recall | 0.0700 | 14.00% |

### rerank_gain_on_docling
| Metric | Abs | Rel% |
|---|---:|---:|
| faithfulness | 0.1795 | 32.09% |
| answer_relevancy | -0.0013 | -0.21% |
| context_precision | 0.0383 | 8.98% |
| context_recall | -0.0100 | -1.92% |

### docling_gain_without_rerank
| Metric | Abs | Rel% |
|---|---:|---:|
| faithfulness | 0.0140 | 2.57% |
| answer_relevancy | 0.0037 | 0.62% |
| context_precision | -0.0100 | -2.29% |
| context_recall | 0.0200 | 4.00% |

### docling_gain_with_rerank
| Metric | Abs | Rel% |
|---|---:|---:|
| faithfulness | 0.1186 | 19.12% |
| answer_relevancy | -0.0025 | -0.41% |
| context_precision | -0.0750 | -13.89% |
| context_recall | -0.0600 | -10.53% |

### overall_best_vs_baseline
| Metric | Abs | Rel% |
|---|---:|---:|
| faithfulness | 0.1935 | 35.48% |
| answer_relevancy | 0.0024 | 0.40% |
| context_precision | 0.0283 | 6.48% |
| context_recall | 0.0100 | 2.00% |
