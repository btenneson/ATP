$( =====================================================================
   hyperreal.mm -- the infinitesimals, and the claim |I| = |RR|.

   Brian Tenneson.

   A PROPOSAL.  The mathematics is settled; what is unverified is whether
   these strings are well formed under set.mm's grammar and whether the
   definitions meet set.mm's eliminability and non-creativity conditions.
   Both are checkable, and the commands are at the bottom.

   Append to set.mm and test.  Do not trust it until it parses.
   ===================================================================== $)

$( ---------------------------------------------------------------------
   0.  THE DEFINITION, IN ORDINARY MATHEMATICS

   F is a nonprincipal ultrafilter on NN0.
   *R = ( RR ^m NN0 ) / ~F, where  z ~F w  iff  { m : z(m) = w(m) } e. F.

       I  =  { [z] e. *R  :  A. r e. RR+  { m e. NN0 : |z(m)| < r } e. F }

   THE CONDITION QUANTIFIES OVER POSITIVE REAL CONSTANTS r, NOT OVER
   SEQUENCES.  Quantifying over sequences x, with the condition
   { m : |z(m)| < |x(m)| } e. F, makes I EMPTY: take x = z and the set is
   (/), which lies in no filter.  Infinitesimal means "smaller than every
   STANDARD positive real", which is what admits eps = <1/(m+1)> and
   excludes <1,1,1,...>.

   Well defined on classes: if z ~F w then { m : z(m) = w(m) } e. F, and
   intersecting with { m : |z(m)| < r } gives the same condition for w.

   Stating the condition on REPRESENTATIVES is what keeps this small.  The
   order <*, the field arithmetic and the diagonal embedding are not needed
   to say what an infinitesimal is, so three definitions and all of their
   well-definedness obligations disappear.
   --------------------------------------------------------------------- $)

$( ---------------------------------------------------------------------
   1.  NONPRINCIPAL ULTRAFILTERS ON NN0
   --------------------------------------------------------------------- $)

$( Nonprincipal = contains no finite set.  This is the only place
   nonprincipality is used: it forces every cofinite set into f, which is
   what makes <1/(m+1)> infinitesimal.  Over a PRINCIPAL ultrafilter the
   ultrapower collapses to RR and I = { 0 }, so the main claim is FALSE
   without this condition -- it is a hypothesis, not decoration.           $)

  cnpu $a class NPU $.
  df-npu $a |- NPU = { f e. ( UFil ` NN0 ) | ( f i^i Fin ) = (/) } $.

$( ---------------------------------------------------------------------
   2.  THE F-EQUIVALENCE AND THE ULTRAPOWER
   --------------------------------------------------------------------- $)

$( Reflexive needs NN0 e. f; symmetric is immediate; transitive needs
   closure under finite intersection.  All three are filter properties.    $)

  cuer $a class ~Uf $.
  df-uer $a |- ( ~Uf ` f ) = { <. z , w >. |
      ( ( z e. ( RR ^m NN0 ) /\ w e. ( RR ^m NN0 ) ) /\
        { m e. NN0 | ( z ` m ) = ( w ` m ) } e. f ) } $.

$( NOT named RR* -- that token is the EXTENDED reals RR u. { -oo , +oo }
   in set.mm, a different object, and reusing it would collide silently.   $)

  chyp $a class Hyp $.
  df-hyp $a |- ( Hyp ` f ) = ( ( RR ^m NN0 ) /. ( ~Uf ` f ) ) $.

$( ---------------------------------------------------------------------
   3.  THE INFINITESIMALS
   --------------------------------------------------------------------- $)

  cinfml $a class Infml $.
  df-infml $a |- ( Infml ` f ) = { x e. ( Hyp ` f ) |
      E. z e. ( RR ^m NN0 ) ( x = [ z ] ( ~Uf ` f ) /\
        A. r e. RR+ { m e. NN0 | ( abs ` ( z ` m ) ) < r } e. f ) } $.

$( ---------------------------------------------------------------------
   4.  THE STATEMENT:  | I | = | RR |
   --------------------------------------------------------------------- $)

$( Cardinal equality is equinumerosity, so this is the right primitive:
   "~~" asserts a bijection exists.  ( card ` A ) = ( card ` B ) would say
   the same thing but drags in card and needs both sides to be well
   ordered, which costs choice for no gain here.

   PROOF SKETCH, four moves:

     RR  ~<_  I
        eps = ( m e. NN0 |-> ( 1 / ( m + 1 ) ) ) is infinitesimal, since
        { m : 1 / ( m + 1 ) < r } is cofinite and f is NONPRINCIPAL.
        r |-> [ ( m e. NN0 |-> ( r x. ( 1 / ( m + 1 ) ) ) ) ] injects RR
        into I.  Injective because r =/= s makes the agreement set empty
        and (/) is in no filter.

     I  ~<_  Hyp f                subset dominance

     Hyp f  ~<_  ( RR ^m NN0 )    invert the quotient surjection; AC, which
                                  the ultrafilter already required.
                                  NOT via Hyp f C_ ~P ( RR ^m NN0 ), which
                                  gives only 2 ^ 2 ^ aleph0 -- far too weak.

     ( RR ^m NN0 )  ~~  RR        ( 2 ^ aleph0 ) ^ aleph0 = 2 ^ aleph0

   then sbth closes it.  No continuum hypothesis, and independent of which
   nonprincipal ultrafilter is chosen -- only cardinality is used, never
   the particular f.                                                       $)

  infmlen $p |- ( f e. NPU -> ( Infml ` f ) ~~ RR ) $= ? $.

$( =====================================================================
   HOW TO CHECK THIS FILE

       copy /b set.mm + hyperreal.mm setmm_ext.mm
       python setmm_grammar.py roundtrip setmm_ext.mm --sample 3000
       python setmm_grammar.py tree setmm_ext.mm df-infml
       python setmm_grammar.py tree setmm_ext.mm infmlen

   infmlen will report INCOMPLETE under metamath.py -- correct, its proof
   is '?'.  What matters is that nothing FAILS and roundtrip stays at zero.

   WHAT PARSING DOES NOT ESTABLISH.  Well-formedness is necessary, not
   sufficient.  set.mm requires every df-* to be ELIMINABLE and
   NON-CREATIVE; those are review conditions no parser checks.

   SPELLINGS I AM LEAST SURE OF, in the order I would check them:
     * UFil, and whether it takes NN0 in this form
     * the two-variable abstraction  { <. z , w >. | ph }
     * argument order in  ( A /. R )
     * [ A ] R  for equivalence classes
     * whether RR+ and abs are available in these positions

       python metamath.py search "UFil" --logical-only --limit 40
       python metamath.py search --prefix df-ufil
       python metamath.py search --prefix df-qs
       python metamath.py search --prefix df-ec
       python metamath.py search --prefix df-map
       python metamath.py search "Fin" --logical-only --limit 30
   ===================================================================== $)
