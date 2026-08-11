from __future__ import annotations

from dataclasses import dataclass

from .certificates import ModelPairCertificate, ProofCertificate, ProofNode
from .logic import Formula, Sequent


@dataclass(frozen=True)
class VerificationResult:
    accepted: bool
    reason: str


class ClassicalLKVerifier:
    VERSION = "ald-lk-verifier-0.2"

    def verify_proof(self, certificate: ProofCertificate) -> VerificationResult:
        try:
            self._verify_node(certificate.root)
            return VerificationResult(True, "verified LK proof certificate")
        except ValueError as exc:
            return VerificationResult(False, str(exc))

    def _verify_node(self, node: ProofNode) -> None:
        rule = node.rule
        if rule == "ID":
            if node.premises:
                raise ValueError("ID must have no premises")
            if not (node.sequent.antecedent & node.sequent.succedent):
                raise ValueError("ID requires a formula on both sides")
            return

        principal = node.principal
        if principal is None:
            raise ValueError(f"{rule} requires a principal formula")

        if rule == "CUT":
            if len(node.premises) != 2:
                raise ValueError("CUT requires two premises")
            lemma_proof, use_proof = node.premises
            expected_lemma = Sequent.make(node.sequent.antecedent, (principal,))
            expected_use = Sequent.make(
                node.sequent.antecedent | {principal}, node.sequent.succedent
            )
            if lemma_proof.sequent != expected_lemma:
                raise ValueError("CUT lemma premise does not match conclusion context")
            if use_proof.sequent != expected_use:
                raise ValueError("CUT use premise does not match conclusion context")

        elif rule == "NOT_R":
            if principal.op != "not" or principal not in node.sequent.succedent:
                raise ValueError("NOT_R principal must be a negation in the succedent")
            if len(node.premises) != 1:
                raise ValueError("NOT_R requires one premise")
            inner = principal.args[0]
            expected = Sequent.make(
                node.sequent.antecedent | {inner},
                node.sequent.succedent - {principal},
            )
            if node.premises[0].sequent != expected:
                raise ValueError("NOT_R premise does not match conclusion")

        elif rule == "NOT_L":
            if principal.op != "not" or principal not in node.sequent.antecedent:
                raise ValueError("NOT_L principal must be a negation in the antecedent")
            if len(node.premises) != 1:
                raise ValueError("NOT_L requires one premise")
            inner = principal.args[0]
            expected = Sequent.make(
                node.sequent.antecedent - {principal},
                node.sequent.succedent | {inner},
            )
            if node.premises[0].sequent != expected:
                raise ValueError("NOT_L premise does not match conclusion")

        elif rule == "OR_R":
            if principal.op != "or" or principal not in node.sequent.succedent:
                raise ValueError("OR_R principal must be a disjunction in the succedent")
            if len(node.premises) != 1:
                raise ValueError("OR_R requires one premise")
            left, right = principal.args
            expected = Sequent.make(
                node.sequent.antecedent,
                (node.sequent.succedent - {principal}) | {left, right},
            )
            if node.premises[0].sequent != expected:
                raise ValueError("OR_R premise does not match conclusion")

        elif rule == "OR_L":
            if principal.op != "or" or principal not in node.sequent.antecedent:
                raise ValueError("OR_L principal must be a disjunction in the antecedent")
            if len(node.premises) != 2:
                raise ValueError("OR_L requires two premises")
            left, right = principal.args
            base = node.sequent.antecedent - {principal}
            expected_left = Sequent.make(base | {left}, node.sequent.succedent)
            expected_right = Sequent.make(base | {right}, node.sequent.succedent)
            actual = {node.premises[0].sequent, node.premises[1].sequent}
            if actual != {expected_left, expected_right}:
                raise ValueError("OR_L premises do not match conclusion")

        else:
            raise ValueError(f"unknown rule {rule}")

        for premise in node.premises:
            self._verify_node(premise)

    def verify_model_pair(
        self,
        certificate: ModelPairCertificate,
        axioms: tuple[Formula, ...],
        conjecture: Formula,
    ) -> VerificationResult:
        not_c = Formula.neg(conjecture)
        for axiom in axioms:
            if not axiom.evaluate(certificate.model_for_c):
                return VerificationResult(False, "first model violates an axiom")
            if not axiom.evaluate(certificate.model_for_not_c):
                return VerificationResult(False, "second model violates an axiom")
        if not conjecture.evaluate(certificate.model_for_c):
            return VerificationResult(False, "first model does not satisfy C")
        if not not_c.evaluate(certificate.model_for_not_c):
            return VerificationResult(False, "second model does not satisfy ¬C")
        return VerificationResult(True, "verified model-pair independence certificate")
