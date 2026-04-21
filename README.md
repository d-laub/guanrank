# guanrank

Python implementation of the GuanRank hazard ranking algorithm. Assigns a continuous hazard rank to each subject in a survival dataset — higher rank means higher risk of earlier event. Ranks can be used as regression targets for machine learning models in place of raw survival times.

## Citation

Huang, S., Cai, N., Pacheco, P. P., Narandes, S., Wang, Y., & Xu, W. (2017). Applications of support vector machine (SVM) learning in cancer genomics. *Cancer Genomics & Proteomics*, 15(1), 41–51. https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005887

## Installation

```bash
pip install guanrank
# or with uv
uv add guanrank
```

## Usage

### Functional API

```python
from guanrank import guanrank

T = [5.0, 3.0, 8.0, 3.0]  # time-to-event or censoring times
E = [1,   1,   0,   0  ]  # 1 = event, 0 = censored

ranks = guanrank(T, E)
```

### Sklearn-style API (train/test split)

```python
from guanrank import GuanRank

gr = GuanRank()
train_ranks = gr.fit_transform(T_train, E_train)
test_ranks = gr.transform(T_test, E_test)
```

`fit` stores the training cohort's Kaplan-Meier curve; `transform` scores new subjects by comparing them against the training cohort.
