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
| V1 | pypdf_no_rerank | 0.5234 | 0.4574 | 0.5667 |
| V2 | pypdf_with_rerank | 0.8633 | 0.7348 | 0.7292 |
| V3 | docling_with_rerank | 0.0000 | 0.0000 | 0.0000 |

## 2x2 Group Means

| Group | Faithfulness | Relevancy | Precision | Recall |
|---|---:|---:|---:|---:|
| pypdf_no_rerank | 0.5234 | 0.6091 | 0.4574 | 0.5667 |
| pypdf_with_rerank | 0.8633 | 0.6080 | 0.7348 | 0.7292 |
| docling_no_rerank | 0.6705 | 0.6057 | 0.8000 | 0.7778 |
| docling_with_rerank | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Key Deltas (abs / rel%)

### rerank_gain_on_pypdf
| Metric | Abs | Rel% |
|---|---:|---:|
| faithfulness | 0.3399 | 64.94% |
| answer_relevancy | -0.0011 | -0.18% |
| context_precision | 0.2774 | 60.65% |
| context_recall | 0.1625 | 28.67% |

### rerank_gain_on_docling
| Metric | Abs | Rel% |
|---|---:|---:|
| faithfulness | -0.6705 | -100.00% |
| answer_relevancy | -0.6057 | -100.00% |
| context_precision | -0.8000 | -100.00% |
| context_recall | -0.7778 | -100.00% |

### docling_gain_without_rerank
| Metric | Abs | Rel% |
|---|---:|---:|
| faithfulness | 0.1471 | 28.10% |
| answer_relevancy | -0.0034 | -0.56% |
| context_precision | 0.3426 | 74.90% |
| context_recall | 0.2111 | 37.25% |

### docling_gain_with_rerank
| Metric | Abs | Rel% |
|---|---:|---:|
| faithfulness | -0.8633 | -100.00% |
| answer_relevancy | -0.6080 | -100.00% |
| context_precision | -0.7348 | -100.00% |
| context_recall | -0.7292 | -100.00% |

### overall_best_vs_baseline
| Metric | Abs | Rel% |
|---|---:|---:|
| faithfulness | -0.5234 | -100.00% |
| answer_relevancy | -0.6091 | -100.00% |
| context_precision | -0.4574 | -100.00% |
| context_recall | -0.5667 | -100.00% |
