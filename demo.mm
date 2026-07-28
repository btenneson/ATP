$( Small Metamath database in the style of set.mm, for parser testing. $)
$c ( ) -> -. wff |- $.
$v p q r $.
wp $f wff p $.
wq $f wff q $.
wr $f wff r $.
wi $a wff ( p -> q ) $.
wn $a wff -. p $.
ax-1 $a |- ( p -> ( q -> p ) ) $.
ax-2 $a |- ( ( p -> ( q -> r ) ) -> ( ( p -> q ) -> ( p -> r ) ) ) $.
ax-3 $a |- ( ( -. p -> -. q ) -> ( q -> p ) ) $.
ax-mp $a |- q $.
a1i $p |- ( q -> p ) $= wp wq wi ax-1 ax-mp $.
mp2b $p |- ( p -> r ) $= wp wq wr ax-2 a1i ax-mp $.
id $p |- ( p -> p ) $= wp wi ax-1 ax-2 ax-mp mp2b $.
imim1 $p |- ( ( p -> q ) -> ( p -> r ) ) $= ax-2 id a1i ax-mp $.
con4 $p |- ( q -> p ) $= ax-3 imim1 ax-mp mp2b $.
syl $p |- ( p -> r ) $= a1i mp2b imim1 ax-mp con4 $.
