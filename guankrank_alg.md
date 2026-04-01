# GuanRank Algorithm

Excerpt from [Huang et al. 2017](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005887)

### Complete hazard ranking algorithm

The algorithm generates a single rank value for each individual, which  represents the survival hazard of the individual. The values serve as  prediction targets for machine learning regression models. The complete  hazard ranking algorithm starts with calculating the Kaplan-Meier  survival function for the dataset. The Kaplan-Meier function treats the  time course of the study as a series of intervals (0t, 1t), (1t, 2t),…,  (n-1t, nt) separated by every observed timestamp in the time-event  dataset. The function is expressed as
$$
SR(t=t_k) = \prod_{i=1}^k \frac{n_i - d_i}{n_i} = \prod_{i=1}^k \left( 1 - \frac{d_i}{n_0 - \sum_{j=0}^{i-1}d_j - \sum_{j=0}^{i-1}c_j} \right)
$$
where $n_i$, $d_i$, and $c_i$ are, respectively, the number of subjects at risk, the number of occurred events, and the number of newly censored  cases at the time point it.



Given the Kaplan-Meier survival function, the algorithm compares all possible pairs of subjects and assigns a hazard score to each subject in the  comparison. In brief, for cases where the order of events is clear for  both subjects, the algorithm assigns 1 to the subject with earlier event occurrence; for cases where the order is not clear, the algorithm  assigns a higher score to the subject with a higher risk of earlier  event occurrence based on the Kaplan-Meier survival function. We list  the detailed rules of algorithm as follows. For convenience, we denote  two subjects as A and B, and their last observed follow-up time t1 and t2, respectively. The algorithm assigns scores for A and B based on the  following criteria:

1. If none of the subjects are censored, the subject with a shorter time-to-event is assigned a score of 1, and the other 0 ([Fig 6D](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005887#pcbi-1005887-g006)). In case there is a tie, each is assigned a score of 0.5.

2. If both subjects are censored, and t1 = t2, both are assigned a score of 0.5, representing balanced uncertainty.

3. If t1 = t2, but only A is censored, A is assigned a score of 0, and B is assigned 1.

4. If t1 < t2, and an event happened to A, A is assigned a score of 1, and B is assigned 0 ([Fig 6C](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005887#pcbi-1005887-g006)).

5. If t1 < t2, and an event happened to B, and A is censored, A is  assigned a score of ρ(t1, t2), the conditional probability that an event happened to A before the event happened to B given that no event  happened to A before t1 ([Fig 6A](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005887#pcbi-1005887-g006)); B is assigned 1-ρ(t1, t2). The probability, ρ(t1, t2), can be calculated using Kaplan-Meier survival function:
   $$
   \rho(t_1, t_2) = 1 - \frac{SR(t_2)}{SR(t_1)}
   $$

6. If subjects have different observed survival time in the study, and both are censored, we rely on Kaplan-Meier estimator to calculate the score ([Fig 6B](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005887#pcbi-1005887-g006)). Here, we assume t1 < t2. We calculate ρ(t1, t2), the conditional  probability that an event happened to A between t1 and t2 given that no  event happened to A before t1, using the aforementioned equation. Then, A is assigned [1+ρ(t1, t2)]/2, and B is assigned [1-ρ(t1, t2)]/2.

Given a dataset of N subjects, each subject is compared to the other N-1 subjects. For each subject, the summation of N-1 comparison scores is  assigned as the final hazard rank. By intuition, an event is more likely to happen early to a subject with a higher hazard rank than one with a  lower rank. In sum, for a censored subject (E = 0) whose last observed  follow-up time point is t, its hazard rank is:
$$
Rank = \sum_{\forall T = t, E = 0} \frac{1}{2} + \sum_{\forall T > t, E = 1} \rho(T, t) + \sum_{\forall T > t, E = 0} \frac{1+\rho(T, t)}{2} + \sum_{\forall T < t, E = 0} \frac{1-\rho(T, t)}{2}
$$
For an uncensored subject (E = 1), its hazard rank is:
$$
Rank = \sum_{\forall T = t, E = 0} \frac{1}{2} + \sum_{\forall T > t, E = 1} 1 + \sum_{\forall T > t, E = 0} 1 + \sum_{\forall T < t, E = 0} [1 - \rho(T,t)]
$$