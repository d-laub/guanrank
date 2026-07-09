# guanrank

Python implementation of the GuanRank hazard ranking algorithm. Assigns a continuous hazard rank to each subject in a survival dataset — higher rank means higher risk of earlier event. Ranks can be used as regression targets for machine learning models in place of raw, right-censored survival times.

## Algorithm

GuanRank ([Huang et al., 2017](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005887)) collapses right-censored survival data into a single scalar hazard per subject:

1. **Kaplan-Meier curve.** Estimate the survival function `SR(t)` from all observed event/censoring times.
2. **Pairwise scoring.** For every ordered pair of subjects, assign a score in `[0, 1]` under six rules. When the event ordering is unambiguous (both observed, or one event clearly precedes the other), the earlier-event subject scores 1 and the other 0. When censoring makes the ordering uncertain, the score is the Kaplan-Meier conditional probability `ρ(t₁, t₂) = 1 − SR(t₂)/SR(t₁)` that the event fell in the ambiguous interval.
3. **Raw rank.** Sum each subject's pairwise scores.
4. **Normalization.** Divide every raw rank by the largest raw rank in the training set, so the highest-hazard subject maps to `1.0`.

### Input / output

- **Inputs** — `T`: time-to-event or censoring time per subject; `E`: event indicator (`1` = event observed, `0` = right-censored).
- **Output** — one normalized hazard rank per subject, in input order. In-sample ranks lie in `(0, 1]`, with the highest-hazard subject at `1.0`. Out-of-sample ranks from `GuanRank.transform` share the training scale and may exceed `1.0` when a held-out subject is riskier than every training subject.

The pairwise rules are documented in [`guankrank_alg.md`](guankrank_alg.md).

## Citation

Huang et al. (2017). Complete hazard ranking to analyze right-censored data: An ALS survival study. *PLOS Comp Bio*, 15(1), 41–51. https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005887

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

`fit` stores the training cohort's Kaplan-Meier curve and normalization constant (its maximum raw rank); `transform` scores new subjects against the training cohort and divides by that same constant, keeping held-out ranks on the training scale.
