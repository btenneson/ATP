"""
Generate a Metamath-format corpus with set.mm-like STATISTICS.

This is NOT ZFC.  It is a structural stand-in used only to exercise the
pipeline where set.mm is unavailable: power-law citation (a few lemmas cited
thousands of times, most cited once or twice), deep dependency chains, a large
symbol vocabulary, and premise counts in the observed range.  Any number
measured on it describes the harness, not mathematics.
"""
import random, sys
rng = random.Random(7)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
out = ["$( synthetic corpus with set.mm-like structure -- NOT real mathematics $)"]
out.append("$c |- wff set class ( ) -> <-> = e. A. E. -. /\\ \\/ { } " + " ".join(s for ts in [[f"c{t}_{i}" for i in range(12)] for t in range(40)] for s in ts) + " $.")
VARS = ["ph","ps","ch","th","ta","x","y","z","A","B","C","D","F","G","R","S"]
out.append("$v " + " ".join(VARS) + " $.")

AX = ["ax-1","ax-2","ax-3","ax-mp","ax-gen","ax-ext","ax-sep","ax-pow",
      "ax-un","ax-inf","ax-ac","ax-reg","ax-pr","ax-nul"]
for a in AX:
    out.append("%s $a |- ( %s -> ( %s -> %s ) ) $." % (a, rng.choice(VARS),
                                                       rng.choice(VARS), rng.choice(VARS)))
labels = list(AX)
# popularity weights: Zipf, so a few lemmas dominate citations as in set.mm
import bisect
_cum=[]
def refresh(pool):
    global _cum
    _cum=[]; s=0.0
    for i in range(len(pool)):
        s += 1.0/(i+1)**0.9; _cum.append(s)
def pick(pool, k):
    if not pool: return []
    if len(_cum)!=len(pool): refresh(pool)
    tot=_cum[-1]; out_=set()
    for _ in range(k*3):
        if len(out_)>=k: break
        out_.add(pool[bisect.bisect_left(_cum, rng.random()*tot)])
    return list(out_)

N_TOPICS = 40
TOPIC_SYMS = [[f"c{t}_{i}" for i in range(12)] for t in range(N_TOPICS)]
TOPIC_OF = {}
SYM = ["|-","(",")","->","<->","=","e.","A.","E.","-.","/\\","\\/","{","}","wff","class","set"]
for n in range(N):
    lab = "th%05d" % n
    ntok = rng.randint(6, 34)
    # A real theorem's premises SHARE VOCABULARY with it: a lemma about
    # ordinals gets cited by theorems about ordinals.  Drawing premises by
    # popularity alone, independently of the statement, leaves no signal a
    # content-based selector could find and makes frequency the optimal
    # predictor by construction.  So each theorem is given a topic, its
    # statement is drawn mostly from that topic's symbols, and its premises are
    # drawn preferentially from the same topic.
    topic = rng.randrange(N_TOPICS)
    tsyms = TOPIC_SYMS[topic]
    stmt = "|- " + " ".join(
        (rng.choice(tsyms) if rng.random() < 0.7 else rng.choice(SYM + VARS))
        for _ in range(ntok))
    # popularity ordering: earlier labels are the heavily cited ones
    k = max(1, int(rng.lognormvariate(1.0, 0.6)))
    same = TOPIC_OF.setdefault(topic, [])
    prem = []
    if same:                       # most premises come from the same topic
        prem += rng.sample(same, min(len(same), max(1, int(k * 0.7))))
    prem += pick(labels, k - len(prem))          # the rest by popularity
    prem = list(dict.fromkeys(prem)) or [rng.choice(labels)]
    TOPIC_OF[topic] = (same + [lab])[-400:]
    steps = " ".join(prem) + " " + " ".join(rng.choice(prem) for _ in range(rng.randint(2, 25)))
    out.append("%s $p %s $= %s $." % (lab, stmt, steps))
    labels.append(lab)
open("fake_zfc.mm","w").write("\n".join(out)+"\n")
print("wrote fake_zfc.mm with %d statements" % (len(AX)+N))
