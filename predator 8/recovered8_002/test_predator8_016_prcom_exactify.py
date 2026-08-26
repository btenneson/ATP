import unittest
import predator8_016_prcom_exactify as X

class ExactifyIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.E = X.B.load_engine('Predator_8.001_FROZEN.py')

    def test_complete_probe_finds_and_verifies_selftest_identity(self):
        E=self.E
        mm=E.MM(); mm.read(E.Toks(E.SELFTEST))
        by_tc=E.G.build_grammar(mm)
        idx=E.Index(mm,by_tc)
        stat='|- ( ph -> ph )'.split()
        target_data=mm.fs.make_assertion(stat)
        goal=E.G.parse(stat[1:],'wff',by_tc)
        fvar,fallback={},{}
        for lab in mm.order:
            typ,d=mm.labels[lab]
            if typ=='$f':
                fvar[d[1]]=lab
                fallback.setdefault(d[0],E.G.Tree(None,d[0],(),d[1]))
        ctx=X.ProbeContext(E,idx,mm,target_data,fvar,fallback)
        start=E.Node([(goal,None,0)],{},(),0)
        pr=X.run_probe(ctx,start,max_depth=6,max_expansions=10000)
        self.assertEqual(pr.exact_h,6)
        self.assertIsNotNone(pr.witness)
        self.assertIsNotNone(pr.witness.closed_witness)
        root,sub=X.B.reconstruct(pr.witness.closed_witness)
        proof=root.emit(sub,fvar,fallback)
        check=E.MM()
        check.read(E.Toks(E.SELFTEST+'\nchk $p |- ( ph -> ph ) $= '+' '.join(proof)+' $.'))
        self.assertEqual(check.verify('chk'),'ok')

    def test_shallow_complete_probe_returns_lower_bound(self):
        E=self.E
        mm=E.MM(); mm.read(E.Toks(E.SELFTEST))
        by_tc=E.G.build_grammar(mm); idx=E.Index(mm,by_tc)
        stat='|- ( ph -> ph )'.split(); target_data=mm.fs.make_assertion(stat)
        goal=E.G.parse(stat[1:],'wff',by_tc)
        fvar,fallback={},{}
        for lab in mm.order:
            typ,d=mm.labels[lab]
            if typ=='$f':
                fvar[d[1]]=lab; fallback.setdefault(d[0],E.G.Tree(None,d[0],(),d[1]))
        ctx=X.ProbeContext(E,idx,mm,target_data,fvar,fallback)
        start=E.Node([(goal,None,0)],{},(),0)
        pr=X.run_probe(ctx,start,max_depth=2,max_expansions=10000)
        self.assertIsNone(pr.exact_h)
        self.assertEqual(pr.lower_bound,3)
        self.assertTrue(pr.complete_to_requested_depth)

if __name__=='__main__': unittest.main()
