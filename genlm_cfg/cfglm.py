"""
Fast computation of the posterior distrubtion over the next word in a WCFG language model.
"""

from genlm_cfg.cfg import CFG, _gen_nt
from genlm_cfg.lm import LM
from genlm_cfg.semiring import Boolean, Float


EOS = '▪'


def locally_normalize(self, **kwargs):
    """
    Locally normalizes the grammar: return a transformed grammar such that

    (1) the total weight of each block of rules with a common head sum to one;

    (2) each derivation in the transformed grammar is proportional to the original grammar
        (i.e., it is has the same score modulo a multiplicative normalization constant)

    """
    new = self.spawn()
    Z = self.agenda(**kwargs)
    for r in self:
        if Z[r.head] == 0:
            continue
        new.add(r.w * Z.product(r.body) / Z[r.head], r.head, *r.body)
    return new


def add_EOS(cfg):
    "Append the EOS symbol to the language generated by `cfg`."
    S = _gen_nt('<START>')
    new = cfg.spawn(S=S)
    assert EOS not in cfg.V
    new.V.add(EOS)
    new.add(cfg.R.one, S, cfg.S, EOS)
    for r in cfg:
        new.add(r.w, r.head, *r.body)
    return new


class BoolCFGLM(LM):
    "LM-like interface for Boolean-masking CFG models; uses Earley's algorithm for inference."

    def __init__(self, cfg, alg='earley'):
        if EOS not in cfg.V:
            cfg = add_EOS(cfg)
        if cfg.R != Boolean:
            cfg = cfg.map_values(lambda x: Boolean(x > 0), Boolean)
        if alg == 'earley':
            from genlm_cfg.parse.earley import Earley

            self.model = Earley(cfg.prefix_grammar)
        elif alg == 'cky':
            from genlm_cfg.parse.cky import CKYLM

            self.model = CKYLM(cfg)
        else:
            raise ValueError(f'unrecognized option {alg}')
        super().__init__(eos=EOS, V=cfg.V)

    def p_next(self, context):
        assert set(context) <= self.V, f'OOVs detected: {set(context) - self.V}'
        p = self.model.next_token_weights(self.model.chart(context)).trim()
        return Float.chart({w: 1 for w in p})

    def __call__(self, context):
        return float(super().__call__(context) > 0)

    def clear_cache(self):
        self.model.clear_cache()

    @classmethod
    def from_string(cls, x, semiring=Boolean, **kwargs):
        return cls(CFG.from_string(x, semiring), **kwargs)