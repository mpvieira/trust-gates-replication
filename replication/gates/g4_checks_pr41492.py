"""G4 claim checks for PR #41492 (azure-ai-evaluation, int()->float() threshold comparison).
Run from sdk/evaluation/azure-ai-evaluation with the EVAL profile, at the merge commit and again with _base_eval.py from the parent.
C2: F1 evaluator with a fractional score; C3: synthetic lower-is-better evaluator; C4: score == threshold; R: non-numeric score."""
import asyncio, sys
from azure.ai.evaluation._evaluators._common._base_eval import EvaluatorBase
from azure.ai.evaluation import F1ScoreEvaluator
def report(m): sys.__stderr__.write(m+"\n")
# C2: "other score-based evaluators also benefit": F1 with a fractional score
r = F1ScoreEvaluator(threshold=0.5)(ground_truth="the quick brown fox", response="the quick fox")
report(f"C2 F1 score={r['f1_score']:.3f} threshold=0.5 -> {r['f1_result']}")
# C3: "affects both higher_is_better and lower_is_better branches": synthetic lower-is-better evaluator
class Lower(EvaluatorBase):
    def __init__(self, threshold, score): super().__init__(threshold=threshold, _higher_is_better=False); self._s=score
    async def _do_eval(self, eval_input): return {"x_score": self._s}
    def __call__(self, **kw): return super().__call__(**kw)
    def _convert_kwargs_to_eval_input(self, **kw): return [kw]
for score, thr in [(2.5, 2), (0.4, 0.5), (2.0, 2)]:
    out = asyncio.run(Lower(thr, score)._real_call(q="x"))
    report(f"C3 lower_is_better score={score} threshold={thr} -> {out.get('x_result')}  (correct: {'pass' if score<=thr else 'fail'})")
# C4 boundary: score == threshold (higher is better)
class Higher(Lower):
    def __init__(self, threshold, score): EvaluatorBase.__init__(self, threshold=threshold, _higher_is_better=True); self._s=score
out = asyncio.run(Higher(0.5, 0.5)._real_call(q="x")); report(f"C4 boundary score==threshold -> {out.get('x_result')} (correct: pass)")
# Robustness: non-numeric score (evaluator failure path)
out = asyncio.run(Higher(0.5, "N/A")._real_call(q="x")); report(f"R  non-numeric score -> result keys: {[k for k in out if k.endswith('_result')]} (error swallowed by print)")
